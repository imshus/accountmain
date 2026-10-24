"""Reports from the double-entry books. All amounts are whole paise; every report carries its proof.

Balances follow Tally for every account: balance = opening + debits - credits, shown with "Dr"
(positive) or "Cr" (negative). The trial balance tallies whenever opening balances tally,
because every voucher's debits equal its credits.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import and_, func, select

from .. import gst
from ..compat import to_datetime
from ..database import engine
from ..formatting import indian
from ..reports import AGEING_BUCKETS, _col, _report, gst_net_payable
from . import chart, service
from .db import bank_lines, bill_allocations, ledgers, voucher_lines, vouchers


def _r(paise) -> float:
    return int(paise) / 100


def _fmt(paise) -> str:
    return indian(int(paise) / 100)


def _drcr(paise) -> str:
    paise = int(paise)
    return "0.00" if paise == 0 else f"{indian(abs(paise) / 100)} {'Dr' if paise > 0 else 'Cr'}"


def _period(company: dict, start: date | None, end: date | None) -> tuple[date, date]:
    start = start or company["fy_start"]
    return start, end or date(2100, 12, 31)


def _latest_voucher_date(company_id: int) -> date | None:
    with engine.connect() as conn:
        return conn.execute(select(func.max(vouchers.c.date)).where(and_(
            vouchers.c.company_id == company_id, vouchers.c.cancelled.is_(False)))).scalar()


def _year_start(company: dict, day: date) -> date:
    """First day of the financial year containing ``day``, but never before the books begin."""
    return max(service.fy_of(day)[0], company["fy_start"])


def _fy_period(company: dict, start: date | None, end: date | None) -> tuple[date, date]:
    """The period asked for. With no dates, the financial year of the latest voucher (or of today when there are none),
    so period reports never run across years; with only an end date, from the start of that date's financial year."""
    if start is not None:
        return start, end or date(2100, 12, 31)
    if end is not None:
        return _year_start(company, end), end
    anchor = max(_latest_voucher_date(company["id"]) or date.today(), company["fy_start"])
    return _year_start(company, anchor), service.fy_of(anchor)[1]


def _period_text(start: date, end: date) -> str:
    return f"{start:%d %b %Y} to {end:%d %b %Y}" if end.year < 2100 else f"from {start:%d %b %Y}"


def entries(company_id: int, until: date | None = None) -> pd.DataFrame:
    """Every line of every live voucher, with its voucher's details."""
    v, l = vouchers, voucher_lines
    query = (
        select(v.c.id.label("voucher_id"), v.c.vtype, v.c.number, v.c.date, v.c.narration, v.c.reference,
               l.c.id.label("line_id"), l.c.position, l.c.ledger_id, l.c.dr_paise.label("dr"), l.c.cr_paise.label("cr"))
        .join(v, v.c.id == l.c.voucher_id)
        .where(and_(v.c.company_id == company_id, v.c.cancelled.is_(False)))
    )
    if until:
        query = query.where(v.c.date <= until)
    with engine.connect() as conn:
        frame = pd.read_sql(query, conn)
    frame["date"] = to_datetime(frame["date"]).dt.date
    for col in ("dr", "cr"):
        frame[col] = frame[col].astype("int64")
    return frame


def ledger_frame(company_id: int) -> pd.DataFrame:
    frame = pd.DataFrame(service.list_ledgers(company_id))
    frame["primary"] = frame.group_name.map(chart.primary)
    frame["nature"] = frame.group_name.map(chart.nature)
    frame["statement"] = frame.group_name.map(chart.statement)
    return frame.set_index("id")


PL_BROUGHT_FORWARD = -1  # row id of the "Profit & Loss A/c" line (earlier years' profit) in balances()


def balances(company: dict, start: date, end: date, extra_brought_forward: int = 0) -> pd.DataFrame:
    """Per ledger: opening at ``start``, debits and credits in the period, closing at ``end`` (paise).

    As in Tally, income and expense ledgers start each financial year at zero: their opening is only the
    movement since the start of the financial year containing ``start``. Everything they moved in earlier
    years is carried into one "Profit & Loss A/c" row (id PL_BROUGHT_FORWARD) under Capital Account, so
    the closing balances still add up to the opening-balance difference (nil when openings tally).
    ``extra_brought_forward`` (+ = Dr) is added to that row: the balance sheet passes earlier years' stock change.
    Column ``earlier`` holds each P&L ledger's share of that row (0 for balance-sheet ledgers).
    """
    led = ledger_frame(company["id"])
    lines = entries(company["id"], end)
    before = lines[lines.date < start]
    inside = lines[lines.date >= start]
    year_start = service.fy_of(start)[0]
    this_year = before[before.date >= year_start]
    out = led[["name", "group_name", "primary", "nature", "statement", "tax_kind", "gstin", "state_code"]].copy()
    moved_before = (before.dr - before.cr).groupby(before.ledger_id).sum().reindex(out.index).fillna(0)
    moved_this_year = (this_year.dr - this_year.cr).groupby(this_year.ledger_id).sum().reindex(out.index).fillna(0)
    is_pl = out.statement == "pl"
    # Opening balances are as at the books-start day. New P&L openings are refused, but older books may have
    # some: they count as the day before the books begin, i.e. this year's if the books began mid-year.
    opening_this_year = company["fy_start"] - timedelta(days=1) >= year_start
    pl_opening = led.opening_paise if opening_this_year else 0
    out["opening"] = np.where(is_pl, moved_this_year + pl_opening, led.opening_paise + moved_before).astype("int64")
    out["dr"] = inside.groupby("ledger_id").dr.sum().reindex(out.index).fillna(0).astype("int64")
    out["cr"] = inside.groupby("ledger_id").cr.sum().reindex(out.index).fillna(0).astype("int64")
    # Per P&L ledger, what it moved in earlier years: the part carried into the brought-forward row.
    out["earlier"] = np.where(is_pl, moved_before - moved_this_year + (0 if opening_this_year else led.opening_paise), 0).astype("int64")
    earlier = int(out.earlier.sum()) + extra_brought_forward
    if earlier:
        carried = pd.DataFrame([{"name": "Profit & Loss A/c (brought forward)", "group_name": "Capital Account", "primary": "Capital Account",
                                 "nature": "liability", "statement": "bs", "tax_kind": None, "gstin": None, "state_code": None,
                                 "opening": earlier, "dr": 0, "cr": 0, "earlier": 0}], index=pd.Index([PL_BROUGHT_FORWARD], name=out.index.name))
        out = pd.concat([out, carried])
        for col in ("opening", "dr", "cr", "earlier"):
            out[col] = out[col].astype("int64")
    out["closing"] = out.opening + out.dr - out.cr
    return out


# --- Day book and ledgers ---------------------------------------------------------------------------


