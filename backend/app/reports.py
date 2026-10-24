"""Accounting reports computed with pandas/NumPy from a sheet's table.

Every amount is converted to whole paise (int64) before any arithmetic, so totals and
running balances are exact. Balances follow Tally's convention for every account type:
balance = opening + debits - credits, shown as an amount with "Dr" (positive) or "Cr"
(negative). Each report includes the checks that prove it adds up.

Which column plays which part (date, account, debit, credit...) comes from the sheet's
mapping: detected automatically from the column names and editable by the user.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import classify, gst
from .compat import to_datetime
from .formatting import indian

ROLES = {
    "date": "Date",
    "account": "Account / party / ledger",
    "debit": "Debit",
    "credit": "Credit",
    "amount": "Signed amount (if no Debit/Credit)",
    "voucher_no": "Voucher / invoice number",
    "voucher_type": "Voucher type",
    "narration": "Particulars / narration",
    "group": "Group (Tally 'Under')",
    "due_date": "Due date",
    "outstanding": "Pending / outstanding amount",
    "taxable": "Taxable value",
    "cgst": "CGST",
    "sgst": "SGST / UTGST",
    "igst": "IGST",
    "cess": "Cess",
    "tax": "Total GST (when not split)",
    "rate": "GST rate %",
    "gstin": "GSTIN",
    "invoice_value": "Invoice value",
    "item": "Item / product",
}

# Specific roles first so that e.g. "taxable_value" is not taken as the amount. Within a role,
# patterns are tried in order (a "ledger" column beats a generic "name" column).
_ROLE_PATTERNS: dict[str, tuple[list[str], str | None]] = {
    "taxable": ([r"(^|_)(taxable|taxable_value|taxable_amount|assessable|assessable_value)(_|$)"], "number"),
    "cgst": ([r"(^|_)cgst"], "number"),
    "sgst": ([r"(^|_)(sgst|utgst)"], "number"),
    "igst": ([r"(^|_)igst"], "number"),
    "cess": ([r"(^|_)cess"], "number"),
    "rate": ([r"(^|_)(gst_rate|tax_rate|rate_of_tax|gst_percent|gst_pct|tax_percent|gst_rate_percent)(_|$)"], "number"),
    "tax": ([r"^(gst|gst_amount|gst_amt|tax|tax_amount|total_tax|total_gst)(_|$)"], "number"),
    "gstin": ([r"(^|_)(gstin|gst_no|gst_number|gstin_uin|gstin_no)(_|$)"], "text"),
    "invoice_value": ([r"(^|_)(invoice_value|invoice_total|inv_value|invoice_amount|grand_total|bill_amount|bill_total|"
                       r"bill_value|total_amount|net_payable|voucher_total)(_|$)", r"^total$"], "number"),
    "outstanding": ([r"(^|_)(pending|outstanding|balance_due|due_amount|unpaid)(_|$)"], "number"),
    "due_date": ([r"(^|_)due(_|$)"], "date"),
    "date": ([r"(^|_)(date|dt|dated)(_|$)"], "date"),
    "debit": ([r"(^|_)(debit|debits|dr|withdrawal|withdrawals|paid_out)(_|$)"], "number"),
    "credit": ([r"(^|_)(credit|credits|cr|deposit|deposits|paid_in)(_|$)"], "number"),
    "amount": ([r"(^|_)(amount|amt|net_amount)(_|$)"], "number"),
    "voucher_no": ([r"(^|_)(vou|voucher|vch|invoice|inv|bill|ref)_?(no|num|number)(_|$)", r"^(voucher|invoice|bill|reference|ref)$"], None),
    "voucher_type": ([r"(^|_)(vch_type|voucher_type|vou_type)(_|$)", r"^type$"], "text"),
    "narration": ([r"(^|_)(particulars|narration|description|details|remarks)(_|$)"], "text"),
    "group": ([r"(^|_)(group|under|parent)(_|$)"], "text"),
    "item": ([r"(^|_)(item|item_name|product|product_name|goods|stock_item|item_description)(_|$)"], "text"),
    "account": ([
        r"(^|_)(ledger|account|party)(_|$)",
        r"(^|_)(party_name|customer|vendor|supplier|client|payee)(_|$)",
        r"(^|_)(head|category|account_head)(_|$)",
        r"(^|_)name(_|$)",
    ], "text"),
}
# Number columns that are never a rupee amount (weights, purity, carats, counts, rates); the upload
# summary's "net" pattern also catches "Net Wt", so its pick is checked against this. Weights are often
# run together ("NetWt", "GrossWt" → "netwt", "grosswt"), hence any word ending in wt/weight.
_METAL_NAME = (r"(^|_)[a-z0-9]*(wt|wts|weight|weights)(_|$)"
               r"|(^|_)(fine|tunch|touch|purity|karat|karats|kt|carat|carats|ct|cts|tola|tolas|gm|gms|gram|grams|mg)(_|$)")
_METAL_COLUMN = re.compile(_METAL_NAME)
_NOT_AMOUNT = re.compile(_METAL_NAME + r"|(^|_)(qty|quantity|pcs|pieces|nos|units|kg|rate|percent|pct|wastage)(_|$)")
# "Gross", "Less" and "Net" alone are the weights of a jewellery register (one that also has weight, purity
# or tunch columns); elsewhere they can be rupee amounts.
_BARE_WEIGHT = re.compile(r"^(gross|grs|less|net)$")


class ReportError(ValueError):
    """The report cannot be produced from this sheet. The message is shown to the user."""


# --- Mapping ---------------------------------------------------------------------------------


def detect_mapping(profile: dict) -> dict[str, str]:
    """Best guess of which column plays each role, from names, types and the upload summary."""
    columns = [c for c in profile["columns"] if c["non_null"] > 0]
    calculated = set(profile.get("calculated_columns", []))
    detected = profile.get("summary", {}).get("detected", {})
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for role, (patterns, kind) in _ROLE_PATTERNS.items():
        for pattern in patterns:
            regex = re.compile(pattern)
            match = next(
                (c["name"] for c in columns
                 if c["name"] not in used and c["name"] not in calculated
                 and (kind is None or c["kind"] == kind) and regex.search(c["name"])),
                None,
            )
            if match:
                mapping[role] = match
                used.add(match)
                break
    # Fall back to the upload summary's picks.
    for role, key in (("date", "date"), ("debit", "debit"), ("credit", "credit"), ("account", "category")):
        if role not in mapping and detected.get(key) and detected[key] not in used:
            mapping[role] = detected[key]
            used.add(detected[key])
    if ("debit" in mapping) != ("credit" in mapping):
        mapping.pop("debit", None)
        mapping.pop("credit", None)
    if "debit" not in mapping and "amount" not in mapping:
        # A register has no debit/credit: its invoice value (or the summary's main amount) is the amount,
        # but never a weight, purity, quantity or rate column (a weights-only register has no amount).
        metal = any(_METAL_COLUMN.search(c["name"]) for c in profile["columns"])
        fallback = next((c for c in (mapping.get("invoice_value"), detected.get("amount"))
                         if c and not _NOT_AMOUNT.search(c) and not (metal and _BARE_WEIGHT.match(c))), None)
        if fallback:
            mapping["amount"] = fallback
    return mapping


def effective_mapping(profile: dict) -> dict[str, str]:
    names = {c["name"] for c in profile["columns"]}
    saved = {k: v for k, v in (profile.get("mapping") or {}).items() if v in names and k in ROLES}
    return saved if profile.get("mapping") is not None else detect_mapping(profile)


# --- Helpers ---------------------------------------------------------------------------------


def _paise(series: pd.Series) -> np.ndarray:
    values = pd.to_numeric(series, errors="coerce").astype("float64").fillna(0.0).to_numpy()
    return np.round(values * 100).astype(np.int64)


def _rupees(paise) -> float:
    return int(paise) / 100


def _need(mapping: dict, *roles: str) -> None:
    missing = [ROLES[r] for r in roles if r not in mapping]
    if missing:
        raise ReportError("Choose which column holds: " + ", ".join(missing) + " (use 'Column roles').")


def _signed(frame: pd.DataFrame, mapping: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    """(debit, credit, signed) in paise per row, plus a note on how they were derived."""
    if "debit" in mapping and "credit" in mapping:
        dr, cr = _paise(frame[mapping["debit"]]), _paise(frame[mapping["credit"]])
        both = (dr != 0) & (cr != 0)
        note = f"{int(both.sum())} rows have both a debit and a credit." if both.any() else ""
        return dr, cr, dr - cr, note
    if "amount" in mapping:
        signed = _paise(frame[mapping["amount"]])
        return np.where(signed > 0, signed, 0), np.where(signed < 0, -signed, 0), signed, (
            "Using the signed amount column: positive amounts are treated as debits, negative as credits."
        )
    raise ReportError("Choose the Debit and Credit columns, or one signed Amount column (use 'Column roles').")


def _date_col(frame: pd.DataFrame, mapping: dict, role: str = "date") -> pd.Series:
    return to_datetime(frame[mapping[role]])


def _dates_text(values: pd.Series) -> list[str | None]:
    return [None if pd.isna(v) else v.strftime("%Y-%m-%d") for v in values]


def _filter_period(frame: pd.DataFrame, mapping: dict, start: date | None, end: date | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(rows before the period, rows in the period). Without a date column everything is 'in'."""
    if "date" not in mapping or (start is None and end is None):
        return frame.iloc[0:0], frame
    when = _date_col(frame, mapping)
    before = frame[when < pd.Timestamp(start)] if start else frame.iloc[0:0]
    inside = frame
    if start:
        inside = inside[_date_col(inside, mapping) >= pd.Timestamp(start)]
    if end:
        inside = inside[_date_col(inside, mapping) <= pd.Timestamp(end)]
    return before, inside


