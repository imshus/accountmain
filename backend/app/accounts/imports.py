"""Turn uploaded registers and bank statements into the company's books.

Sales register row  -> Sales voucher:    Customer Dr (invoice value) / Sales Cr (taxable) / Output GST Cr
Negative sales row  -> Credit Note:      the mirror image (a sales return)
Purchase row        -> Purchase voucher: Purchase Dr / Input GST Dr / Supplier Cr
Negative purchase   -> Debit Note:       the mirror image (a purchase return)

The invoice value must equal taxable value + GST: up to Rs 1 of difference is posted to Round Off;
anything larger goes to Suspense A/c and is reported, so it is never hidden. Every voucher remembers
its source row, so importing the same file twice does not double the books; and an invoice already in the
books (same party, same invoice / supplier bill number, same financial year) is skipped even when it
comes from a new upload of the same file.
"""

import math
import re

from datetime import date

import pandas as pd
from sqlalchemy import and_, insert, select

from .. import gst, reports
from ..books import _normalise
from ..database import engine
from ..editing import load_frame
from . import chart, service
from .db import bank_lines, ledgers, metal_lines, voucher_lines, vouchers
from .service import AccountsError, Line

ROUND_OFF_LIMIT = 100  # paise


def _imported_sources(conn, company_id: int, prefix: str) -> set[str]:
    return set(conn.execute(select(vouchers.c.source).where(and_(
        vouchers.c.company_id == company_id, vouchers.c.source.like(f"{prefix}%"), vouchers.c.cancelled.is_(False),
    ))).scalars())


def financial_year(company: dict, day: date) -> date:
    return service.fy_of(day, company["fy_start"].month)[0]


def existing_documents(conn, company: dict, skip_prefix: str) -> dict[tuple[str, str, date], set[int]]:
    """Live invoices already in the books: (type, invoice / supplier bill no. in lower case, FY start) -> party ledger ids.
    Vouchers whose source starts with ``skip_prefix`` (this upload's own rows) are left to the per-row guard."""
    v = vouchers
    rows = conn.execute(select(v.c.id, v.c.vtype, v.c.number, v.c.reference, v.c.date, v.c.source).where(and_(
        v.c.company_id == company["id"], v.c.cancelled.is_(False),
        v.c.vtype.in_(("Sales", "Credit Note", "Purchase", "Debit Note"))))).all()
    rows = [r for r in rows if not (r.source or "").startswith(skip_prefix)]
    ids = [r.id for r in rows]
    parties: dict[int, set[int]] = {}
    for table in (voucher_lines, metal_lines):  # a sale by weight has metal lines only
        for start in range(0, len(ids), 500):
            query = (select(table.c.voucher_id, table.c.ledger_id).join(ledgers, ledgers.c.id == table.c.ledger_id)
                     .where(and_(table.c.voucher_id.in_(ids[start:start + 500]), ledgers.c.group_name.in_(chart.PARTY_GROUPS))))
            for vid, lid in conn.execute(query).all():
                parties.setdefault(vid, set()).add(lid)
    index: dict[tuple[str, str, date], set[int]] = {}
    for r in rows:
        # Purchases carry our own number with the supplier's bill number as reference; a sales invoice
        # number that was not a valid GST document number is kept as reference too.
        for text in ([r.reference] if r.vtype in ("Purchase", "Debit Note") else [r.number, r.reference]):
            if text and text.strip():
                key = (r.vtype, text.strip().lower(), financial_year(company, r.date))
                index.setdefault(key, set()).update(parties.get(r.id, ()))
    return index


def already_in_books(index: dict, company: dict, vtype: str, number: str, day: date, party_id: int) -> bool:
    """True when this party already has this invoice / bill number in this financial year (not cancelled)."""
    number = (number or "").strip().lower()
    return bool(number) and party_id in index.get((vtype, number, financial_year(company, day)), ())


def duplicates_note(labels: list[str], purchases: bool) -> list[str]:
    if not labels:
        return []
    shown = ", ".join(labels[:10]) + (f" and {len(labels) - 10} more" if len(labels) > 10 else "")
    return [f"{len(labels)} invoice{'s are' if len(labels) != 1 else ' is'} already in the books (same party, same "
            f"{'supplier bill' if purchases else 'invoice'} number, same financial year), so not posted again: {shown}. "
            "To post one again, cancel the earlier voucher first."]


_STATE_COLUMN = re.compile(r"(^|_)(place_of_supply|pos|supply_state|state|state_code|state_name)(_|$)")


def _state_code(value) -> str | None:
    """'07', 7, '07-Delhi' or 'Delhi' -> '07'; anything else -> None."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    match = re.match(r"^(\d{1,2})(\D|$)", text)
    if match:
        code = match.group(1).zfill(2)
        return code if code in gst.STATE_CODES else None
    letters = re.sub(r"[^a-z]", "", text.lower())
    return next((code for code, name in gst.STATE_CODES.items() if letters and re.sub(r"[^a-z]", "", name.lower()) == letters), None)


def place_of_supply(sheet: dict) -> dict[int, str]:
    """Row id -> state code from the register's place-of-supply / state column (empty when it has none)."""
    column = next((c["name"] for c in sheet["profile"]["columns"] if _STATE_COLUMN.search(c["name"])), None)
    if column is None:
        return {}
    frame = load_frame(sheet)
    codes = {int(rowid): _state_code(value) for rowid, value in zip(frame["_rowid"], frame[column])}
    return {rowid: code for rowid, code in codes.items() if code}


