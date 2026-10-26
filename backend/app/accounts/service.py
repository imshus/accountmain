"""Companies, ledgers and vouchers: creation, validation, audit trail and imports.

Rules enforced on every voucher (Tally-style double entry):
- at least two lines; each line is either a debit or a credit; total debits = total credits;
- the date is on or after the books-start date (fy_start) and after the company's locked period;
- Receipt: a cash/bank ledger is debited; Payment: a cash/bank ledger is credited;
  Contra: only cash/bank ledgers;
- GST document numbers (Sales, Credit Note, Debit Note) are unique per financial year, counting
  cancelled ones, and at most 16 characters (CGST Rule 46);
- bill-wise allocations only on party ledgers and adding up to the party line;
- metal lines (fine milligrams) balance per metal, just like rupees.
Every create/update/cancel is written to the audit log with before/after snapshots.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import and_, func, insert, select, update

from .. import gst
from ..database import columns_of, engine
from ..excel_loader import to_number
from . import chart
from .db import audit_log, bank_lines, bill_allocations, companies, ledgers, metal_lines, metal_openings, voucher_lines, vouchers

PREFIX = {
    "Sales": "INV", "Purchase": "PUR", "Receipt": "RCT", "Payment": "PMT",
    "Contra": "CTR", "Journal": "JV", "Credit Note": "CN", "Debit Note": "DN",
    "Metal Receipt": "MR", "Metal Issue": "MI",
}
GST_DOCUMENTS = {"Sales", "Credit Note", "Debit Note"}


class AccountsError(ValueError):
    """The request was rejected. The message is shown to the user."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def fy_of(day: date, fy_start_month: int = 4) -> tuple[date, date]:
    """First and last day of the Indian financial year (April-March) containing ``day``."""
    start_year = day.year if day.month >= fy_start_month else day.year - 1
    return date(start_year, fy_start_month, 1), date(start_year + 1, fy_start_month, 1) - timedelta(days=1)


def fy_label(day: date) -> str:
    start, _ = fy_of(day)
    return f"{start.year % 100:02d}-{(start.year + 1) % 100:02d}"


def to_paise(value, what: str = "Amount") -> int:
    """Rupees to whole paise; half a paisa is rounded up (1.005 -> 101), never to the even paisa."""
    if isinstance(value, float) and math.isnan(value):
        raise AccountsError(f'{what} "{value}" is not a number.')
    return _scaled(value, 100, what)


def _decimal(value, what: str) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()) or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        # str() of a float is its shortest repr (3.666, not 3.66599...), so register weights stay exact.
        number = Decimal(str(to_number(value) if isinstance(value, str) else value))
    except (InvalidOperation, ValueError):
        raise AccountsError(f'{what} "{value}" is not a number.') from None
    if not number.is_finite():
        raise AccountsError(f'{what} "{value}" is not a number.')
    return number