def _sorted(frame: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    if "date" not in mapping:
        return frame
    return frame.assign(_when=_date_col(frame, mapping)).sort_values(["_when", "_rowid"], kind="stable").drop(columns="_when")


def _col(key: str, label: str, fmt: str) -> dict:
    return {"key": key, "label": label, "format": fmt}


def _report(title: str, mapping: dict, **parts) -> dict:
    return {"title": title, "mapping": mapping, "cards": [], "tables": [], "checks": [], "options": {}} | parts


def _accounts(frame: pd.DataFrame, mapping: dict) -> pd.Series:
    return frame[mapping["account"]].astype("string").fillna("(blank)").str.strip()


# --- Ledger and books ----------------------------------------------------------------------


def ledger(frame: pd.DataFrame, mapping: dict, account: str | None, start: date | None, end: date | None) -> dict:
    """Account statement with opening balance, running balance (Dr/Cr) and closing balance."""
    options = {}
    if "account" in mapping:
        accounts = _accounts(frame, mapping)
        options["accounts"] = sorted(accounts.unique().tolist())
        if account:
            frame = frame[accounts == account]
            if frame.empty:
                raise ReportError(f'No entries for "{account}".')
    _signed(frame.head(0), mapping)  # validates the mapping early
    frame = _sorted(frame, mapping)
    before, inside = _filter_period(frame, mapping, start, end)
    opening = int(_signed(before, mapping)[2].sum()) if len(before) else 0
    dr, cr, signed, note = _signed(inside, mapping)
    running = opening + np.cumsum(signed)
    closing = opening + int(signed.sum())

    # Particulars: the narration if there is one, else the account (when showing all accounts).
    particulars_role = "narration" if "narration" in mapping else ("account" if "account" in mapping and not account else None)
    extra = [r for r in ("voucher_type", "voucher_no") if r in mapping]
    if particulars_role == "narration" and "account" in mapping and not account:
        extra.insert(0, "account")
    dates = _dates_text(_date_col(inside, mapping)) if "date" in mapping else [None] * len(inside)
    columns = [_col("date", "Date", "date")] if "date" in mapping else []
    columns.append(_col("particulars", "Particulars", "text"))
    columns += [_col(r, ROLES[r].split(" (")[0].split(" /")[0], "text") for r in extra]
    columns += [_col("debit", "Debit", "money"), _col("credit", "Credit", "money"), _col("balance", "Balance", "drcr")]

    def text_of(role: str, i: int):
        value = _accounts(inside, mapping).iloc[i] if role == "account" else inside[mapping[role]].iloc[i]
        if value is None or pd.isna(value):
            return None
        return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)

    rows = [{"particulars": "Opening balance", "balance": _rupees(opening), "_kind": "opening"}]
    for i in range(len(inside)):
        row = {"date": dates[i], "particulars": text_of(particulars_role, i) if particulars_role else None,
               "debit": _rupees(dr[i]) or None, "credit": _rupees(cr[i]) or None, "balance": _rupees(running[i])}
        for r in extra:
            row[r] = text_of(r, i)
        rows.append(row)
    total_dr, total_cr = int(dr.sum()), int(cr.sum())
    check_ok = opening + total_dr - total_cr == closing
    title = f"Ledger: {account}" if account else "Ledger (all entries)"
    report = _report(
        title,
        mapping,
        options=options,
        cards=[
            {"label": "Opening balance", "value": _rupees(opening), "format": "drcr"},
            {"label": "Total debit", "value": _rupees(total_dr), "format": "money"},
            {"label": "Total credit", "value": _rupees(total_cr), "format": "money"},
            {"label": "Closing balance", "value": _rupees(closing), "format": "drcr"},
        ],
        tables=[{
            "title": None,
            "columns": columns,
            "rows": rows,
            "total": {"particulars": "Total / closing balance", "debit": _rupees(total_dr), "credit": _rupees(total_cr),
                      "balance": _rupees(closing)},
        }],
    )
    report["checks"].append({
        "level": "ok" if check_ok else "warning",
        "message": f"Opening {_fmt_drcr(opening)} + debits {_fmt(total_dr)} − credits {_fmt(total_cr)} = closing {_fmt_drcr(closing)}.",
    })
    if note:
        report["checks"].append({"level": "info", "message": note})
    return report