def split_unsplit_gst(company: dict, gstin: str, heads: dict[str, int], unsplit: int, state: str | None = None) -> None:
    """Add a GST amount given as one figure to IGST (other state) or CGST + SGST (same state, odd paisa to SGST).
    The party's state comes from a valid GSTIN, else from the place of supply; "URP" or a mistyped GSTIN says
    nothing about the state, so without a place of supply the party is taken to be in the company's state."""
    if not unsplit:
        return
    gstin = (gstin or "").strip().upper()
    party_state = gstin[:2] if gstin and gst.gstin_problem(gstin) is None else (state or "")
    if company.get("state_code") and party_state and party_state != company["state_code"]:
        heads["igst"] += unsplit
    else:
        heads["cgst"] += unsplit // 2
        heads["sgst"] += unsplit - unsplit // 2


def posting_lines(conn, company_id: int, vtype: str, party_id: int, main_ledger: int, total: int, taxable: int,
                  heads: dict[str, int], label: str, problems: list[str]) -> list[Line]:
    """Party, Sales/Purchase and GST lines of one imported invoice (positive paise; GST already split by head).
    The invoice value must equal taxable value + GST: up to Rs 1 goes to Round Off, more to Suspense A/c (reported)."""
    difference = total - taxable - sum(heads.values())
    # Party on the side that matches the document: customers owe on sales, we owe suppliers on purchases.
    party_dr = vtype in ("Sales", "Debit Note")
    side = "output" if vtype in ("Sales", "Credit Note") else "input"
    lines = [Line(party_id, dr=total if party_dr else 0, cr=0 if party_dr else total)]
    if taxable:
        lines.append(Line(main_ledger, dr=0 if party_dr else taxable, cr=taxable if party_dr else 0))
    for head, amount in heads.items():
        if amount:
            lid = service._tax_ledger(conn, company_id, f"{side}_{head}")
            lines.append(Line(lid, dr=0 if party_dr else amount, cr=amount if party_dr else 0))
    if difference:
        if abs(difference) <= ROUND_OFF_LIMIT:
            lid = service.ensure_ledger(conn, company_id, "Round Off", "Indirect Expenses")
        else:
            lid = service.ensure_ledger(conn, company_id, "Suspense A/c", "Suspense A/c")
            problems.append(f"{label}: invoice value differs from taxable value + GST by {difference / 100:,.2f}; "
                            "the difference was posted to Suspense A/c.")
        # On the income/tax side of the voucher: a positive difference is more to receive (Cr on sales).
        lines.append(Line(lid, dr=0 if (party_dr == (difference > 0)) else abs(difference),
                          cr=abs(difference) if (party_dr == (difference > 0)) else 0))
    return lines


def document_number(sales: bool, number: str, label: str, problems: list[str]) -> tuple[str, str]:
    """(our voucher number, reference). Purchases use our own series with the supplier's bill no as reference;
    a sales number that is not a valid GST document number is replaced and kept as reference."""
    number = (number or "").strip()
    if not sales:
        return "", number
    if number and (len(number) > 16 or not re.fullmatch(r"[A-Za-z0-9/-]+", number)):
        problems.append(f"{label}: invoice number {number!r} is not a valid GST document number (Rule 46); "
                        "a new number was given and the original kept as reference.")
        return "", number
    return number, ""


