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

from __future__ import annotations

import math
import re
from collections.abc import Callable
from datetime import date, datetime, timezone

import pandas as pd
from sqlalchemy import and_, insert, select
from sqlalchemy.exc import DataError, IntegrityError

from .. import gst, reports
from ..books import HEADS, _normalise
from ..database import _safe_reason, engine, upsert
from ..editing import load_frame
from . import chart, service
from .db import bank_lines, ledgers, metal_lines, register_imports, voucher_lines, vouchers
from .service import AccountsError, Line

ROUND_OFF_LIMIT = 100  # paise


def _imported_sources(conn, company_id: int, prefix: str) -> set[str]:
    # startswith with autoescape: the "_" in a table name is a wildcard to LIKE (ds1_a_b would match ds1_aab's rows).
    return set(conn.execute(select(vouchers.c.source).where(and_(
        vouchers.c.company_id == company_id, vouchers.c.source.startswith(prefix, autoescape=True), vouchers.c.cancelled.is_(False),
    ))).scalars())


def imported_tables(company_id: int, tables) -> set[str]:
    """The sheets (table names) among ``tables`` already in the company's books: a live voucher came from one of their
    rows (import_register and the jewellery import both mark it "import:<table>:<row>")."""
    found = set()
    with engine.connect() as conn:
        for table in dict.fromkeys(tables):
            if conn.execute(select(vouchers.c.id).where(and_(
                    vouchers.c.company_id == company_id, vouchers.c.cancelled.is_(False),
                    vouchers.c.source.startswith(f"import:{table}:", autoescape=True))).limit(1)).first():
                found.add(table)
    return found


def answered_tables(company_id: int, tables) -> set[str]:
    """The sheets among ``tables`` that a register import has run for in the company's books (the person said which
    register they are), even one that posted nothing new: every row already in the books, or none could be posted."""
    tables = list(dict.fromkeys(tables))
    if not tables:
        return set()
    with engine.connect() as conn:
        return set(conn.execute(select(register_imports.c.table_name).where(and_(
            register_imports.c.company_id == company_id, register_imports.c.table_name.in_(tables)))).scalars())


def note_register(conn, company_id: int, table: str, register: str) -> None:
    """Remember, in the import's transaction, that ``table`` was imported as ``register`` (see answered_tables); a
    later import of the sheet replaces the note."""
    statement = upsert(register_imports).values(company_id=company_id, table_name=table, register=register,
                                                at=datetime.now(timezone.utc))
    conn.execute(statement.on_conflict_do_update(index_elements=[register_imports.c.company_id, register_imports.c.table_name],
                                                 set_={"register": statement.excluded.register, "at": statement.excluded.at}))


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
    invoices = and_(v.c.company_id == company_id, v.c.cancelled.is_(False),
                    v.c.vtype.in_(("Sales", "Credit Note", "Purchase", "Debit Note")))
    rows = conn.execute(select(v.c.id, v.c.vtype, v.c.number, v.c.reference, v.c.date, v.c.source).where(invoices)).all()
    rows = [r for r in rows if not (r.source or "").startswith(skip_prefix)]
    ids = {r.id for r in rows}
    # Every ledger on the voucher, not only Sundry Debtors / Creditors: a register's party "Cash" is the
    # Cash-in-Hand ledger, and a sale by weight has metal lines only. One joined read per table, not batches of ids.
    amounts: dict[int, dict[int, int]] = {}
    for table, rupees in ((voucher_lines, True), (metal_lines, False)):
        cols = (table.c.voucher_id, table.c.ledger_id) + ((table.c.dr_paise, table.c.cr_paise) if rupees else ())
        for vid, lid, *money in conn.execute(select(*cols).join(v, v.c.id == table.c.voucher_id).where(invoices)).all():
            if vid not in ids:
                continue
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
                     is_party: bool = True, value: int = 0, dated: bool = True) -> bool:
    """True when this party already has this invoice / bill number in this financial year (not cancelled).
    The party is the same ledger or the same valid GSTIN. A register's party "Cash" (not a party ledger) is
    shared by many suppliers, so there the date and invoice value must match too, as a re-upload repeats them.
    ``dated`` False: the bill's date was filled in (the day of an add from the chat), so it is not compared."""
    number = _as_reference(number).lower()  # as a voucher keeps it
    gstins = {g for g in map(_valid_gstin, gstins) if g}
    for entry in index.get((vtype, number, financial_year(day)), []) if number else []:
        if gstins & entry["gstins"]:
            return True
        if party_id in entry["ledgers"] and (is_party or ((not dated or entry["date"] == day)
                                                          and entry["ledgers"][party_id] == abs(value))):
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