def day_book(frame: pd.DataFrame, mapping: dict, start: date | None, end: date | None) -> dict:
    """Totals per day with a running balance (cash / bank book view)."""
    _need(mapping, "date")
    _, inside = _filter_period(_sorted(frame, mapping), mapping, start, end)
    dr, cr, signed, note = _signed(inside, mapping)
    days = _date_col(inside, mapping).dt.normalize()
    table = pd.DataFrame({"day": days, "dr": dr, "cr": cr, "signed": signed}).dropna(subset=["day"])
    grouped = table.groupby("day").agg(entries=("signed", "size"), dr=("dr", "sum"), cr=("cr", "sum"), net=("signed", "sum"))
    running = grouped["net"].cumsum()
    rows = [
        {"date": day.strftime("%Y-%m-%d"), "entries": int(r.entries), "debit": _rupees(r.dr), "credit": _rupees(r.cr),
         "net": _rupees(r.net), "balance": _rupees(running.loc[day])}
        for day, r in grouped.iterrows()
    ]
    undated = int(days.isna().sum())
    report = _report(
        "Day book",
        mapping,
        tables=[{
            "title": None,
            "columns": [_col("date", "Date", "date"), _col("entries", "Entries", "count"), _col("debit", "Debit", "money"),
                        _col("credit", "Credit", "money"), _col("net", "Net", "money"), _col("balance", "Running balance", "drcr")],
            "rows": rows,
            "total": {"date": "Total", "entries": int(grouped["entries"].sum()), "debit": _rupees(grouped["dr"].sum()),
                      "credit": _rupees(grouped["cr"].sum()), "net": _rupees(grouped["net"].sum())},
        }],
    )
    if undated:
        report["checks"].append({"level": "warning", "message": f"{undated} entries have no date and are not in the day book."})
    if note:
        report["checks"].append({"level": "info", "message": note})
    return report


# --- Trial balance, P&L, balance sheet ------------------------------------------------------------


def _balances(frame: pd.DataFrame, mapping: dict, overrides: dict[str, str]) -> pd.DataFrame:
    _need(mapping, "account")
    dr, cr, signed, _ = _signed(frame, mapping)
    table = pd.DataFrame({"account": _accounts(frame, mapping).to_numpy(), "dr": dr, "cr": cr, "net": signed})
    if "group" in mapping:
        table["file_group"] = frame[mapping["group"]].astype("string").fillna("").to_numpy()
    grouped = table.groupby("account", sort=True).agg(dr=("dr", "sum"), cr=("cr", "sum"), net=("net", "sum"))
    groups, sources = [], []
    for name, row in grouped.iterrows():
        if name in overrides:
            groups.append(overrides[name])
            sources.append("you")
            continue
        group, source = classify.classify(name, int(row.net))
        if group == classify.UNCLASSIFIED and "file_group" in table:
            file_group = table.loc[table.account == name, "file_group"].mode()
            if len(file_group) and file_group.iloc[0]:
                group, source = classify.classify(file_group.iloc[0], int(row.net))
                source = "group column" if group != classify.UNCLASSIFIED else source
        groups.append(group)
        sources.append(source)
    grouped["group"] = groups
    grouped["source"] = sources
    return grouped


