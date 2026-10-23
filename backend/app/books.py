"""Sales and purchase registers side by side: comparison, GST, trading P&L, parties, ledgers.

Each register sheet is first normalised to the same columns (date, party, invoice number,
taxable value, CGST/SGST/IGST/cess, invoice value, item) using its column roles, with money
in whole paise so every total, difference and running balance is exact. Every report
carries checks that prove its totals add up.
"""

import re
from datetime import date

import numpy as np
import pandas as pd

from . import reports
from .duck import cached, sheet_key
from .editing import load_frame
from .formatting import indian
from .reports import AGEING_BUCKETS, ROLES, _col, _fmt, _paise, _report, _rupees

REGISTERS = {"sales": "Sales", "purchases": "Purchases"}
HEADS = ("cgst", "sgst", "igst", "cess")
_QUANTITY = re.compile(r"(^|_)(qty|quantity|pcs|pieces|nos|units|wt|weight|gr_wt|net_wt|gross_wt|fine|carat|ct|kg|gm|grams?)(_|$)")
# Columns already compared as money (or meaningless to add up, like the GST rate) are left out of
# the "columns in both files" comparison.
_MONEY_ROLES = {"debit", "credit", "amount", "taxable", "cgst", "sgst", "igst", "cess", "tax", "invoice_value", "outstanding", "rate"}
_RATE_NAME = re.compile(r"(^|_)(rate|percent|pct|tunch|purity)(_|$)")


class BookError(ValueError):
    """The books report cannot be produced. The message is shown to the user."""


def _normalise(sheet: dict) -> tuple[pd.DataFrame, list[dict], dict[str, tuple[str, pd.Series]]]:
    """(standard frame, notes, other number columns) for one register sheet."""
    profile = sheet["profile"]
    mapping = reports.effective_mapping(profile)
    frame = load_frame(sheet)
    name = f'{REGISTERS[sheet["register"]]} · {sheet["sheet_name"]}'
    notes: list[dict] = []
    out = pd.DataFrame({"register": sheet["register"], "source": sheet["sheet_name"], "rowid": frame["_rowid"].to_numpy()})

    out["date"] = pd.to_datetime(frame[mapping["date"]], errors="coerce").to_numpy() if "date" in mapping else pd.NaT
    if "date" not in mapping:
        notes.append({"level": "warning", "message": f"{name}: no date column chosen, so monthly figures and ageing leave it out."})
    for role, column in (("party", "account"), ("invoice_no", "voucher_no"), ("gstin", "gstin"), ("item", "item")):
        if column in mapping:
            values = frame[mapping[column]].astype("string").str.strip()
            out[role] = values.fillna("(blank)" if role in ("party", "item") else "").to_numpy()
        else:
            out[role] = "(not given)" if role in ("party", "item") else ""
    if "account" not in mapping:
        notes.append({"level": "warning", "message": f"{name}: no customer/supplier column chosen; party reports group everything as '(not given)'."})

    for head in HEADS:
        out[head] = _paise(frame[mapping[head]]) if head in mapping else 0
    split = any(h in mapping for h in ("cgst", "sgst", "igst"))
    out["gst_unsplit"] = _paise(frame[mapping["tax"]]) if "tax" in mapping and not split else 0
    out["tax"] = out["cgst"] + out["sgst"] + out["igst"] + out["gst_unsplit"]

    value_col = mapping.get("invoice_value") or mapping.get("amount")
    if "taxable" in mapping:
        out["taxable"] = _paise(frame[mapping["taxable"]])
        out["invoice_value"] = _paise(frame[value_col]) if value_col else out["taxable"] + out["tax"] + out["cess"]
        if not value_col:
            notes.append({"level": "info", "message": f"{name}: invoice value = taxable value + GST (no invoice-total column)."})
    elif value_col:
        out["invoice_value"] = _paise(frame[value_col])
        out["taxable"] = out["invoice_value"] - out["tax"] - out["cess"]
        notes.append({"level": "info", "message": f'{name}: no taxable-value column, so taxable value = "{value_col}" − GST.'})
    else:
        raise BookError(f"{name}: choose its taxable value or invoice total column (open the sheet → Reports → Column roles).")

    if "outstanding" in mapping:
        out["pending"] = _paise(frame[mapping["outstanding"]])

    labels = {c["name"]: c["label"] for c in profile["columns"]}
    used = {mapping[r] for r in mapping if r in _MONEY_ROLES}
    identifiers = {c["name"] for c in profile["columns"] if c.get("role") == "identifier"}
    others = {
        c["name"]: (labels[c["name"]], pd.to_numeric(frame[c["name"]], errors="coerce").reset_index(drop=True))
        for c in profile["columns"]
        if c["kind"] == "number" and c["name"] not in used and c["name"] not in identifiers and c["non_null"] > 0
        and not _RATE_NAME.search(c["name"])
    }
    return out, notes, others


