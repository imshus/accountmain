"""Turn uploaded registers and bank statements into the company's books.

Sales register row  -> Sales voucher:    Customer Dr (invoice value) / Sales Cr (taxable) / Output GST Cr
Negative sales row  -> Credit Note:      the mirror image (a sales return)
Purchase row        -> Purchase voucher: Purchase Dr / Input GST Dr / Supplier Cr
Negative purchase   -> Debit Note:       the mirror image (a purchase return)

The invoice value must equal taxable value + GST: up to Rs 1 of difference is posted to Round Off;
anything larger goes to Suspense A/c and is reported, so it is never hidden. Every voucher remembers
its source row, so importing the same file twice does not double the books; and an invoice already in the
books (same party ledger or GSTIN, same invoice / supplier bill number, same financial year) is skipped even when it
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


def financial_year(day: date) -> date:
    """First day of the April–March year containing ``day``: invoice serials restart on 1 April (Rule 46),
    whatever date the company's books begin on."""
    return service.fy_of(day)[0]


def _valid_gstin(text) -> str:
    text = (text or "").strip().upper() if isinstance(text, str) else ""
    return text if text and gst.gstin_problem(text) is None else ""


def existing_documents(conn, company_id: int, skip_prefix: str) -> dict[tuple[str, str, date], list[dict]]:
    """Live invoices already in the books: (type, invoice / supplier bill no. in lower case, FY start) -> one entry per
    voucher with its date, its ledgers (rupees on each) and its party ledgers' GSTINs.
    Vouchers whose source starts with ``skip_prefix`` (this upload's own rows) are left to the per-row guard."""
    v = vouchers
    rows = conn.execute(select(v.c.id, v.c.vtype, v.c.number, v.c.reference, v.c.date, v.c.source).where(and_(
        v.c.company_id == company_id, v.c.cancelled.is_(False),
        v.c.vtype.in_(("Sales", "Credit Note", "Purchase", "Debit Note"))))).all()
    rows = [r for r in rows if not (r.source or "").startswith(skip_prefix)]
    ids = [r.id for r in rows]
    # Every ledger on the voucher, not only Sundry Debtors / Creditors: a register's party "Cash" is the
    # Cash-in-Hand ledger, and a sale by weight has metal lines only.
    amounts: dict[int, dict[int, int]] = {}
    for table, rupees in ((voucher_lines, True), (metal_lines, False)):
        for start in range(0, len(ids), 500):
            cols = (table.c.voucher_id, table.c.ledger_id) + ((table.c.dr_paise, table.c.cr_paise) if rupees else ())
            for vid, lid, *money in conn.execute(select(*cols).where(table.c.voucher_id.in_(ids[start:start + 500]))).all():
                on_voucher = amounts.setdefault(vid, {})
                on_voucher[lid] = on_voucher.get(lid, 0) + sum(money)
    # A renamed or differently spelt party is a new ledger, but its GSTIN is the same registration.
    party_gstins = {lid: g for lid, group, text in conn.execute(select(ledgers.c.id, ledgers.c.group_name, ledgers.c.gstin)
                    .where(ledgers.c.company_id == company_id)).all()
                    if group in chart.PARTY_GROUPS and (g := _valid_gstin(text))}
    index: dict[tuple[str, str, date], list[dict]] = {}
    for r in rows:
        on_voucher = amounts.get(r.id, {})
        entry = {"date": r.date, "ledgers": on_voucher,
                 "gstins": {party_gstins[lid] for lid in on_voucher if lid in party_gstins}}
        # Purchases carry our own number with the supplier's bill number as reference; a sales invoice
        # number that was not a valid GST document number is kept as reference too.
        texts = [r.reference] if r.vtype in ("Purchase", "Debit Note") else [r.number, r.reference]
        for text in {t.strip().lower() for t in texts if t and t.strip()}:
            index.setdefault((r.vtype, text, financial_year(r.date)), []).append(entry)
    return index