def trial_balance(frame: pd.DataFrame, mapping: dict, overrides: dict[str, str]) -> dict:
    balances = _balances(frame, mapping, overrides)
    rows = []
    for name, r in balances.sort_values("group", kind="stable").iterrows():
        rows.append({
            "account": name, "group": r.group, "source": r.source,
            "debit": _rupees(r.dr), "credit": _rupees(r.cr),
            "closing_dr": _rupees(r.net) if r.net > 0 else None,
            "closing_cr": _rupees(-r.net) if r.net < 0 else None,
        })
    total_dr = int(balances.net[balances.net > 0].sum())
    total_cr = int(-balances.net[balances.net < 0].sum())
    difference = total_dr - total_cr
    report = _report(
        "Trial balance",
        mapping,
        cards=[
            {"label": "Total Dr balances", "value": _rupees(total_dr), "format": "money"},
            {"label": "Total Cr balances", "value": _rupees(total_cr), "format": "money"},
            {"label": "Difference", "value": _rupees(difference), "format": "money", "hint": "Balanced" if difference == 0 else None},
        ],
        tables=[{
            "title": None,
            "columns": [_col("account", "Account", "text"), _col("group", "Group", "group"),
                        _col("debit", "Total debit", "money"), _col("credit", "Total credit", "money"),
                        _col("closing_dr", "Closing Dr", "money"), _col("closing_cr", "Closing Cr", "money")],
            "rows": rows,
            "total": {"account": "Total", "debit": _rupees(balances.dr.sum()), "credit": _rupees(balances.cr.sum()),
                      "closing_dr": _rupees(total_dr), "closing_cr": _rupees(total_cr)},
        }],
        options={"groups": list(classify.GROUPS) + [classify.UNCLASSIFIED]},
    )
    if difference == 0:
        report["checks"].append({"level": "ok", "message": f"Total Dr balances equal total Cr balances ({_fmt(total_dr)})."})
    else:
        hints = ["This is expected for single-entry data such as a sales register or bank statement, where only one side of each entry is recorded."]
        if difference % 900 == 0:
            hints.append("The difference is divisible by 9, which often means two digits were swapped (e.g. 54 typed as 45).")
        if difference % 2 == 0:
            hints.append(f"Half the difference is {_fmt(abs(difference) // 2)}; look for an entry of that amount posted on the wrong side.")
        report["checks"].append({
            "level": "warning",
            "message": f"The trial balance does not tally: Dr {_fmt(total_dr)} vs Cr {_fmt(total_cr)}, difference {_fmt(abs(difference))}. " + " ".join(hints),
        })
    _classification_checks(report, balances)
    return report


def _classification_checks(report: dict, balances: pd.DataFrame) -> None:
    unclassified = balances[(balances.group == classify.UNCLASSIFIED) & (balances.net != 0)]
    if len(unclassified):
        names = ", ".join(unclassified.index[:8]) + (" ..." if len(unclassified) > 8 else "")
        report["checks"].append({
            "level": "warning",
            "message": f"{len(unclassified)} accounts could not be classified ({names}). Choose their group in the trial "
            "balance; until then the profit & loss and balance sheet are provisional.",
        })
    guessed = balances[balances.source.isin(["direction", "party name"])]
    if len(guessed):
        report["checks"].append({
            "level": "info",
            "message": f"{len(guessed)} accounts were grouped from their balance direction or name pattern "
            "(e.g. rent or interest, party names); check the Group column.",
        })


def profit_and_loss(frame: pd.DataFrame, mapping: dict, overrides: dict[str, str], opening_stock: float, closing_stock: float) -> dict:
    balances = _balances(frame, mapping, overrides)
    by_group = balances.groupby("group")["net"].sum()
    get = lambda g: int(by_group.get(g, 0))  # noqa: E731
    open_p, close_p = int(round(opening_stock * 100)), int(round(closing_stock * 100))
    sales, direct_inc = -get("Sales Accounts"), -get("Direct Incomes")
    purchases, direct_exp = get("Purchase Accounts"), get("Direct Expenses")
    indirect_inc, indirect_exp = -get("Indirect Incomes"), get("Indirect Expenses")
    gross = (sales + direct_inc + close_p) - (open_p + purchases + direct_exp)
    net = gross + indirect_inc - indirect_exp

    def lines(group: str, sign: int) -> list[dict]:
        part = balances[balances.group == group]
        return [{"item": f"  {name}", "amount": _rupees(sign * r.net)} for name, r in part.iterrows() if r.net]

    rows = [
        {"item": "Sales", "amount": _rupees(sales), "_kind": "group"}, *lines("Sales Accounts", -1),
        {"item": "Direct incomes", "amount": _rupees(direct_inc), "_kind": "group"}, *lines("Direct Incomes", -1),
        {"item": "Closing stock", "amount": _rupees(close_p), "_kind": "group"},
        {"item": "Less: Opening stock", "amount": _rupees(-open_p), "_kind": "group"},
        {"item": "Less: Purchases", "amount": _rupees(-purchases), "_kind": "group"}, *lines("Purchase Accounts", -1),
        {"item": "Less: Direct expenses", "amount": _rupees(-direct_exp), "_kind": "group"}, *lines("Direct Expenses", -1),
        {"item": "Gross profit" if gross >= 0 else "Gross loss", "amount": _rupees(gross), "_kind": "total"},
        {"item": "Add: Indirect incomes", "amount": _rupees(indirect_inc), "_kind": "group"}, *lines("Indirect Incomes", -1),
        {"item": "Less: Indirect expenses", "amount": _rupees(-indirect_exp), "_kind": "group"}, *lines("Indirect Expenses", -1),
        {"item": "Net profit" if net >= 0 else "Net loss", "amount": _rupees(net), "_kind": "total"},
    ]
    report = _report(
        "Profit & loss",
        mapping,
        cards=[
            {"label": "Sales", "value": _rupees(sales), "format": "money"},
            {"label": "Gross profit" if gross >= 0 else "Gross loss", "value": _rupees(gross), "format": "money"},
            {"label": "Net profit" if net >= 0 else "Net loss", "value": _rupees(net), "format": "money"},
        ],
        tables=[{"title": None, "columns": [_col("item", "Particulars", "text"), _col("amount", "Amount", "money")], "rows": rows, "total": None}],
    )
    pl_net = -int(balances[balances.group.map(classify.statement_of) == "pl"].net.sum())
    check = pl_net + (close_p - open_p) == net
    report["checks"].append({
        "level": "ok" if check else "warning",
        "message": f"Check: income minus expenses of all P&L accounts ({_fmt(pl_net)}) plus the stock change "
        f"({_fmt(close_p - open_p)}) equals the net {'profit' if net >= 0 else 'loss'} ({_fmt(net)}).",
    })
    if not closing_stock:
        report["checks"].append({
            "level": "info",
            "message": "Closing stock is 0. It cannot be worked out from ledgers; enter it above if the business holds stock.",
        })
    _classification_checks(report, balances)
    return report