def day_book(company: dict, start: date | None, end: date | None, vtype: str | None = None) -> dict:
    start, end = _period(company, start, end)
    lines = entries(company["id"], end)
    lines = lines[lines.date >= start]
    if vtype:
        lines = lines[lines.vtype == vtype]
    names = ledger_frame(company["id"]).name
    rows = []
    for vid, group in lines.sort_values(["date", "voucher_id", "position"]).groupby("voucher_id", sort=False):
        head = group.iloc[0]
        dr = [names[i] for i in group[group.dr > 0].ledger_id]
        cr = [names[i] for i in group[group.cr > 0].ledger_id]
        rows.append({"date": head.date.isoformat(), "type": head.vtype, "number": head.number,
                     "debit_ledgers": ", ".join(dr), "credit_ledgers": ", ".join(cr),
                     "amount": _r(group.dr.sum()), "narration": head.narration or "", "voucher_id": int(vid)})
    total = int(lines.dr.sum())
    report = _report(f"Day book ({_period_text(start, end)})", {}, cards=[
        {"label": "Vouchers", "value": len(rows), "format": "count"},
        {"label": "Total debits = credits", "value": _r(total), "format": "money"},
    ], tables=[{
        "title": None,
        "columns": [_col("date", "Date", "date"), _col("type", "Type", "text"), _col("number", "No.", "text"),
                    _col("debit_ledgers", "Debit", "text"), _col("credit_ledgers", "Credit", "text"),
                    _col("amount", "Amount", "money"), _col("narration", "Narration", "text")],
        "rows": rows,
        "total": {"date": "Total", "amount": _r(total)},
    }], options={"voucher_types": chart.VOUCHER_TYPES})
    ok = int(lines.dr.sum()) == int(lines.cr.sum())
    report["checks"].append({"level": "ok" if ok else "warning",
                             "message": f"Total debits {_fmt(lines.dr.sum())} {'=' if ok else '≠'} total credits {_fmt(lines.cr.sum())}."})
    return report


def ledger_report(company: dict, ledger_id: int | None, start: date | None, end: date | None, cash_bank_only: bool = False) -> dict:
    asked_start, asked_end = start, end
    start, end = _period(company, start, end)
    led = ledger_frame(company["id"])
    choices = led[led.group_name.isin(chart.CASH_BANK)] if cash_bank_only else led
    options = {"ledgers": [{"id": int(i), "name": r["name"], "group": r.group_name} for i, r in choices.sort_values("name").iterrows()]}
    title = "Cash / bank book" if cash_bank_only else "Ledger"
    if not ledger_id:
        report = _report(title, {}, options=options)
        report["checks"].append({"level": "info", "message": f"Choose a {'cash or bank ' if cash_bank_only else ''}ledger."})
        return report
    if ledger_id not in led.index:
        raise service.AccountsError("Ledger not found.")
    pl_ledger = chart.statement(led.group_name[ledger_id]) == "pl"
    if pl_ledger and asked_start is None:
        # Income and expense ledgers start each financial year at zero: with no start date show one year, as the trial balance does.
        start, end = _fy_period(company, None, asked_end)
    bal = balances(company, start, end).loc[ledger_id]
    lines = entries(company["id"], end)
    own = lines[(lines.ledger_id == ledger_id) & (lines.date >= start)].sort_values(["date", "voucher_id", "position"])
    others = lines[lines.voucher_id.isin(own.voucher_id) & (lines.ledger_id != ledger_id)]
    other_names = others.groupby("voucher_id").ledger_id.apply(lambda ids: [led.name[i] for i in ids])
    running = int(bal.opening) + np.cumsum((own.dr - own.cr).to_numpy())
    rows = [{"particulars": "Opening balance", "balance": _r(bal.opening), "_kind": "opening"}]
    for (_, line), run in zip(own.iterrows(), running):
        names = other_names.get(line.voucher_id, [])
        particulars = names[0] if len(names) == 1 else (f"{names[0]} (+{len(names) - 1} more)" if names else "")
        rows.append({"date": line.date.isoformat(), "particulars": particulars, "type": line.vtype, "number": line.number,
                     "debit": _r(line.dr) or None, "credit": _r(line.cr) or None, "balance": _r(run)})
    closing = int(bal.closing)
    report = _report(f"{title}: {led.name[ledger_id]} ({led.group_name[ledger_id]})", {}, options=options, cards=[
        {"label": "Opening", "value": _r(bal.opening), "format": "drcr"},
        {"label": "Debits", "value": _r(bal.dr), "format": "money"},
        {"label": "Credits", "value": _r(bal.cr), "format": "money"},
        {"label": "Closing", "value": _r(closing), "format": "drcr"},
    ], tables=[{
        "title": None,
        "columns": [_col("date", "Date", "date"), _col("particulars", "Particulars", "text"), _col("type", "Type", "text"),
                    _col("number", "No.", "text"), _col("debit", "Debit", "money"), _col("credit", "Credit", "money"),
                    _col("balance", "Balance", "drcr")],
        "rows": rows,
        "total": {"particulars": "Total / closing", "debit": _r(bal.dr), "credit": _r(bal.cr), "balance": _r(closing)},
    }])
    ok = int(bal.opening) + int(bal.dr) - int(bal.cr) == closing == (int(running[-1]) if len(running) else int(bal.opening))
    report["checks"].append({"level": "ok" if ok else "warning",
                             "message": f"Opening {_drcr(bal.opening)} + debits {_fmt(bal.dr)} − credits {_fmt(bal.cr)} = closing {_drcr(closing)}."})
    nature = chart.nature(led.group_name[ledger_id])
    if (nature in ("asset", "expense") and closing < 0) or (nature in ("liability", "income") and closing > 0):
        side = "Cr" if closing < 0 else "Dr"
        hint = {"Cash-in-Hand": "Cash cannot be negative: an entry is missing or wrong.",
                "Sundry Debtors": "A Cr balance on a customer means an advance received.",
                "Sundry Creditors": "A Dr balance on a supplier means an advance paid."}.get(led.group_name[ledger_id], "")
        report["checks"].append({"level": "warning" if led.group_name[ledger_id] == "Cash-in-Hand" else "info",
                                 "message": f"Unusual {side} balance for a {led.group_name[ledger_id]} ledger. {hint}".strip()})
    if pl_ledger and asked_start is None:
        report["checks"].append({"level": "info", "message": f"Income and expense ledgers start each financial year at zero, so this shows "
                                 f"{_period_text(start, end)}. Choose dates to see another year."})
    elif pl_ledger and (own.date > service.fy_of(start)[1]).any():
        report["checks"].append({"level": "info", "message": f"This period runs past the year end ({service.fy_of(start)[1]:%d %b %Y}), so the "
                                 "balance adds up more than one financial year. Choose dates within one year to see that year's balance."})
    return report


# --- Trial balance, P&L, balance sheet ----------------------------------------------------------------