def remembered_ledger(known: dict | None, key, find: Callable[[], int]) -> int:
    """A ledger id found (or made) once per import, kept in ``known`` by ``key``. Only for ledgers looked up outside the
    rows' savepoints, so a row that is rolled back cannot take a remembered ledger with it."""
    if known is None:
        return find()
    if key not in known:
        known[key] = find()
    return known[key]


def posting_lines(conn, company_id: int, vtype: str, party_id: int, main_ledger: int, total: int, taxable: int,
                  heads: dict[str, int], label: str, problems: list[str], known: dict | None = None) -> list[Line]:
    """Party, Sales/Purchase and GST lines of one imported invoice (positive paise; GST already split by head).
    The invoice value must equal taxable value + GST: up to Rs 1 goes to Round Off, more to Suspense A/c (reported).
    ``known``: the import's ledger ids (remembered_ledger), so each tax ledger is looked up once, not once per row."""
    difference = total - taxable - sum(heads.values())
    # Party on the side that matches the document: customers owe on sales, we owe suppliers on purchases.
    party_dr = vtype in ("Sales", "Debit Note")
    side = "output" if vtype in ("Sales", "Credit Note") else "input"
    lines = [Line(party_id, dr=total if party_dr else 0, cr=0 if party_dr else total)]
    if taxable:
        lines.append(Line(main_ledger, dr=0 if party_dr else taxable, cr=taxable if party_dr else 0))
    for head, amount in heads.items():
        if amount:
            kind = f"{side}_{head}"
            lid = remembered_ledger(known, ("tax", kind), lambda: service._tax_ledger(conn, company_id, kind))
            lines.append(Line(lid, dr=0 if party_dr else amount, cr=amount if party_dr else 0))
    if difference:
        if abs(difference) <= ROUND_OFF_LIMIT:
            lid = remembered_ledger(known, "Round Off", lambda: service.ensure_ledger(conn, company_id, "Round Off", "Indirect Expenses"))
        else:
            lid = remembered_ledger(known, "Suspense A/c", lambda: service.ensure_ledger(conn, company_id, "Suspense A/c", "Suspense A/c"))
            problems.append(f"{label}: invoice value differs from taxable value + GST by {difference / 100:,.2f}; "
                            "the difference was posted to Suspense A/c.")
        # On the income/tax side of the voucher: a positive difference is more to receive (Cr on sales).
        lines.append(Line(lid, dr=0 if (party_dr == (difference > 0)) else abs(difference),
                          cr=abs(difference) if (party_dr == (difference > 0)) else 0))
    return lines


def _as_reference(number) -> str:
    """A register's invoice / bill number as a voucher keeps it for reference: at most the column's 60 characters (a
    longer cell is text pasted there, not a bill number: Postgres refuses it whole, where SQLite kept it), and no NULs."""
    return (number or "").replace("\x00", "").strip()[:service.REFERENCE_LENGTH].strip()