def _scaled(value, scale: int, what: str) -> int:
    number = _decimal(value, what)
    return 0 if number is None else int((number * scale).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def to_mg(grams, what: str = "Weight") -> int:
    """Grams (up to 3 decimals) to whole milligrams."""
    return _scaled(grams, 1000, what)


def to_mct(carats, what: str = "Carats") -> int:
    """Carats to thousandths of a carat."""
    return _scaled(carats, 1000, what)


def to_bp(percent, what: str = "Tunch") -> int:
    """Tunch / purity percent to hundredths of a percent (76.5 -> 7650)."""
    return _scaled(percent, 100, what)


def half_up(numerator: int, denominator: int) -> int:
    """Integer division rounded half away from zero, as Excel's ROUND does."""
    q, r = divmod(abs(numerator), denominator)
    q += 2 * r >= denominator
    return q if numerator >= 0 else -q


def rate_bp(rate) -> int:
    """GST rate percent to hundredths of a percent (0.25 -> 25, 18 -> 1800), exactly."""
    return _scaled(rate or 0, 100, "GST rate")


def place_of_supply(party: dict | None) -> str | None:
    """State code of a party: from its GSTIN when the GSTIN is valid, else the state chosen on the ledger."""
    if not party:
        return None
    gstin, state = party.get("gstin"), party.get("state_code")
    gstin = gstin.strip().upper() if isinstance(gstin, str) else ""
    if gstin and gst.gstin_problem(gstin) is None:
        return gstin[:2]
    return state if isinstance(state, str) and state else None


def fine_of(net_mg: int, tunch_bp: int) -> int:
    """Fine weight = net weight x tunch / 100, to the milligram."""
    return half_up(net_mg * tunch_bp, 10000)


def net_of(gross_mg: int, dia_mct: int = 0, stn_mct: int = 0) -> int:
    """Net metal = gross - (diamond + stone carats) x 0.2 g per carat."""
    return gross_mg - half_up((dia_mct + stn_mct) * 2, 10)


def _audit(conn, company_id: int, action: str, entity: str, entity_id: int | None, before=None, after=None):
    conn.execute(insert(audit_log).values(
        company_id=company_id, at=_now(), action=action, entity=entity, entity_id=entity_id,
        before_json=json.dumps(before, default=str) if before is not None else None,
        after_json=json.dumps(after, default=str) if after is not None else None,
    ))


# --- Companies and ledgers ------------------------------------------------------------------------


def create_company(name: str, gstin: str | None, fy_start: date) -> int:
    gstin = (gstin or "").strip().upper() or None
    if gstin and gst.gstin_problem(gstin):
        raise AccountsError(f"GSTIN {gstin}: {gst.gstin_problem(gstin)}.")
    with engine.begin() as conn:
        company_id = conn.execute(insert(companies).values(
            name=name.strip(), gstin=gstin, state_code=gstin[:2] if gstin else None,
            fy_start=fy_start, created_at=_now(),
        )).inserted_primary_key[0]
        for ledger, (group, tax_kind) in chart.DEFAULT_LEDGERS.items():
            conn.execute(insert(ledgers).values(company_id=company_id, name=ledger, group_name=group, opening_paise=0,
                                                tax_kind=tax_kind, created_at=_now()))
        _audit(conn, company_id, "create", "company", company_id, after={"name": name, "gstin": gstin, "fy_start": fy_start})
    return company_id


def list_companies() -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(select(companies).order_by(companies.c.id.desc())).mappings().all()
        counts = dict(conn.execute(
            select(vouchers.c.company_id, func.count()).where(vouchers.c.cancelled.is_(False)).group_by(vouchers.c.company_id)
        ).all())
    return [_company_out(r) | {"voucher_count": counts.get(r["id"], 0)} for r in rows]


def _company_out(row) -> dict:
    data = dict(row)
    if data["created_at"].tzinfo is None:
        data["created_at"] = data["created_at"].replace(tzinfo=timezone.utc)
    return data


def get_company(company_id: int) -> dict:
    with engine.connect() as conn:
        row = conn.execute(select(companies).where(companies.c.id == company_id)).mappings().first()
    if row is None:
        raise AccountsError("Company not found.")
    return _company_out(row)


def update_company(company_id: int, **values) -> dict:
    before = get_company(company_id)
    if values.get("gstin"):
        values["gstin"] = values["gstin"].strip().upper()
        if gst.gstin_problem(values["gstin"]):
            raise AccountsError(f"GSTIN {values['gstin']}: {gst.gstin_problem(values['gstin'])}.")
        values["state_code"] = values["gstin"][:2]
    with engine.begin() as conn:
        if values.get("fy_start") and values["fy_start"] != before["fy_start"]:
            # Opening balances are as at the books-start day, so it can only move while there are no vouchers.
            count = conn.execute(select(func.count()).select_from(vouchers).where(and_(
                vouchers.c.company_id == company_id, vouchers.c.cancelled.is_(False)))).scalar_one()
            if count:
                raise AccountsError(f"The books-start date can only be changed before any voucher is entered; this company already has "
                                    f"{count} voucher{'s' if count != 1 else ''}. Make a new company for the earlier year instead.")
        elif "fy_start" in values:
            values.pop("fy_start")  # unchanged, or None: keep the date
        if not values:
            return before
        conn.execute(update(companies).where(companies.c.id == company_id).values(**values))
        _audit(conn, company_id, "lock" if "locked_until" in values else "update", "company", company_id, before, values)
    return get_company(company_id)


def list_ledgers(company_id: int) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(select(ledgers).where(ledgers.c.company_id == company_id).order_by(ledgers.c.group_name, ledgers.c.name)).mappings().all()
    return [dict(r) for r in rows]


def ledger_map(company_id: int) -> dict[int, dict]:
    return {r["id"]: r for r in list_ledgers(company_id)}


def metal_opening_map(conn, company_id: int) -> dict[tuple[int, str], int]:
    """(ledger id, metal) -> opening fine mg (+ = Dr)."""
    rows = conn.execute(select(metal_openings.c.ledger_id, metal_openings.c.metal, metal_openings.c.opening_mg)
                        .join(ledgers, ledgers.c.id == metal_openings.c.ledger_id).where(ledgers.c.company_id == company_id)).all()
    return {(lid, metal): mg for lid, metal, mg in rows if mg}


def _save_metal_openings(conn, company_id: int, ledger_id: int, opening_metal: dict[str, int]) -> None:
    for metal, mg in opening_metal.items():
        if metal not in chart.METALS:
            raise AccountsError(f"Unknown metal {metal!r}.")
        before = conn.execute(select(metal_openings.c.opening_mg).where(and_(
            metal_openings.c.ledger_id == ledger_id, metal_openings.c.metal == metal))).scalar()
        if before == mg or (before is None and not mg):
            continue
        conn.execute(metal_openings.delete().where(and_(metal_openings.c.ledger_id == ledger_id, metal_openings.c.metal == metal)))
        conn.execute(insert(metal_openings).values(ledger_id=ledger_id, metal=metal, opening_mg=mg))
        _audit(conn, company_id, "update", "ledger", ledger_id, {f"opening_{metal}_mg": before or 0}, {f"opening_{metal}_mg": mg})


def save_ledger(company_id: int, ledger_id: int | None, name: str, group: str, opening, gstin: str | None = None,
                credit_days: int | None = None, opening_metal: dict[str, int] | None = None, state_code: str | None = None) -> dict:
    name = name.strip()
    if not name:
        raise AccountsError("Give the ledger a name.")
    if group not in chart.GROUPS:
        raise AccountsError(f"Unknown group {group!r}.")
    gstin = (gstin or "").strip().upper() or None
    if gstin and gst.gstin_problem(gstin):
        raise AccountsError(f"GSTIN {gstin}: {gst.gstin_problem(gstin)}.")
    state_code = (state_code or "").strip() or None
    if state_code and state_code not in gst.STATE_CODES:
        raise AccountsError(f"Unknown state code {state_code!r}; choose the state from the list.")
    opening_paise = to_paise(opening, "Opening balance")
    if opening_paise and chart.statement(group) == "pl":
        raise AccountsError(f"{group} is an income/expense group: its ledgers start every financial year at zero, so \"{name}\" cannot "
                            "have an opening balance. Put earlier years' profit or loss in Capital, or enter this year's figures "
                            "as vouchers dated on or after the books-start date.")
    # A valid GSTIN fixes the state (its first two digits); otherwise the state chosen on the ledger is the place of supply.
    values = {"name": name, "group_name": group, "opening_paise": opening_paise, "gstin": gstin,
              "state_code": gstin[:2] if gstin else state_code, "credit_days": credit_days}
    with engine.begin() as conn:
        clash = conn.execute(select(ledgers.c.id).where(and_(ledgers.c.company_id == company_id, func.lower(ledgers.c.name) == name.lower()))).scalar()
        if clash and clash != ledger_id:
            raise AccountsError(f'A ledger called "{name}" already exists.')
        if ledger_id:
            before = conn.execute(select(ledgers).where(ledgers.c.id == ledger_id)).mappings().first()
            if before is None or before["company_id"] != company_id:
                raise AccountsError("Ledger not found.")
            conn.execute(update(ledgers).where(ledgers.c.id == ledger_id).values(**values))
            _audit(conn, company_id, "update", "ledger", ledger_id, dict(before), values)
        else:
            ledger_id = conn.execute(insert(ledgers).values(company_id=company_id, created_at=_now(), **values)).inserted_primary_key[0]
            _audit(conn, company_id, "create", "ledger", ledger_id, after=values)
        if opening_metal:
            _save_metal_openings(conn, company_id, ledger_id, opening_metal)
    return ledger_map(company_id)[ledger_id]


def ensure_ledger(conn, company_id: int, name: str, group: str, *, gstin: str | None = None, tax_kind: str | None = None) -> int:
    existing = conn.execute(select(ledgers.c.id, ledgers.c.gstin).where(and_(ledgers.c.company_id == company_id, func.lower(ledgers.c.name) == name.lower()))).first()
    if existing:
        if gstin and not existing.gstin and not gst.gstin_problem(gstin):
            conn.execute(update(ledgers).where(ledgers.c.id == existing.id).values(gstin=gstin, state_code=gstin[:2]))
        return existing.id
    valid = gstin if gstin and not gst.gstin_problem(gstin) else None
    return conn.execute(insert(ledgers).values(
        company_id=company_id, name=name, group_name=group, opening_paise=0, tax_kind=tax_kind,
        gstin=valid, state_code=valid[:2] if valid else None, created_at=_now(),
    )).inserted_primary_key[0]


def _tax_ledger(conn, company_id: int, kind: str) -> int:
    row = conn.execute(select(ledgers.c.id).where(and_(ledgers.c.company_id == company_id, ledgers.c.tax_kind == kind))).first()
    if row:
        return row.id
    if kind == "tds_receivable":  # TDS customers deducted from what they paid us: an asset until claimed
        return ensure_ledger(conn, company_id, "TDS Receivable", "Loans & Advances (Asset)", tax_kind=kind)
    direction, head = kind.split("_")
    return ensure_ledger(conn, company_id, f"{direction.title()} {head.upper()}", "Duties & Taxes", tax_kind=kind)


# --- Vouchers --------------------------------------------------------------------------------------


@dataclass
class Line:
    ledger_id: int
    dr: int = 0
    cr: int = 0
    bills: list[dict] = field(default_factory=list)  # {kind, bill_ref, amount (signed paise), bill_date, due_date}


METAL_DETAILS = ("item", "purity", "tunch_bp", "gross_mg", "net_mg", "dia_mct", "stn_mct", "pieces", "tag_no")


@dataclass
class MetalLine:
    """Fine metal (mg) debited or credited to a ledger, with optional item details for stock lines."""
    ledger_id: int
    metal: str = "gold"
    dr: int = 0
    cr: int = 0
    details: dict = field(default_factory=dict)  # keys from METAL_DETAILS


def next_number(conn, company_id: int, vtype: str, day: date) -> str:
    start, end = fy_of(day)
    prefix = f"{PREFIX[vtype]}/{fy_label(day)}/"
    numbers = conn.execute(select(vouchers.c.number).where(and_(
        vouchers.c.company_id == company_id, vouchers.c.vtype == vtype, vouchers.c.date >= start, vouchers.c.date <= end,
        vouchers.c.number.like(f"{prefix}%"),
    ))).scalars().all()
    used = [int(m.group(1)) for n in numbers if (m := re.search(r"(\d+)$", n))]
    return f"{prefix}{(max(used) + 1 if used else 1):04d}"


def _validate_metal(metal: list[MetalLine]) -> None:
    for line in metal:
        if line.metal not in chart.METALS:
            raise AccountsError(f"Unknown metal {line.metal!r}.")
        if line.dr < 0 or line.cr < 0 or (line.dr > 0) == (line.cr > 0):
            raise AccountsError("Each metal line must have either a debit or a credit fine weight (not both, not zero).")
    for name in chart.METALS:
        mine = [l for l in metal if l.metal == name]
        dr, cr = sum(l.dr for l in mine), sum(l.cr for l in mine)
        if dr != cr:
            raise AccountsError(f"{name.title()} debits {dr / 1000:,.3f} g and credits {cr / 1000:,.3f} g differ by "
                                f"{abs(dr - cr) / 1000:,.3f} g fine. They must be equal.")


def _validate(conn, company: dict, vtype: str, day: date, number: str, lines: list[Line], voucher_id: int | None,
              metal: list[MetalLine] = ()) -> None:
    if vtype not in chart.VOUCHER_TYPES:
        raise AccountsError(f"Unknown voucher type {vtype!r}.")
    if company.get("fy_start") and day < company["fy_start"]:
        # Earlier entries would sit outside the opening balances, so the reports could not agree.
        raise AccountsError(f"The date {day:%d/%m/%Y} is before the books begin on {company['fy_start']:%d/%m/%Y}; enter vouchers dated "
                            f"on or after that day. If this is the company's first entry, change \"Books begin from\" (under Ledgers) "
                            f"to an earlier date first.")
    if company.get("locked_until") and day <= company["locked_until"]:
        raise AccountsError(f"Books are locked up to {company['locked_until']:%d %b %Y}; this voucher's date is inside the locked period.")
    if vtype in chart.METAL_VOUCHERS:
        if lines:
            raise AccountsError(f"A {vtype} moves metal only; post rupees with a separate voucher.")
        if len(metal) < 2:
            raise AccountsError(f"A {vtype} needs metal going out of one ledger and into another.")
    elif len(lines) < 2 and (lines or not metal):  # a sale purely by weight may have metal lines and no rupees
        raise AccountsError("A voucher needs at least two lines (one debit and one credit).")
    for line in lines:
        if line.dr < 0 or line.cr < 0 or (line.dr > 0) == (line.cr > 0):
            raise AccountsError("Each line must have either a debit or a credit amount (not both, not zero).")
    total_dr, total_cr = sum(l.dr for l in lines), sum(l.cr for l in lines)
    if total_dr != total_cr:
        raise AccountsError(f"Debits {total_dr / 100:,.2f} and credits {total_cr / 100:,.2f} differ by {abs(total_dr - total_cr) / 100:,.2f}. They must be equal.")
    _validate_metal(metal)
    by_id = {r.id: r for r in conn.execute(select(ledgers).where(ledgers.c.company_id == company["id"])).all()}
    for line in [*lines, *metal]:
        if line.ledger_id not in by_id:
            raise AccountsError("A line uses a ledger that does not belong to this company.")
    groups = [by_id[l.ledger_id].group_name for l in lines]
    cash = [g in chart.CASH_BANK for g in groups]
    if vtype == "Contra" and not all(cash):
        raise AccountsError("A Contra voucher can only move money between cash and bank ledgers.")
    if vtype == "Receipt" and not any(c and l.dr for c, l in zip(cash, lines)):
        raise AccountsError("A Receipt must debit a cash or bank ledger (the money received).")
    if vtype == "Payment" and not any(c and l.cr for c, l in zip(cash, lines)):
        raise AccountsError("A Payment must credit a cash or bank ledger (the money paid).")
    if vtype in GST_DOCUMENTS:
        if len(number) > 16:
            raise AccountsError(f"GST document numbers can be at most 16 characters (Rule 46); {number!r} has {len(number)}.")
        if not re.fullmatch(r"[A-Za-z0-9/-]+", number):
            raise AccountsError("GST document numbers may contain only letters, digits, '/' and '-' (Rule 46).")
    start, end = fy_of(day)
    same_number = and_(vouchers.c.company_id == company["id"], vouchers.c.vtype == vtype, func.lower(vouchers.c.number) == number.lower(),
                       vouchers.c.date >= start, vouchers.c.date <= end, vouchers.c.id != (voucher_id or 0))
    # Rule 46: a GST document number is used once in a financial year, even if that invoice was later cancelled.
    if vtype not in GST_DOCUMENTS:
        same_number = and_(same_number, vouchers.c.cancelled.is_(False))
    clash = conn.execute(select(vouchers.c.cancelled).where(same_number).order_by(vouchers.c.cancelled)).first()
    if clash is not None:
        raise AccountsError(f"{vtype} number {number} is already used in this financial year"
                            + (" by a cancelled voucher; a cancelled GST document number cannot be reused (Rule 46). " if clash.cancelled else ". ")
                            + "Leave the number blank to take the next one.")
    for line, group in zip(lines, groups):
        if not line.bills:
            continue
        if group not in chart.PARTY_GROUPS:
            raise AccountsError("Bill-wise details can only be given on customer or supplier ledgers.")
        signed = line.dr - line.cr
        if sum(b["amount"] for b in line.bills) != signed:
            raise AccountsError("Bill-wise amounts on a party line must add up to that line's amount.")


def _default_bills(conn, company_id: int, vtype: str, number: str, reference: str, day: date, lines: list[Line]) -> None:
    """Party lines without bill-wise details get Tally's defaults: an invoice opens a New Ref named after
    its number (for purchases, the supplier's bill number when given); anything else is On Account."""
    party_ids = set(conn.execute(select(ledgers.c.id).where(and_(
        ledgers.c.company_id == company_id, ledgers.c.group_name.in_(chart.PARTY_GROUPS)))).scalars())
    bill_ref = (reference or number) if vtype in ("Purchase", "Debit Note") else number
    for line in lines:
        if line.ledger_id in party_ids and not line.bills:
            kind = "new" if vtype in ("Sales", "Purchase", "Credit Note", "Debit Note") else "on_account"
            line.bills = [{"kind": kind, "bill_ref": bill_ref if kind == "new" else None, "amount": line.dr - line.cr, "bill_date": day}]


def pending_by_bill(conn, party_id: int) -> dict[str, int]:
    """Open amount (signed paise, + = Dr) of each bill of a party."""
    rows = conn.execute(
        select(bill_allocations.c.bill_ref, func.sum(bill_allocations.c.amount_paise))
        .join(voucher_lines, voucher_lines.c.id == bill_allocations.c.line_id)
        .join(vouchers, vouchers.c.id == voucher_lines.c.voucher_id)
        .where(and_(bill_allocations.c.ledger_id == party_id, vouchers.c.cancelled.is_(False),
                    bill_allocations.c.kind.in_(["new", "against"])))
        .group_by(bill_allocations.c.bill_ref)
    ).all()
    return {ref: int(total) for ref, total in rows if ref is not None}


def _snapshot(conn, voucher_id: int) -> dict:
    head = conn.execute(select(*columns_of(vouchers).values()).where(vouchers.c.id == voucher_id)).mappings().first()
    lines = conn.execute(select(voucher_lines).where(voucher_lines.c.voucher_id == voucher_id).order_by(voucher_lines.c.position)).mappings().all()
    line_ids = [l["id"] for l in lines]
    bills = conn.execute(select(bill_allocations).where(bill_allocations.c.line_id.in_(line_ids))).mappings().all() if line_ids else []
    metal = conn.execute(select(metal_lines).where(metal_lines.c.voucher_id == voucher_id).order_by(metal_lines.c.position)).mappings().all()
    return {**dict(head), "lines": [dict(l) | {"bills": [dict(b) for b in bills if b["line_id"] == l["id"]]} for l in lines],
            "metal_lines": [dict(m) for m in metal]}


def _write_metal(conn, voucher_id: int, metal: list[MetalLine]) -> None:
    for position, line in enumerate(metal):
        details = {k: line.details.get(k) for k in METAL_DETAILS}
        conn.execute(insert(metal_lines).values(voucher_id=voucher_id, position=position, ledger_id=line.ledger_id,
                                                metal=line.metal, dr_mg=line.dr, cr_mg=line.cr, **details))


def _write_lines(conn, voucher_id: int, day: date, lines: list[Line], credit_days: dict[int, int | None]) -> None:
    for position, line in enumerate(lines):
        line_id = conn.execute(insert(voucher_lines).values(
            voucher_id=voucher_id, position=position, ledger_id=line.ledger_id, dr_paise=line.dr, cr_paise=line.cr,
        )).inserted_primary_key[0]
        for bill in line.bills:
            bill_date = bill.get("bill_date") or day
            days = credit_days.get(line.ledger_id)
            due = bill.get("due_date") or (date.fromordinal(bill_date.toordinal() + days) if days else None)
            conn.execute(insert(bill_allocations).values(
                line_id=line_id, ledger_id=line.ledger_id, kind=bill["kind"], bill_ref=bill.get("bill_ref"),
                amount_paise=bill["amount"], bill_date=bill_date, due_date=due,
            ))


def save_voucher(company_id: int, vtype: str, day: date, lines: list[Line], *, number: str | None = None, narration: str = "",
                 reference: str = "", source: str = "manual", voucher_id: int | None = None, conn=None,
                 metal: list[MetalLine] | None = None, items_text: str | None = None, net_mg: int | None = None) -> int:
    """items_text / net_mg: an imported bill's item names and net weight, for the voucher list (kept by an update that
    leaves the items on its metal lines as they were)."""
    metal = metal or []

    def run(c) -> int:
        company = dict(c.execute(select(companies).where(companies.c.id == company_id)).mappings().first() or {})
        if not company:
            raise AccountsError("Company not found.")
        num = (number or "").strip() or next_number(c, company_id, vtype, day)
        _default_bills(c, company_id, vtype, num, reference, day, lines)
        _validate(c, company, vtype, day, num, lines, voucher_id, metal)
        credit_days = dict(c.execute(select(ledgers.c.id, ledgers.c.credit_days).where(ledgers.c.company_id == company_id)).all())
        if voucher_id:
            before = _snapshot(c, voucher_id)
            if before["company_id"] != company_id:
                raise AccountsError("Voucher not found.")
            if company.get("locked_until") and before["date"] <= company["locked_until"]:
                raise AccountsError("This voucher is in the locked period and cannot be changed.")
            c.execute(voucher_lines.delete().where(voucher_lines.c.voucher_id == voucher_id))
            c.execute(metal_lines.delete().where(metal_lines.c.voucher_id == voucher_id))
            # Once an edit changes the items, the list reads them from the new metal lines, not the import's summary.
            same = [[m[k] for k in METAL_DETAILS] for m in before["metal_lines"]] == [[l.details.get(k) for k in METAL_DETAILS] for l in metal]
            c.execute(update(vouchers).where(vouchers.c.id == voucher_id).values(
                vtype=vtype, number=num, date=day, narration=narration, reference=reference, updated_at=_now(),
                **({} if same else {"items_text": None, "net_mg": None})))
            _write_lines(c, voucher_id, day, lines, credit_days)
            _write_metal(c, voucher_id, metal)
            _audit(c, company_id, "update", "voucher", voucher_id, before, _snapshot(c, voucher_id))
            return voucher_id
        new_id = c.execute(insert(vouchers).values(
            company_id=company_id, vtype=vtype, number=num, date=day, narration=narration, reference=reference,
            source=source, cancelled=False, created_at=_now(), updated_at=_now(), items_text=items_text, net_mg=net_mg,
        )).inserted_primary_key[0]
        _write_lines(c, new_id, day, lines, credit_days)
        _write_metal(c, new_id, metal)
        _audit(c, company_id, "create" if source == "manual" else "import", "voucher", new_id, after=_snapshot(c, new_id))
        return new_id

    if conn is not None:
        return run(conn)
    with engine.begin() as c:
        return run(c)


def cancel_voucher(company_id: int, voucher_id: int) -> None:
    with engine.begin() as conn:
        before = _snapshot(conn, voucher_id)
        if before["company_id"] != company_id:
            raise AccountsError("Voucher not found.")
        company = conn.execute(select(companies).where(companies.c.id == company_id)).mappings().first()
        if company["locked_until"] and before["date"] <= company["locked_until"]:
            raise AccountsError("This voucher is in the locked period and cannot be cancelled.")
        conn.execute(update(vouchers).where(vouchers.c.id == voucher_id).values(cancelled=True, updated_at=_now()))
        _audit(conn, company_id, "cancel", "voucher", voucher_id, before, {"cancelled": True})


def get_voucher(company_id: int, voucher_id: int) -> dict:
    with engine.connect() as conn:
        snap = _snapshot(conn, voucher_id)
    if snap["company_id"] != company_id:
        raise AccountsError("Voucher not found.")
    names = ledger_map(company_id)
    for line in [*snap["lines"], *snap["metal_lines"]]:
        line["ledger"] = names[line["ledger_id"]]["name"]
    return snap


def stored_metal(snapshot: dict) -> list[MetalLine]:
    """A saved voucher's metal lines, to carry them over when only its rupee lines are edited."""
    return [MetalLine(m["ledger_id"], m["metal"], m["dr_mg"], m["cr_mg"], {k: m[k] for k in METAL_DETAILS})
            for m in snapshot.get("metal_lines", [])]


def list_vouchers(company_id: int, vtype: str | None, start: date | None, end: date | None, search: str | None,
                  offset: int, limit: int) -> dict:
    v, l, m = vouchers, voucher_lines, metal_lines
    head = columns_of(v)
    totals = select(l.c.voucher_id, func.sum(l.c.dr_paise).label("amount")).group_by(l.c.voucher_id).subquery()
    # Each item's net weight is on its own stock line; the party or Sales line on the other side carries none.
    fine = (select(m.c.voucher_id, func.sum(m.c.dr_mg).label("fine_mg"), func.sum(m.c.net_mg).label("item_net_mg"))
            .group_by(m.c.voucher_id).subquery())
    # Outer joins: metal-only vouchers have no rupee lines, and most vouchers have no metal.
    query = (select(*head.values(), func.coalesce(totals.c.amount, 0).label("amount"), func.coalesce(fine.c.fine_mg, 0).label("fine_mg"),
                    fine.c.item_net_mg)
             .outerjoin(totals, totals.c.voucher_id == v.c.id).outerjoin(fine, fine.c.voucher_id == v.c.id)
             .where(v.c.company_id == company_id))
    if vtype:
        query = query.where(v.c.vtype == vtype)
    if start:
        query = query.where(v.c.date >= start)
    if end:
        query = query.where(v.c.date <= end)
    if search:
        like = f"%{search.strip()}%"
        matching = select(l.c.voucher_id).join(ledgers, ledgers.c.id == l.c.ledger_id).where(ledgers.c.name.ilike(like))
        matching_metal = select(m.c.voucher_id).join(ledgers, ledgers.c.id == m.c.ledger_id).where(
            ledgers.c.name.ilike(like) | m.c.item.ilike(like) | m.c.tag_no.ilike(like))
        query = query.where(v.c.number.ilike(like) | v.c.narration.ilike(like) | v.c.reference.ilike(like) | head["items_text"].ilike(like)
                            | v.c.id.in_(matching) | v.c.id.in_(matching_metal))
    with engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(query.subquery())).scalar_one()
        rows = conn.execute(query.order_by(v.c.date.desc(), v.c.id.desc()).offset(offset).limit(limit)).mappings().all()
        ids = [r["id"] for r in rows]
        parties: dict[int, list[str]] = {}
        items: dict[int, list[str]] = {}
        if ids:
            for table in (l, m):
                for vid, name in conn.execute(
                    select(table.c.voucher_id, ledgers.c.name).join(ledgers, ledgers.c.id == table.c.ledger_id)
                    .where(table.c.voucher_id.in_(ids)).order_by(table.c.position)
                ).all():
                    if name not in parties.setdefault(vid, []):
                        parties[vid].append(name)
            # Each name once, in the order of its first line.
            for vid, name in conn.execute(
                select(m.c.voucher_id, m.c.item).where(m.c.voucher_id.in_(ids), m.c.item.isnot(None))
                .group_by(m.c.voucher_id, m.c.item).order_by(func.min(m.c.position))
            ).all():
                items.setdefault(vid, []).append(name)
    out = []
    for r in rows:
        row = dict(r) | {"ledgers": parties.get(r["id"], [])}
        stored, item_net = row.pop("items_text"), row.pop("item_net_mg")
        if stored is None and row["net_mg"] is None:  # entered by hand: its metal lines describe the items, if any
            row |= {"items": items.get(r["id"], [])[:3], "net_mg": item_net}
        else:  # imported: the register's own rows, each item and weight once (net_mg is the voucher's own column)
            row["items"] = stored.split("\n")[:3] if stored else []
        out.append(row)
    return {"total": total, "rows": out}