def trial_balance(company: dict, start: date | None, end: date | None) -> dict:
    start, end = _fy_period(company, start, end)
    bal = balances(company, start, end)
    bal = bal[(bal.opening != 0) | (bal.dr != 0) | (bal.cr != 0)]
    rows = []
    order = list(chart.GROUPS)
    for primary_group in sorted(bal.primary.unique(), key=lambda g: order.index(g) if g in order else 99):
        part = bal[bal.primary == primary_group]
        net = int(part.closing.sum())
        rows.append({"account": primary_group, "closing_dr": _r(net) if net > 0 else None, "closing_cr": _r(-net) if net < 0 else None,
                     "debit": _r(part.dr.sum()), "credit": _r(part.cr.sum()), "_kind": "group"})
        for lid, r in part.sort_values(["group_name", "name"]).iterrows():
            rows.append({"account": f"  {r['name']}" + (f" ({r.group_name})" if r.group_name != primary_group else ""),
                         "opening": _r(r.opening), "debit": _r(r.dr), "credit": _r(r.cr),
                         "closing_dr": _r(r.closing) if r.closing > 0 else None, "closing_cr": _r(-r.closing) if r.closing < 0 else None,
                         **({"ledger_id": int(lid)} if lid != PL_BROUGHT_FORWARD else {})})
    total_dr = int(bal.closing[bal.closing > 0].sum())
    total_cr = int(-bal.closing[bal.closing < 0].sum())
    opening_diff = int(ledger_frame(company["id"]).opening_paise.sum())
    if opening_diff:
        rows.append({"account": "Difference in opening balances", "closing_dr": _r(-opening_diff) if opening_diff < 0 else None,
                     "closing_cr": _r(opening_diff) if opening_diff > 0 else None, "_kind": "group"})
    tally_dr = total_dr + (-opening_diff if opening_diff < 0 else 0)
    tally_cr = total_cr + (opening_diff if opening_diff > 0 else 0)
    report = _report(f"Trial balance ({_period_text(start, end)})", {}, cards=[
        {"label": "Total Dr", "value": _r(tally_dr), "format": "money"},
        {"label": "Total Cr", "value": _r(tally_cr), "format": "money"},
        {"label": "Difference", "value": _r(tally_dr - tally_cr), "format": "money", "hint": "Tallied" if tally_dr == tally_cr else None},
    ], tables=[{
        "title": None,
        "columns": [_col("account", "Particulars", "text"), _col("opening", "Opening", "drcr"), _col("debit", "Debit", "money"),
                    _col("credit", "Credit", "money"), _col("closing_dr", "Closing Dr", "money"), _col("closing_cr", "Closing Cr", "money")],
        "rows": rows,
        "total": {"account": "Grand total", "debit": _r(bal.dr.sum()), "credit": _r(bal.cr.sum()), "closing_dr": _r(tally_dr), "closing_cr": _r(tally_cr)},
    }])
    report["checks"].append({"level": "ok" if bal.dr.sum() == bal.cr.sum() else "warning",
                             "message": f"Every voucher balances: period debits {_fmt(bal.dr.sum())} = credits {_fmt(bal.cr.sum())}."})
    if opening_diff:
        report["checks"].append({"level": "warning", "message": f"Opening balances do not tally (difference {_drcr(opening_diff)}). "
                                 "Fix the ledger opening balances; the difference is shown as a separate line, as Tally does."})
    if tally_dr != tally_cr:
        report["checks"].append({"level": "warning", "message": f"The trial balance does not tally: Dr {_fmt(tally_dr)} ≠ Cr {_fmt(tally_cr)} "
                                 f"(difference {_fmt(abs(tally_dr - tally_cr))}). Check the opening balances under Ledgers and any "
                                 "vouchers dated before the books begin."})
    elif not opening_diff:
        report["checks"].append({"level": "ok", "message": f"The trial balance tallies: Dr {_fmt(tally_dr)} = Cr {_fmt(tally_cr)}."})
    if (bal.index == PL_BROUGHT_FORWARD).any():
        carried = int(bal.closing[PL_BROUGHT_FORWARD])
        report["checks"].append({"level": "info", "message": f"Profit & Loss A/c {_drcr(carried)}: {'profit' if carried <= 0 else 'loss'} of the years "
                                 f"before {service.fy_of(start)[0]:%d %b %Y}, brought forward into Capital (income and expense ledgers start each year "
                                 "at zero)."})
    suspense = bal[bal.group_name == "Suspense A/c"]
    if suspense.closing.any():
        report["checks"].append({"level": "warning", "message": f"Suspense A/c holds {_drcr(suspense.closing.sum())}: unexplained differences to clear."})
    return report


def _pl_figures(bal: pd.DataFrame, opening_stock: int | None, closing_stock: int) -> dict:
    by_group = bal.groupby("primary").closing.sum()
    get = lambda g: int(by_group.get(g, 0))  # noqa: E731
    stock_ledgers = int(bal[bal.group_name == "Stock-in-Hand"].opening.sum())
    open_stock = stock_ledgers if opening_stock is None else opening_stock
    figures = {
        "sales": -get("Sales Accounts"), "direct_inc": -get("Direct Incomes"), "purchases": get("Purchase Accounts"),
        "direct_exp": get("Direct Expenses"), "indirect_inc": -get("Indirect Incomes"), "indirect_exp": get("Indirect Expenses"),
        "opening_stock": open_stock, "closing_stock": closing_stock,
    }
    figures["gross"] = (figures["sales"] + figures["direct_inc"] + closing_stock) - (open_stock + figures["purchases"] + figures["direct_exp"])
    figures["net"] = figures["gross"] + figures["indirect_inc"] - figures["indirect_exp"]
    return figures


def _stock_paise(opening_stock: float | None, closing_stock: float) -> tuple[int | None, int]:
    open_p = None if opening_stock is None else service.to_paise(opening_stock, "Opening stock")
    return open_p, service.to_paise(closing_stock or 0, "Closing stock")


def _opening_stock_check(company: dict, start: date, opening_stock: int | None, f: dict, effect: str) -> dict | None:
    """Without an opening stock entered, a period after the books begin uses the books-start stock, which is wrong
    once a year has closed: a year's opening stock is the previous year's closing stock."""
    if opening_stock is not None or start <= company["fy_start"] or not (f["opening_stock"] or f["closing_stock"]):
        return None
    return {"level": "warning", "message": f"Opening stock {_fmt(f['opening_stock'])} is the Stock-in-Hand balance from the books (stock on "
            f"{company['fy_start']:%d %b %Y}, when the books begin), not the stock in hand on {start - timedelta(days=1):%d %b %Y}. "
            f"Enter the previous period's closing stock in Opening stock; until then {effect}."}