def document_number(sales: bool, number: str, label: str, problems: list[str]) -> tuple[str, str]:
    """(our voucher number, reference). Purchases use our own series with the supplier's bill no as reference;
    a sales number that is not a valid GST document number is replaced and kept as reference."""
    number = (number or "").strip()
    if not sales:
        return "", _as_reference(number)
    if number and (len(number) > 16 or not re.fullmatch(r"[A-Za-z0-9/-]+", number)):
        problems.append(f"{label}: invoice number {number!r} is not a valid GST document number (Rule 46); "
                        "a new number was given and the original kept as reference.")
        return "", _as_reference(number)
    return number, ""


def _item_columns(sheet: dict, found: dict[str, str]) -> tuple[str | None, str | None]:
    """(item column, net-weight column) of a register that is not posted by weight. A bare "Net" is a weight only beside
    other jewellery columns (purity, tunch, gross weight...); elsewhere it is usually the net amount in rupees."""
    names = [c["name"] for c in sheet["profile"]["columns"]]
    net = found.get("net")
    if net == "net" and not any(reports._JEWELLERY_COLUMN.search(n) for n in names):
        net = None
    return reports.effective_mapping(sheet["profile"]).get("item") or found.get("item"), net


_MAX_NET_MG = 10 ** 12  # a thousand tonnes: a larger "weight" is something else (a barcode pasted into the column)


def _item_summary(row, item_col: str | None, net_col: str | None) -> tuple[str | None, int | None]:
    """(item name, net weight in mg) of one register row, kept on its voucher so the list can show "Ring · 12 g"."""
    name = _text(row[item_col]) if item_col else None
    try:
        net = abs(service.to_mg(row[net_col], "Net weight")) if net_col else 0
    except (ArithmeticError, ValueError, TypeError):  # not a weight (AccountsError is a ValueError): posted without one
        net = 0
    return (" ".join(name.split())[:120] if name else None), (net if 0 < net <= _MAX_NET_MG else None)


# A column that names the customer or supplier. A "Category" or "Head" column is the kind of item in a list of items
# (Ring, Pendant), not a party, although the column roles take it as an account for other sheets.
_PARTY_COLUMN = re.compile(r"(^|_)(ledger|account|party|party_name|customer|vendor|supplier|client|payee|buyer|seller|name)(_|$)")
# A sheet with no amount column: its price or value column is the bill's amount.
_PRICE_COLUMN = re.compile(r"(^|_)(price|set_price|sale_price|selling_price|mrp|value|total)(_|$)")


# A date column the uploader kept as text (a "-" or "N/A" among its dates): read as dates when the chat adds the sheet.
_DATE_COLUMN = re.compile(r"(^|_)(date|dt|dated|bill_date|invoice_date)(_|$)")


def loose_sheet(sheet: dict) -> dict:
    """The sheet as an add from the chat reads it, which must not stop at a missing column role (asked for on
    2026-10-28): a "Category" column is not taken as the customer or supplier; a date column kept as text is the date
    (read by text_dates); and a sheet with no amount column takes its first price or value column as the bill's amount,
    never one part of the value (metal, diamond, stone or labour value: the jewellery import adds the parts up).
    Column roles the person chose are used as they are."""
    from . import metal  # metal imports this module

    profile = sheet["profile"]
    if profile.get("mapping") is not None:
        return sheet
    mapping = reports.detect_mapping(profile)
    if "account" in mapping and not _PARTY_COLUMN.search(mapping["account"]):
        mapping.pop("account")
    if "date" not in mapping:
        text_date = next((c["name"] for c in profile["columns"] if c["kind"] == "text" and c["non_null"] > 0
                          and _DATE_COLUMN.search(c["name"])), None)
        if text_date:
            mapping["date"] = text_date
    if not any(role in mapping for role in ("taxable", "invoice_value", "amount", "debit")):
        parts = [re.compile(metal._COLUMNS[k]) for k in metal._VALUE_PARTS]
        price = next((c["name"] for c in profile["columns"] if c["kind"] == "number" and c["non_null"] > 0
                      and _PRICE_COLUMN.search(c["name"]) and not reports._NOT_AMOUNT.search(c["name"])
                      and not any(p.match(c["name"]) for p in parts)), None)
        if price:
            mapping["amount"] = price
    return {**sheet, "profile": {**profile, "mapping": mapping}}


