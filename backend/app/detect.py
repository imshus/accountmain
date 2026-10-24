"""What kind of document is this sheet? Sales register, purchase register, bank statement or ledger.

Evidence is scored, not guessed from one word, and every point comes with a plain reason the person
can check: the voucher-type values in the rows (S / Sales / P / Purchase), column headers (customer vs
supplier, output vs input GST), invoice-number patterns (S/0071 vs PB-046), and the file and sheet
names. The result says how sure it is; when the evidence is thin it says so instead of guessing.
"""

from __future__ import annotations

import re

from . import reports

KINDS = {
    "sales": "Sales register",
    "purchases": "Purchase register",
    "bank": "Bank statement",
    "ledger": "Ledger / day book",
    "other": "Other data",
}

# (pattern on lower-cased text, kind, points, reason template)
_NAME_SIGNS = [
    (r"purchase|purch\b|\bbills?\b|inward|gstr[-_ ]?2|supplier|vendor", "purchases", 3, 'the {where} says "{hit}"'),
    (r"(?<![a-z])sales?(?![a-z])|outward|gstr[-_ ]?1|customer|debtor", "sales", 3, 'the {where} says "{hit}"'),
    (r"bank|statement|passbook|\bstmt\b|hdfc|icici|\bsbi\b|axis|kotak", "bank", 3, 'the {where} says "{hit}"'),
    (r"ledger|day ?book|trial ?balance|journal", "ledger", 2, 'the {where} says "{hit}"'),
]
_HEADER_SIGNS = [
    (r"(^|_)(customer|buyer|consignee|bill_to|billed_to|ship_to|debtor|recipient)(_|$)", "sales", 2, 'it has a "{label}" column'),
    (r"(^|_)(supplier|vendor|seller|creditor|supplier_invoice|supplier_bill|party_bill)(_|$)", "purchases", 2, 'it has a "{label}" column'),
    (r"output_?(cgst|sgst|igst|gst|tax)|(^|_)sales?_(value|amount|amt)(_|$)", "sales", 3, '"{label}" is output tax or sales value'),
    (r"input_?(cgst|sgst|igst|gst|tax)|(^|_)itc(_|$)|input_tax_credit|eligible_itc|(^|_)purchase_(value|amount|amt)(_|$)",
     "purchases", 3, '"{label}" is input tax credit or purchase value'),
    (r"(^|_)(withdrawal|withdrawals|deposit|deposits|cheque|chq|utr|closing_balance|running_balance)(_|$)", "bank", 2,
     '"{label}" is a bank statement column'),
]
_TYPE_VALUES = {  # voucher-type cell values (lower case) -> kind
    "s": "sales", "sale": "sales", "sales": "sales", "si": "sales", "sales invoice": "sales", "tax invoice": "sales",
    "sr": "sales", "sales return": "sales", "credit note": "sales", "cn": "sales",
    "p": "purchases", "pur": "purchases", "purc": "purchases", "purchase": "purchases", "pi": "purchases",
    "purchase invoice": "purchases", "pr": "purchases", "purchase return": "purchases", "debit note": "purchases", "dn": "purchases",
}
_NUMBER_SIGNS = [
    (r"^(s|si|inv|sale|sales|ti|tax)[/-]", "sales", 'invoice numbers look like sales invoices ("{example}")'),
    (r"^(p|pb|pi|pur|purc|bill|grn)[/-]", "purchases", 'bill numbers look like purchase bills ("{example}")'),
]


def _top_values(column: dict) -> list[tuple[str, int]]:
    stats = column.get("stats") or {}
    return [(str(t["value"]), int(t["count"])) for t in stats.get("top", [])] if isinstance(stats, dict) else []