class Books:
    """All register sheets of a book, normalised and stacked."""

    def __init__(self, book: dict):
        self.book = book
        frames, self.notes = [], []
        self.sheets = {"sales": [], "purchases": []}
        parts: dict[str, list[tuple[str, int, dict]]] = {"sales": [], "purchases": []}  # (sheet name, rows, other columns)
        for sheet in book["sheets"]:
            if sheet["register"] not in REGISTERS:
                continue
            frame, notes, others = _normalise(sheet)
            frames.append(frame)
            self.notes += notes
            self.sheets[sheet["register"]].append(sheet)
            parts[sheet["register"]].append((sheet["sheet_name"], len(frame), others))
        if not self.sheets["sales"] or not self.sheets["purchases"]:
            missing = " and ".join(REGISTERS[r] for r in REGISTERS if not self.sheets[r])
            raise BookError(f"This set has no {missing} sheet. Mark one under 'Sheets in this set'.")
        self.others = {register: self._stack_others(sheets) for register, sheets in parts.items()}
        common = set(self.others["sales"]) & set(self.others["purchases"])
        self.lacking = {register: {} for register in REGISTERS}  # register → column → sheets without it
        for register, sheets in parts.items():
            for col in sorted(common):
                lacking = [name for name, _, others in sheets if col not in others]
                if lacking:
                    self.lacking[register][col] = lacking
                    stock = ("; in the stock summary and gross profit, the items on those entries have an incomplete quantity "
                             "in hand and closing value" if _QUANTITY.search(col) else "")
                    self.notes.append({"level": "warning", "message": (
                        f'{REGISTERS[register]}: {", ".join(lacking)} {"has" if len(lacking) == 1 else "have"} no '
                        f'"{self.others[register][col][0]}" column, so {"its" if len(lacking) == 1 else "their"} entries count as '
                        f"nil in that column's totals{stock}. Add the column to {'that sheet' if len(lacking) == 1 else 'those sheets'} "
                        "for full figures.")})
        self.all = pd.concat(frames, ignore_index=True)
        self.sales = self.all[self.all.register == "sales"]
        self.purchases = self.all[self.all.register == "purchases"]

    @staticmethod
    def _stack_others(sheets: list[tuple[str, int, dict]]) -> dict[str, tuple[str, pd.Series]]:
        """Each extra number column over all the register's rows, in sheet order; blank (NaN) for a sheet without it."""
        stacked = {}
        for col in dict.fromkeys(col for _, _, others in sheets for col in others):
            label = next(others[col][0] for _, _, others in sheets if col in others)
            pieces = [others[col][1] if col in others else pd.Series(np.nan, index=range(rows), dtype="float64")
                      for _, rows, others in sheets]
            stacked[col] = (label, pd.concat(pieces, ignore_index=True))
        return stacked

    def gst_checks(self) -> list[dict]:
        checks = []
        for register, sheets in self.sheets.items():
            for sheet in sheets:
                mapping = reports.effective_mapping(sheet["profile"])
                if not any(r in mapping for r in ("cgst", "sgst", "igst", "tax")):
                    continue
                try:
                    summary = reports.gst_summary(load_frame(sheet), mapping)
                except reports.ReportError:
                    continue
                for check in summary["checks"]:
                    checks.append({**check, "message": f'{REGISTERS[register]} · {sheet["sheet_name"]}: {check["message"]}'})
        return checks


def _net_gst(books: Books) -> dict:
    output = {h: int(books.sales[h].sum()) for h in ("igst", "cgst", "sgst", "cess")}
    credit = {h: int(books.purchases[h].sum()) for h in ("igst", "cgst", "sgst", "cess")}
    unsplit = int(books.sales["gst_unsplit"].sum()), int(books.purchases["gst_unsplit"].sum())
    result = reports.gst_net_payable(output, credit)
    return {"output": output, "credit": credit, "unsplit": unsplit, **result}


def _pct(part: int, whole: int) -> float | None:
    return round(part / whole, 6) if whole else None


def _months(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame["date"]).dt.to_period("M")


# --- Reports ---------------------------------------------------------------------------------