def import_register(company_id: int, sheet: dict, register: str) -> dict:
    """Post one sales or purchase register sheet. Returns counts and a list of problems.
    Jewellery registers (fine weight / tunch columns) are posted by weight; see metal.import_jewellery."""
    if register not in ("sales", "purchases"):
        raise AccountsError("Choose whether the sheet is a sales or a purchase register.")
    from . import metal  # metal imports this module

    if metal.detect_jewellery(sheet):
        return metal.import_jewellery(company_id, sheet, register)
    frame, notes, _ = _normalise({**sheet, "register": register})
    company = service.get_company(company_id)
    states = place_of_supply(sheet)
    created, skipped, problems, duplicates = 0, 0, [], []
    sales = register == "sales"
    with engine.begin() as conn:
        done = _imported_sources(conn, company_id, f"import:{sheet['table_name']}:")
        in_books = existing_documents(conn, company, f"import:{sheet['table_name']}:")
        main_ledger = service.ensure_ledger(conn, company_id, "Sales" if sales else "Purchase",
                                            "Sales Accounts" if sales else "Purchase Accounts")
        for row in frame.itertuples(index=False):
            source = f"import:{sheet['table_name']}:{row.rowid}"
            label = f"row {row.rowid}" + (f" ({row.invoice_no})" if row.invoice_no else "")
            if source in done:
                skipped += 1
                continue
            if pd.isna(row.date):
                problems.append(f"{label}: no date, not posted.")
                continue
            if row.party in ("(blank)", "(not given)"):
                problems.append(f"{label}: no customer/supplier name, not posted.")
                continue
            value = int(row.invoice_value)
            if value == 0:
                problems.append(f"{label}: zero value, not posted.")
                continue
            returned = value < 0
            vtype = ("Credit Note" if returned else "Sales") if sales else ("Debit Note" if returned else "Purchase")
            sign = -1 if returned else 1
            party_id = service.ensure_ledger(conn, company_id, row.party, "Sundry Debtors" if sales else "Sundry Creditors",
                                             gstin=row.gstin or None)
            if already_in_books(in_books, company, vtype, row.invoice_no, pd.Timestamp(row.date).date(), party_id):
                skipped += 1
                duplicates.append(label)
                continue
            taxable = sign * int(row.taxable)
            heads = {h: sign * int(getattr(row, h)) for h in ("cgst", "sgst", "igst", "cess")}
            split_unsplit_gst(company, row.gstin, heads, sign * int(row.gst_unsplit), states.get(int(row.rowid)))
            lines = posting_lines(conn, company_id, vtype, party_id, main_ledger, abs(value), taxable, heads, label, problems)
            number, reference = document_number(sales, row.invoice_no, label, problems)
            try:
                with conn.begin_nested():
                    service.save_voucher(company_id, vtype, pd.Timestamp(row.date).date(), lines, number=number or None,
                                         reference=reference, narration=f"Imported from {sheet['sheet_name']}",
                                         source=source, conn=conn)
                created += 1
            except AccountsError as exc:
                problems.append(f"{label}: {exc}")
    return {"created": created, "skipped": skipped, "problems": problems,
            "notes": duplicates_note(duplicates, not sales) + [n["message"] for n in notes]}


_BALANCE = re.compile(r"(^|_)(balance|bal|closing_balance|running_balance)(_|$)")
_REF = re.compile(r"(^|_)(chq|cheque|ref|reference|utr|txn_id|transaction_id)(_|$)")


def _text(value) -> str | None:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text or None


def import_bank_statement(company_id: int, bank_ledger_id: int, sheet: dict) -> dict:
    ledger = service.ledger_map(company_id).get(bank_ledger_id)
    if ledger is None or ledger["group_name"] not in ("Bank Accounts", "Bank OD A/c"):
        raise AccountsError("Choose a bank ledger to reconcile.")
    mapping = reports.effective_mapping(sheet["profile"])
    if "date" not in mapping:
        raise AccountsError("The statement needs a date column (set it under Reports → Column roles).")
    frame = load_frame(sheet)
    if "debit" in mapping and "credit" in mapping:
        withdrawal = reports._paise(frame[mapping["debit"]])
        deposit = reports._paise(frame[mapping["credit"]])
    elif "amount" in mapping:
        signed = reports._paise(frame[mapping["amount"]])
        withdrawal, deposit = [max(-s, 0) for s in signed], [max(s, 0) for s in signed]
    else:
        raise AccountsError("The statement needs Withdrawal/Deposit (Debit/Credit) columns or one signed Amount column.")
    balance_col = next((c["name"] for c in sheet["profile"]["columns"] if c["kind"] == "number" and _BALANCE.search(c["name"])), None)
    dates = pd.to_datetime(frame[mapping["date"]], errors="coerce")
    narration = frame[mapping["narration"]] if "narration" in mapping else None
    ref_col = mapping.get("voucher_no") or next(
        (c["name"] for c in sheet["profile"]["columns"] if _REF.search(c["name"])), None)
    refs = frame[ref_col] if ref_col else None
    created, skipped, problems = 0, 0, []
    with engine.begin() as conn:
        done = set(conn.execute(select(bank_lines.c.source).where(and_(
            bank_lines.c.company_id == company_id, bank_lines.c.source.like(f"bank:{sheet['table_name']}:%")))).scalars())
        for i, rowid in enumerate(frame["_rowid"]):
            source = f"bank:{sheet['table_name']}:{rowid}"
            if source in done:
                skipped += 1
                continue
            if pd.isna(dates.iloc[i]):
                problems.append(f"row {rowid}: no date, skipped.")
                continue
            w, d = int(withdrawal[i]), int(deposit[i])
            if not w and not d:
                continue
            bal = frame[balance_col].iloc[i] if balance_col else None
            conn.execute(insert(bank_lines).values(
                company_id=company_id, bank_ledger_id=bank_ledger_id, date=dates.iloc[i].date(),
                narration=_text(narration.iloc[i]) if narration is not None else None,
                reference=_text(refs.iloc[i]) if refs is not None else None,
                withdrawal_paise=w, deposit_paise=d,
                balance_paise=None if bal is None or (isinstance(bal, float) and math.isnan(bal)) or pd.isna(bal) else int(round(float(bal) * 100)),
                source=source,
            ))
            created += 1
    return {"created": created, "skipped": skipped, "problems": problems, "notes": []}