def classify(sheet: dict, filename: str) -> dict:
    """{"kind", "label", "confidence": high | medium | low, "reasons": [...], "jewellery": bool} for one sheet."""
    profile = sheet["profile"]
    columns = profile["columns"]
    rows = max(int(sheet.get("row_count") or 0), 1)
    score = {k: 0 for k in KINDS}
    reasons: dict[str, list[str]] = {k: [] for k in KINDS}

    def add(kind: str, points: int, reason: str) -> None:
        score[kind] += points
        if reason not in reasons[kind]:
            reasons[kind].append(reason)

    for where, text in (("file name", filename), ("sheet name", sheet.get("sheet_name") or "")):
        for pattern, kind, points, template in _NAME_SIGNS:
            hit = re.search(pattern, text.lower())
            if hit:
                add(kind, points, template.format(where=where, hit=text if len(text) < 60 else hit.group(0)))

    for col in columns:
        name = col["name"]
        for pattern, kind, points, template in _HEADER_SIGNS:
            if re.search(pattern, name):
                add(kind, points, template.format(label=col["label"]))

    mapping = reports.effective_mapping(profile)
    type_col = next((c for c in columns if c["name"] == mapping.get("voucher_type")), None)
    if type_col:
        counted: dict[str, int] = {}
        for value, count in _top_values(type_col):
            kind = _TYPE_VALUES.get(value.strip().lower())
            if kind:
                counted[kind] = counted.get(kind, 0) + count
        for kind, count in counted.items():
            share = count / rows
            if share >= 0.5:
                values = sorted({v for v, _ in _top_values(type_col) if _TYPE_VALUES.get(v.strip().lower()) == kind})
                add(kind, 5 if share >= 0.9 else 3,
                    f'{round(share * 100)}% of rows have {type_col["label"]} = {", ".join(repr(v) for v in values[:3])}')

    number_col = next((c for c in columns if c["name"] == mapping.get("voucher_no")), None)
    if number_col:
        examples = [v for v, _ in _top_values(number_col)][:10]
        for pattern, kind, template in _NUMBER_SIGNS:
            hits = [e for e in examples if re.match(pattern, e.strip().lower())]
            if examples and len(hits) >= max(1, len(examples) // 2):
                add(kind, 2, template.format(example=hits[0]))

    roles = set(mapping)
    if {"debit", "credit"} <= roles and "account" in roles and not score["bank"]:
        add("ledger", 2, "it has Debit, Credit and Account columns")
    jewellery = any(re.match(r"^(fine|gold_fine|tunch|touch|net_wt|gr_wt)$", c["name"]) for c in columns)

    best = max(score, key=lambda k: score[k])
    ranked = sorted(score.values(), reverse=True)
    margin = ranked[0] - ranked[1]
    if ranked[0] == 0:
        best, confidence = "other", "low"
    else:
        confidence = "high" if ranked[0] >= 4 and margin >= 3 else "medium" if margin >= 2 else "low"
    if best in ("sales", "purchases") and jewellery:
        reasons[best].append("it is a jewellery register (gross / net / fine weights and tunch)")
    contrary = [r for k, rs in reasons.items() if k != best for r in rs]
    return {"kind": best, "label": KINDS[best], "confidence": confidence, "reasons": reasons.get(best, []),
            "against": contrary, "jewellery": jewellery}


def describe_documents(datasets: list[dict]) -> tuple[str, list[dict]]:
    """Text for the AI (what each uploaded file is and why) and the same as data for the app."""
    found, lines = [], []
    for dataset in datasets:
        for sheet in dataset["sheets"]:
            result = classify(sheet, dataset["filename"])
            period = (sheet["profile"].get("summary") or {}).get("period")
            entry = {"dataset_id": dataset["id"], "filename": dataset["filename"], "sheet_name": sheet["sheet_name"],
                     "table_name": sheet["table_name"], "rows": sheet["row_count"], "period": period, **result}
            found.append(entry)
            lines.append(
                f'- File "{dataset["filename"]}", sheet "{sheet["sheet_name"]}" (table {sheet["table_name"]}, {sheet["row_count"]} rows'
                + (f', {period["from"]} to {period["to"]}' if period else "") + "): "
                + f'detected as {result["label"]} ({result["confidence"]} confidence)'
                + (f'; because {"; ".join(result["reasons"])}' if result["reasons"] else "; no clear evidence either way")
                + (f'; evidence the other way: {"; ".join(result["against"])}' if result["against"] else "")
            )
    kinds = [f["kind"] for f in found]
    if "sales" in kinds and "purchases" in kinds:
        lines.append("There is a sales register and a purchase register: they can be compared (the 'registers' table "
                     "stacks both, with a register column).")
    return "\n".join(lines), found
