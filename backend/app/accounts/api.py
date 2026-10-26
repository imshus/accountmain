"""HTTP routes for the double-entry books."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, select

from .. import cloud, database, gst
from ..database import engine
from . import chart, imports, metal, reports, service
from .db import bill_allocations, voucher_lines, vouchers
from .service import AccountsError, Line, MetalLine, to_mg, to_paise

router = APIRouter(prefix="/api")

VoucherType = Literal["Sales", "Purchase", "Receipt", "Payment", "Contra", "Journal", "Credit Note", "Debit Note",
                      "Metal Receipt", "Metal Issue"]
Metal = Literal["gold", "silver"]


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except AccountsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _company(company_id: int) -> dict:
    return _guard(service.get_company, company_id)


# --- Companies & ledgers -----------------------------------------------------------------------------


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    gstin: str | None = Field(default=None, max_length=15)
    fy_start: date | None = None


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    gstin: str | None = Field(default=None, max_length=15)
    locked_until: date | None = None
    fy_start: date | None = None  # books-start date; only while the company has no vouchers


@router.get("/accounts/meta")
def meta():
    return {"groups": [{"name": g, "parent": p, "nature": n} for g, (p, n) in chart.GROUPS.items()],
            "voucher_types": chart.VOUCHER_TYPES, "metals": list(chart.METALS),
            "states": [{"code": code, "name": name} for code, name in gst.STATE_CODES.items()]}


@router.get("/companies")
def list_companies():
    return service.list_companies()


@router.post("/companies", status_code=201)
def create_company(body: CompanyIn):
    fy_start = body.fy_start or service.fy_of(date.today())[0]
    return _company(_guard(service.create_company, body.name, body.gstin, fy_start))


@router.get("/companies/{company_id}")
def get_company(company_id: int):
    return _company(company_id)


@router.put("/companies/{company_id}")
def update_company(company_id: int, body: CompanyUpdate):
    _company(company_id)
    values = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    return _guard(service.update_company, company_id, **values)


class LedgerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    group: str
    opening: str | float | None = 0  # + = Dr; "1,000 Cr" also accepted
    gstin: str | None = None
    state_code: str | None = Field(default=None, max_length=2)  # place of supply when there is no valid GSTIN
    credit_days: int | None = Field(default=None, ge=0, le=365)
    # Opening fine metal in grams (+ = Dr: owes us / in hand; "12.5 Cr" also accepted). None = leave unchanged.
    opening_gold: str | float | None = None
    opening_silver: str | float | None = None

    def metal_openings(self) -> dict[str, int]:
        return {name: to_mg(value, f"Opening {name}") for name, value in (("gold", self.opening_gold), ("silver", self.opening_silver))
                if value is not None}


@router.get("/companies/{company_id}/ledgers")
def list_ledgers(company_id: int):
    company = _company(company_id)
    # Balance-sheet ledgers close with everything to date; income and expense ledgers with the latest financial
    # year only (as the trial balance shows them), their earlier years being in Capital as "Profit & Loss A/c".
    year_start = reports._fy_period(company, None, None)[0]
    bal = reports.balances(company, year_start, date(2100, 12, 31))
    with engine.connect() as conn:
        openings = service.metal_opening_map(conn, company_id)
    closings = {name: metal.metal_closing(company, name) for name in metal.metals_in_use(company_id)}
    out = []
    for r in service.list_ledgers(company_id):
        metals = {name: {"opening_mg": openings.get((r["id"], name), 0), "closing_mg": int(closing.get(r["id"], 0))}
                  for name, closing in closings.items() if openings.get((r["id"], name)) or closing.get(r["id"])}
        pl = chart.statement(r["group_name"]) == "pl"
        out.append(r | {"closing_paise": int(bal.closing.get(r["id"], 0)), "metal": metals,
                        "closing_from": year_start.isoformat() if pl else None,
                        "earlier_years_paise": int(bal.earlier.get(r["id"], 0))})
    return out


@router.post("/companies/{company_id}/ledgers", status_code=201)
def create_ledger(company_id: int, body: LedgerIn):
    _company(company_id)
    return _guard(lambda: service.save_ledger(company_id, None, body.name, body.group, body.opening, body.gstin, body.credit_days,
                                              body.metal_openings(), body.state_code))


@router.put("/companies/{company_id}/ledgers/{ledger_id}")
def update_ledger(company_id: int, ledger_id: int, body: LedgerIn):
    _company(company_id)
    return _guard(lambda: service.save_ledger(company_id, ledger_id, body.name, body.group, body.opening, body.gstin, body.credit_days,
                                              body.metal_openings(), body.state_code))


# --- Vouchers -----------------------------------------------------------------------------------------


class BillIn(BaseModel):
    kind: Literal["new", "against", "advance", "on_account"]
    bill_ref: str | None = None
    amount: str | float  # rupees on the same side as the line


class LineIn(BaseModel):
    ledger_id: int
    dr: str | float | None = None
    cr: str | float | None = None
    bills: list[BillIn] = []


class MetalLineIn(BaseModel):
    ledger_id: int
    metal: Metal = "gold"
    dr: str | float | None = None  # fine grams
    cr: str | float | None = None


class VoucherIn(BaseModel):
    vtype: VoucherType
    date: date
    number: str | None = Field(default=None, max_length=40)
    narration: str = Field(default="", max_length=2000)
    reference: str = Field(default="", max_length=60)
    lines: list[LineIn] = []
    metal: list[MetalLineIn] | None = None  # None on an update keeps the voucher's metal lines


def _metal(body: VoucherIn) -> list[MetalLine]:
    return [MetalLine(m.ledger_id, m.metal, dr=to_mg(m.dr, f"Metal line {i} debit"), cr=to_mg(m.cr, f"Metal line {i} credit"))
            for i, m in enumerate(body.metal or [], start=1)]


def _lines(body: VoucherIn) -> list[Line]:
    out = []
    for i, line in enumerate(body.lines, start=1):
        dr, cr = to_paise(line.dr, f"Line {i} debit"), to_paise(line.cr, f"Line {i} credit")
        sign = 1 if dr else -1
        bills = [{"kind": b.kind, "bill_ref": b.bill_ref, "amount": sign * abs(to_paise(b.amount, "Bill amount"))} for b in line.bills]
        out.append(Line(line.ledger_id, dr=dr, cr=cr, bills=bills))
    return out


@router.get("/companies/{company_id}/vouchers")
def list_vouchers(company_id: int, vtype: str | None = None, start: date | None = None, end: date | None = None,
                  search: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500)):
    _company(company_id)
    return service.list_vouchers(company_id, vtype, start, end, search, offset, limit)


@router.get("/companies/{company_id}/vouchers/{voucher_id}")
def get_voucher(company_id: int, voucher_id: int):
    return _guard(service.get_voucher, company_id, voucher_id)


@router.post("/companies/{company_id}/vouchers", status_code=201)
def create_voucher(company_id: int, body: VoucherIn):
    _company(company_id)
    vid = _guard(lambda: service.save_voucher(company_id, body.vtype, body.date, _lines(body), number=body.number,
                                              narration=body.narration, reference=body.reference, metal=_metal(body)))
    return service.get_voucher(company_id, vid)


@router.put("/companies/{company_id}/vouchers/{voucher_id}")
def update_voucher(company_id: int, voucher_id: int, body: VoucherIn):
    _company(company_id)
    kept = _metal(body) if body.metal is not None else service.stored_metal(_guard(service.get_voucher, company_id, voucher_id))
    _guard(lambda: service.save_voucher(company_id, body.vtype, body.date, _lines(body), number=body.number,
                                        narration=body.narration, reference=body.reference, voucher_id=voucher_id, metal=kept))
    return service.get_voucher(company_id, voucher_id)


@router.delete("/companies/{company_id}/vouchers/{voucher_id}", status_code=204)
def cancel_voucher(company_id: int, voucher_id: int):
    _guard(service.cancel_voucher, company_id, voucher_id)


class InvoiceItem(BaseModel):
    ledger_id: int | None = None  # defaults to the "Sales" / "Purchase" ledger
    taxable: str | float
    rate: float = Field(ge=0, le=100)


class InvoiceIn(BaseModel):
    vtype: Literal["Sales", "Purchase", "Credit Note", "Debit Note"]
    date: date
    number: str | None = Field(default=None, max_length=40)
    party_id: int
    items: list[InvoiceItem] = Field(min_length=1)
    cess: str | float | None = None
    round_off: bool = True
    narration: str = ""
    reference: str = ""


@router.post("/companies/{company_id}/vouchers/invoice", status_code=201)
def create_invoice(company_id: int, body: InvoiceIn):
    company = _company(company_id)

    def run():
        with engine.begin() as conn:
            default = service.ensure_ledger(conn, company_id, "Sales" if body.vtype in ("Sales", "Credit Note") else "Purchase",
                                            "Sales Accounts" if body.vtype in ("Sales", "Credit Note") else "Purchase Accounts")
            items = [{"ledger_id": i.ledger_id or default, "taxable": to_paise(i.taxable, "Taxable value"), "rate": i.rate} for i in body.items]
            lines, summary = service.gst_invoice_lines(conn, company, body.vtype, body.party_id, items, body.round_off, to_paise(body.cess, "Cess"))
            vid = service.save_voucher(company_id, body.vtype, body.date, lines, number=body.number, narration=body.narration,
                                       reference=body.reference, conn=conn)
        return vid, summary

    vid, summary = _guard(run)
    return service.get_voucher(company_id, vid) | {"summary": summary}


class AgainstIn(BaseModel):
    bill_ref: str
    amount: str | float


class SettlementIn(BaseModel):
    vtype: Literal["Receipt", "Payment"]
    date: date
    party_id: int
    cash_bank_id: int
    amount: str | float
    against: list[AgainstIn] = []
    tds: str | float | None = None
    number: str | None = None
    narration: str = ""
    reference: str = ""


@router.post("/companies/{company_id}/vouchers/settlement", status_code=201)
def create_settlement(company_id: int, body: SettlementIn):
    _company(company_id)

    def run():
        with engine.begin() as conn:
            against = [{"bill_ref": a.bill_ref, "amount": to_paise(a.amount, "Bill amount")} for a in body.against]
            lines = service.settlement_lines(conn, company_id, body.vtype, body.party_id, body.cash_bank_id,
                                             to_paise(body.amount), against, to_paise(body.tds, "TDS"))
            return service.save_voucher(company_id, body.vtype, body.date, lines, number=body.number, narration=body.narration,
                                        reference=body.reference, conn=conn)

    return service.get_voucher(company_id, _guard(run))


class JewelItemIn(BaseModel):
    item: str | None = None
    purity: str | None = None
    tunch: float | None = Field(default=None, gt=0, le=100)
    gross: str | float | None = None  # grams
    diamond_ct: str | float | None = None
    stone_ct: str | float | None = None
    net: str | float | None = None  # grams; default gross - (diamond + stone ct) x 0.2
    fine: str | float | None = None  # grams; default net x tunch / 100
    pieces: int | None = Field(default=None, ge=0)
    tag_no: str | None = None
    diamond_value: str | float | None = None
    stone_value: str | float | None = None
    labour_rate: str | float | None = None  # rupees per gram of net weight
    labour_value: str | float | None = None
    metal_value: str | float | None = None
    settle: Literal["Wt", "Rs"] = "Wt"


class JewelleryInvoiceIn(BaseModel):
    vtype: Literal["Sales", "Purchase", "Credit Note", "Debit Note"]
    date: date
    number: str | None = Field(default=None, max_length=40)
    party_id: int
    metal: Metal = "gold"
    items: list[JewelItemIn] = Field(min_length=1)
    gst_rate: float = Field(default=3, ge=0, le=100)
    metal_rate: str | float | None = None  # rupees per fine gram, for items settled in rupees
    round_off: bool = True
    narration: str = ""
    reference: str = ""


@router.post("/companies/{company_id}/vouchers/jewellery", status_code=201)
def create_jewellery_invoice(company_id: int, body: JewelleryInvoiceIn):
    company = _company(company_id)

    def run():
        with engine.begin() as conn:
            lines, moved, summary = metal.jewellery_invoice(
                conn, company, body.vtype, body.party_id, body.metal, [i.model_dump() for i in body.items], body.gst_rate,
                body.round_off, to_paise(body.metal_rate, "Metal rate"))
            vid = service.save_voucher(company_id, body.vtype, body.date, lines, number=body.number, narration=body.narration,
                                       reference=body.reference, conn=conn, metal=moved)
        return vid, summary

    vid, summary = _guard(run)
    return service.get_voucher(company_id, vid) | {"summary": summary}


class MetalItemIn(BaseModel):
    item: str | None = None
    purity: str | None = None
    tunch: float | None = Field(default=None, gt=0, le=100)
    gross: str | float | None = None
    net: str | float | None = None
    fine: str | float | None = None


class MetalMoveIn(BaseModel):
    vtype: Literal["Metal Receipt", "Metal Issue"]
    date: date
    number: str | None = Field(default=None, max_length=40)
    party_id: int
    metal: Metal = "gold"
    items: list[MetalItemIn] = Field(min_length=1)
    narration: str = ""
    reference: str = ""


@router.post("/companies/{company_id}/vouchers/metal", status_code=201)
def create_metal_move(company_id: int, body: MetalMoveIn):
    _company(company_id)

    def run():
        with engine.begin() as conn:
            moved = metal.metal_transfer(conn, company_id, body.vtype, body.party_id, body.metal, [i.model_dump() for i in body.items])
            return service.save_voucher(company_id, body.vtype, body.date, [], number=body.number, narration=body.narration,
                                        reference=body.reference, conn=conn, metal=moved)

    return service.get_voucher(company_id, _guard(run))


class RateCutIn(BaseModel):
    date: date
    party_id: int
    metal: Metal = "gold"
    fine: str | float  # grams of fine metal to convert
    rate: str | float  # rupees per fine gram
    gst_rate: float = Field(default=3, ge=0, le=100)
    round_off: bool = True
    number: str | None = Field(default=None, max_length=40)
    narration: str = ""


@router.post("/companies/{company_id}/vouchers/rate-cut", status_code=201)
def create_rate_cut(company_id: int, body: RateCutIn):
    company = _company(company_id)

    def run():
        with engine.begin() as conn:
            fine = to_mg(body.fine, "Fine weight")
            rate = to_paise(body.rate, "Rate")
            vtype, lines, moved, summary = metal.rate_cut(conn, company, body.party_id, body.metal, fine, rate, body.gst_rate, body.round_off)
            narration = body.narration or f"Rate cut: {fine / 1000:,.3f} g fine {body.metal} @ {rate / 100:,.2f}/g"
            vid = service.save_voucher(company_id, vtype, body.date, lines, number=body.number, narration=narration,
                                       reference="Rate cut", conn=conn, metal=moved)
        return vid, summary

    vid, summary = _guard(run)
    return service.get_voucher(company_id, vid) | {"summary": summary}


@router.get("/companies/{company_id}/metal-balance/{party_id}")
def metal_balance(company_id: int, party_id: int):
    """Fine metal a party owes us (+) or we owe it (-), per metal, in grams."""
    _company(company_id)
    with engine.connect() as conn:
        balances = {name: metal.party_metal(conn, company_id, party_id, name) for name in chart.METALS}
    return {name: mg / 1000 for name, mg in balances.items() if mg}


@router.get("/companies/{company_id}/bills/{party_id}")
def pending_bills(company_id: int, party_id: int):
    """Open bills of a party (for receipts/payments against bills)."""
    _company(company_id)
    b, l, v = bill_allocations, voucher_lines, vouchers
    with engine.connect() as conn:
        frame = pd.read_sql(select(b.c.bill_ref, b.c.kind, b.c.amount_paise, b.c.bill_date)
                            .join(l, l.c.id == b.c.line_id).join(v, v.c.id == l.c.voucher_id)
                            .where(and_(v.c.company_id == company_id, v.c.cancelled.is_(False), b.c.ledger_id == party_id,
                                        b.c.kind.in_(["new", "against"]))), conn)
    out = []
    for ref, g in frame.groupby("bill_ref"):
        pending = int(g.amount_paise.sum())
        if pending:
            new = g[g.kind == "new"]
            out.append({"bill_ref": ref, "pending": pending / 100, "bill_date": str(new.bill_date.min()) if len(new) else None})
    return sorted(out, key=lambda r: r["bill_date"] or "")


@router.get("/companies/{company_id}/audit")
def audit(company_id: int, limit: int = Query(200, ge=1, le=2000)):
    _company(company_id)
    return service.audit_trail(company_id, limit)


# --- Imports ---------------------------------------------------------------------------------------------


class RegisterImport(BaseModel):
    dataset_id: int
    table_name: str
    register_type: Literal["sales", "purchases"]  # "register" would shadow a BaseModel attribute


class BookImport(BaseModel):
    book_id: int


class BankImport(BaseModel):
    dataset_id: int
    table_name: str
    bank_ledger_id: int


def _sheet(dataset_id: int, table_name: str) -> dict:
    dataset = database.get_dataset(dataset_id)
    sheet = next((s for s in (dataset or {}).get("sheets", []) if s["table_name"] == table_name), None)
    if sheet is None:
        raise HTTPException(status_code=404, detail="Sheet not found.")
    return sheet


@router.post("/companies/{company_id}/import/register")
def import_register(company_id: int, body: RegisterImport):
    _company(company_id)
    result = _guard(imports.import_register, company_id, _sheet(body.dataset_id, body.table_name), body.register_type)
    if result["created"] or result["skipped"]:  # in the books now: the upload is filed under this register
        cloud.set_register(body.dataset_id, body.register_type)
    return result


@router.post("/companies/{company_id}/import/book")
def import_book(company_id: int, body: BookImport):
    _company(company_id)
    book = database.get_book(body.book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Sales + purchases set not found.")
    total: dict[str, Any] = {"created": 0, "skipped": 0, "problems": [], "notes": []}
    for sheet in book["sheets"]:
        if sheet["register"] in ("sales", "purchases"):
            result = _guard(imports.import_register, company_id, sheet, sheet["register"])
            total["created"] += result["created"]
            total["skipped"] += result["skipped"]
            total["problems"] += [f"{sheet['sheet_name']}: {p}" for p in result["problems"]]
            total["notes"] += result["notes"]
    return total


@router.post("/companies/{company_id}/import/bank")
def import_bank(company_id: int, body: BankImport):
    _company(company_id)
    return _guard(imports.import_bank_statement, company_id, body.bank_ledger_id, _sheet(body.dataset_id, body.table_name))


# --- Reports ---------------------------------------------------------------------------------------------

REPORT_KINDS = {
    "dashboard": "Dashboard",
    "day_book": "Day book",
    "ledger": "Ledger",
    "cash_bank_book": "Cash / bank book",
    "trial_balance": "Trial balance",
    "profit_and_loss": "Profit & loss",
    "balance_sheet": "Balance sheet",
    "receivables": "Receivables",
    "payables": "Payables",
    "gstr1": "GSTR-1",
    "gstr3b": "GSTR-3B",
    "bank_reconciliation": "Bank reconciliation",
    "metal_balances": "Gold balances",
    "metal_ledger": "Gold ledger",
    "stock_grams": "Stock in grams",
}


@router.get("/companies/{company_id}/reports")
def report_kinds(company_id: int):
    _company(company_id)
    return REPORT_KINDS


@router.get("/companies/{company_id}/reports/{kind}")
def report(company_id: int, kind: str, ledger_id: int | None = None, start: date | None = None, end: date | None = None,
           as_of: date | None = None, opening_stock: float | None = None, closing_stock: float = 0.0, vtype: str | None = None,
           metal_name: Metal = Query("gold", alias="metal"), rate: float | None = Query(None, gt=0)):
    company = _company(company_id)
    builders = {
        "dashboard": lambda: reports.dashboard(company),
        "day_book": lambda: reports.day_book(company, start, end, vtype),
        "ledger": lambda: reports.ledger_report(company, ledger_id, start, end),
        "cash_bank_book": lambda: reports.ledger_report(company, ledger_id, start, end, cash_bank_only=True),
        "trial_balance": lambda: reports.trial_balance(company, start, end),
        "profit_and_loss": lambda: reports.profit_and_loss(company, start, end, opening_stock, closing_stock),
        "balance_sheet": lambda: reports.balance_sheet(company, end or as_of, opening_stock, closing_stock),
        "receivables": lambda: reports.outstanding(company, "receivable", as_of or end),
        "payables": lambda: reports.outstanding(company, "payable", as_of or end),
        "gstr1": lambda: reports.gstr1(company, start, end),
        "gstr3b": lambda: reports.gstr3b(company, start, end),
        "bank_reconciliation": lambda: reports.bank_reconciliation(company, ledger_id, as_of or end),
        "metal_balances": lambda: metal.metal_balances(company, metal_name, as_of or end, rate),
        "metal_ledger": lambda: metal.metal_ledger(company, ledger_id, metal_name, start, end),
        "stock_grams": lambda: metal.stock_grams(company, metal_name, start, end),
    }
    if kind not in builders:
        raise HTTPException(status_code=404, detail="Unknown report.")
    return _guard(builders[kind])