def profit_and_loss(company: dict, start: date | None, end: date | None, opening_stock: float | None, closing_stock: float) -> dict:
    start, end = _fy_period(company, start, end)
    bal = balances(company, start, end)
    if start > _year_start(company, start):
        # A period inside a financial year shows only its own income and expenses, not the year to date
        # that balances() carries in the opening of P&L ledgers.
        bal = bal.assign(closing=np.where(bal.statement == "pl", bal.dr - bal.cr, bal.closing))
    open_p, close_p = _stock_paise(opening_stock, closing_stock)
    f = _pl_figures(bal, open_p, close_p)

    def detail(primary_group: str, sign: int) -> list[dict]:
        part = bal[(bal.primary == primary_group) & (bal.closing != 0)].sort_values("name")
        return [{"item": f"  {r['name']}", "amount": _r(sign * r.closing)} for _, r in part.iterrows()]

    rows = [
        {"item": "TRADING ACCOUNT", "_kind": "heading"},
        {"item": "Sales", "amount": _r(f["sales"]), "_kind": "group"}, *detail("Sales Accounts", -1),
        {"item": "Direct incomes", "amount": _r(f["direct_inc"]), "_kind": "group"}, *detail("Direct Incomes", -1),
        {"item": "Closing stock", "amount": _r(f["closing_stock"]), "_kind": "group"},
        {"item": "Less: Opening stock", "amount": _r(-f["opening_stock"]), "_kind": "group"},
        {"item": "Less: Purchases", "amount": _r(-f["purchases"]), "_kind": "group"}, *detail("Purchase Accounts", -1),
        {"item": "Less: Direct expenses", "amount": _r(-f["direct_exp"]), "_kind": "group"}, *detail("Direct Expenses", -1),
        {"item": "Gross profit" if f["gross"] >= 0 else "Gross loss", "amount": _r(f["gross"]), "_kind": "total"},
        {"item": "PROFIT & LOSS ACCOUNT", "_kind": "heading"},
        {"item": "Add: Indirect incomes", "amount": _r(f["indirect_inc"]), "_kind": "group"}, *detail("Indirect Incomes", -1),
        {"item": "Less: Indirect expenses", "amount": _r(-f["indirect_exp"]), "_kind": "group"}, *detail("Indirect Expenses", -1),
        {"item": "Net profit" if f["net"] >= 0 else "Net loss", "amount": _r(f["net"]), "_kind": "total"},
    ]
    report = _report(f"Profit & loss ({_period_text(start, end)})", {}, cards=[
        {"label": "Sales", "value": _r(f["sales"]), "format": "money"},
        {"label": "Gross profit" if f["gross"] >= 0 else "Gross loss", "value": _r(f["gross"]), "format": "money"},
        {"label": "Net profit" if f["net"] >= 0 else "Net loss", "value": _r(f["net"]), "format": "money"},
        {"label": "Net margin", "value": round(f["net"] / f["sales"], 6) if f["sales"] else 0, "format": "percent"},
    ], tables=[{"title": None, "columns": [_col("item", "Particulars", "text"), _col("amount", "Amount", "money")], "rows": rows, "total": None}])
    pl_total = -int(bal[bal.statement == "pl"].closing.sum())
    ok = pl_total + f["closing_stock"] - f["opening_stock"] == f["net"]
    report["checks"].append({"level": "ok" if ok else "warning",
                             "message": f"Check: income − expenses of all P&L ledgers ({_fmt(pl_total)}) + stock change "
                             f"({_fmt(f['closing_stock'] - f['opening_stock'])}) = net {'profit' if f['net'] >= 0 else 'loss'} ({_fmt(f['net'])})."})
    if not closing_stock:
        report["checks"].append({"level": "info", "message": "Closing stock is 0. Enter the value of goods in hand at the period end (from the Stock summary or a physical count)."})
    stock_check = _opening_stock_check(company, start, open_p, f, "the gross and net profit are off by the difference")
    if stock_check:
        report["checks"].append(stock_check)
    report["checks"].append({"level": "info", "message": "GST ledgers are in Duties & Taxes (balance sheet), so tax never inflates sales or costs."})
    return report


_BS_LIAB = ["Capital Account", "Loans (Liability)", "Current Liabilities", "Branch / Divisions", "Suspense A/c"]
_BS_ASSET = ["Fixed Assets", "Investments", "Current Assets", "Misc. Expenses (ASSET)"]


def balance_sheet(company: dict, end: date | None, opening_stock: float | None, closing_stock: float) -> dict:
    # Current-year profit from the start of the financial year containing the balance sheet date; earlier
    # years' profit comes in through the "Profit & Loss A/c" row of balances().
    start = _fy_period(company, None, end)[0]
    end = end or date(2100, 12, 31)
    bal = balances(company, start, end)
    open_p, close_p = _stock_paise(opening_stock, closing_stock)
    if open_p is not None and start > company["fy_start"]:
        # This year's opening stock less the books' stock is the stock change of the earlier years: their profit,
        # so it belongs in the brought-forward line, not in this year's profit.
        earlier_stock_gain = open_p - int(bal[bal.group_name == "Stock-in-Hand"].opening.sum())
        bal = balances(company, start, end, extra_brought_forward=-earlier_stock_gain)
    f = _pl_figures(bal, open_p, close_p)
    bs = bal[(bal.statement == "bs") & (bal.group_name != "Stock-in-Hand")]
    opening_diff = int(ledger_frame(company["id"]).opening_paise.sum())

    rows, totals = [], {}
    for side, groups, sign in (("Liabilities", _BS_LIAB, -1), ("Assets", _BS_ASSET, 1)):
        rows.append({"item": side.upper(), "_kind": "heading"})
        total = 0
        for g in groups:
            part = bs[bs.primary == g]
            amount = sign * int(part.closing.sum())
            if g == "Capital Account":
                amount += f["net"]
            if g == "Current Assets":
                amount += f["closing_stock"]
            if not amount and part.closing.eq(0).all() and not (g == "Capital Account" and f["net"]):
                continue
            total += amount
            rows.append({"item": g, "amount": _r(amount), "_kind": "group"})
            for sub, members in part.groupby("group_name"):
                if sub != g:
                    rows.append({"item": f"  {sub}", "amount": _r(sign * members.closing.sum())})
                rows += [{"item": f"    {r['name']}", "amount": _r(sign * r.closing)} for _, r in members.sort_values("name").iterrows() if r.closing]
            if g == "Capital Account":
                rows.append({"item": "  Profit & loss (current period)", "amount": _r(f["net"])})
            if g == "Current Assets" and f["closing_stock"]:
                rows.append({"item": "  Closing stock", "amount": _r(f["closing_stock"])})
        if side == "Liabilities" and opening_diff:
            rows.append({"item": "Difference in opening balances", "amount": _r(opening_diff), "_kind": "group"})
            total += opening_diff
        rows.append({"item": f"Total {side.lower()}", "amount": _r(total), "_kind": "total"})
        totals[side] = total
    diff = totals["Assets"] - totals["Liabilities"]
    report = _report(f"Balance sheet as on {end:%d %b %Y}" if end.year < 2100 else "Balance sheet (latest)", {}, cards=[
        {"label": "Total assets", "value": _r(totals["Assets"]), "format": "money"},
        {"label": "Total liabilities & capital", "value": _r(totals["Liabilities"]), "format": "money"},
        {"label": "Difference", "value": _r(diff), "format": "money", "hint": "Tallied" if diff == 0 else None},
    ], tables=[{"title": None, "columns": [_col("item", "Particulars", "text"), _col("amount", "Amount", "money")], "rows": rows, "total": None}])
    if diff == 0:
        report["checks"].append({"level": "ok", "message": "Assets = liabilities + capital + profit. The balance sheet tallies."})
    else:
        report["checks"].append({"level": "warning", "message": f"The balance sheet differs by {_fmt(abs(diff))}. Check stock ledgers that have entries during the period, or opening balances."})
    stock_check = _opening_stock_check(company, start, open_p, f, "the totals are right but profit is split wrongly between "
                                       "this year and the Profit & Loss A/c brought forward")
    if stock_check:
        report["checks"].append(stock_check)
    return report


# --- Bill-wise outstanding ---------------------------------------------------------------------------