def text_dates(values: pd.Series) -> pd.Series:
    """A date column kept as text, read as the upload reads dates: the format that fits the column best (10/06/2026 is
    10 June, the Indian order); NaT where a cell is not a date ("-", "N/A"), which then gets the add's own date."""
    from ..excel_loader import _parse_dates

    found, _notes = _parse_dates(list(values.dropna().unique()))
    return pd.Series([found.get(v, pd.NaT) if not pd.isna(v) else pd.NaT for v in values], index=values.index,
                     dtype="datetime64[ns]")


def date_kept_as_text(sheet: dict, mapping: dict[str, str]) -> str | None:
    """The date column, when the upload kept it as text (then read with text_dates)."""
    kinds = {c["name"]: c["kind"] for c in sheet["profile"]["columns"]}
    column = mapping.get("date")
    return column if column and kinds.get(column) == "text" else None


# Dates before this are an empty or broken Excel cell (Excel's day 0 is 1899-12-30), never a bill.
_EARLIEST_BILL_YEAR = 2000


def fit_books_start(conn, company: dict, days) -> dict | None:
    """In an add from the chat: move the books-start date back to the financial year of the earliest of ``days`` (the
    bills about to be posted, outside any locked period) when it is before the books begin and the company has no
    opening balances (service.move_books_start_back), on the posting's own transaction, so a stopped or failed add
    leaves it as it was. {"from", "to"} when it moved, else None."""
    locked = company.get("locked_until")
    days = [d for d in days if d is not None and d.year >= _EARLIEST_BILL_YEAR and not (locked and d <= locked)]
    earliest = min(days, default=None)
    if earliest is None or not company.get("fy_start") or earliest >= company["fy_start"]:
        return None
    start = service.fy_of(earliest)[0]
    if not service.move_books_start_back(company["id"], start, conn):
        return None
    return {"from": company["fy_start"], "to": start}


def one_bill_sheet(sheet: dict, default_date: date | None) -> bool:
    """A list of items with no date, bill number or customer/supplier column, added from the chat: one bill for it all."""
    mapping = reports.effective_mapping(sheet["profile"])
    return default_date is not None and not any(role in mapping for role in ("date", "voucher_no", "account"))


# "Total", "Grand Total", "G. Total", "G.TOTAL", "GTOTAL", "Bill Total", "TOTAL SALE": in any cell of a total row.
_TOTAL_WORD = re.compile(r"\btotals?\b|\bg\.?\s*totals?\b|\bgtotals?\b", re.IGNORECASE)
# Rates and purities are not added up in a total row, so they are not compared.
_NOT_SUMMED = re.compile(r"(^|_)(rate|tunch|touch|purity|karat|kt|percent|pct)(_|$)")
_SUM_TOLERANCE = 0.0051  # to the paisa and the milligram, after Excel's float noise