_BS_SIDES = {"asset": "Assets", "liability": "Liabilities & capital"}


def balance_sheet(frame: pd.DataFrame, mapping: dict, overrides: dict[str, str], opening_stock: float, closing_stock: float) -> dict:
    balances = _balances(frame, mapping, overrides)
    pl = profit_and_loss(frame, mapping, overrides, opening_stock, closing_stock)
    net_profit = int(round(pl["cards"][2]["value"] * 100))
    bs = balances[balances.group.map(classify.statement_of) == "bs"]
    close_p = int(round(closing_stock * 100))

    rows: list[dict] = []
    totals = {}
    for nature, label in (("liability", "Liabilities & capital"), ("asset", "Assets")):
        part = bs[bs.group.map(classify.nature_of) == nature]
        sign = -1 if nature == "liability" else 1
        rows.append({"item": label, "amount": None, "_kind": "heading"})
        total = 0
        for group, members in part.groupby("group"):
            amount = sign * int(members.net.sum())
            total += amount
            rows.append({"item": group, "amount": _rupees(amount), "_kind": "group"})
            rows += [{"item": f"  {name}", "amount": _rupees(sign * r.net)} for name, r in members.iterrows() if r.net]
        if nature == "liability":
            rows.append({"item": "Profit & loss (current period)", "amount": _rupees(net_profit), "_kind": "group"})
            total += net_profit
        else:
            if close_p:
                rows.append({"item": "Closing stock", "amount": _rupees(close_p), "_kind": "group"})
                total += close_p
        rows.append({"item": f"Total {label.lower()}", "amount": _rupees(total), "_kind": "total"})
        totals[nature] = total
    suspense = int(balances[balances.group.isin(["Suspense A/c", classify.UNCLASSIFIED])].net.sum())
    difference = totals["asset"] - totals["liability"]
    report = _report(
        "Balance sheet",
        mapping,
        cards=[
            {"label": "Total assets", "value": _rupees(totals["asset"]), "format": "money"},
            {"label": "Total liabilities & capital", "value": _rupees(totals["liability"]), "format": "money"},
            {"label": "Difference", "value": _rupees(difference), "format": "money", "hint": "Balanced" if difference == 0 else None},
        ],
        tables=[{"title": None, "columns": [_col("item", "Particulars", "text"), _col("amount", "Amount", "money")], "rows": rows, "total": None}],
    )
    if difference == 0:
        report["checks"].append({"level": "ok", "message": "Assets equal liabilities plus capital and profit."})
    else:
        report["checks"].append({
            "level": "warning",
            "message": f"The balance sheet does not tally by {_fmt(abs(difference))}. "
            + (f"Unclassified/suspense accounts hold {_fmt_drcr(suspense)}. " if suspense else "")
            + "A balance sheet needs every account of the business (a full ledger or trial balance export); "
            "registers and bank statements alone cannot produce one.",
        })
    _classification_checks(report, balances)
    return report


# --- Ageing ----------------------------------------------------------------------------------------

AGEING_BUCKETS = [(0, 30), (31, 60), (61, 90), (91, 180), (181, None)]


def _fifo_pending(accounts: np.ndarray, when: pd.Series, signed: np.ndarray) -> np.ndarray:
    """What is still open of each entry (paise) once each party's payments are set off against its oldest bills.

    A party's net balance stays open on its newest bills, which is the same as paying the oldest first (FIFO).
    Bills are the entries on the side of the balance (debits for a receivable, credits for a payable); undated
    entries count as the oldest (a Tally export leaves the opening balance undated).
    """
    order = pd.DataFrame({"account": accounts, "when": when.to_numpy(), "signed": np.asarray(signed, dtype=np.int64)})
    order = order.sort_values("when", kind="stable", na_position="first")  # stable: sheet order within a date
    party = order["account"].to_numpy()
    net = order.groupby(party, sort=False)["signed"].transform("sum").to_numpy()
    sign = np.where(net > 0, 1, -1)
    bill = np.clip(order["signed"].to_numpy() * sign, 0, None)
    # Bills of the same party newer than each one: the balance is left on the newest bills first.
    newer = pd.Series(bill[::-1]).groupby(party[::-1], sort=False).cumsum().to_numpy()[::-1] - bill
    pending = np.zeros(len(order), dtype=np.int64)
    pending[order.index.to_numpy()] = np.clip(np.abs(net) - newer, 0, bill) * sign
    return pending