def outstanding(company: dict, kind: str, as_of: date | None) -> dict:
    """Receivables (kind='receivable', Sundry Debtors) or payables ('payable', Sundry Creditors), bill by bill."""
    as_of = as_of or date.today()
    group = "Sundry Debtors" if kind == "receivable" else "Sundry Creditors"
    sign = 1 if kind == "receivable" else -1  # receivables are Dr (+), payables Cr (-)
    led = ledger_frame(company["id"])
    parties = led[led.group_name == group]
    b, l, v = bill_allocations, voucher_lines, vouchers
    with engine.connect() as conn:
        bills = pd.read_sql(
            select(b.c.ledger_id, b.c.kind, b.c.bill_ref, b.c.amount_paise.label("amount"), b.c.bill_date, b.c.due_date, v.c.vtype, v.c.number)
            .join(l, l.c.id == b.c.line_id).join(v, v.c.id == l.c.voucher_id)
            .where(and_(v.c.company_id == company["id"], v.c.cancelled.is_(False), v.c.date <= as_of, b.c.ledger_id.in_(parties.index.tolist()))),
            conn,
        )
    rows, party_rows, total_pending, total_on_account, total_opening = [], [], 0, 0, 0
    labels = [f"{lo}-{hi} days" if hi else f"Over {lo - 1} days" for lo, hi in AGEING_BUCKETS]
    bucket_totals = {lab: 0 for lab in ["Not due", *labels]}
    for lid, p in parties.iterrows():
        mine = bills[bills.ledger_id == lid]
        refs = mine[mine.kind.isin(["new", "against"])].groupby("bill_ref", dropna=False)
        party_pending = 0
        for ref, g in refs:
            pending = int(g.amount.sum()) * sign
            if pending == 0:
                continue
            new = g[g.kind == "new"]
            bill_date = to_datetime(new.bill_date).min() if len(new) else to_datetime(g.bill_date).min()
            due = to_datetime(new.due_date).max() if len(new) and new.due_date.notna().any() else bill_date
            overdue = (pd.Timestamp(as_of) - due).days if pd.notna(due) else None
            bucket = "Not due" if overdue is not None and overdue < 0 else next(
                (lab for (lo, hi), lab in zip(AGEING_BUCKETS, labels) if overdue is not None and overdue >= lo and (hi is None or overdue <= hi)), labels[-1])
            bucket_totals[bucket] += pending
            rows.append({"party": p["name"], "bill": ref if isinstance(ref, str) else "(no ref)",
                         "bill_date": None if pd.isna(bill_date) else bill_date.date().isoformat(),
                         "due_date": None if pd.isna(due) else due.date().isoformat(),
                         "billed": _r(int(new.amount.sum()) * sign) if len(new) else None, "pending": _r(pending),
                         "overdue": overdue if overdue is not None and overdue > 0 else None, "bucket": bucket})
            party_pending += pending
        on_account = int(mine[mine.kind.isin(["on_account", "advance"])].amount.sum()) * sign
        opening = int(p.opening_paise) * sign
        balance = party_pending + on_account + opening
        if party_pending or on_account or opening:
            party_rows.append({"party": p["name"], "bills": _r(party_pending), "on_account": _r(on_account) or None,
                               "opening": _r(opening) or None, "net": _r(balance)})
        total_pending += balance
        total_on_account += on_account
        total_opening += opening
    # Proof: bill-wise totals = party ledger balances.
    bal = balances(company, company["fy_start"], as_of)
    ledger_total = int(bal[bal.group_name == group].closing.sum()) * sign
    title = "Receivables (amounts customers owe you)" if kind == "receivable" else "Payables (amounts you owe suppliers)"
    report = _report(f"{title} as on {as_of:%d %b %Y}", {}, cards=[
        {"label": "Total outstanding", "value": _r(total_pending), "format": "money"},
        *[{"label": lab, "value": _r(v), "format": "money"} for lab, v in bucket_totals.items() if v],
        # Unadjusted advances and opening balances are not bills, so they sit outside the age buckets;
        # buckets + these = total outstanding.
        *([{"label": "Advances / on account (unadjusted)", "value": _r(total_on_account), "format": "money"}] if total_on_account else []),
        *([{"label": "Opening (not bill-wise)", "value": _r(total_opening), "format": "money"}] if total_opening else []),
    ], tables=[
        {"title": "By party", "columns": [_col("party", "Party", "text"), _col("bills", "Pending bills", "money"),
                                          _col("on_account", "On account / advance", "money"), _col("opening", "Opening (not bill-wise)", "money"),
                                          _col("net", "Net outstanding", "money")],
         "rows": sorted(party_rows, key=lambda r: -r["net"]), "total": {"party": "Total", "net": _r(total_pending)}},
        {"title": "Bill by bill", "columns": [_col("party", "Party", "text"), _col("bill", "Bill", "text"), _col("bill_date", "Bill date", "date"),
                                              _col("due_date", "Due", "date"), _col("billed", "Billed", "money"), _col("pending", "Pending", "money"),
                                              _col("overdue", "Days overdue", "count"), _col("bucket", "Age", "text")],
         "rows": sorted(rows, key=lambda r: (r["party"], r["bill_date"] or "")), "total": None},
    ])
    ok = ledger_total == total_pending
    report["checks"].append({"level": "ok" if ok else "warning",
                             "message": f"Bill-wise outstanding {_fmt(total_pending)} {'=' if ok else '≠'} {group} ledger balances {_fmt(ledger_total)}."})
    report["checks"].append({"level": "info", "message": "Aged by due date (bill date + the party's credit days, if set). Negative pending = advance or excess payment."})
    return report


# --- GST returns --------------------------------------------------------------------------------------


def _gst_invoices(company: dict, start: date, end: date) -> pd.DataFrame:
    """One row per Sales / Credit Note voucher: party, GSTIN, taxable value and tax by head (paise, sign-corrected)."""
    led = ledger_frame(company["id"])
    lines = entries(company["id"], end)
    lines = lines[(lines.date >= start) & lines.vtype.isin(["Sales", "Credit Note"])]
    rows = []
    for vid, g in lines.groupby("voucher_id"):
        head = g.iloc[0]
        sign = -1 if head.vtype == "Credit Note" else 1
        net = (g.cr - g.dr) * sign  # positive = income/tax side of a sale
        groups = g.ledger_id.map(led.group_name)
        kinds = g.ledger_id.map(led.tax_kind)
        party_rows = g[groups.isin(chart.PARTY_GROUPS).to_numpy()]
        party_id = int(party_rows.ledger_id.iloc[0]) if len(party_rows) else None
        rows.append({
            "voucher_id": int(vid), "vtype": head.vtype, "number": head.number, "date": head.date,
            "party": led.name.get(party_id, "(cash)") if party_id else "(cash)",
            # pandas gives NaN (not None) for a missing GSTIN once any ledger has one.
            "gstin": gstin if party_id and isinstance(gstin := led.gstin.get(party_id), str) else "",
            "state": (service.place_of_supply(led.loc[party_id].to_dict()) if party_id else None) or company.get("state_code") or "",
            "taxable": int(net[(groups.map(chart.primary) == "Sales Accounts").to_numpy()].sum()),
            **{h: int(net[(kinds == f"output_{h}").to_numpy()].sum()) for h in ("igst", "cgst", "sgst", "cess")},
            "value": int((party_rows.dr - party_rows.cr).sum() * sign) if len(party_rows) else int(net[(groups.isin(chart.CASH_BANK)).to_numpy()].sum() * -1),
        })
    frame = pd.DataFrame(rows, columns=["voucher_id", "vtype", "number", "date", "party", "gstin", "state", "taxable", "igst", "cgst", "sgst", "cess", "value"])
    frame["tax"] = frame.igst + frame.cgst + frame.sgst
    frame["rate"] = [gst.nearest_rate(t / x * 100, d) if x else None for t, x, d in zip(frame.tax, frame.taxable, frame.date)]
    # astype(bool): with no invoices map() gives an object Series, which pandas would take as column labels, not a mask.
    frame["registered"] = frame.gstin.map(lambda g: bool(g) and gst.gstin_problem(g) is None).astype(bool)
    return frame