def compare(books: Books) -> dict:
    s, p = books.sales, books.purchases
    net = _net_gst(books)
    s_tax, p_tax = int(s.taxable.sum()), int(p.taxable.sum())
    s_gst, p_gst = int(s.tax.sum() + s.cess.sum()), int(p.tax.sum() + p.cess.sum())
    cash = sum(net["cash"].values())

    lines = [("Entries", len(s), len(p), "count")]
    lines.append(("Taxable value", s_tax, p_tax, "money"))
    for head, label in (("cgst", "CGST"), ("sgst", "SGST"), ("igst", "IGST"), ("cess", "Cess"), ("gst_unsplit", "GST (not split)")):
        if s[head].any() or p[head].any():
            lines.append((label, int(s[head].sum()), int(p[head].sum()), "money"))
    lines.append(("Total GST", s_gst, p_gst, "money"))
    lines.append(("Invoice value", int(s.invoice_value.sum()), int(p.invoice_value.sum()), "money"))
    summary_rows = [
        {"metric": label, "sales": a if fmt == "count" else _rupees(a), "purchases": b if fmt == "count" else _rupees(b),
         "difference": (a - b) if fmt == "count" else _rupees(a - b)}
        for label, a, b, fmt in lines
    ]

    tables = [{
        "title": "Sales vs purchases",
        "columns": [_col("metric", "", "text"), _col("sales", "Sales", "money"), _col("purchases", "Purchases", "money"),
                    _col("difference", "Sales − purchases", "money")],
        "rows": summary_rows,
        "total": None,
    }]

    if s.date.notna().any() or p.date.notna().any():
        months = pd.DataFrame({
            "month": _months(books.all), "register": books.all.register,
            "taxable": books.all.taxable, "gst": books.all.tax + books.all.cess,
        }).dropna(subset=["month"])
        pivot = months.pivot_table(index="month", columns="register", values=["taxable", "gst"], aggfunc="sum", fill_value=0)
        rows = []
        for month in pivot.index:
            st, pt = int(pivot.get(("taxable", "sales"), pd.Series(0, index=pivot.index))[month]), int(pivot.get(("taxable", "purchases"), pd.Series(0, index=pivot.index))[month])
            sg, pg = int(pivot.get(("gst", "sales"), pd.Series(0, index=pivot.index))[month]), int(pivot.get(("gst", "purchases"), pd.Series(0, index=pivot.index))[month])
            rows.append({"month": month.strftime("%b %Y"), "sales": _rupees(st), "purchases": _rupees(pt), "difference": _rupees(st - pt),
                         "output_gst": _rupees(sg), "input_gst": _rupees(pg), "gst_difference": _rupees(sg - pg)})
        tables.append({
            "title": "Month by month",
            "columns": [_col("month", "Month", "text"), _col("sales", "Sales (taxable)", "money"), _col("purchases", "Purchases (taxable)", "money"),
                        _col("difference", "Difference", "money"), _col("output_gst", "Output GST", "money"),
                        _col("input_gst", "Input GST", "money"), _col("gst_difference", "Output − input GST", "money")],
            "rows": rows,
            "total": None,
        })

    common = sorted(set(books.others["sales"]) & set(books.others["purchases"]))
    if common:
        rows = []
        for col in common:
            label, sold = books.others["sales"][col]
            _, bought = books.others["purchases"][col]
            sold_sum, bought_sum = float(np.round(sold.sum(), 6)), float(np.round(bought.sum(), 6))
            rows.append({"column": label, "bought": bought_sum, "sold": sold_sum, "balance": round(bought_sum - sold_sum, 6)})
        tables.append({
            "title": "Columns in both files (e.g. quantities, weights)",
            "columns": [_col("column", "Column", "text"), _col("bought", "Purchased", "number"), _col("sold", "Sold", "number"),
                        _col("balance", "Purchased − sold", "number")],
            "rows": rows,
            "total": None,
        })

    items = _item_table(books)
    if items:
        tables.append(items)

    parties_both = sorted(set(s.party) & set(p.party) - {"(blank)", "(not given)"})
    if parties_both:
        rows = []
        for party in parties_both:
            sold = int(s.loc[s.party == party, "invoice_value"].sum())
            bought = int(p.loc[p.party == party, "invoice_value"].sum())
            rows.append({"party": party, "sold": _rupees(sold), "bought": _rupees(bought), "net": _rupees(sold - bought)})
        tables.append({
            "title": "Parties who are both customer and supplier",
            "columns": [_col("party", "Party", "text"), _col("sold", "Sold to them", "money"), _col("bought", "Bought from them", "money"),
                        _col("net", "Net (Dr = they owe you)", "drcr")],
            "rows": rows,
            "total": None,
        })

    cards = [
        {"label": "Sales (taxable)", "value": _rupees(s_tax), "format": "money"},
        {"label": "Purchases (taxable)", "value": _rupees(p_tax), "format": "money"},
        {"label": "Sales − purchases", "value": _rupees(s_tax - p_tax), "format": "money"},
        {"label": "Margin on sales", "value": _pct(s_tax - p_tax, s_tax) or 0, "format": "percent"},
        {"label": "Output GST", "value": _rupees(s_gst), "format": "money"},
        {"label": "Input GST", "value": _rupees(p_gst), "format": "money"},
        {"label": "GST payable in cash", "value": _rupees(cash), "format": "money"},
    ]
    report = _report("Sales vs purchases", {}, cards=cards, tables=tables)
    report["checks"] += _consistency(books)
    report["checks"].append({
        "level": "info",
        "message": "Sales − purchases is before opening/closing stock and expenses; see Gross profit for the figure with stock.",
    })
    if items and any(v < 0 for row in items["rows"] for k, v in row.items() if k.startswith("bal_")):
        report["checks"].append({
            "level": "info",
            "message": "A negative item balance means more was sold than bought in this period: sold from opening stock, "
            "or a purchase bill is missing.",
        })
    problems = [c for c in books.gst_checks() if c["level"] == "warning"]
    if problems:
        report["checks"].append({"level": "warning", "message": f"{len(problems)} GST data problems found in the registers; see the GST tab."})
    report["checks"] += books.notes
    return report


def _item_table(books: Books) -> dict | None:
    s, p = books.sales, books.purchases
    if (s.item == "(not given)").all() or (p.item == "(not given)").all():
        return None
    quantity_cols = [c for c in sorted(set(books.others["sales"]) & set(books.others["purchases"])) if _QUANTITY.search(c)][:2]
    sold = s.groupby("item").agg(sold_value=("taxable", "sum"), sold_entries=("taxable", "size"))
    bought = p.groupby("item").agg(bought_value=("taxable", "sum"), bought_entries=("taxable", "size"))
    table = bought.join(sold, how="outer").fillna(0)
    labels = {}
    for col in quantity_cols:
        labels[col] = books.others["sales"][col][0]
        # The extra columns were stacked in the same sheet order as the register rows.
        sold_q = pd.Series(books.others["sales"][col][1].to_numpy(), index=s.index).groupby(s.item).sum()
        bought_q = pd.Series(books.others["purchases"][col][1].to_numpy(), index=p.index).groupby(p.item).sum()
        table[f"bought_{col}"] = bought_q.reindex(table.index).fillna(0)
        table[f"sold_{col}"] = sold_q.reindex(table.index).fillna(0)
        table[f"bal_{col}"] = table[f"bought_{col}"] - table[f"sold_{col}"]
    table = table.sort_values("sold_value", ascending=False)
    columns = [_col("item", "Item", "text"), _col("bought_value", "Purchased value", "money"), _col("sold_value", "Sold value", "money"),
               _col("difference", "Sold − purchased", "money")]
    for col in quantity_cols:
        label = labels[col]
        columns += [_col(f"bought_{col}", f"{label} purchased", "number"), _col(f"sold_{col}", f"{label} sold", "number"),
                    _col(f"bal_{col}", f"{label} balance", "number")]
    rows = []
    for item, r in table.iterrows():
        row = {"item": item, "bought_value": _rupees(r.bought_value), "sold_value": _rupees(r.sold_value),
               "difference": _rupees(int(r.sold_value) - int(r.bought_value))}
        for col in quantity_cols:
            row |= {f"bought_{col}": round(float(r[f"bought_{col}"]), 6), f"sold_{col}": round(float(r[f"sold_{col}"]), 6),
                    f"bal_{col}": round(float(r[f"bal_{col}"]), 6)}
        rows.append(row)
    return {"title": "Item-wise: purchased vs sold", "columns": columns, "rows": rows, "total": None}