def already_in_books(index: dict, vtype: str, number: str, day: date, party_id: int | None, gstins=(),
                     is_party: bool = True, value: int = 0) -> bool:
    """True when this party already has this invoice / bill number in this financial year (not cancelled).
    The party is the same ledger or the same valid GSTIN. A register's party "Cash" (not a party ledger) is
    shared by many suppliers, so there the date and invoice value must match too, as a re-upload repeats them."""
    number = (number or "").strip().lower()
    gstins = {g for g in map(_valid_gstin, gstins) if g}
    for entry in index.get((vtype, number, financial_year(day)), []) if number else []:
        if gstins & entry["gstins"]:
            return True
        if party_id in entry["ledgers"] and (is_party or (entry["date"] == day and entry["ledgers"][party_id] == abs(value))):
            return True
    return False


def number_clash(conn, index: dict, vtype: str, number: str, day: date, label: str, error: str) -> str | None:
    """Problem text for a sales invoice refused because its number is already used this year by another party:
    either the same invoice under a renamed customer, or a repeated number. Taking the next number would post it twice."""
    entries = index.get((vtype, (number or "").strip().lower(), financial_year(day)), []) if number else []
    if vtype not in ("Sales", "Credit Note") or not entries or "already used" not in error or "cancelled" in error:
        return None
    ids = {lid for entry in entries for lid in entry["ledgers"]}
    names = sorted(conn.execute(select(ledgers.c.name).where(and_(ledgers.c.id.in_(ids),
                                                                ledgers.c.group_name.in_(sorted(chart.PARTY_GROUPS))))).scalars())
    whom = f" (for {', '.join(repr(n) for n in names)})" if names else ""
    return (f"{label}: {vtype} number {number.strip()} is already in the books this financial year{whom}. If it is the same "
            "invoice (the customer was renamed or spelt differently), it is already posted and nothing more is needed; if "
            "it is a different invoice, correct its number in the register (Rule 46: one invoice per number a year). Not posted.")


def ledger_facts(conn, ledger_id: int) -> tuple[bool, str]:
    """(is a customer / supplier ledger, its valid GSTIN or ''). Cash or Bank may hold a stray GSTIN copied from
    a register row, which is not the party's registration."""
    led = conn.execute(select(ledgers.c.group_name, ledgers.c.gstin).where(ledgers.c.id == ledger_id)).first()
    is_party = led.group_name in chart.PARTY_GROUPS
    return is_party, _valid_gstin(led.gstin) if is_party else ""


def duplicates_note(labels: list[str], purchases: bool) -> list[str]:
    if not labels:
        return []
    shown = ", ".join(labels[:10]) + (f" and {len(labels) - 10} more" if len(labels) > 10 else "")
    return [f"{len(labels)} invoice{'s are' if len(labels) != 1 else ' is'} already in the books (same party, same "
            f"{'supplier bill' if purchases else 'invoice'} number, same financial year), so not posted again: {shown}. "
            "To post one again, cancel the earlier voucher first."]


# The party's state: on a sales register the place of supply is the customer's state, and an explicit place-of-supply
# column wins over a billing "State" column. On a purchase register the place of supply ("State of Supply",
# "POS State" ...) is usually our own state, so only a plain supplier "State" column says where the supplier is.
_POS_COLUMN = re.compile(r"(^|_)(place_of_supply|pos|supply_state|state_of_supply)(_|$)")
_STATE_WORD = re.compile(r"(^|_)state(_|$)")
_SUPPLY_WORD = re.compile(r"(^|_)(supply|place|pos)(_|$)")
# "POS No" / "POS ID" is a shop's billing counter, not a place of supply.
_NOT_STATE = re.compile(r"(^|_)(no|num|number|counter|terminal|id|machine|till|device|user)(_|$)")
FOREIGN = "96"  # GST code for a place of supply outside India (exports): not a state, but not a mistake either


def _letters(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower().replace("&", "and"))