def gstr1(company: dict, start: date | None, end: date | None) -> dict:
    start, end = _fy_period(company, start, end)
    inv = _gst_invoices(company, start, end)
    own_state = company.get("state_code") or ""
    money = lambda x: _r(x)  # noqa: E731
    sales, notes = inv[inv.vtype == "Sales"], inv[inv.vtype == "Credit Note"]
    b2b = sales[sales.registered]
    unreg = sales[~sales.registered]
    inter = unreg.state.ne(own_state) & unreg.state.ne("")
    b2cl = unreg[inter & (unreg.value > 1_00_000_00)]
    b2cs = unreg.drop(b2cl.index)
    cols_inv = [_col("gstin", "GSTIN", "text"), _col("party", "Party", "text"), _col("number", "Invoice", "text"), _col("date", "Date", "date"),
                _col("value", "Invoice value", "money"), _col("pos", "Place of supply", "text"), _col("rate", "Rate %", "text"),
                _col("taxable", "Taxable", "money"), _col("igst", "IGST", "money"), _col("cgst", "CGST", "money"), _col("sgst", "SGST", "money"), _col("cess", "Cess", "money")]

    def inv_rows(frame: pd.DataFrame) -> list[dict]:
        return [{"gstin": r.gstin, "party": r.party, "number": r.number, "date": r.date.isoformat(), "value": money(r.value),
                 "pos": f"{r.state}-{gst.STATE_CODES.get(r.state, '?')}" if r.state else "", "rate": "mixed" if r.rate is None and r.tax else f"{r.rate:g}" if r.rate is not None else "0",
                 "taxable": money(r.taxable), "igst": money(r.igst), "cgst": money(r.cgst), "sgst": money(r.sgst), "cess": money(r.cess)}
                for r in frame.sort_values("date").itertuples()]

    def totals(frame: pd.DataFrame) -> dict:
        return {"gstin": "Total", "value": money(frame.value.sum()), "taxable": money(frame.taxable.sum()), "igst": money(frame.igst.sum()),
                "cgst": money(frame.cgst.sum()), "sgst": money(frame.sgst.sum()), "cess": money(frame.cess.sum())}

    b2cs_g = b2cs.assign(pos=b2cs.state.where(b2cs.state != "", own_state), rate_s=b2cs.rate.map(lambda x: "mixed" if x is None else f"{x:g}"))
    b2cs_rows = [{"pos": f"{pos}-{gst.STATE_CODES.get(pos, '?')}", "rate": rate, "type": "Inter-state" if pos != own_state else "Intra-state",
                  "taxable": money(g.taxable.sum()), "igst": money(g.igst.sum()), "cgst": money(g.cgst.sum()), "sgst": money(g.sgst.sum()), "cess": money(g.cess.sum())}
                 for (pos, rate), g in b2cs_g.groupby(["pos", "rate_s"])]
    series = inv.assign(series=inv.number.str.replace(r"\d+$", "", regex=True))
    docs = [{"doc": f"{vt} ({prefix or 'no prefix'})", "from": g.number.min(), "to": g.number.max(), "count": len(g)}
            for (vt, prefix), g in series.groupby(["vtype", "series"])]
    tables = [
        {"title": f"Table 4A — B2B invoices ({len(b2b)})", "columns": cols_inv, "rows": inv_rows(b2b), "total": totals(b2b) if len(b2b) else None},
        {"title": f"Table 5 — B2C large, inter-state over ₹1 lakh ({len(b2cl)})", "columns": cols_inv, "rows": inv_rows(b2cl), "total": totals(b2cl) if len(b2cl) else None},
        {"title": "Table 7 — B2C small (by place of supply and rate)",
         "columns": [_col("pos", "Place of supply", "text"), _col("type", "Type", "text"), _col("rate", "Rate %", "text"), _col("taxable", "Taxable", "money"),
                     _col("igst", "IGST", "money"), _col("cgst", "CGST", "money"), _col("sgst", "SGST", "money"), _col("cess", "Cess", "money")],
         "rows": b2cs_rows, "total": None},
        {"title": f"Table 9B — Credit notes ({len(notes)})", "columns": cols_inv, "rows": inv_rows(notes), "total": totals(notes) if len(notes) else None},
        {"title": "Table 13 — Documents issued", "columns": [_col("doc", "Document", "text"), _col("from", "From", "text"), _col("to", "To", "text"), _col("count", "Count", "count")],
         "rows": docs, "total": None},
    ]
    report = _report(f"GSTR-1 summary ({_period_text(start, end)})", {}, cards=[
        {"label": "Taxable value (net of credit notes)", "value": money(sales.taxable.sum() - notes.taxable.sum()), "format": "money"},
        {"label": "Tax (net)", "value": money(sales.tax.sum() + sales.cess.sum() - notes.tax.sum() - notes.cess.sum()), "format": "money"},
        {"label": "B2B invoices", "value": len(b2b), "format": "count"},
        {"label": "B2C invoices", "value": len(unreg), "format": "count"},
    ], tables=tables)
    mixed = inv[inv.rate.isna() & (inv.tax != 0)]
    if len(mixed):
        report["checks"].append({"level": "warning", "message": f"{len(mixed)} invoices have tax that does not match a single valid rate "
                                 f"({', '.join(mixed.number.head(6))}); check their tax or split them by rate."})
    report["checks"].append({"level": "info", "message": "HSN summary (Table 12) needs HSN codes on items, which these vouchers do not carry; "
                             "B2C large threshold used: ₹1 lakh (from 1 Aug 2024)."})
    report["checks"].append({"level": "info", "message": "This is a working summary to check against the GST portal, not a filing file."})
    return report