def _consistency(books: Books) -> list[dict]:
    """Prove the combined totals equal the sum of the sheets, and months add up to the totals."""
    checks = []
    for register, label in REGISTERS.items():
        part = books.all[books.all.register == register]
        by_sheet = part.groupby("source")["invoice_value"].sum()
        if int(by_sheet.sum()) == int(part.invoice_value.sum()):
            names = ", ".join(f"{k} {_fmt(int(v))}" for k, v in by_sheet.items())
            checks.append({"level": "ok", "message": f"{label} invoice value {_fmt(int(part.invoice_value.sum()))} = sum of sheets ({names})."})
        undated = int(part.date.isna().sum())
        if undated:
            checks.append({"level": "warning", "message": f"{undated} {label.lower()} entries have no date and are missing from the monthly table."})
        if (part.taxable < 0).any():
            checks.append({"level": "info", "message": f"{int((part.taxable < 0).sum())} {label.lower()} entries are negative (credit/debit notes); they reduce the totals."})
    return checks


def gst_report(books: Books) -> dict:
    net = _net_gst(books)
    heads = [h for h in ("igst", "cgst", "sgst", "cess") if net["output"][h] or net["credit"][h]]
    rows = [{"head": h.upper(), "output": _rupees(net["output"][h]), "input": _rupees(net["credit"][h]),
             "cash": _rupees(net["cash"][h]), "carried": _rupees(net["credit_left"][h])} for h in heads]
    tables = [{
        "title": "Net GST payable (output tax − input tax credit)",
        "columns": [_col("head", "Tax", "text"), _col("output", "Output tax (sales)", "money"), _col("input", "Input credit (purchases)", "money"),
                    _col("cash", "Pay in cash (rounded)", "money"), _col("carried", "Credit carried forward", "money")],
        "rows": rows,
        "total": {"head": "Total", "output": _rupees(sum(net["output"].values())), "input": _rupees(sum(net["credit"].values())),
                  "cash": _rupees(sum(net["cash"].values())), "carried": _rupees(sum(net["credit_left"].values()))},
    }]
    used = [f"{src.upper()} credit → {dst.upper()}: {_fmt(v)}" for src, dsts in net["used"].items() for dst, v in dsts.items()]
    if books.all.date.notna().any():
        frame = pd.DataFrame({"month": _months(books.all), "register": books.all.register, "gst": books.all.tax + books.all.cess}).dropna(subset=["month"])
        pivot = frame.pivot_table(index="month", columns="register", values="gst", aggfunc="sum", fill_value=0)
        tables.append({
            "title": "Month by month (before credit carried between months)",
            "columns": [_col("month", "Month", "text"), _col("output", "Output GST", "money"), _col("input", "Input GST", "money"),
                        _col("net", "Output − input", "money")],
            "rows": [{"month": m.strftime("%b %Y"), "output": _rupees(int(pivot.get("sales", pd.Series(0, index=pivot.index))[m])),
                      "input": _rupees(int(pivot.get("purchases", pd.Series(0, index=pivot.index))[m])),
                      "net": _rupees(int(pivot.get("sales", pd.Series(0, index=pivot.index))[m]) - int(pivot.get("purchases", pd.Series(0, index=pivot.index))[m]))}
                     for m in pivot.index],
            "total": None,
        })
    cards = [
        {"label": "Output GST", "value": _rupees(sum(net["output"].values())), "format": "money"},
        {"label": "Input tax credit", "value": _rupees(sum(net["credit"].values())), "format": "money"},
        {"label": "Pay in cash", "value": _rupees(sum(net["cash"].values())), "format": "money"},
        {"label": "Credit carried forward", "value": _rupees(sum(net["credit_left"].values())), "format": "money"},
    ]
    report = _report("GST: output vs input", {}, cards=cards, tables=tables)
    report["checks"].append({
        "level": "info",
        "message": "Credit is used in the legal order (Rule 88A): IGST credit first; CGST and SGST credit never pay each other; "
        "cash per head is rounded to the rupee (Section 170). " + ("Used: " + "; ".join(used) + "." if used else ""),
    })
    if any(net["unsplit"]):
        report["checks"].append({"level": "warning", "message": "Some GST is in a single column not split into CGST/SGST/IGST, so it is not in the "
                                 "head-wise payable. Map the CGST/SGST/IGST columns for an exact figure."})
    report["checks"].append({"level": "info", "message": "Input credit assumes every purchase invoice is eligible (not blocked under "
                             "Section 17(5)) and appears in GSTR-2B. Check before filing."})
    report["checks"] += books.gst_checks()
    return report


_MEASURE_PRIORITY = ["qty", "quantity", "pcs", "pieces", "nos", "units", "net_wt", "gr_wt", "gross_wt", "weight", "wt", "fine"]