# The GST portal writes "Jammu and Kashmir" where gst.STATE_CODES has "&"; older names are still common in registers.
_STATE_NAMES = {_letters(name): code for code, name in gst.STATE_CODES.items()} | {
    "orissa": "21", "pondicherry": "34", "uttaranchal": "05", "newdelhi": "07", "nctofdelhi": "07",
    "andamanandnicobar": "35", "dadraandnagarhaveli": "26", "damananddiu": "26",
} | {name: FOREIGN for name in ("foreigncountry", "foreign", "outsideindia", "export", "exports", "overseas")}


def state_text(code: str) -> str:
    return f"{code}-{'Foreign Country' if code == FOREIGN else gst.STATE_CODES.get(code, '?')}"


def _state_code(value) -> str | None:
    """'07', 7, '07-Delhi', 'Delhi' or 'Jammu and Kashmir' -> state code; anything else -> None."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    match = re.match(r"^(\d{1,2})(\D|$)", text)
    if match:
        code = match.group(1).zfill(2)
        return code if code in gst.STATE_CODES or code == FOREIGN else None
    return _STATE_NAMES.get(_letters(text))


def _read_states(frame: pd.DataFrame, column: str) -> tuple[dict[int, str], dict[int, str]]:
    """(row id -> state code, row id -> text that is not a state) for one column."""
    codes, unknown = {}, {}
    for rowid, value in zip(frame["_rowid"], frame[column]):
        if value is None or (not isinstance(value, str) and pd.isna(value)) or not str(value).strip():
            continue
        code = _state_code(value)
        if code:
            codes[int(rowid)] = code
        else:
            unknown[int(rowid)] = str(value).strip()
    return codes, unknown


def place_of_supply(sheet: dict, sales: bool) -> tuple[dict[int, str], list[str]]:
    """(row id -> party's state code, problems) from the register's place-of-supply / state column."""
    what = "place of supply" if sales else "supplier state"
    names = [c["name"] for c in sheet["profile"]["columns"] if not _NOT_STATE.search(c["name"])]
    plain = [n for n in names if _STATE_WORD.search(n) and not _SUPPLY_WORD.search(n)]
    candidates = ([n for n in names if _POS_COLUMN.search(n)] if sales else []) + plain
    if not candidates:
        return {}, []
    frame = load_frame(sheet)
    problems, column, codes, unknown = [], None, {}, {}
    for name in candidates:
        codes, unknown = _read_states(frame, name)
        if len(unknown) > len(codes):  # mostly not states: some other column that happens to be called "state"
            problems.append(f"Column '{name}' was not read as the {what}: most of its values (such as "
                            f"{next(iter(unknown.values()))!r}) are not Indian states.")
            continue
        column = name
        break
    if column is None:
        return {}, problems
    for other in candidates[candidates.index(column) + 1:]:
        theirs = _read_states(frame, other)[0]
        differ = [rowid for rowid, code in codes.items() if theirs.get(rowid, code) != code]
        if differ:
            shown = ", ".join(f"row {rowid} ({state_text(codes[rowid])} vs {state_text(theirs[rowid])})" for rowid in differ[:5])
            problems.append(f"Columns '{column}' and '{other}' disagree on {shown}{' and more' if len(differ) > 5 else ''}; "
                            f"the GST follows '{column}' as the {what}. If '{other}' is right, correct the register and those vouchers' GST.")
    if unknown:
        shown = ", ".join(f"row {rowid} ({text!r})" for rowid, text in list(unknown.items())[:10])
        more = f" and {len(unknown) - 10} more" if len(unknown) > 10 else ""
        problems.append(f"{what.capitalize()} not recognised on {shown}{more}; those rows were taxed by the party's GSTIN "
                        "or ledger state, else as within your own state. Write the state as '27-Maharashtra' or its "
                        "two-digit GST state code ('96-Foreign Country' for exports) and check those vouchers' GST.")
    return codes, problems


def _looks_like_gstin(text: str) -> bool:
    """A mistyped GSTIN, as opposed to 'URP', 'Unregistered' or 'NA' (which say the party has none): 13+ letters and
    digits starting with a state code (letter O typed for zero allowed) or holding a PAN-like run such as AAACU3333C."""
    text = re.sub(r"[^0-9A-Za-z]", "", text).upper()
    return len(text) >= 13 and bool(re.match(r"[0-9O]{2}", text) or re.search(r"[A-Z]{5}[0-9O]{4}[A-Z]", text))


def note_bad_gstin(bad: dict[tuple[str, str], list[str]], gstin: str, label: str, used: str = "") -> None:
    """Remember a posted invoice whose GSTIN is mistyped (not 'URP' and the like), for gstin_warnings().
    ``used`` is the valid GSTIN on the party's ledger that was used in its place, if any."""
    gstin = (gstin or "").strip().upper()
    if gstin and gst.gstin_problem(gstin) is not None and _looks_like_gstin(gstin):
        bad.setdefault((gstin, used), []).append(label)


def gstin_warnings(bad: dict[tuple[str, str], list[str]]) -> list[str]:
    """One problem per GSTIN in the register that is not valid."""
    out = []
    for (gstin, used), labels in bad.items():
        shown = ", ".join(labels[:5]) + (f" and {len(labels) - 5} more" if len(labels) > 5 else "")
        if used:
            out.append(f"GSTIN {gstin} ({shown}): {gst.gstin_problem(gstin)}, so it was not used; the GSTIN {used} saved on "
                       "the party's ledger was used instead, for the GST and in GSTR-1. Correct the GSTIN in the register; "
                       "if the ledger's GSTIN is the wrong one, correct it under Ledgers and check the GST on those vouchers.")
        else:
            out.append(f"GSTIN {gstin} ({shown}): {gst.gstin_problem(gstin)}, so it was not used. The party was treated as "
                       "unregistered and its state taken from the place of supply or its ledger, else as your own state. "
                       "Correct the GSTIN on the party's ledger and check the GST on those vouchers.")
    return out


def _has_vouchers(conn, ledger_id: int) -> bool:
    for table in (voucher_lines, metal_lines):
        if conn.execute(select(table.c.id).join(vouchers, vouchers.c.id == table.c.voucher_id).where(and_(
                table.c.ledger_id == ledger_id, vouchers.c.cancelled.is_(False))).limit(1)).first():
            return True
    return False


def party_state(conn, company: dict, party_id: int, gstin: str, place: str | None, label: str,
                problems: list[str]) -> tuple[str | None, str, str]:
    """(state that decides IGST or CGST + SGST, state GSTR-1 will report, ledger GSTIN used in place of the row's)
    for one imported invoice. A valid GSTIN gives the state (on the row, else on a customer / supplier ledger: the one
    GSTR-1 reports), then the register's place of supply, then the state saved on the ledger. GSTR-1 reads the state
    from the party ledger, so a place of supply is saved on a party ledger that has no state and no invoices yet; the
    caller reports any remaining disagreement. Cash / Bank (a register's party "Cash") are not parties: a GSTIN or
    state copied onto them from another row says nothing about this invoice."""
    own = company.get("state_code") or ""
    gstin = _valid_gstin(gstin)
    led = dict(conn.execute(select(ledgers.c.group_name, ledgers.c.gstin, ledgers.c.state_code)
                            .where(ledgers.c.id == party_id)).mappings().first())
    is_party = led["group_name"] in chart.PARTY_GROUPS
    saved = _valid_gstin(led["gstin"]) if is_party else ""
    registered = gstin[:2] or saved[:2]
    if registered and place and place != registered:
        problems.append(f"{label}: place of supply {state_text(place)} differs from the state of the party's GSTIN "
                        f"({state_text(registered)}); the GSTIN's state was used, as the GST returns use it. "
                        "If the place of supply is right (bill-to / ship-to), correct this voucher's GST.")
    if (is_party and place and place != FOREIGN and not registered and not led["state_code"]
            and not _has_vouchers(conn, party_id)):
        conn.execute(ledgers.update().where(ledgers.c.id == party_id).values(state_code=place))
        led["state_code"] = place
    reported = (service.place_of_supply(led) if is_party else None) or own
    return registered or place or (led["state_code"] if is_party else None), reported, "" if gstin else saved


def check_reported_state(company: dict, vtype: str, party: str, heads: dict[str, int], state: str | None, reported: str,
                         label: str, problems: list[str]) -> None:
    """Report a sale whose GST heads (IGST vs CGST + SGST) or place of supply disagree with what GSTR-1 will show."""
    own = company.get("state_code")
    if vtype not in ("Sales", "Credit Note") or not own or not any(heads[h] for h in ("igst", "cgst", "sgst")):
        return
    fix = "Give sales to another state their own customer ledger with the right state (Ledgers), or correct the GST."
    if bool(heads["igst"]) != (reported != own):
        problems.append(f"{label}: posted with {'IGST' if heads['igst'] else 'CGST + SGST'}, but GSTR-1 shows '{party}' in "
                        f"{state_text(reported)}, so this invoice will be reported as {'intra' if reported == own else 'inter'}-state. {fix}")
    elif state and state != reported:
        problems.append(f"{label}: place of supply is {state_text(state)}, but GSTR-1 shows '{party}' in {state_text(reported)} "
                        f"(the state on its ledger), so the return will name the wrong state. {fix}")


def split_unsplit_gst(company: dict, gstin: str, heads: dict[str, int], unsplit: int, state: str | None = None) -> None:
    """Add a GST amount given as one figure to IGST (other state) or CGST + SGST (same state, odd paisa to SGST).
    The party's state comes from a valid GSTIN, else ``state`` (from party_state()); "URP" or a mistyped GSTIN says
    nothing about the state, so without a state the party is taken to be in the company's state."""
    if not unsplit:
        return
    gstin = (gstin or "").strip().upper()
    state = gstin[:2] if gstin and gst.gstin_problem(gstin) is None else state
    if company.get("state_code") and state and state != company["state_code"]:
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
    sales = register == "sales"
    states, problems = place_of_supply(sheet, sales)
    created, skipped, duplicates, bad_gstins = 0, 0, [], {}
    with engine.begin() as conn:
        done = _imported_sources(conn, company_id, f"import:{sheet['table_name']}:")
        in_books = existing_documents(conn, company_id, f"import:{sheet['table_name']}:")
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
            day = pd.Timestamp(row.date).date()
            # By GSTIN first, so a renamed or differently spelt party does not get a new, empty ledger.
            if already_in_books(in_books, vtype, row.invoice_no, day, None, [row.gstin]):
                skipped += 1
                duplicates.append(label)
                continue
            party_id = service.ensure_ledger(conn, company_id, row.party, "Sundry Debtors" if sales else "Sundry Creditors",
                                             gstin=row.gstin or None)
            is_party, saved_gstin = ledger_facts(conn, party_id)
            if already_in_books(in_books, vtype, row.invoice_no, day, party_id, [saved_gstin], is_party, value):
                skipped += 1
                duplicates.append(label)
                continue
            taxable = sign * int(row.taxable)
            heads = {h: sign * int(getattr(row, h)) for h in ("cgst", "sgst", "igst", "cess")}
            state, reported, used = party_state(conn, company, party_id, row.gstin, states.get(int(row.rowid)), label, problems)
            split_unsplit_gst(company, row.gstin, heads, sign * int(row.gst_unsplit), state)
            check_reported_state(company, vtype, row.party, heads, state, reported, label, problems)
            lines = posting_lines(conn, company_id, vtype, party_id, main_ledger, abs(value), taxable, heads, label, problems)
            number, reference = document_number(sales, row.invoice_no, label, problems)
            try:
                with conn.begin_nested():
                    service.save_voucher(company_id, vtype, day, lines, number=number or None,
                                         reference=reference, narration=f"Imported from {sheet['sheet_name']}",
                                         source=source, conn=conn)
                created += 1
                note_bad_gstin(bad_gstins, row.gstin, label, used)
            except AccountsError as exc:
                problems.append(number_clash(conn, in_books, vtype, number, day, label, str(exc)) or f"{label}: {exc}")
    return {"created": created, "skipped": skipped, "problems": problems + gstin_warnings(bad_gstins),
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