def gstr3b(company: dict, start: date | None, end: date | None) -> dict:
    start, end = _fy_period(company, start, end)
    inv = _gst_invoices(company, start, end)
    led = ledger_frame(company["id"])
    lines = entries(company["id"], end)
    lines = lines[lines.date >= start]
    kinds = lines.ledger_id.map(led.tax_kind)
    out_tax = {h: int((lines.cr - lines.dr)[(kinds == f"output_{h}").to_numpy()].sum()) for h in ("igst", "cgst", "sgst", "cess")}
    itc = {h: int((lines.dr - lines.cr)[(kinds == f"input_{h}").to_numpy()].sum()) for h in ("igst", "cgst", "sgst", "cess")}
    net = gst_net_payable(out_tax, itc)
    sign = np.where(inv.vtype == "Credit Note", -1, 1)
    taxable_out = int((inv.taxable * sign).sum())
    heads = ("igst", "cgst", "sgst", "cess")
    tables = [
        {"title": "3.1(a) Outward taxable supplies", "columns": [_col("item", "", "text"), _col("taxable", "Taxable value", "money"),
         *(_col(h, h.upper(), "money") for h in heads)],
         "rows": [{"item": "Outward taxable supplies (other than zero-rated, nil, exempt)", "taxable": _r(taxable_out), **{h: _r(out_tax[h]) for h in heads}}],
         "total": None},
        {"title": "4. Eligible input tax credit", "columns": [_col("item", "", "text"), *(_col(h, h.upper(), "money") for h in heads)],
         "rows": [{"item": "4(A)(5) All other ITC", **{h: _r(itc[h]) for h in heads}},
                  {"item": "4(C) Net ITC available", **{h: _r(itc[h]) for h in heads}, "_kind": "total"}], "total": None},
        {"title": "6.1 Payment of tax", "columns": [_col("head", "Tax", "text"), _col("liability", "Liability", "money"), _col("itc", "Paid by ITC", "money"),
         _col("cash", "Paid in cash (rounded)", "money"), _col("carry", "ITC carried forward", "money")],
         "rows": [{"head": h.upper(), "liability": _r(out_tax[h]), "itc": _r(sum(net["used"][s].get(h, 0) for s in net["used"])),
                   "cash": _r(net["cash"][h]), "carry": _r(net["credit_left"][h])} for h in heads],
         "total": {"head": "Total", "liability": _r(sum(out_tax.values())), "cash": _r(sum(net["cash"].values())), "carry": _r(sum(net["credit_left"].values()))}},
    ]
    report = _report(f"GSTR-3B summary ({_period_text(start, end)})", {}, cards=[
        {"label": "Output tax", "value": _r(sum(out_tax.values())), "format": "money"},
        {"label": "Input tax credit", "value": _r(sum(itc.values())), "format": "money"},
        {"label": "Pay in cash", "value": _r(sum(net["cash"].values())), "format": "money"},
        {"label": "ITC carried forward", "value": _r(sum(net["credit_left"].values())), "format": "money"},
    ], tables=tables)
    gstr1_tax = int(((inv.tax + inv.cess) * sign).sum())
    ok = gstr1_tax == sum(out_tax.values())
    report["checks"].append({"level": "ok" if ok else "warning",
                             "message": f"Output tax in GST ledgers {_fmt(sum(out_tax.values()))} {'=' if ok else '≠'} tax on sales/credit-note vouchers (GSTR-1) {_fmt(gstr1_tax)}."
                             + ("" if ok else " Output GST was also posted from other voucher types (e.g. journals); check them.")})
    report["checks"].append({"level": "info", "message": "ITC is taken from Input GST ledgers; confirm each bill appears in GSTR-2B and is not blocked under Section 17(5). "
                             "Credit is used in the Rule 88A order; cash per head is rounded to the rupee (Section 170)."})
    return report


# --- Bank reconciliation -----------------------------------------------------------------------------

MATCH_BEFORE_DAYS, MATCH_AFTER_DAYS = 3, 10  # bank date may be up to 3 days before / 10 days after the book date


def bank_reconciliation(company: dict, bank_ledger_id: int | None, as_of: date | None) -> dict:
    led = ledger_frame(company["id"])
    banks = led[led.group_name.isin(["Bank Accounts", "Bank OD A/c"])]
    options = {"ledgers": [{"id": int(i), "name": r["name"], "group": r.group_name} for i, r in banks.iterrows()]}
    if not bank_ledger_id:
        report = _report("Bank reconciliation", {}, options=options)
        report["checks"].append({"level": "info", "message": "Choose a bank ledger, then upload its statement under Import."})
        return report
    with engine.connect() as conn:
        stmt = pd.read_sql(select(bank_lines).where(and_(bank_lines.c.company_id == company["id"], bank_lines.c.bank_ledger_id == bank_ledger_id)), conn)
    if stmt.empty:
        raise service.AccountsError("No bank statement imported for this ledger yet (Import → Bank statement).")
    stmt["date"] = to_datetime(stmt.date).dt.date
    as_of = as_of or max(stmt.date)
    stmt = stmt[stmt.date <= as_of].sort_values(["date", "id"])
    first = min(stmt.date)
    lines = entries(company["id"], as_of)
    book = lines[(lines.ledger_id == bank_ledger_id)].copy()
    cleared_before = book[book.date < first - timedelta(days=MATCH_AFTER_DAYS)]
    book = book[book.date >= first - timedelta(days=MATCH_AFTER_DAYS)]

    # Greedy one-to-one matching: same direction and amount, date window, reference match first, then nearest date.
    pairs, used_bank = [], set()
    for line in book.sort_values(["date", "line_id"]).itertuples():
        amount, deposit = (line.dr, True) if line.dr else (line.cr, False)
        cand = stmt[(stmt.deposit_paise == amount) if deposit else (stmt.withdrawal_paise == amount)]
        cand = cand[~cand.id.isin(used_bank)]
        cand = cand[(cand.date >= line.date - timedelta(days=MATCH_BEFORE_DAYS)) & (cand.date <= line.date + timedelta(days=MATCH_AFTER_DAYS))]
        if cand.empty:
            continue
        # Cheque / UTR numbers: any run of 4+ digits from the voucher's reference found in the bank line.
        reference = line.reference if isinstance(line.reference, str) else ""
        digits = [d.lstrip("0") for d in re.findall(r"\d{4,}", reference) if d.lstrip("0")]
        as_text = lambda v: v if isinstance(v, str) else ""  # noqa: E731
        score = cand.apply(lambda r: (0 if digits and any(d in f"{as_text(r.narration)} {as_text(r.reference)}" for d in digits) else 1,
                                      abs((r.date - line.date).days)), axis=1)
        best = cand.loc[score.sort_values().index[0]]
        used_bank.add(int(best.id))
        pairs.append((line.line_id, int(best.id)))
    matched_book = {p[0] for p in pairs}
    open_book = book[~book.line_id.isin(matched_book)]
    open_bank = stmt[~stmt.id.isin(used_bank)]

    book_balance = int(balances(company, company["fy_start"], as_of).loc[bank_ledger_id].closing)
    dep_not_credited = int(open_book.dr.sum())
    chq_not_presented = int(open_book.cr.sum())
    bank_credits = int(open_bank.deposit_paise.sum())
    bank_debits = int(open_bank.withdrawal_paise.sum())
    computed_bank = book_balance - dep_not_credited + chq_not_presented + bank_credits - bank_debits
    last = stmt[stmt.balance_paise.notna()]
    statement_balance = int(last.balance_paise.iloc[-1]) if len(last) else None

    rows = [
        {"item": "Balance as per books", "amount": _r(book_balance), "_kind": "group"},
        {"item": f"Less: deposits in books not yet credited by bank ({int((open_book.dr > 0).sum())})", "amount": _r(-dep_not_credited)},
        {"item": f"Add: payments in books not yet debited by bank — cheques not presented ({int((open_book.cr > 0).sum())})", "amount": _r(chq_not_presented)},
        {"item": f"Add: credits in bank not in books — interest, direct receipts ({int((open_bank.deposit_paise > 0).sum())})", "amount": _r(bank_credits)},
        {"item": f"Less: debits in bank not in books — charges, direct debits ({int((open_bank.withdrawal_paise > 0).sum())})", "amount": _r(-bank_debits)},
        {"item": "Balance as per bank (calculated)", "amount": _r(computed_bank), "_kind": "total"},
    ]
    if statement_balance is not None:
        rows.append({"item": "Balance as per bank statement", "amount": _r(statement_balance), "_kind": "group"})
    names = led.name
    unmatched_rows = [{"side": "Books", "date": r.date.isoformat(), "detail": f"{r.vtype} {r.number}" + (f" · {r.narration}" if isinstance(r.narration, str) and r.narration else ""),
                       "in": _r(r.dr) or None, "out": _r(r.cr) or None} for r in open_book.itertuples()]
    text = lambda v: v if isinstance(v, str) else ""  # noqa: E731  (pandas gives NaN for empty text)
    unmatched_rows += [{"side": "Bank", "date": r.date.isoformat(), "detail": text(r.narration) + (f" · {r.reference}" if text(r.reference) else ""),
                        "in": _r(r.deposit_paise) or None, "out": _r(r.withdrawal_paise) or None} for r in open_bank.itertuples()]
    report = _report(f"Bank reconciliation: {names[bank_ledger_id]} as on {as_of:%d %b %Y}", {}, options=options, cards=[
        {"label": "Balance as per books", "value": _r(book_balance), "format": "money"},
        {"label": "Matched entries", "value": len(pairs), "format": "count"},
        {"label": "Unmatched in books", "value": len(open_book), "format": "count"},
        {"label": "Unmatched in bank", "value": len(open_bank), "format": "count"},
        {"label": "Balance as per bank", "value": _r(computed_bank), "format": "money"},
    ], tables=[
        {"title": "Reconciliation statement", "columns": [_col("item", "Particulars", "text"), _col("amount", "Amount", "money")], "rows": rows, "total": None},
        {"title": "Items to reconcile", "columns": [_col("side", "In", "text"), _col("date", "Date", "date"), _col("detail", "Details", "text"),
                                                   _col("in", "Money in", "money"), _col("out", "Money out", "money")],
         "rows": sorted(unmatched_rows, key=lambda r: r["date"]), "total": None},
    ])
    if statement_balance is not None:
        ok = statement_balance == computed_bank
        report["checks"].append({"level": "ok" if ok else "warning",
                                 "message": f"Calculated bank balance {_fmt(computed_bank)} {'=' if ok else '≠'} statement closing balance {_fmt(statement_balance)}."
                                 + ("" if ok else f" Difference {_fmt(statement_balance - computed_bank)}: an entry may be missing in the books before the statement period, "
                                    "or the bank ledger's opening balance differs from the statement's.")})
    report["checks"].append({"level": "info", "message": f"Matched on amount and direction within {MATCH_BEFORE_DAYS} days before to {MATCH_AFTER_DAYS} days "
                             "after the book date, preferring a cheque/UTR number found in the bank narration."})
    if len(cleared_before):
        report["checks"].append({"level": "info", "message": f"{len(cleared_before)} book entries dated before the statement period were treated as already cleared."})
    if len(open_bank):
        report["checks"].append({"level": "info", "message": "Post the bank-only items (charges, interest, receipts) as vouchers so the books catch up."})
    return report