def _stock(books: Books, measure: str | None) -> tuple[pd.DataFrame | None, str | None, list[str]]:
    """Per item: quantity bought and sold, weighted-average cost and closing stock value (paise)."""
    s, p = books.sales, books.purchases
    if (s.item == "(not given)").all() or (p.item == "(not given)").all():
        return None, None, []
    common = sorted(set(books.others["sales"]) & set(books.others["purchases"]))
    measures = [c for c in common if _QUANTITY.search(c)]
    if not measures:
        return None, None, []
    if measure not in measures:
        measure = next((m for name in _MEASURE_PRIORITY for m in measures if m == name), measures[0])
    sold = pd.Series(books.others["sales"][measure][1].to_numpy(), index=s.index)
    bought = pd.Series(books.others["purchases"][measure][1].to_numpy(), index=p.index)
    # AS-2 average cost = cost of the units counted ÷ those units, so a bill with no quantity (a blank cell, or a
    # sheet without the column) adds to neither.
    table = pd.DataFrame({
        "bought_q": bought.groupby(p.item).sum(), "bought_v": p.taxable.where(bought.notna(), 0).groupby(p.item).sum(),
        "sold_q": sold.groupby(s.item).sum(), "sold_v": s.groupby("item").taxable.sum(),
        "bought_gap": bought.isna().groupby(p.item).sum(), "sold_gap": sold.isna().groupby(s.item).sum(),
    }).fillna(0)
    # Such entries leave the item's stock incomplete when their sheet has no such column, or when other entries of
    # the item have a quantity (an item never given one, like freight, is not stock).
    rows = pd.DataFrame({
        "item": np.concatenate([p.item.to_numpy(), s.item.to_numpy()]),
        "counted": np.concatenate([bought.notna().to_numpy(), sold.notna().to_numpy()]),
        "sheetless": np.concatenate([p.source.isin(books.lacking["purchases"].get(measure, [])).to_numpy(),
                                     s.source.isin(books.lacking["sales"].get(measure, [])).to_numpy()]),
    })
    flagged = rows.groupby("item")[["counted", "sheetless"]].any().any(axis=1).reindex(table.index, fill_value=False)
    table.loc[~flagged, ["bought_gap", "sold_gap"]] = 0
    table["closing_q"] = table.bought_q - table.sold_q
    with np.errstate(divide="ignore", invalid="ignore"):
        table["avg_cost"] = np.where(table.bought_q > 0, table.bought_v / table.bought_q, 0)  # paise per unit
    table["closing_v"] = np.where(table.closing_q > 0, np.round(table.closing_q * table.avg_cost), 0).astype("int64")
    table["cogs"] = np.round(np.minimum(table.sold_q, table.bought_q).clip(lower=0) * table.avg_cost).astype("int64")
    return table.sort_values("closing_v", ascending=False), measure, measures


def _stock_gaps(books: Books, table: pd.DataFrame, measure: str) -> str | None:
    """Which items' stock is incomplete because some of their entries have no quantity, and why; None if none."""
    gaps = table[(table.bought_gap > 0) | (table.sold_gap > 0)]
    if gaps.empty:
        return None
    label = books.others["sales"][measure][0]
    bought, sold = int(gaps.bought_gap.sum()), int(gaps.sold_gap.sum())
    counts = " and ".join(f"{n} {kind} entr{'y' if n == 1 else 'ies'}" for n, kind in ((bought, "purchase"), (sold, "sales")) if n)
    sheets = "; ".join(f'{REGISTERS[r]}: {", ".join(names)} {"has" if len(names) == 1 else "have"} no "{label}" column'
                       for r in REGISTERS if (names := books.lacking[r].get(measure)))
    names = ", ".join(gaps.index[:6]) + (f" and {len(gaps) - 6} more" if len(gaps) > 6 else "")
    return (f"{counts} of {names} {'has' if bought + sold == 1 else 'have'} no {label}{f' ({sheets})' if sheets else ''}, so "
            f"{'its' if len(gaps) == 1 else 'their'} {label} in hand and closing value are incomplete: purchases without a {label} "
            f"are left out of the average cost, and sales without one are not taken out of stock. Fill in the {label} on those "
            f"entries{' or add the column to those sheets' if sheets else ''} for a full figure.")


def stock_summary(books: Books, measure: str | None) -> dict:
    table, measure, measures = _stock(books, measure)
    if table is None:
        raise BookError("A stock summary needs an item column and a quantity/weight column in both registers "
                        "(set them under each file's Reports → Column roles).")
    label = books.others["sales"][measure][0]
    rows = [{"item": item, "bought": round(float(r.bought_q), 6), "sold": round(float(r.sold_q), 6), "closing": round(float(r.closing_q), 6),
             "avg_cost": round(float(r.avg_cost) / 100, 4) if r.bought_q else None, "value": _rupees(int(r.closing_v)),
             "_kind": None} for item, r in table.iterrows()]
    total = int(table.closing_v.sum())
    negative = table[table.closing_q < 0]
    report = _report(f"Stock summary by {label}", {}, cards=[
        {"label": "Closing stock (at cost)", "value": _rupees(total), "format": "money"},
        {"label": "Items", "value": len(table), "format": "count"},
        {"label": "Items sold beyond purchases", "value": len(negative), "format": "count"},
    ], tables=[{
        "title": None,
        "columns": [_col("item", "Item", "text"), _col("bought", f"{label} purchased", "number"), _col("sold", f"{label} sold", "number"),
                    _col("closing", f"{label} in hand", "number"), _col("avg_cost", f"Average cost per {label}", "money"),
                    _col("value", "Closing value", "money")],
        "rows": rows,
        "total": {"item": "Total", "value": _rupees(total)},
    }], options={"measures": [{"name": m, "label": books.others["sales"][m][0]} for m in measures]})
    report["checks"].append({"level": "info", "message": "Valued at cost under AS-2: weighted-average purchase cost (taxable value, "
                             "excluding recoverable GST) × quantity in hand. Opening stock is not in the registers, so it is taken as nil."})
    if gaps := _stock_gaps(books, table, measure):
        report["checks"].append({"level": "warning", "message": gaps})
    if len(negative):
        report["checks"].append({"level": "warning", "message": f"{len(negative)} items were sold beyond what was purchased "
                                 f"({', '.join(negative.index[:6])}); they came from opening stock or a purchase bill is missing, and are valued at 0."})
    report["checks"].append({"level": "info", "message": "Cost must not exceed what the stock can be sold for (net realisable value); "
                             "write down slow or damaged items yourself."})
    return report