def total_rows(sheet: dict, raw: pd.DataFrame, mapping: dict[str, str]) -> list[int]:
    """Rows (ids) that only add up the rows above them: a grand total, or a bill's subtotal ("Bill Total"). Such a row
    has no date, bill number or party; its text cells are blank or say "total"; and each of its figures (rates and
    purities aside) equals the sum of the rows since its bill began, or since the last total, over two rows or more.
    As in a supplier's packing list (each item's subtotal under its diamond lines, a grand total at the end), a row with
    at least two matching figures still counts when the others are in columns blank on every row added up (an amount
    worked out only on the total row, such as the diamonds' value), or at most half as many as match are off (the
    supplier's subtotal of fine weight at another tunch); and a grand total under subtotals adds up the rows since the
    last grand total, the subtotals left out.
    An add from the chat leaves them out, so they are neither posted as bills nor joined into the bill above."""
    kinds = {c["name"]: c["kind"] for c in sheet["profile"]["columns"]}
    keys = [mapping[role] for role in ("date", "voucher_no", "account") if mapping.get(role) in raw]
    numbers = [c for c, k in kinds.items() if k == "number" and c in raw and not _NOT_SUMMED.search(c)]
    texts = [c for c, k in kinds.items() if k == "text" and c in raw and c not in keys]

    def blank(value) -> bool:
        return value is None or (not isinstance(value, str) and pd.isna(value)) or not str(value).strip()

    def figure(value) -> float:
        try:
            return 0.0 if blank(value) else float(value)
        except (TypeError, ValueError):
            return 0.0

    def adds_up(values: dict[str, float], sums: dict[str, float], count: int) -> bool:
        if count < 2:
            return False
        matched = [c for c, v in values.items() if abs(v - sums[c]) <= _SUM_TOLERANCE]
        off = [c for c in values if c not in matched and sums[c]]
        if len(matched) == len(values):
            return True
        return len(matched) >= max(2, 2 * len(off))

    found: list[int] = []
    since_bill, bill_rows = dict.fromkeys(numbers, 0.0), 0
    since_total, total_rows_seen = dict.fromkeys(numbers, 0.0), 0
    since_grand, grand_rows = dict.fromkeys(numbers, 0.0), 0  # not reset by a subtotal
    for record in raw.to_dict("records"):
        # "Grand Total" typed in the Date or Customer column labels the row: it does not start a bill.
        labels = [str(record[k]) for k in keys if not blank(record[k]) and _TOTAL_WORD.search(str(record[k]))]
        starts = any(not blank(record[k]) for k in keys) and not labels
        if starts:
            since_bill, bill_rows = dict.fromkeys(numbers, 0.0), 0
        words = labels + [str(record[c]) for c in texts if not blank(record[c])]
        values = {c: figure(record[c]) for c in numbers if figure(record[c])}
        if not starts and values and (not words or any(_TOTAL_WORD.search(w) for w in words)):
            subtotal = adds_up(values, since_bill, bill_rows) or adds_up(values, since_total, total_rows_seen)
            if subtotal or adds_up(values, since_grand, grand_rows):
                found.append(int(record["_rowid"]))
                since_bill, bill_rows = dict.fromkeys(numbers, 0.0), 0
                since_total, total_rows_seen = dict.fromkeys(numbers, 0.0), 0
                if not subtotal:
                    since_grand, grand_rows = dict.fromkeys(numbers, 0.0), 0
                continue
        for c in numbers:
            since_bill[c] += figure(record[c])
            since_total[c] += figure(record[c])
            since_grand[c] += figure(record[c])
        bill_rows += 1
        total_rows_seen += 1
        grand_rows += 1
    return found


def totals_note(rowids: list[int]) -> list[str]:
    """The total rows an add from the chat left out, as one note (a packing list has a subtotal under every item)."""
    if not rowids:
        return []
    shown = ", ".join(str(rowid) for rowid in rowids[:3]) + (f" and {len(rowids) - 3} more" if len(rowids) > 3 else "")
    if len(rowids) == 1:
        return [f"1 row ({shown}) only adds up the rows above it (a total), so it was left out."]
    return [f"{len(rowids)} rows ({shown}) only add up the rows above them (subtotals or a total), so they were left out."]


def item_row(date_value, number, party) -> bool:
    """A row with no date, bill number or party: in a register with those columns, an item typed under the bill above
    it (its cells left blank, or merged in Excel)."""
    return pd.isna(date_value) and not str(number or "").strip() and party in ("(blank)", "(not given)")