def audit_trail(company_id: int, limit: int = 200) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(select(audit_log).where(audit_log.c.company_id == company_id).order_by(audit_log.c.id.desc()).limit(limit)).mappings().all()
    return [dict(r) for r in rows]


# --- Builders for common vouchers --------------------------------------------------------------------


def gst_invoice_lines(conn, company: dict, vtype: str, party_id: int, items: list[dict], round_off: bool, cess_paise: int = 0) -> tuple[list[Line], dict]:
    """Lines for a Sales/Purchase/Credit Note/Debit Note with GST.

    items: [{"ledger_id": sales/purchase ledger, "taxable": paise, "rate": percent}]. CGST+SGST when the
    party's place of supply (GSTIN state, else the ledger's state) equals the company's state, else IGST.
    Returns the lines and a summary of the amounts.
    """
    party = conn.execute(select(ledgers).where(ledgers.c.id == party_id)).mappings().first()
    if party is None or party["company_id"] != company["id"]:
        raise AccountsError("Party ledger not found.")
    pos = place_of_supply(dict(party))
    inter = bool(pos and company.get("state_code") and pos != company["state_code"])
    # Sales and sales returns (Credit Note) move output tax; purchases and purchase returns (Debit Note) input tax.
    side = "output" if vtype in ("Sales", "Credit Note") else "input"
    taxable_total, heads = 0, {"cgst": 0, "sgst": 0, "igst": 0}
    item_lines: list[tuple[int, int]] = []
    for item in items:
        taxable = int(item["taxable"])
        if taxable <= 0:
            raise AccountsError("Each item needs a positive taxable value.")
        item_lines.append((item["ledger_id"], taxable))
        taxable_total += taxable
        tax = half_up(taxable * rate_bp(item.get("rate")), 10000)
        if inter:
            heads["igst"] += tax
        else:
            heads["cgst"] += tax // 2
            heads["sgst"] += tax - tax // 2  # the odd paisa goes to SGST so the halves add up
    gross = taxable_total + sum(heads.values()) + cess_paise
    rounded = half_up(gross, 100) * 100 if round_off else gross  # Rs 1,050.50 -> Rs 1,051
    diff = rounded - gross

    # Sales and Debit Note: party Dr, income/taxes Cr. Purchase and Credit Note: the mirror.
    party_dr = vtype in ("Sales", "Debit Note")
    lines = [Line(party_id, dr=rounded if party_dr else 0, cr=0 if party_dr else rounded)]
    for ledger_id, taxable in item_lines:
        lines.append(Line(ledger_id, dr=0 if party_dr else taxable, cr=taxable if party_dr else 0))
    for head, amount in heads.items():
        if amount:
            lid = _tax_ledger(conn, company["id"], f"{side}_{head}")
            lines.append(Line(lid, dr=0 if party_dr else amount, cr=amount if party_dr else 0))
    if cess_paise:
        lid = _tax_ledger(conn, company["id"], f"{side}_cess")
        lines.append(Line(lid, dr=0 if party_dr else cess_paise, cr=cess_paise if party_dr else 0))
    if diff:
        lid = ensure_ledger(conn, company["id"], "Round Off", "Indirect Expenses")
        # Rounding up on a sale is extra income (Cr); rounding down is an expense (Dr). Mirror for purchases.
        if party_dr:
            lines.append(Line(lid, dr=0 if diff > 0 else -diff, cr=diff if diff > 0 else 0))
        else:
            lines.append(Line(lid, dr=diff if diff > 0 else 0, cr=0 if diff > 0 else -diff))
    summary = {"taxable": taxable_total, **heads, "cess": cess_paise, "round_off": diff, "total": rounded, "inter_state": inter}
    return lines, summary