def profit_and_loss(books: Books, opening_stock: float, closing_stock: float | None) -> dict:
    sales, purchases = int(books.sales.taxable.sum()), int(books.purchases.taxable.sum())
    computed_note = gaps = None
    if closing_stock is None:
        table, measure, _ = _stock(books, None)
        closing_stock = (int(table.closing_v.sum()) / 100) if table is not None else 0.0
        if table is not None:
            computed_note = (f"Closing stock {_fmt(int(table.closing_v.sum()))} is from the Stock summary (weighted-average cost by "
                             f"{books.others['sales'][measure][0]}). Enter a figure above to override it.")
            gaps = _stock_gaps(books, table, measure)
    open_p, close_p = int(round(opening_stock * 100)), int(round(closing_stock * 100))
    gross = sales + close_p - open_p - purchases
    rows = [
        {"item": "Sales (taxable value, excluding GST)", "amount": _rupees(sales), "_kind": "group"},
        {"item": "Add: Closing stock", "amount": _rupees(close_p)},
        {"item": "Less: Opening stock", "amount": _rupees(-open_p)},
        {"item": "Less: Purchases (taxable value, excluding GST)", "amount": _rupees(-purchases), "_kind": "group"},
        {"item": "Gross profit" if gross >= 0 else "Gross loss", "amount": _rupees(gross), "_kind": "total"},
    ]
    report = _report(
        "Trading account (gross profit)",
        {},
        cards=[
            {"label": "Sales", "value": _rupees(sales), "format": "money"},
            {"label": "Cost of goods sold", "value": _rupees(open_p + purchases - close_p), "format": "money"},
            {"label": "Gross profit" if gross >= 0 else "Gross loss", "value": _rupees(gross), "format": "money"},
            {"label": "Gross margin", "value": _pct(gross, sales) or 0, "format": "percent"},
        ],
        tables=[{"title": None, "columns": [_col("item", "Particulars", "text"), _col("amount", "Amount", "money")], "rows": rows, "total": None}],
    )
    report["checks"].append({"level": "ok" if sales - (open_p + purchases - close_p) == gross else "warning",
                             "message": f"Sales {_fmt(sales)} − cost of goods sold {_fmt(open_p + purchases - close_p)} = gross profit {_fmt(gross)}."})
    report["checks"].append({"level": "info", "message": "GST is left out: tax collected on sales is owed to the government and "
                             "tax paid on purchases is claimed back, so neither is income or expense."})
    if computed_note:
        report["checks"].append({"level": "info", "message": computed_note})
        if gaps:
            report["checks"].append({"level": "warning", "message": "Closing stock, and so gross profit, may be misstated: " + gaps})
    elif not closing_stock:
        report["checks"].append({"level": "info", "message": "Closing stock is 0. If goods bought are still unsold, enter their value, "
                                 "otherwise gross profit is understated."})
    report["checks"].append({"level": "info", "message": "Net profit also needs expenses such as rent and salaries; upload a ledger or "
                             "expense sheet for those."})
    return report


def parties(books: Books) -> dict:
    tables = []
    cards = []
    for register, title, label in (("sales", "Customers (receivable from sales)", "Sold"), ("purchases", "Suppliers (payable for purchases)", "Bought")):
        part = books.all[books.all.register == register]
        g = part.groupby("party").agg(entries=("invoice_value", "size"), value=("invoice_value", "sum"), last=("date", "max")).sort_values("value", ascending=False)
        rows = [{"party": name, "entries": int(r["entries"]), "value": _rupees(r["value"]),
                 "last": None if pd.isna(r["last"]) else pd.Timestamp(r["last"]).strftime("%Y-%m-%d")} for name, r in g.iterrows()]
        tables.append({
            "title": title,
            "columns": [_col("party", "Party", "text"), _col("entries", "Invoices", "count"), _col("value", f"{label} (invoice value)", "money"),
                        _col("last", "Last invoice", "date")],
            "rows": rows,
            "total": {"party": "Total", "entries": int(g["entries"].sum()), "value": _rupees(int(g["value"].sum()))},
        })
        cards.append({"label": f"{'Customers' if register == 'sales' else 'Suppliers'}", "value": len(g), "format": "count"})
    report = _report("Customers and suppliers", {}, cards=cards, tables=tables,
                     options={"parties": sorted(set(books.all.party) - {"(not given)"})})
    report["checks"].append({"level": "info", "message": "Amounts are full invoice values. Payments are not in these registers, so "
                             "they show what was billed, not what is still unpaid."})
    return report