def bill_groups(frame: pd.DataFrame, one_bill: bool, join_items: bool) -> list[list[int]]:
    """The register's rows (positions in ``frame``) grouped into bills: every row its own bill; all rows one bill for a
    list of items; and with ``join_items`` (an add from the chat), an item row joins the bill above it."""
    if one_bill:
        return [list(range(len(frame)))]
    groups: list[list[int]] = []
    for position, row in enumerate(frame.itertuples(index=False)):
        if join_items and groups and item_row(row.date, row.invoice_no, row.party):
            groups[-1].append(position)
        else:
            groups.append([position])
    return groups


def _join_rows(frame: pd.DataFrame, raw: pd.DataFrame, groups: list[list[int]], item_col: str | None,
               net_col: str | None) -> tuple[pd.DataFrame, dict[int, tuple], dict[int, str]]:
    """One row per bill: the bill's first row with the amounts of all its rows added up; and, by that row's id, the
    bill's items and net weight, and its label, for the bills of several rows."""
    money = [c for c in ("invoice_value", "taxable", *HEADS, "gst_unsplit", "tax") if c in frame]
    firsts, items, labels = [], {}, {}
    for group in groups:
        first = frame.iloc[[group[0]]].copy()
        for column in money:
            first[column] = int(frame[column].iloc[group].sum())
        firsts.append(first)
        if len(group) > 1:
            rowids = [frame["rowid"].iloc[position] for position in group]
            listed = [_item_summary(raw.loc[rowid], item_col, net_col) for rowid in rowids]
            items[rowids[0]] = ("\n".join(dict.fromkeys(name for name, _ in listed if name)) or None,
                                sum(net or 0 for _, net in listed) or None)
            labels[rowids[0]] = f"rows {rowids[0]}–{rowids[-1]}"
    return pd.concat(firsts, ignore_index=True), items, labels


def filled_notes(filled: dict[str, int], default_date: date | None, default_party: str | None) -> list[str]:
    """What the import filled in for bills that had no date or no party (an import asked for from the chat)."""
    def bills(n: int) -> str:
        return f"{n} bill{'s' if n != 1 else ''}"

    notes = []
    if filled["date"]:
        notes.append(f"{bills(filled['date'])} had no date, so {'it is' if filled['date'] == 1 else 'they are'} dated "
                     f"{default_date:%d/%m/%Y} (the day it was added).")
    if filled["party"]:
        notes.append(f"{bills(filled['party'])} had no customer or supplier name, so {'it is' if filled['party'] == 1 else 'they are'} "
                     f"under {default_party}.")
    return notes