def ageing(frame: pd.DataFrame, mapping: dict, as_of: date | None) -> dict:
    _need(mapping, "account")
    if "due_date" not in mapping:
        _need(mapping, "date")
    basis = "due_date" if "due_date" in mapping else "date"
    as_of = as_of or date.today()
    when = _date_col(frame, mapping, basis)
    accounts = _accounts(frame, mapping).to_numpy()
    later = 0
    if "outstanding" in mapping:
        pending = _paise(frame[mapping["outstanding"]])
        source = f'the "{mapping["outstanding"]}" column'
    else:
        # Only what had happened by the as-on date: bills, payments and credit notes entered after it are left out
        # (by entry date even when ageing by due date; a bill not yet due on that date is still owed).
        if "date" in mapping:
            entered = _date_col(frame, mapping)
            # timedelta, not pd.Timedelta: pandas 2 makes the latter nanoseconds, which overflow after 2262
            after = (entered >= pd.Timestamp(as_of) + timedelta(days=1)).to_numpy()
        else:
            entered, after = when, np.zeros(len(frame), dtype=bool)
        later = int(after.sum())
        pending = _fifo_pending(accounts, entered, np.where(after, 0, _signed(frame, mapping)[2]))
        source = ("each party's balance: no pending-amount column was chosen, so payments and credits are set off against "
                  "that party's oldest bills first (FIFO) and only the unpaid newer bills are aged")
    days = (pd.Timestamp(as_of) - when).dt.days
    labels = [f"{lo}-{hi} days" if hi else f"Over {lo - 1} days" for lo, hi in AGEING_BUCKETS]
    bucket = pd.Series("No date", index=frame.index)
    for (lo, hi), label in zip(AGEING_BUCKETS, labels):
        mask = (days >= lo) & ((days <= hi) if hi else True)
        bucket[mask.fillna(False).to_numpy()] = label
    bucket[(days < 0).fillna(False).to_numpy()] = "Not yet due"
    table = pd.DataFrame({"account": accounts, "bucket": bucket.to_numpy(), "pending": pending})
    table = table[table.pending != 0]
    pivot = table.pivot_table(index="account", columns="bucket", values="pending", aggfunc="sum", fill_value=0)
    order = ["Not yet due", *labels, "No date"]
    present = [b for b in order if b in pivot.columns]
    pivot = pivot[present]
    pivot["total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("total", ascending=False, kind="stable")  # stable: ties stay A-Z on any CPU
    keys = {b: f"b{i}" for i, b in enumerate(present)}
    rows = [{"account": name, **{keys[b]: _rupees(r[b]) or None for b in present}, "total": _rupees(r["total"])} for name, r in pivot.iterrows()]
    report = _report(
        "Receivables / payables ageing",
        mapping,
        cards=[{"label": b, "value": _rupees(pivot[b].sum()), "format": "money"} for b in present],
        tables=[{
            "title": None,
            "columns": [_col("account", "Party", "text"), *(_col(keys[b], b, "money") for b in present), _col("total", "Total", "money")],
            "rows": rows,
            "total": {"account": "Total", **{keys[b]: _rupees(pivot[b].sum()) for b in present}, "total": _rupees(pivot["total"].sum())},
        }],
    )
    report["checks"].append({"level": "info", "message": f"Aged as on {as_of:%d %b %Y} by {'due date' if basis == 'due_date' else 'entry date'}, using {source}."})
    if later:
        report["checks"].append({"level": "info", "message": f"{later} entries dated after {as_of:%d %b %Y} are left out: they had not "
                                 "happened on the as-on date. Choose a later as-on date to include them."})
    if pivot.empty:
        report["checks"].append({"level": "ok", "message": f"Nothing was outstanding on {as_of:%d %b %Y}: every party's bills "
                                 "up to that date were paid or set off."})
    return report


# --- GST -------------------------------------------------------------------------------------------


def gst_summary(frame: pd.DataFrame, mapping: dict) -> dict:
    heads = [r for r in ("cgst", "sgst", "igst", "cess") if r in mapping]
    if not heads and "tax" in mapping:
        heads = ["tax"]  # one GST column, not split into CGST/SGST/IGST
    if not heads:
        raise ReportError("Choose the CGST, SGST, IGST, Cess or total GST column (use 'Column roles').")
    data = {r: _paise(frame[mapping[r]]) for r in heads}
    for r in ("cgst", "sgst", "igst", "cess", "tax"):
        data.setdefault(r, np.zeros(len(frame), dtype=np.int64))
    tax = data["cgst"] + data["sgst"] + data["igst"] + data["tax"]
    taxable = _paise(frame[mapping["taxable"]]) if "taxable" in mapping else None
    dates = _date_col(frame, mapping) if "date" in mapping else None
    labels = {"cgst": "CGST", "sgst": "SGST", "igst": "IGST", "cess": "Cess", "tax": "GST"}
    shown = [h for h in ("cgst", "sgst", "igst", "tax") if h in heads]

    cards = []
    if taxable is not None:
        cards.append({"label": "Taxable value", "value": _rupees(taxable.sum()), "format": "money"})
    for r in heads:
        if r != "tax":
            cards.append({"label": labels[r], "value": _rupees(data[r].sum()), "format": "money"})
    cards.append({"label": "Total GST", "value": _rupees(tax.sum() + data["cess"].sum()), "format": "money"})

    def table_rows(keys: pd.DataFrame, key_text) -> list[dict]:
        return [{"key": key_text(k), "entries": int(r.entries), "taxable": _rupees(r.taxable),
                 **{h: _rupees(r[h]) for h in shown}, "total": _rupees(sum(r[h] for h in shown) + r.cess)}
                for k, r in keys.iterrows()]

    base = pd.DataFrame({"taxable": taxable if taxable is not None else 0, **{h: data[h] for h in shown},
                         "cess": data["cess"], "entries": 1})
    columns = [_col("entries", "Entries", "count"), _col("taxable", "Taxable value", "money"),
               *(_col(h, labels[h], "money") for h in shown if h != "tax"), _col("total", "Total GST", "money")]
    tables = []
    rate = None
    fraction_note = None
    if "rate" in mapping:
        rate = pd.to_numeric(frame[mapping["rate"]], errors="coerce").to_numpy(dtype="float64")
        if taxable is not None and _rates_are_fractions(rate, taxable, tax):
            rate = np.round(rate * 100, 4)
            fraction_note = (f'The "{mapping["rate"]}" column holds rates as fractions (0.18 = 18%, Excel\'s percent format), '
                             "so they were read as percentages; the tax amounts confirm it.")
    elif taxable is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            rate = np.where(taxable != 0, np.round(tax / taxable * 100, 2), np.nan)
    if rate is not None:
        by_rate = base.assign(rate=rate).groupby("rate", dropna=False).sum()
        tables.append({
            "title": "By rate" + ("" if "rate" in mapping else " (implied by tax ÷ taxable value)"),
            "columns": [_col("key", "Rate %", "text"), *columns],
            "rows": table_rows(by_rate, lambda k: "—" if pd.isna(k) else f"{k:g}"),
            "total": None,
        })
    if dates is not None:
        monthly = base.assign(month=dates.dt.to_period("M").to_numpy()).groupby("month").sum()
        tables.append({
            "title": "By month",
            "columns": [_col("key", "Month", "text"), *columns],
            "rows": table_rows(monthly, lambda m: m.strftime("%b %Y")),
            "total": None,
        })

    report = _report("GST summary", mapping, cards=cards, tables=tables)
    report["checks"] += _gst_checks(frame, mapping, data, taxable, rate, dates)
    if fraction_note:
        report["checks"].append({"level": "info", "message": fraction_note})
    return report


def _rates_are_fractions(rate: np.ndarray, taxable: np.ndarray, tax: np.ndarray) -> bool:
    """True when a rate column holds 0.18 for 18%: every rate is at most 1 and rate × 100 fits the tax amounts
    (on at least half the rows, and on more rows than reading the rates as percentages would)."""
    given = ~np.isnan(rate)
    if not given.any() or (rate[given] > 1).any() or not (rate[given] > 0).any():
        return False
    rows = given & (taxable != 0) & (tax != 0)
    if not rows.any():
        return False
    tolerance = np.maximum(100, np.abs(taxable[rows]) * 0.0005)  # same tolerance as the tax ≠ taxable × rate check
    as_fraction = np.abs(tax[rows] - np.round(taxable[rows] * rate[rows])) <= tolerance
    as_percent = np.abs(tax[rows] - np.round(taxable[rows] * rate[rows] / 100)) <= tolerance
    return int(as_fraction.sum()) * 2 >= int(rows.sum()) and as_fraction.sum() > as_percent.sum()


def _rows_of(frame: pd.DataFrame, mask: np.ndarray, mapping: dict) -> str:
    picked = frame[mask]
    if "voucher_no" in mapping:
        refs = [str(v) for v in picked[mapping["voucher_no"]].head(6)]
    else:
        refs = [f"entry {int(i)}" for i in picked["_rowid"].head(6)]
    return ", ".join(refs) + (" ..." if mask.sum() > 6 else "")


def _gst_checks(frame, mapping, data, taxable, rate, dates) -> list[dict]:
    """Register validations from the GST research (rules 1, 2, 5, 7, 10, 16, 20)."""
    checks = []

    def flag(mask: np.ndarray, message: str, level: str = "warning"):
        mask = np.asarray(mask, dtype=bool)
        if mask.any():
            checks.append({"level": level, "message": f"{int(mask.sum())} {message}: {_rows_of(frame, mask, mapping)}."})

    flag((data["igst"] != 0) & ((data["cgst"] != 0) | (data["sgst"] != 0)), "entries charge both IGST and CGST/SGST (a supply is either intra-state or inter-state)")
    if "cgst" in mapping and "sgst" in mapping:
        flag(np.abs(data["cgst"] - data["sgst"]) > 5, "entries have CGST different from SGST (they must be equal halves)")
    tax = data["cgst"] + data["sgst"] + data["igst"] + data["tax"]
    if taxable is not None and "rate" in mapping and rate is not None:
        expected = np.round(taxable * np.nan_to_num(rate) / 100)
        tolerance = np.maximum(100, np.abs(taxable) * 0.0005)  # Rs 1 or 0.05%, a design tolerance (no statutory one)
        wrong = (np.abs(tax - expected) > tolerance) & ~np.isnan(rate)
        inclusive = np.round(taxable * np.nan_to_num(rate) / (100 + np.nan_to_num(rate)))
        looks_inclusive = wrong & (np.abs(tax - inclusive) <= tolerance)
        flag(wrong & ~looks_inclusive, "entries where tax ≠ taxable value × rate (beyond ₹1)")
        flag(looks_inclusive, "entries where the 'taxable value' looks tax-inclusive (tax = value × rate ÷ (100 + rate))")
        flag((np.nan_to_num(rate) == 0) & (tax != 0), "entries at 0% rate that still carry tax")
        if dates is not None:
            on = [None if pd.isna(d) else d.date() for d in dates]
            invalid = np.array([not np.isnan(r) and r not in gst.valid_rates(d) for r, d in zip(rate, on)])
            flag(invalid, "entries use a GST rate that was not valid on their date (12% and 28% ended on 22 Sept 2025)")
    if "gstin" in mapping:
        values = frame[mapping["gstin"]].astype("string")
        problems = {v: gst.gstin_problem(v) for v in values.dropna().unique() if str(v).strip()}
        bad = values.map(lambda v: bool(problems.get(v)) if v is not None and not pd.isna(v) else False).to_numpy(dtype=bool)
        if bad.any():
            examples = "; ".join(f"{v} ({p})" for v, p in list((k, p) for k, p in problems.items() if p)[:4])
            checks.append({"level": "warning", "message": f"{int(bad.sum())} entries have an invalid GSTIN: {examples}."})
        elif problems:
            checks.append({"level": "ok", "message": f"All {len(problems)} GSTINs pass the format, state-code and check-character test."})
    if "voucher_no" in mapping:
        numbers = frame[mapping["voucher_no"]].astype("string").str.strip()
        dup = numbers.duplicated(keep=False) & numbers.notna()
        if "rate" not in mapping:  # a multi-rate invoice legitimately has several lines
            flag(dup.to_numpy(), "entries share an invoice number with another entry", level="info")
    if not checks:
        checks.append({"level": "ok", "message": "No GST data problems found by the automatic checks."})
    return checks


def gst_net_payable(output: dict[str, int], credit: dict[str, int]) -> dict:
    """Net GST payable per head after using input tax credit in the legal order (Rule 88A).

    IGST credit pays IGST first, then CGST and SGST (split to leave the most credit usable);
    CGST credit pays CGST then IGST; SGST credit pays SGST then IGST; CGST and SGST credit
    can never pay each other. Amounts in paise; cash per head is rounded to the rupee (s.170).
    """
    due = {h: output.get(h, 0) for h in ("igst", "cgst", "sgst", "cess")}
    left = {h: credit.get(h, 0) for h in ("igst", "cgst", "sgst", "cess")}
    used = {h: {} for h in left}

    def pay(source: str, target: str, amount: int | None = None):
        amount = min(left[source], due[target]) if amount is None else min(amount, left[source], due[target])
        if amount > 0:
            left[source] -= amount
            due[target] -= amount
            used[source][target] = used[source].get(target, 0) + amount

    pay("igst", "igst")
    # Spread remaining IGST credit over CGST/SGST so that each head's own credit can still be used.
    need_c = max(due["cgst"] - left["cgst"], 0)
    need_s = max(due["sgst"] - left["sgst"], 0)
    pay("igst", "cgst", need_c)
    pay("igst", "sgst", need_s)
    pay("igst", "cgst")
    pay("igst", "sgst")
    pay("cgst", "cgst")
    pay("cgst", "igst")
    pay("sgst", "sgst")
    pay("sgst", "igst")
    pay("cess", "cess")
    cash = {h: _round_rupee(due[h]) for h in due}
    return {"cash": cash, "credit_left": left, "used": used}


def _round_rupee(paise: int) -> int:
    """Nearest rupee in paise, 50 paise and above rounded up (Section 170 CGST Act); integer arithmetic only."""
    paise = int(paise)
    sign = -1 if paise < 0 else 1
    return sign * ((abs(paise) + 50) // 100 * 100)


KINDS = {
    "ledger": "Ledger",
    "day_book": "Day book",
    "trial_balance": "Trial balance",
    "profit_and_loss": "Profit & loss",
    "balance_sheet": "Balance sheet",
    "ageing": "Ageing",
    "gst": "GST summary",
}


def build(kind: str, frame: pd.DataFrame, profile: dict, *, account: str | None = None, start: date | None = None,
          end: date | None = None, as_of: date | None = None, opening_stock: float = 0.0, closing_stock: float = 0.0) -> dict:
    mapping = effective_mapping(profile)
    overrides = profile.get("classification") or {}
    if kind == "ledger":
        return ledger(frame, mapping, account, start, end)
    if kind == "day_book":
        return day_book(frame, mapping, start, end)
    if kind == "trial_balance":
        return trial_balance(frame, mapping, overrides)
    if kind == "profit_and_loss":
        return profit_and_loss(frame, mapping, overrides, opening_stock, closing_stock)
    if kind == "balance_sheet":
        return balance_sheet(frame, mapping, overrides, opening_stock, closing_stock)
    if kind == "ageing":
        return ageing(frame, mapping, as_of)
    if kind == "gst":
        return gst_summary(frame, mapping)
    raise ReportError(f"Unknown report {kind!r}.")


def gst_heads(frame: pd.DataFrame, profile: dict) -> dict[str, int]:
    """Total tax per head (paise) of a register, for the net GST payable calculation."""
    mapping = effective_mapping(profile)
    return {h: int(_paise(frame[mapping[h]]).sum()) for h in ("igst", "cgst", "sgst", "cess") if h in mapping}


# --- Formatting for check messages ---------------------------------------------------------------


def _fmt(paise: int) -> str:
    return indian(int(paise) / 100)


def _fmt_drcr(paise: int) -> str:
    if paise == 0:
        return "0.00"
    return f"{indian(abs(int(paise)) / 100)} {'Dr' if paise > 0 else 'Cr'}"