def party_ledger(books: Books, party: str | None) -> dict:
    options = {"parties": sorted(set(books.all.party) - {"(not given)"})}
    if not party:
        report = _report("Party ledger", {}, options=options)
        report["checks"].append({"level": "info", "message": "Choose a party to see all their sales and purchase invoices with a running balance."})
        return report
    entries = books.all[books.all.party == party].assign(_when=lambda f: pd.to_datetime(f["date"])).sort_values(["_when", "register", "rowid"])
    if entries.empty:
        raise BookError(f'No entries for "{party}".')
    debit = np.where(entries.register == "sales", entries.invoice_value, 0)
    credit = np.where(entries.register == "purchases", entries.invoice_value, 0)
    running = np.cumsum(debit - credit)
    rows = [
        {"date": None if pd.isna(w) else w.strftime("%Y-%m-%d"), "type": "Sales invoice" if reg == "sales" else "Purchase bill",
         "invoice": inv or None, "debit": _rupees(d) or None, "credit": _rupees(c) or None, "balance": _rupees(b)}
        for w, reg, inv, d, c, b in zip(entries._when, entries.register, entries.invoice_no, debit, credit, running)
    ]
    closing = int(running[-1])
    report = _report(
        f"Ledger: {party}",
        {},
        options=options,
        cards=[
            {"label": "Sales to them (Dr)", "value": _rupees(int(debit.sum())), "format": "money"},
            {"label": "Purchases from them (Cr)", "value": _rupees(int(credit.sum())), "format": "money"},
            {"label": "Balance", "value": _rupees(closing), "format": "drcr"},
        ],
        tables=[{
            "title": None,
            "columns": [_col("date", "Date", "date"), _col("type", "Type", "text"), _col("invoice", "Invoice", "text"),
                        _col("debit", "Debit", "money"), _col("credit", "Credit", "money"), _col("balance", "Balance", "drcr")],
            "rows": rows,
            "total": {"type": "Total", "debit": _rupees(int(debit.sum())), "credit": _rupees(int(credit.sum())), "balance": _rupees(closing)},
        }],
    )
    report["checks"].append({"level": "ok" if int(debit.sum()) - int(credit.sum()) == closing else "warning",
                             "message": f"Debits {_fmt(int(debit.sum()))} − credits {_fmt(int(credit.sum()))} = balance {_fmt(abs(closing))} "
                             f"{'Dr (they owe you)' if closing > 0 else 'Cr (you owe them)' if closing < 0 else ''}."})
    report["checks"].append({"level": "info", "message": "Payments and receipts are not in the registers, so this is the billed balance."})
    return report


def ageing(books: Books, as_of: date | None) -> dict:
    as_of = as_of or date.today()
    labels = [f"{lo}-{hi} days" if hi else f"Over {lo - 1} days" for lo, hi in AGEING_BUCKETS]
    tables, cards = [], []
    for register, title in (("sales", "Receivables (customers)"), ("purchases", "Payables (suppliers)")):
        part = books.all[books.all.register == register]
        pending = part["pending"].fillna(part.invoice_value) if "pending" in part else part.invoice_value
        days = (pd.Timestamp(as_of) - pd.to_datetime(part.date)).dt.days
        bucket = pd.Series("No date", index=part.index)
        for (lo, hi), label in zip(AGEING_BUCKETS, labels):
            bucket[((days >= lo) & ((days <= hi) if hi else True)).fillna(False)] = label
        bucket[(days < 0).fillna(False)] = "Not yet due"  # dated after the as-on date
        frame = pd.DataFrame({"party": part.party, "bucket": bucket, "pending": pending.fillna(0).astype("int64")})
        pivot = frame.pivot_table(index="party", columns="bucket", values="pending", aggfunc="sum", fill_value=0)
        present = [b for b in ["Not yet due", *labels, "No date"] if b in pivot.columns]
        pivot = pivot[present].assign(total=lambda t: t.sum(axis=1)).sort_values("total", ascending=False)
        keys = {b: f"b{i}" for i, b in enumerate(present)}
        tables.append({
            "title": title,
            "columns": [_col("party", "Party", "text"), *(_col(keys[b], b, "money") for b in present), _col("total", "Total", "money")],
            "rows": [{"party": n, **{keys[b]: _rupees(r[b]) or None for b in present}, "total": _rupees(r["total"])} for n, r in pivot.iterrows()],
            "total": {"party": "Total", **{keys[b]: _rupees(int(pivot[b].sum())) for b in present}, "total": _rupees(int(pivot["total"].sum()))},
        })
        cards.append({"label": title.split(" (")[0], "value": _rupees(int(pivot["total"].sum())), "format": "money"})
    report = _report("Ageing", {}, cards=cards, tables=tables)
    report["checks"].append({"level": "info", "message": f"Aged as on {as_of:%d %b %Y} by invoice date. Without a pending-amount column every "
                             "invoice is treated as unpaid; map a pending/outstanding column for real dues."})
    return report