def import_register(company_id: int, sheet: dict, register: str, before_commit: Callable[[], None] | None = None,
                    default_date: date | None = None, default_party: str | None = None) -> dict:
    """Post one sales or purchase register sheet. Returns counts and a list of problems.
    Jewellery registers (fine weight / tunch columns) are posted by weight; see metal.import_jewellery.
    A row's item name and net weight, when the register has them, are kept on its voucher for the voucher list
    (no metal lines: the rupees are all that is posted). ``before_commit`` is called last, inside the transaction: if
    it raises (the chat that asked for the import was stopped), nothing is posted. ``default_date`` / ``default_party``
    (an add asked for from the chat, which must not stop at a missing detail): the date and the customer or supplier of
    a bill that has none, instead of leaving it out."""
    if register not in ("sales", "purchases"):
        raise AccountsError("Choose whether the sheet is a sales or a purchase register.")
    from . import metal  # metal imports this module

    if default_date is not None or default_party:
        sheet = loose_sheet(sheet)
    if metal.detect_jewellery(sheet):
        return metal.import_jewellery(company_id, sheet, register, before_commit, default_date, default_party)
    raw = load_frame(sheet)
    frame, notes, _ = _normalise({**sheet, "register": register}, raw)
    text_date = date_kept_as_text(sheet, reports.effective_mapping(sheet["profile"])) if default_date else None
    if text_date:  # a "-" among the dates kept the column as text: read it as dates, day first
        frame["date"] = text_dates(raw[text_date]).to_numpy()
    # An add from the chat leaves out the rows that only add up those above them (a total, a bill's subtotal).
    totals = total_rows(sheet, raw, reports.effective_mapping(sheet["profile"])) if default_date else []
    if totals:
        frame = frame[~frame["rowid"].isin(totals)].reset_index(drop=True)
    item_col, net_col = _item_columns(sheet, metal.register_columns(sheet))
    raw = raw.set_index("_rowid")
    # Rows that are items of one bill become one row: the whole sheet for a list of items (one_bill_sheet), or, in an add
    # from the chat, the item rows typed under a bill with its date, number and party left blank.
    groups = bill_groups(frame, one_bill_sheet(sheet, default_date), join_items=default_date is not None)
    joined_items: dict[int, tuple] = {}
    joined_labels: dict[int, str] = {}
    if any(len(group) > 1 for group in groups):
        frame, joined_items, joined_labels = _join_rows(frame, raw, groups, item_col, net_col)
    service.get_company(company_id)  # "Company not found." before any work
    sales = register == "sales"
    states, problems = place_of_supply(sheet, sales)
    created, skipped, duplicates, bad_gstins = 0, 0, [], {}
    filled = {"date": 0, "party": 0}
    with engine.begin() as conn:
        # First of all: an import of the same sheet running meanwhile (a double tap, the chat and the Books screen) is
        # waited for, and its rows are then found in `done` below instead of being posted again.
        service.lock_books(conn, company_id)
        company = service.get_company(company_id, conn)
        done = _imported_sources(conn, company_id, f"import:{sheet['table_name']}:")
        # An add from the chat: bills dated before the books begin move the start back, in this same transaction.
        books_start = fit_books_start(conn, company, [
            pd.Timestamp(r.date).date() for r in frame.itertuples(index=False)
            if not pd.isna(r.date) and f"import:{sheet['table_name']}:{r.rowid}" not in done]) if default_date else None
        if books_start:
            company = service.get_company(company_id, conn)
        in_books = existing_documents(conn, company_id, f"import:{sheet['table_name']}:")
        main_ledger = service.ensure_ledger(conn, company_id, "Sales" if sales else "Purchase",
                                            "Sales Accounts" if sales else "Purchase Accounts")
        known: dict = {}  # ledger ids looked up once per import (remembered_ledger)
        for row in frame.itertuples(index=False):
            source = f"import:{sheet['table_name']}:{row.rowid}"
            label = joined_labels.get(row.rowid) or f"row {row.rowid}" + (f" ({row.invoice_no})" if row.invoice_no else "")
            if source in done:
                skipped += 1
                continue
            undated, party = pd.isna(row.date), row.party
            if undated and default_date is None:
                problems.append(f"{label}: no date, not posted.")
                continue
            unnamed = party in ("(blank)", "(not given)")
            if unnamed and not default_party:
                problems.append(f"{label}: no customer/supplier name, not posted.")
                continue
            party = default_party if unnamed else party
            value = int(row.invoice_value)
            if value == 0:
                problems.append(f"{label}: zero value, not posted.")
                continue
            returned = value < 0
            vtype = ("Credit Note" if returned else "Sales") if sales else ("Debit Note" if returned else "Purchase")
            sign = -1 if returned else 1
            day = default_date if undated else pd.Timestamp(row.date).date()
            # By GSTIN first, so a renamed or differently spelt party does not get a new, empty ledger.
            if already_in_books(in_books, vtype, row.invoice_no, day, None, [row.gstin]):
                skipped += 1
                duplicates.append(label)
                continue
            party_id = service.ensure_ledger(conn, company_id, party, "Sundry Debtors" if sales else "Sundry Creditors",
                                             gstin=row.gstin or None)
            is_party, saved_gstin = ledger_facts(conn, party_id)
            # A filled-in party (Cash Supplier) is shared by many: there the date and value must match too, as for "Cash".
            if already_in_books(in_books, vtype, row.invoice_no, day, party_id, [saved_gstin], is_party and not unnamed, value,
                                dated=not undated):
                skipped += 1
                duplicates.append(label)
                continue
            taxable = sign * int(row.taxable)
            heads = {h: sign * int(getattr(row, h)) for h in ("cgst", "sgst", "igst", "cess")}
            state, reported, used = party_state(conn, company, party_id, row.gstin, states.get(int(row.rowid)), label, problems)
            split_unsplit_gst(company, row.gstin, heads, sign * int(row.gst_unsplit), state)
            check_reported_state(company, vtype, party, heads, state, reported, label, problems)
            lines = posting_lines(conn, company_id, vtype, party_id, main_ledger, abs(value), taxable, heads, label, problems, known)
            number, reference = document_number(sales, row.invoice_no, label, problems)
            item, net_mg = joined_items.get(row.rowid) or _item_summary(raw.loc[row.rowid], item_col, net_col)
            try:
                with conn.begin_nested():
                    service.save_voucher(company_id, vtype, day, lines, number=number or None,
                                         reference=reference, narration=f"Imported from {sheet['sheet_name']}",
                                         source=source, conn=conn, items_text=item, net_mg=net_mg, company=company)
                created += 1
                filled["date"] += undated
                filled["party"] += unnamed
                note_bad_gstin(bad_gstins, row.gstin, label, used)
            except AccountsError as exc:
                problems.append(number_clash(conn, in_books, vtype, number, day, label, str(exc)) or f"{label}: {exc}")
            except (DataError, IntegrityError) as exc:  # only the row's savepoint is rolled back; the import goes on
                problems.append(refused(label, exc))
        note_register(conn, company_id, sheet["table_name"], register)
        if before_commit:
            before_commit()
    return {"created": created, "skipped": skipped, "problems": problems + gstin_warnings(bad_gstins),
            "notes": duplicates_note(duplicates, not sales) + filled_notes(filled, default_date, default_party)
            + totals_note(totals) + [n["message"] for n in notes], "books_start": books_start}