# --- Dashboard ----------------------------------------------------------------------------------------


def dashboard(company: dict) -> dict:
    # Positions are closing balances; sales, purchases and profit are for the latest financial year.
    start, end = _fy_period(company, None, None)
    bal = balances(company, start, end)
    f = _pl_figures(bal, 0, 0)  # no opening or closing stock: income less expenses of the P&L ledgers
    cash = int(bal[bal.group_name == "Cash-in-Hand"].closing.sum())
    bank = int(bal[bal.group_name.isin(["Bank Accounts", "Bank OD A/c"])].closing.sum())
    receivable = int(bal[bal.group_name == "Sundry Debtors"].closing.sum())
    payable = -int(bal[bal.group_name == "Sundry Creditors"].closing.sum())
    out_tax = -int(bal[bal.tax_kind.fillna("").str.startswith("output")].closing.sum())
    itc = int(bal[bal.tax_kind.fillna("").str.startswith("input")].closing.sum())
    groups = bal[(bal.closing != 0)].groupby("primary").closing.sum()
    report = _report(f"{company['name']} — position {_period_text(start, end)}", {}, cards=[
        {"label": "Cash", "value": _r(cash), "format": "drcr"},
        {"label": "Bank", "value": _r(bank), "format": "drcr"},
        {"label": "Receivables", "value": _r(receivable), "format": "money"},
        {"label": "Payables", "value": _r(payable), "format": "money"},
        {"label": "Sales", "value": _r(f["sales"]), "format": "money"},
        {"label": "Purchases", "value": _r(f["purchases"]), "format": "money"},
        {"label": "Net GST (output − input)", "value": _r(out_tax - itc), "format": "money"},
        {"label": "Profit before stock", "value": _r(f["net"]), "format": "money"},
    ], tables=[{"title": "Balances by group", "columns": [_col("group", "Group", "text"), _col("balance", "Balance", "drcr")],
                "rows": [{"group": g, "balance": _r(v)} for g, v in groups.items()], "total": None}])
    from . import metal  # jewellers: fine-metal position beside the rupees

    for name in metal.metals_in_use(company["id"]):
        closing = metal.metal_closing(company, name)
        groups_by_id = ledger_frame(company["id"]).group_name
        kinds = closing.index.map(groups_by_id)
        stock = int(closing[kinds == "Stock-in-Hand"].sum())
        parties = closing[kinds.isin(list(chart.PARTY_GROUPS))]
        report["cards"] += [
            {"label": f"{name.title()} stock (fine g)", "value": stock / 1000, "format": "weight"},
            {"label": f"{name.title()} owed to us (fine g)", "value": int(parties[parties > 0].sum()) / 1000, "format": "weight"},
            {"label": f"{name.title()} we owe (fine g)", "value": int(-parties[parties < 0].sum()) / 1000, "format": "weight"},
        ]
    opening_diff = int(ledger_frame(company["id"]).opening_paise.sum())
    total = int(bal.closing.sum())
    if total == 0:
        report["checks"].append({"level": "ok", "message": "Books are in balance: total debit balances = total credit balances."})
    elif total == opening_diff:
        report["checks"].append({"level": "warning", "message": f"Opening balances differ by {_drcr(opening_diff)}; fix them under Ledgers."})
    else:
        report["checks"].append({"level": "warning", "message": f"Total debit and credit balances differ by {_drcr(total)}; open the trial balance "
                                 "to find the cause."})
    report["checks"].append({"level": "info", "message": "Profit before stock = income − expenses of the year, before opening and closing stock; "
                             "see Profit & loss for the profit after stock."})
    return report