def day_book(books: Books) -> dict:
    frame = books.all.assign(day=pd.to_datetime(books.all.date).dt.normalize()).dropna(subset=["day"])
    pivot = frame.pivot_table(index="day", columns="register", values="invoice_value", aggfunc=["sum", "size"], fill_value=0)
    get = lambda kind, reg: pivot.get((kind, reg), pd.Series(0, index=pivot.index))  # noqa: E731
    rows = [{"date": d.strftime("%Y-%m-%d"), "sales_n": int(get("size", "sales")[d]), "sales": _rupees(int(get("sum", "sales")[d])),
             "purchases_n": int(get("size", "purchases")[d]), "purchases": _rupees(int(get("sum", "purchases")[d])),
             "net": _rupees(int(get("sum", "sales")[d]) - int(get("sum", "purchases")[d]))} for d in pivot.index]
    return _report("Day book: sales and purchases", {}, tables=[{
        "title": None,
        "columns": [_col("date", "Date", "date"), _col("sales_n", "Sales invoices", "count"), _col("sales", "Sales value", "money"),
                    _col("purchases_n", "Purchase bills", "count"), _col("purchases", "Purchase value", "money"), _col("net", "Sales − purchases", "money")],
        "rows": rows,
        "total": {"date": "Total", "sales": _rupees(int(get("sum", "sales").sum())), "purchases": _rupees(int(get("sum", "purchases").sum())),
                  "net": _rupees(int(get("sum", "sales").sum() - get("sum", "purchases").sum()))},
    }])


KINDS = {
    "compare": "Comparison",
    "gst": "GST (output vs input)",
    "stock": "Stock summary",
    "profit_and_loss": "Gross profit",
    "parties": "Customers & suppliers",
    "party_ledger": "Party ledger",
    "ageing": "Ageing",
    "day_book": "Day book",
}


def build(kind: str, book: dict, *, party: str | None = None, as_of: date | None = None,
          opening_stock: float = 0.0, closing_stock: float | None = None, measure: str | None = None) -> dict:
    books = Books(book)
    if kind == "compare":
        return compare(books)
    if kind == "gst":
        return gst_report(books)
    if kind == "stock":
        return stock_summary(books, measure)
    if kind == "profit_and_loss":
        return profit_and_loss(books, opening_stock, closing_stock)
    if kind == "parties":
        return parties(books)
    if kind == "party_ledger":
        return party_ledger(books, party)
    if kind == "ageing":
        return ageing(books, as_of)
    if kind == "day_book":
        return day_book(books)
    raise BookError(f"Unknown report {kind!r}.")


def guess_register(sheet_name: str, filename: str) -> str | None:
    """'sales' / 'purchases' from a sheet or file name, if it says so."""
    text = f"{sheet_name} {filename}".lower()
    if re.search(r"purchase|purch|bills?\b|supplier|vendor|inward", text):
        return "purchases"
    if re.search(r"sales?\b|sale_|invoice|customer|outward", text):
        return "sales"
    return None


_TEXT_ROWS = {"Month by month": 24, "Item-wise: purchased vs sold": 20, "Parties who are both customer and supplier": 15}


def _text_value(value, fmt: str) -> str:
    if isinstance(value, bool) or value is None:
        return "" if value is None else str(value)
    if isinstance(value, int):  # entry counts
        return indian(value, 0)
    if isinstance(value, float):
        if fmt == "money":
            return indian(value)
        if fmt == "percent":
            return f"{indian(value * 100)}%"
        if fmt == "drcr":
            return f"{indian(abs(value))} {'Dr' if value > 0 else 'Cr'}" if value else "0.00"
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


def _markdown(table: dict) -> str:
    columns = table["columns"]
    limit = _TEXT_ROWS.get(table["title"], len(table["rows"]))
    lines = [f'{table["title"]}:', "| " + " | ".join(c["label"] or "" for c in columns) + " |",
             "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join(_text_value(row.get(c["key"]), c["format"]) for c in columns) + " |" for row in table["rows"][:limit]]
    if len(table["rows"]) > limit:
        lines.append(f'(+{len(table["rows"]) - limit} more rows; use analyse on the "registers" table for them)')
    return "\n".join(lines)


def combined_text(sheets: list[dict]) -> str:
    """The sales vs purchases comparison of the files shared in a chat, as exact text for the AI: totals,
    margin, GST set-off, month by month, items and common parties. Remembered until the data changes."""
    def build_text() -> str:
        try:
            books = Books({"sheets": sheets})
        except (BookError, KeyError, ValueError) as exc:
            return f"<combined>\nThe registers could not be compared: {exc}\n</combined>"
        report = compare(books)
        net = _net_gst(books)
        heads = [h for h in ("igst", "cgst", "sgst", "cess") if net["output"][h] or net["credit"][h]]
        cards = " · ".join(f'{c["label"]} {_text_value(float(c["value"]), c["format"])}' for c in report["cards"])
        parts = [
            "The shared files include a sales register and a purchase register. The app compared them exactly "
            "(rupees, from each register's taxable value, GST and invoice value columns):",
            f"Key figures: {cards}",
        ]
        if heads:
            show = lambda values: ", ".join(f"{h.upper()} {_fmt(values[h])}" for h in heads)  # noqa: E731
            parts.append(
                f"GST set-off (input credit used in the legal order, Rule 88A): output tax {show(net['output'])}; "
                f"input tax credit {show(net['credit'])}; payable in cash {show(net['cash'])}; "
                f"credit carried forward {show(net['credit_left'])}."
            )
        parts += [_markdown(table) for table in report["tables"]]
        # "; see the GST tab" points at screens of the comparison page, not the chat.
        notes = [re.split(r";\s*see ", c["message"])[0] for c in report["checks"] if c["level"] in ("warning", "info")][:8]
        if notes:
            parts.append("Notes:\n" + "\n".join(f"- {n}" for n in notes))
        return "<combined>\n" + "\n\n".join(parts) + "\n</combined>"

    key = ("combined", *(sheet_key(s) + (s["register"],) for s in sheets))
    return cached(key, build_text)


__all__ = ["KINDS", "REGISTERS", "ROLES", "BookError", "build", "combined_text", "guess_register"]