def settlement_lines(conn, company_id: int, vtype: str, party_id: int, cash_bank_id: int, amount: int, against: list[dict],
                     tds_paise: int = 0) -> list[Line]:
    """Receipt (customer pays) or Payment (pay a supplier), optionally against bills and with TDS deducted.

    Receipt with TDS: Cash/Bank Dr amount, TDS Receivable Dr tds, Customer Cr amount + tds (the customer settled that much).
    Payment with TDS: Supplier Dr amount + tds, Cash/Bank Cr amount, TDS Payable Cr tds.
    """
    if tds_paise < 0:
        raise AccountsError("TDS cannot be negative.")
    if amount <= 0:
        raise AccountsError("Enter a positive amount.")
    allocated = sum(int(a["amount"]) for a in against)
    if allocated > amount + tds_paise:
        raise AccountsError("Bills allocated add up to more than the amount.")
    open_bills = pending_by_bill(conn, party_id)
    for a in against:
        pending = abs(open_bills.get(a["bill_ref"], 0))
        if not pending:
            raise AccountsError(f"Bill {a['bill_ref']} has nothing pending for this party.")
        if int(a["amount"]) > pending:
            raise AccountsError(f"Bill {a['bill_ref']} has only {pending / 100:,.2f} pending; "
                                f"put the extra {(int(a['amount']) - pending) / 100:,.2f} on account instead.")
    on_account = amount + tds_paise - allocated
    if vtype == "Receipt":
        bills = [{"kind": "against", "bill_ref": a["bill_ref"], "amount": -int(a["amount"])} for a in against]
        if on_account:
            bills.append({"kind": "on_account", "bill_ref": None, "amount": -on_account})
        lines = [Line(cash_bank_id, dr=amount)]
        if tds_paise:
            lines.append(Line(_tax_ledger(conn, company_id, "tds_receivable"), dr=tds_paise))
        return [*lines, Line(party_id, cr=amount + tds_paise, bills=bills)]
    bills = [{"kind": "against", "bill_ref": a["bill_ref"], "amount": int(a["amount"])} for a in against]
    if on_account:
        bills.append({"kind": "on_account", "bill_ref": None, "amount": on_account})
    lines = [Line(party_id, dr=amount + tds_paise, bills=bills), Line(cash_bank_id, cr=amount)]
    if tds_paise:
        lines.append(Line(_tax_ledger(conn, company_id, "tds_payable"), cr=tds_paise))
    return lines