def refused(label: str, exc: Exception) -> str:
    """Problem text for a row the database refused (a figure too large to store, say): Postgres, unlike SQLite, checks
    every value, and the import reports the row and goes on with the next one rather than failing as a whole."""
    return f"{label}: the database could not store it ({_safe_reason(exc)}). Not posted."


_BANK_REFERENCE_LENGTH = 80  # bank_lines.reference
_BALANCE = re.compile(r"(^|_)(balance|bal|closing_balance|running_balance)(_|$)")
_REF = re.compile(r"(^|_)(chq|cheque|ref|reference|utr|txn_id|transaction_id)(_|$)")


def _text(value) -> str | None:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).replace("\x00", "").strip()  # Postgres cannot store NUL characters
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
    created, skipped, problems, rows = 0, 0, [], []
    with engine.begin() as conn:
        service.lock_books(conn, company_id)  # the same statement imported twice at once is added once
        done = set(conn.execute(select(bank_lines.c.source).where(and_(
            bank_lines.c.company_id == company_id,
            bank_lines.c.source.startswith(f"bank:{sheet['table_name']}:", autoescape=True)))).scalars())
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
            reference = _text(refs.iloc[i]) if refs is not None else None
            rows.append(dict(
                company_id=company_id, bank_ledger_id=bank_ledger_id, date=dates.iloc[i].date(),
                narration=_text(narration.iloc[i]) if narration is not None else None,
                reference=reference[:_BANK_REFERENCE_LENGTH] if reference else None,
                withdrawal_paise=w, deposit_paise=d,
                balance_paise=None if bal is None or (isinstance(bal, float) and math.isnan(bal)) or pd.isna(bal) else int(round(float(bal) * 100)),
                source=source,
            ))
            created += 1
        if rows:  # the whole statement in one insert: each statement is a trip to the database
            conn.execute(insert(bank_lines), rows)
    return {"created": created, "skipped": skipped, "problems": problems, "notes": []}
