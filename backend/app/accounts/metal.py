"""Jewellery: fine-metal (gold / silver) accounts kept beside the rupee books.

Every party and the stock ledger carry a metal balance in whole milligrams of fine metal:
    net  = gross - (diamond + stone carats) x 0.2 g        fine = net x tunch / 100
A sale settled by weight ("Wt") debits the customer's metal account with the fine weight and bills
rupees only for diamonds, stones and labour; settled in rupees ("Rs") the metal value is billed and the
metal goes to the Sales ledger. A rate cut later turns metal owed into rupees at an agreed rate; it is an
ordinary Sales (or Purchase) voucher that also moves the metal, so GST returns and bills see it.

Metal entries (fine weight, balanced per voucher like rupees):
    sale              Stock Cr     /  Customer Dr (Wt) or Sales Dr (Rs)
    purchase          Stock Dr     /  Supplier Cr (Wt) or Purchase Cr (Rs)
    metal received    Stock Dr     /  Party Cr
    metal issued      Party Dr     /  Stock Cr
    rate cut          Sales Dr     /  Customer Cr       (rupees: Customer Dr / Sales Cr / GST Cr)
"""

import re
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import and_, select

from .. import reports
from ..database import engine
from ..editing import load_frame
from ..reports import _col, _report
from . import chart, service
from .db import ledgers, metal_lines, metal_openings, vouchers
from .service import AccountsError, Line, MetalLine, fine_of, half_up, net_of, to_bp, to_mct, to_mg, to_paise


def grams(mg) -> float:
    return int(mg) / 1000


def _g(mg) -> str:
    return f"{int(mg) / 1000:,.3f} g"


def _g_drcr(mg) -> str:
    mg = int(mg)
    return "0.000 g" if mg == 0 else f"{abs(mg) / 1000:,.3f} g {'Dr' if mg > 0 else 'Cr'}"


def stock_ledger(conn, company_id: int, metal: str) -> int:
    if metal not in chart.METALS:
        raise AccountsError(f"Unknown metal {metal!r}.")
    return service.ensure_ledger(conn, company_id, chart.STOCK_LEDGERS[metal], "Stock-in-Hand")


def _party(conn, company_id: int, party_id: int) -> dict:
    row = conn.execute(select(ledgers).where(ledgers.c.id == party_id)).mappings().first()
    if row is None or row["company_id"] != company_id:
        raise AccountsError("Party ledger not found.")
    return dict(row)


def karat_of(purity: str | None, tunch_bp: int | None = None) -> str:
    """'G14KY' -> '14K'; without a karat in the purity code, fall back to 'Not given'."""
    match = re.search(r"(\d{1,2})\s*K", purity, re.IGNORECASE) if isinstance(purity, str) else None
    return f"{int(match.group(1))}K" if match else "Not given"


# --- One item -----------------------------------------------------------------------------------------


def item_weights(item: dict) -> dict:
    """Normalise an item given in grams / carats / percent. Net and fine are computed when not given.

    Returns the stored details (mg, mct, bp) plus 'fine_mg'."""
    gross = to_mg(item.get("gross"), "Gross weight")
    dia = to_mct(item.get("diamond_ct"), "Diamond carats")
    stn = to_mct(item.get("stone_ct"), "Stone carats")
    net = to_mg(item.get("net"), "Net weight") if item.get("net") not in (None, "") else (net_of(gross, dia, stn) if gross else 0)
    tunch = to_bp(item.get("tunch"), "Tunch") if item.get("tunch") not in (None, "") else None
    if tunch is not None and not 0 < tunch <= 10000:
        raise AccountsError("Tunch must be between 0 and 100.")
    if item.get("fine") not in (None, ""):
        fine = to_mg(item.get("fine"), "Fine weight")
    elif tunch is not None and net:
        fine = fine_of(net, tunch)
    else:
        raise AccountsError("Give each item a fine weight, or its net weight and tunch.")
    if fine <= 0:
        raise AccountsError("Fine weight must be more than zero.")
    if net and fine > net:
        raise AccountsError(f"Fine weight {_g(fine)} cannot be more than the net weight {_g(net)}.")
    pieces = item.get("pieces")
    return {
        "item": (item.get("item") or "").strip()[:120] or None, "purity": (item.get("purity") or "").strip()[:20] or None,
        "tunch_bp": tunch, "gross_mg": gross or None, "net_mg": net or None, "dia_mct": dia or None, "stn_mct": stn or None,
        "pieces": int(pieces) if pieces not in (None, "") else None, "tag_no": (item.get("tag_no") or "").strip()[:40] or None,
        "fine_mg": fine,
    }


# --- Voucher builders ----------------------------------------------------------------------------------

SALE_LIKE = {"Sales", "Debit Note"}  # metal leaves stock


def jewellery_invoice(conn, company: dict, vtype: str, party_id: int, metal: str, items: list[dict], gst_rate: float,
                      round_off: bool, metal_rate_paise: int = 0) -> tuple[list[Line], list[MetalLine], dict]:
    """Sales / Purchase / Credit Note / Debit Note of jewellery items, each settled by weight or in rupees."""
    if vtype not in ("Sales", "Purchase", "Credit Note", "Debit Note"):
        raise AccountsError("Choose Sales, Purchase, Credit Note or Debit Note.")
    if not items:
        raise AccountsError("Add at least one item.")
    _party(conn, company["id"], party_id)
    sales_side = vtype in ("Sales", "Credit Note")
    main = service.ensure_ledger(conn, company["id"], "Sales" if sales_side else "Purchase",
                                 "Sales Accounts" if sales_side else "Purchase Accounts")
    stock = stock_ledger(conn, company["id"], metal)
    out = vtype in SALE_LIKE
    taxable, metal_out, fine_wt, fine_rs = 0, [], 0, 0
    for item in items:
        details = item_weights(item)
        fine = details.pop("fine_mg")
        settle = (item.get("settle") or "Wt").strip().lower()
        if settle not in ("wt", "rs"):
            raise AccountsError('Settle each item by weight ("Wt") or in rupees ("Rs").')
        labour = to_paise(item.get("labour_value"), "Labour") if item.get("labour_value") not in (None, "") else \
            half_up((details["net_mg"] or 0) * to_paise(item.get("labour_rate"), "Labour rate"), 1000)
        metal_value = 0
        if settle == "rs":
            if item.get("metal_value") not in (None, ""):
                metal_value = to_paise(item.get("metal_value"), "Metal value")
            elif metal_rate_paise:
                metal_value = half_up(fine * metal_rate_paise, 1000)
            else:
                raise AccountsError("Give the metal rate (₹ per gram fine) for items settled in rupees.")
            fine_rs += fine
        else:
            fine_wt += fine
        taxable += metal_value + to_paise(item.get("diamond_value"), "Diamond value") + to_paise(item.get("stone_value"), "Stone value") + labour
        metal_out.append(MetalLine(stock, metal, dr=0 if out else fine, cr=fine if out else 0, details=details))
    # The other side of the metal: the party (by weight) or Sales/Purchase (sold or bought for rupees).
    for ledger_id, fine in ((party_id, fine_wt), (main, fine_rs)):
        if fine:
            metal_out.append(MetalLine(ledger_id, metal, dr=fine if out else 0, cr=0 if out else fine))
    lines, summary = ([], {"taxable": 0, "total": 0})
    if taxable:
        lines, summary = service.gst_invoice_lines(conn, company, vtype, party_id,
                                                   [{"ledger_id": main, "taxable": taxable, "rate": gst_rate}], round_off)
    return lines, metal_out, {**summary, "fine_by_weight_mg": fine_wt, "fine_in_rupees_mg": fine_rs, "items": len(items)}


def metal_transfer(conn, company_id: int, vtype: str, party_id: int, metal: str, items: list[dict]) -> list[MetalLine]:
    """Metal Receipt (a party gives us metal) or Metal Issue (we give a party metal)."""
    if vtype not in chart.METAL_VOUCHERS:
        raise AccountsError("Choose Metal Receipt or Metal Issue.")
    if not items:
        raise AccountsError("Add at least one line of metal.")
    _party(conn, company_id, party_id)
    stock = stock_ledger(conn, company_id, metal)
    inward = vtype == "Metal Receipt"
    lines, total = [], 0
    for item in items:
        details = item_weights(item)
        fine = details.pop("fine_mg")
        total += fine
        lines.append(MetalLine(stock, metal, dr=fine if inward else 0, cr=0 if inward else fine, details=details))
    lines.append(MetalLine(party_id, metal, dr=0 if inward else total, cr=total if inward else 0))
    return lines


def party_metal(conn, company_id: int, ledger_id: int, metal: str, until: date | None = None) -> int:
    """Metal balance of one ledger in fine mg (+ = Dr: owes us / in hand)."""
    m, v = metal_lines, vouchers
    query = (select(m.c.dr_mg, m.c.cr_mg).join(v, v.c.id == m.c.voucher_id)
             .where(and_(m.c.ledger_id == ledger_id, m.c.metal == metal, v.c.cancelled.is_(False))))
    if until:
        query = query.where(v.c.date <= until)
    moved = sum(dr - cr for dr, cr in conn.execute(query).all())
    opening = conn.execute(select(metal_openings.c.opening_mg).where(and_(
        metal_openings.c.ledger_id == ledger_id, metal_openings.c.metal == metal))).scalar() or 0
    return opening + moved


def rate_cut(conn, company: dict, party_id: int, metal: str, fine_mg: int, rate_paise: int, gst_rate: float,
             round_off: bool) -> tuple[str, list[Line], list[MetalLine], dict]:
    """Convert metal a party owes (or we owe it) into rupees at an agreed rate per fine gram.

    Party owes us metal -> we sell it the metal: a Sales voucher. We owe the party metal -> we buy it: a Purchase."""
    party = _party(conn, company["id"], party_id)
    if fine_mg <= 0 or rate_paise <= 0:
        raise AccountsError("Give the fine weight and the rate per gram.")
    balance = party_metal(conn, company["id"], party_id, metal)
    if balance == 0:
        raise AccountsError(f"{party['name']} has no {metal} balance to convert.")
    if fine_mg > abs(balance):
        raise AccountsError(f"{party['name']} has only {_g(abs(balance))} fine {metal} {'owed to you' if balance > 0 else 'owed by you'}; "
                            f"you entered {_g(fine_mg)}.")
    vtype = "Sales" if balance > 0 else "Purchase"
    main = service.ensure_ledger(conn, company["id"], vtype if vtype == "Sales" else "Purchase",
                                 "Sales Accounts" if vtype == "Sales" else "Purchase Accounts")
    value = half_up(fine_mg * rate_paise, 1000)
    lines, summary = service.gst_invoice_lines(conn, company, vtype, party_id, [{"ledger_id": main, "taxable": value, "rate": gst_rate}], round_off)
    sold = vtype == "Sales"
    metal_out = [MetalLine(party_id, metal, dr=0 if sold else fine_mg, cr=fine_mg if sold else 0),
                 MetalLine(main, metal, dr=fine_mg if sold else 0, cr=0 if sold else fine_mg)]
    return vtype, lines, metal_out, {**summary, "fine_mg": fine_mg, "rate": rate_paise, "value": value}


# --- Jewellery register import ------------------------------------------------------------------------

# Role -> pattern on the column's snake_case name (first matching column wins).
_COLUMNS = {
    "fine": r"^(fine|gold_fine|fine_wt|fine_weight)$",
    "silver_fine": r"^(sil_fine|silver_fine)$",
    "net": r"^(net_wt|net_weight|net|gold_std)$",
    "gross": r"^(gr_wt|gross_wt|gross_weight|gross)$",
    "tunch": r"^(tunch|touch|tunch_pct|tunch_percent)$",
    "purity": r"^(purity|karat|kt)$",
    "dia_wt": r"^(dia_wt|diamond_wt|dia_ct|diamond_ct)$",
    "stn_wt": r"^(stn_wt|stone_wt|stn_ct|stone_ct)$",
    "met_val": r"^(met_val|metal_val|metal_value|gold_val|gold_value)$",
    "dia_val": r"^(dia_val|diamond_val|diamond_value)$",
    "stn_val": r"^(stn_val|stone_val|stone_value)$",
    "lbr_val": r"^(lbr_val|labour_val|labour_value|making_val|making_charges)$",
    "settle": r"^(wt_rs|wt_or_rs|settle|settlement)$",
    "item": r"^(item_name|item|description|product)$",
    "tag": r"^(tag_no|tag|huid)$",
    "pieces": r"^(pc|pcs|pieces)$",
    "type": r"^(type|vch_type|voucher_type|trans_type)$",
}
_DOC_TYPES = {"s": "Sales", "sale": "Sales", "sales": "Sales", "p": "Purchase", "pur": "Purchase", "purchase": "Purchase",
              "sr": "Credit Note", "sales return": "Credit Note", "pr": "Debit Note", "purchase return": "Debit Note"}


def detect_jewellery(sheet: dict) -> dict[str, str] | None:
    """Column mapping when the sheet is a jewellery register (fine weight, or net weight and tunch), else None."""
    names = [c["name"] for c in sheet["profile"]["columns"]]
    found: dict[str, str] = {}
    for role, pattern in _COLUMNS.items():
        hit = next((n for n in names if re.match(pattern, n) and n not in found.values()), None)
        if hit:
            found[role] = hit
    if "fine" in found or "silver_fine" in found or ("net" in found and "tunch" in found):
        return found
    return None


# Column names that are weights, tunch, purity, quantities or rates: never rupees, whatever role they were given.
_NOT_RUPEES = re.compile(r"(^|_)(wt|wts|weight|weights|fine|tunch|touch|purity|karat|kt|qty|quantity|pc|pcs|pieces|rate|"
                         r"gm|gms|gram|grams|mg|ct|carat|carats)(_|$)|^(net|gross|gold_std)$")
_MONEY_ROLES = ("taxable", "invoice_value", "amount", "tax", "cgst", "sgst", "igst", "cess")
_VALUE_PARTS = ("met_val", "dia_val", "stn_val", "lbr_val")


def _rupee_mapping(sheet: dict, cols: dict[str, str]) -> dict[str, str]:
    """The register's column roles, minus any weight / tunch / purity / quantity / rate column taken as rupees."""
    weights = {c for role, c in cols.items() if role not in _VALUE_PARTS}
    mapping = reports.effective_mapping(sheet["profile"])
    return {role: c for role, c in mapping.items()
            if role not in _MONEY_ROLES or (c not in weights and not _NOT_RUPEES.search(c))}


def _money_without_totals(sheet: dict, mapping: dict[str, str], parts: list[str]) -> pd.DataFrame:
    """Money frame of a register with no taxable-value or invoice-total column: the rupees billed are
    metal + diamond + stone + labour value (nothing for a register of weights only) plus any GST columns."""
    frame = load_frame(sheet)
    out = pd.DataFrame({"rowid": frame["_rowid"].to_numpy()})
    out["date"] = pd.to_datetime(frame[mapping["date"]], errors="coerce").to_numpy() if "date" in mapping else pd.NaT
    for role, column in (("party", "account"), ("invoice_no", "voucher_no"), ("gstin", "gstin")):
        blank = "(blank)" if role == "party" else ""
        out[role] = (frame[mapping[column]].astype("string").str.strip().fillna(blank).to_numpy() if column in mapping
                     else ("(not given)" if role == "party" else ""))
    for head in ("cgst", "sgst", "igst", "cess"):
        out[head] = reports._paise(frame[mapping[head]]) if head in mapping else 0
    split = any(h in mapping for h in ("cgst", "sgst", "igst"))
    out["gst_unsplit"] = reports._paise(frame[mapping["tax"]]) if "tax" in mapping and not split else 0
    out["taxable"] = sum((reports._paise(frame[c]) for c in parts), np.zeros(len(frame), dtype="int64"))
    out["invoice_value"] = out.taxable + out.cgst + out.sgst + out.igst + out.cess + out.gst_unsplit
    return out


def _value(row, column: str | None):
    if not column:
        return None
    value = row.get(column)
    return None if value is None or (not isinstance(value, str) and pd.isna(value)) else value


def import_jewellery(company_id: int, sheet: dict, register: str) -> dict:
    """Post a jewellery register: one voucher per invoice (date + voucher no. + party), rupees for the
    billed value and metal lines for every item's fine weight. Each item's net and fine weight are
    re-computed and any difference from the register is reported (the register's figure is posted)."""
    from ..books import _normalise  # rupee columns: taxable value, GST, invoice value, party, GSTIN
    from .imports import (_imported_sources, already_in_books, check_reported_state, document_number, duplicates_note,
                          existing_documents, gstin_warnings, ledger_facts, note_bad_gstin, number_clash, party_state,
                          place_of_supply, posting_lines, split_unsplit_gst)

    cols = detect_jewellery(sheet)
    if cols is None:
        raise AccountsError("This sheet has no fine weight or tunch column.")
    # Rupees are posted only from real rupee columns; a register of weights alone posts metal only.
    mapping = _rupee_mapping(sheet, cols)
    value_cols = [cols[k] for k in _VALUE_PARTS if k in cols]
    if any(role in mapping for role in ("taxable", "invoice_value", "amount")):
        money, notes, _ = _normalise({**sheet, "register": register, "profile": {**sheet["profile"], "mapping": mapping}})
        notes = [n["message"] for n in notes]
    else:
        money = _money_without_totals(sheet, mapping, value_cols)
        notes = (["No taxable-value or invoice-total column, so each invoice's rupees = metal + diamond + stone + labour value."] if value_cols else
                 ["The register has only weights (no rupee column such as Taxable Value, Invoice Total, Metal Value or Labour Value), "
                  "so only fine metal was posted and no rupees. Bill the rupees by a rate cut or a separate invoice."])
    has_rupees = bool(any(money[c].abs().sum() for c in ("taxable", "invoice_value")))
    money = money.set_index("rowid")
    states, problems = place_of_supply(sheet, register == "sales")
    raw = load_frame(sheet).set_index("_rowid")
    company = service.get_company(company_id)
    default_vtype = "Sales" if register == "sales" else "Purchase"
    created, skipped, duplicates, bad_gstins, moved = 0, 0, [], {}, {"gold": 0, "silver": 0}
    checked = {"net": 0, "fine": 0, "total": 0}

    # Invoices: consecutive rows sharing date, voucher number, party and type.
    keys = []
    for rowid in money.index:
        r, m = raw.loc[rowid], money.loc[rowid]
        doc = str(_value(r, cols.get("type")) or "").strip().lower()
        keys.append((m.date, m.invoice_no or f"row{rowid}", m.party, doc))
    groups: list[tuple[tuple, list[int]]] = []
    for key, rowid in zip(keys, money.index):
        if groups and groups[-1][0] == key:
            groups[-1][1].append(rowid)
        else:
            groups.append((key, [rowid]))

    with engine.begin() as conn:
        done = _imported_sources(conn, company_id, f"import:{sheet['table_name']}:")
        in_books = existing_documents(conn, company_id, f"import:{sheet['table_name']}:")
        for (day, number, party, doc), rowids in groups:
            source = f"import:{sheet['table_name']}:{rowids[0]}"
            label = f"rows {rowids[0]}–{rowids[-1]}" if len(rowids) > 1 else f"row {rowids[0]}"
            label += f" (no. {number})" if not str(number).startswith("row") else ""
            if source in done:
                skipped += 1
                continue
            if pd.isna(day):
                problems.append(f"{label}: no date, not posted.")
                continue
            if party in ("(blank)", "(not given)"):
                problems.append(f"{label}: no party name, not posted.")
                continue
            vtype = _DOC_TYPES.get(doc, default_vtype) if doc else default_vtype
            if doc and doc not in _DOC_TYPES:
                problems.append(f"{label}: type {doc!r} not understood; posted as {default_vtype}.")
            sales_side = vtype in ("Sales", "Credit Note")
            first = money.loc[rowids[0]]
            numbered = not str(number).startswith("row")
            on_day = pd.Timestamp(day).date()
            # By GSTIN first, so a renamed or differently spelt party does not get a new, empty ledger.
            if numbered and already_in_books(in_books, vtype, str(number), on_day, None, [first.gstin]):
                skipped += 1
                duplicates.append(label)
                continue
            party_id = service.ensure_ledger(conn, company_id, party, "Sundry Debtors" if sales_side else "Sundry Creditors",
                                             gstin=first.gstin or None)
            is_party, saved_gstin = ledger_facts(conn, party_id)
            value = abs(sum(int(money.loc[rowid].invoice_value) for rowid in rowids))
            if numbered and already_in_books(in_books, vtype, str(number), on_day, party_id, [saved_gstin], is_party, value):
                skipped += 1
                duplicates.append(label)
                continue
            main = service.ensure_ledger(conn, company_id, "Sales" if sales_side else "Purchase",
                                         "Sales Accounts" if sales_side else "Purchase Accounts")
            out = vtype in SALE_LIKE
            returning = vtype in ("Credit Note", "Debit Note")
            place = next((states[int(rowid)] for rowid in rowids if int(rowid) in states), None)
            state, reported, used = party_state(conn, company, party_id, first.gstin, place, label, problems)

            metal: list[MetalLine] = []
            other_side: dict[tuple[int, str], int] = {}
            total = taxable = 0
            heads = {"cgst": 0, "sgst": 0, "igst": 0, "cess": 0}
            signs: dict[str, set[int]] = {"weights": set(), "rupees": set()}  # each the same way on every line of a return
            for rowid in rowids:
                r, m = raw.loc[rowid], money.loc[rowid]
                where = f"row {rowid}"
                try:
                    gross = to_mg(_value(r, cols.get("gross")), "Gross weight")
                    dia = to_mct(_value(r, cols.get("dia_wt")), "Diamond carats")
                    stn = to_mct(_value(r, cols.get("stn_wt")), "Stone carats")
                    net = to_mg(_value(r, cols.get("net")), "Net weight")
                    tunch = to_bp(_value(r, cols.get("tunch")), "Tunch") if _value(r, cols.get("tunch")) is not None else None
                    fines = {"gold": to_mg(_value(r, cols.get("fine")), "Fine"), "silver": to_mg(_value(r, cols.get("silver_fine")), "Silver fine")}
                except AccountsError as exc:
                    problems.append(f"{where}: {exc} Not posted.")
                    continue
                if returning:  # a return may be entered with minus signs; its weights are still weights
                    figures = {"weights": [gross, dia, stn, net, *fines.values()],
                               "rupees": [int(m.invoice_value), int(m.taxable), *(int(getattr(m, h)) for h in ("cgst", "sgst", "igst", "cess", "gst_unsplit"))]}
                    for kind, values in figures.items():
                        signs[kind].update(1 if x > 0 else -1 for x in values if x)
                    gross, dia, stn, net = abs(gross), abs(dia), abs(stn), abs(net)
                    fines = {name: abs(fine) for name, fine in fines.items()}
                if gross and net:
                    expected = net_of(gross, dia, stn)
                    checked["net"] += 1
                    if abs(expected - net) > 1:
                        problems.append(f"{where}: net weight {_g(net)} ≠ gross {_g(gross)} − (diamond + stone {(dia + stn) / 1000:,.3f} ct) × 0.2 = {_g(expected)}.")
                if not net and gross:
                    net = net_of(gross, dia, stn)
                if not fines["gold"] and not fines["silver"] and net and tunch:
                    fines["gold"] = fine_of(net, tunch)
                elif fines["gold"] and net and tunch:
                    expected = fine_of(net, tunch)
                    checked["fine"] += 1
                    if abs(expected - fines["gold"]) > 1:
                        problems.append(f"{where}: fine {_g(fines['gold'])} ≠ net {_g(net)} × tunch {tunch / 100:g} ÷ 100 = {_g(expected)}; the register's figure was posted.")
                # The billed value should be metal + diamonds + stones + labour.
                parts = [_value(r, cols.get(k)) for k in ("met_val", "dia_val", "stn_val", "lbr_val")]
                if any(p is not None for p in parts):
                    billed = sum(to_paise(p) for p in parts if p is not None)
                    checked["total"] += 1
                    if abs(billed - int(m.taxable)) > 100:
                        problems.append(f"{where}: metal + diamond + stone + labour = {billed / 100:,.2f} but the taxable value is {int(m.taxable) / 100:,.2f}.")
                settle = str(_value(r, cols.get("settle")) or "").strip().lower()
                by_weight = settle.startswith("w") if settle else not (_value(r, cols.get("met_val")) or 0)
                purity = _value(r, cols.get("purity"))
                details = {"item": _value(r, cols.get("item")), "purity": str(purity) if purity is not None else None, "tunch_bp": tunch,
                           "gross_mg": gross or None, "net_mg": net or None, "dia_mct": dia or None, "stn_mct": stn or None,
                           "pieces": int(_value(r, cols.get("pieces")) or 0) or None, "tag_no": _value(r, cols.get("tag"))}
                if details["tag_no"] is not None:
                    details["tag_no"] = str(details["tag_no"])[:40]
                if details["item"] is not None:
                    details["item"] = str(details["item"])[:120]
                for name, fine in fines.items():
                    if fine:
                        metal.append(MetalLine(stock_ledger(conn, company_id, name), name, dr=0 if out else fine, cr=fine if out else 0, details=details))
                        key = (party_id if by_weight else main, name)
                        other_side[key] = other_side.get(key, 0) + fine
                total += int(m.invoice_value)
                taxable += int(m.taxable)
                for h in heads:
                    heads[h] += int(getattr(m, h))
                split_unsplit_gst(company, m.gstin, heads, int(m.gst_unsplit), state)
            for (ledger_id, name), fine in other_side.items():
                metal.append(MetalLine(ledger_id, name, dr=fine if out else 0, cr=0 if out else fine))
            if not metal and not total:
                problems.append(f"{label}: no weight or value, not posted.")
                continue
            mixed = [kind for kind, found in signs.items() if len(found) > 1]
            if mixed:
                # Turning only the minus lines round would return all the metal but net the rupees against each other.
                problems.append(f"{label}: this {'sales' if vtype == 'Credit Note' else 'purchase'} return has some {' and '.join(mixed)} "
                                "with minus signs and some without. Enter every line of a return the same way (all with minus "
                                "signs or all without) and import again. Not posted.")
                continue
            if returning and (total < 0 or taxable < 0):  # a return entered with minus signs
                total, taxable, heads = -total, -taxable, {h: -amount for h, amount in heads.items()}
            check_reported_state(company, vtype, party, heads, state, reported, label, problems)
            if total < 0 or taxable < 0:
                problems.append(f"{label}: negative value on a {vtype}. Give a return the type SR (sales return) or "
                                "PR (purchase return) in the Type column, or correct the figures. Not posted.")
                continue
            lines = posting_lines(conn, company_id, vtype, party_id, main, total, taxable, heads, label, problems) if total or taxable else []
            num, reference = document_number(sales_side, str(number) if not str(number).startswith("row") else "", label, problems)
            try:
                with conn.begin_nested():
                    service.save_voucher(company_id, vtype, pd.Timestamp(day).date(), lines, number=num or None, reference=reference,
                                         narration=f"Imported from {sheet['sheet_name']} ({len(rowids)} item{'s' if len(rowids) != 1 else ''})",
                                         source=source, conn=conn, metal=metal)
                created += 1
                note_bad_gstin(bad_gstins, first.gstin, label, used)
                for line in metal:
                    if line.details:
                        moved[line.metal] += line.dr + line.cr
            except AccountsError as exc:
                problems.append(number_clash(conn, in_books, vtype, num, on_day, label, str(exc)) or f"{label}: {exc}")

    already = duplicates_note(duplicates, register == "purchases")
    problems += gstin_warnings(bad_gstins)
    if not created:
        every = groups and skipped == len(groups)  # not when some invoice was refused: that one is not in the books
        return {"created": 0, "skipped": skipped, "problems": problems,
                "notes": (["Every invoice in this sheet is already in the books; nothing new was posted."] if every else []) + already}
    summary = [f"Read as a jewellery register: one voucher per invoice, metal posted by fine weight "
               f"({', '.join(f'{_g(mg)} fine {name}' for name, mg in moved.items() if mg) or 'no metal'})."]
    summary.append(f"Checked every row: net = gross − (diamond + stone ct) × 0.2 on {checked['net']} rows, "
                   f"fine = net × tunch ÷ 100 on {checked['fine']}, value = metal + diamonds + stones + labour on {checked['total']}.")
    # abs(): returns entered with minus signs would otherwise cancel the sales' GST in the sum.
    if has_rupees and not any(money[h].abs().sum() for h in ("cgst", "sgst", "igst", "gst_unsplit")):
        summary.append("The register has no GST amounts, so the invoices were posted without tax. If GST applies (3% on jewellery), "
                       "it is not in the books yet.")
    return {"created": created, "skipped": skipped, "problems": problems, "notes": already + summary + notes}


# --- Reports -------------------------------------------------------------------------------------------


def metal_entries(company_id: int, metal: str, until: date | None = None) -> pd.DataFrame:
    """Every metal line of every live voucher (fine mg), with its voucher's details."""
    m, v = metal_lines, vouchers
    query = (select(v.c.id.label("voucher_id"), v.c.vtype, v.c.number, v.c.date, v.c.narration, m.c.position, m.c.ledger_id,
                    m.c.dr_mg.label("dr"), m.c.cr_mg.label("cr"), *(m.c[k] for k in service.METAL_DETAILS))
             .join(v, v.c.id == m.c.voucher_id)
             .where(and_(v.c.company_id == company_id, v.c.cancelled.is_(False), m.c.metal == metal)))
    if until:
        query = query.where(v.c.date <= until)
    with engine.connect() as conn:
        frame = pd.read_sql(query, conn)
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    for col in ("dr", "cr"):
        frame[col] = frame[col].astype("int64")
    return frame


def _openings(company_id: int, metal: str) -> pd.Series:
    with engine.connect() as conn:
        rows = service.metal_opening_map(conn, company_id)
    return pd.Series({lid: mg for (lid, name), mg in rows.items() if name == metal}, dtype="int64")


def metals_in_use(company_id: int) -> list[str]:
    m, v = metal_lines, vouchers
    with engine.connect() as conn:
        used = set(conn.execute(select(m.c.metal).join(v, v.c.id == m.c.voucher_id).where(v.c.company_id == company_id).distinct()).scalars())
        used |= {name for (_, name) in service.metal_opening_map(conn, company_id)}
    return [name for name in chart.METALS if name in used]


def metal_closing(company: dict, metal: str, until: date | None = None) -> pd.Series:
    """Ledger id -> closing fine mg (+ = Dr)."""
    lines = metal_entries(company["id"], metal, until)
    moved = (lines.dr - lines.cr).groupby(lines.ledger_id).sum()
    opening = _openings(company["id"], metal)
    return opening.add(moved, fill_value=0).astype("int64")


def _wcol(key: str, label: str, fmt: str = "weight") -> dict:
    return _col(key, label, fmt)


def metal_balances(company: dict, metal: str, as_of: date | None, rate: float | None) -> dict:
    """Who owes metal to whom, the metal in hand, and the net metal position."""
    from .reports import balances, ledger_frame  # rupee balances beside the metal ones

    metal = metal or "gold"
    as_of = as_of or date.today()
    led = ledger_frame(company["id"])
    closing = metal_closing(company, metal, as_of)
    rupees = balances(company, company["fy_start"], as_of).closing
    rate_paise = to_paise(rate, "Rate") if rate else 0
    rows, flows, stock, receivable, payable = [], [], 0, 0, 0
    for lid, mg in closing.items():
        if not mg:
            continue
        group = led.group_name.get(lid)
        if group == "Stock-in-Hand":
            stock += int(mg)
            continue
        if chart.statement(group) == "pl":
            flows.append({"ledger": led.name[lid], "fine": grams(abs(mg)),
                          "meaning": "Sold for rupees (incl. rate cuts)" if mg > 0 else "Bought for rupees (incl. rate cuts)"})
            continue
        receivable += max(int(mg), 0)
        payable += max(-int(mg), 0)
        kind = "Customer" if group == "Sundry Debtors" else "Supplier" if group == "Sundry Creditors" else group
        row = {"ledger_id": int(lid), "party": led.name[lid], "kind": kind, "owes_us": grams(mg) if mg > 0 else None,
               "we_owe": grams(-mg) if mg < 0 else None, "rupees": int(rupees.get(lid, 0)) / 100}
        if rate_paise:
            row["value"] = half_up(int(mg) * rate_paise, 1000) / 100
        rows.append(row)
    rows.sort(key=lambda r: -(r["owes_us"] or 0) + (r["we_owe"] or 0))
    position = stock + receivable - payable
    columns = [_col("party", "Party", "text"), _col("kind", "Type", "text"), _wcol("owes_us", "Owes us (fine)"),
               _wcol("we_owe", "We owe (fine)"), _col("rupees", "Rupee balance", "drcr")]
    if rate_paise:
        columns.append(_col("value", "Metal value at rate", "money"))
    total = {"party": "Total", "owes_us": grams(receivable), "we_owe": grams(payable)}
    cards = [
        {"label": f"{metal.title()} in stock (fine)", "value": grams(stock), "format": "weight"},
        {"label": "Customers owe us (fine)", "value": grams(receivable), "format": "weight"},
        {"label": "We owe (fine)", "value": grams(payable), "format": "weight"},
        {"label": "Net metal position", "value": grams(position), "format": "weight", "hint": "stock + owed to us − owed by us"},
    ]
    if rate_paise:
        cards.append({"label": f"Position at ₹{rate:,.2f}/g", "value": half_up(position * rate_paise, 1000) / 100, "format": "money"})
    tables = [{"title": "Metal balance of each party", "columns": columns, "rows": rows, "total": total}]
    if flows:
        tables.append({"title": "Metal settled in rupees", "columns": [_col("ledger", "Ledger", "text"), _col("meaning", "", "text"),
                       _wcol("fine", "Fine")], "rows": flows, "total": None})
    report = _report(f"{metal.title()} balances (fine weight) as on {as_of:%d %b %Y}", {}, cards=cards, tables=tables,
                     options={"metals": metals_in_use(company["id"]) or [metal],
                              "ledgers": [{"id": r["ledger_id"], "name": r["party"], "group": r["kind"]} for r in rows]})
    opening_total = int(_openings(company["id"], metal).sum())
    moved = int(closing.sum()) - opening_total
    report["checks"].append({"level": "ok" if moved == 0 else "warning",
                             "message": "Metal tallies: every voucher's fine debits equal its fine credits." if moved == 0
                             else f"Vouchers' fine debits and credits differ by {_g_drcr(moved)}."})
    if opening_total:
        # Unlike rupees, opening metal need not balance: stock + owed to us - owed by us is the business's own metal.
        report["checks"].append({"level": "info", "message": f"Opening metal (stock + owed to you − owed by you) was {_g_drcr(opening_total)} fine: "
                                 "the business's own metal at the start."})
    if stock < 0:
        report["checks"].append({"level": "warning", "message": f"Stock is {_g(-stock)} fine below zero: more metal went out than came in. "
                                 "Enter the opening stock (Ledgers → Gold Stock) or post the purchases and metal received."})
    report["checks"].append({"level": "info", "message": "Fine = net weight × tunch ÷ 100. A negative position means you owe more metal than you hold "
                             "(a rise in the metal price costs you); a positive one means a fall costs you."})
    return report


def _particulars(group: pd.DataFrame) -> str:
    """Short description of a voucher's items: '5 pcs · net 17.512 g · tunch 60'."""
    items = group[group.net_mg.notna() | group.item.notna()]
    if items.empty:
        return ""
    pieces = int(items.pieces.fillna(1).sum())
    net = int(items.net_mg.fillna(0).sum())
    tunches = sorted({t / 100 for t in items.tunch_bp.dropna()})
    text = f"{pieces} pc{'s' if pieces != 1 else ''}" + (f" · net {_g(net)}" if net else "")
    if tunches:
        text += " · tunch " + ", ".join(f"{t:g}" for t in tunches[:3]) + ("…" if len(tunches) > 3 else "")
    return text


def metal_ledger(company: dict, ledger_id: int | None, metal: str, start: date | None, end: date | None) -> dict:
    """Running fine-weight balance of one party (or the stock ledger)."""
    metal = metal or "gold"
    start = start or company["fy_start"]
    end = end or date(2100, 12, 31)
    lines = metal_entries(company["id"], metal, end)
    names = {r["id"]: r for r in service.list_ledgers(company["id"])}
    used = set(lines.ledger_id) | set(_openings(company["id"], metal).index)
    choices = sorted(({"id": int(i), "name": names[i]["name"], "group": names[i]["group_name"]} for i in used if i in names),
                     key=lambda r: r["name"])
    options = {"ledgers": choices, "metals": metals_in_use(company["id"]) or [metal]}
    if not ledger_id:
        report = _report(f"{metal.title()} ledger", {}, options=options)
        report["checks"].append({"level": "info", "message": "Choose a party (or Gold Stock) to see its metal account."})
        return report
    if ledger_id not in names:
        raise AccountsError("Ledger not found.")
    mine = lines[lines.ledger_id == ledger_id]
    opening = int(_openings(company["id"], metal).get(ledger_id, 0)) + int((mine.dr - mine.cr)[mine.date < start].sum())
    inside = mine[mine.date >= start].sort_values(["date", "voucher_id", "position"])
    by_voucher = {vid: g for vid, g in lines[lines.voucher_id.isin(inside.voucher_id)].groupby("voucher_id")}
    rows = [{"date": None, "particulars": "Opening balance", "balance": grams(opening), "_kind": "opening"}]
    running = opening
    for r in inside.itertuples(index=False):
        running += r.dr - r.cr
        own = pd.notna(r.net_mg) or pd.notna(r.item)  # a stock line describes itself; a party line, its voucher's items
        detail = _particulars(pd.DataFrame([r._asdict()])) if own else _particulars(by_voucher[r.voucher_id])
        name = str(r.item) if own and pd.notna(r.item) else ""
        rows.append({"date": r.date.isoformat(), "type": r.vtype, "number": r.number,
                     "particulars": " · ".join(x for x in (name, detail) if x) or (r.narration or ""),
                     "dr": grams(r.dr) if r.dr else None, "cr": grams(r.cr) if r.cr else None, "balance": grams(running)})
    dr, cr = int(inside.dr.sum()), int(inside.cr.sum())
    rows.append({"particulars": "Closing balance", "dr": grams(dr), "cr": grams(cr), "balance": grams(running), "_kind": "total"})
    report = _report(f"{metal.title()} ledger: {names[ledger_id]['name']}", {}, options=options, cards=[
        {"label": "Opening (fine)", "value": grams(opening), "format": "weight_drcr"},
        {"label": "Debit (fine)", "value": grams(dr), "format": "weight"},
        {"label": "Credit (fine)", "value": grams(cr), "format": "weight"},
        {"label": "Closing (fine)", "value": grams(running), "format": "weight_drcr"},
    ], tables=[{"title": None, "columns": [
        _col("date", "Date", "date"), _col("type", "Type", "text"), _col("number", "No.", "text"),
        _col("particulars", "Particulars", "text"), _wcol("dr", "Dr (fine)"), _wcol("cr", "Cr (fine)"),
        _wcol("balance", "Balance", "weight_drcr")], "rows": rows, "total": None}])
    ok = opening + dr - cr == running
    report["checks"].append({"level": "ok" if ok else "warning",
                             "message": f"Opening {_g_drcr(opening)} + Dr {_g(dr)} − Cr {_g(cr)} = closing {_g_drcr(running)}."})
    report["checks"].append({"level": "info", "message": "Dr = the party owes you metal; Cr = you owe the party metal."})
    return report


def stock_grams(company: dict, metal: str, start: date | None, end: date | None) -> dict:
    """Metal stock in grams: what came in and went out, by karat and by item."""
    metal = metal or "gold"
    start = start or company["fy_start"]
    end = end or date(2100, 12, 31)
    led = {r["id"]: r for r in service.list_ledgers(company["id"])}
    stock_ids = [i for i, r in led.items() if r["group_name"] == "Stock-in-Hand"]
    lines = metal_entries(company["id"], metal, end)
    lines = lines[lines.ledger_id.isin(stock_ids)]
    opening = int(_openings(company["id"], metal).reindex(stock_ids).fillna(0).sum()) + int((lines.dr - lines.cr)[lines.date < start].sum())
    inside = lines[lines.date >= start].copy()
    inside["karat"] = [karat_of(p) for p in inside.purity]
    inside["pcs"] = inside.pieces.fillna(1).astype("int64")
    for col in ("gross_mg", "net_mg", "dia_mct", "stn_mct"):
        inside[col] = inside[col].fillna(0).astype("int64")
    inward, outward = inside[inside.dr > 0], inside[inside.cr > 0]

    def movement(frame: pd.DataFrame) -> pd.DataFrame:
        return frame.groupby("karat").agg(pcs=("pcs", "sum"), net=("net_mg", "sum"), fine_in=("dr", "sum"),
                                          fine_out=("cr", "sum"), dia=("dia_mct", "sum"))

    k_in, k_out = movement(inward), movement(outward)
    karat_rows = []
    for karat in sorted(set(k_in.index) | set(k_out.index), key=lambda k: (k == "Not given", k)):
        i = k_in.loc[karat] if karat in k_in.index else None
        o = k_out.loc[karat] if karat in k_out.index else None
        purities = sorted({str(p) for p in inside[inside.karat == karat].purity.dropna()})
        fine_in_k = int(i.fine_in) if i is not None else 0
        fine_out_k = int(o.fine_out) if o is not None else 0
        karat_rows.append({
            "karat": karat, "purities": ", ".join(purities[:6]),
            "pcs_in": int(i.pcs) if i is not None else None, "net_in": grams(i.net) if i is not None else None,
            "fine_in": grams(fine_in_k) if i is not None else None,
            "pcs_out": int(o.pcs) if o is not None else None, "net_out": grams(o.net) if o is not None else None,
            "fine_out": grams(fine_out_k) if o is not None else None, "dia_out": int(o.dia) / 1000 if o is not None else None,
            "fine_net": grams(fine_in_k - fine_out_k),
        })
    fine_in, fine_out = int(inward.dr.sum()), int(outward.cr.sum())
    closing = opening + fine_in - fine_out

    item_rows = []
    for (item, karat), g in outward.groupby([outward.item.fillna("(no name)"), "karat"]):
        item_rows.append({"item": item, "karat": karat, "pcs": int(g.pcs.sum()), "gross": grams(g.gross_mg.sum()), "net": grams(g.net_mg.sum()),
                          "fine": grams(g.cr.sum()), "dia": int(g.dia_mct.sum()) / 1000, "stn": int(g.stn_mct.sum()) / 1000})
    item_rows.sort(key=lambda r: -r["fine"])
    w = _wcol
    report = _report(f"{metal.title()} stock in grams", {}, cards=[
        {"label": "Opening (fine)", "value": grams(opening), "format": "weight"},
        {"label": "Came in (fine)", "value": grams(fine_in), "format": "weight"},
        {"label": "Went out (fine)", "value": grams(fine_out), "format": "weight"},
        {"label": "Closing (fine)", "value": grams(closing), "format": "weight"},
        {"label": "Pieces out", "value": int(outward.pcs.sum()), "format": "count"},
        {"label": "Diamonds out", "value": int(outward.dia_mct.sum()) / 1000, "format": "carat"},
    ], tables=[
        {"title": "By karat", "columns": [_col("karat", "Karat", "text"), _col("purities", "Purity codes", "text"),
                                          _col("pcs_in", "Pcs in", "count"), w("net_in", "Net in"), w("fine_in", "Fine in"),
                                          _col("pcs_out", "Pcs out", "count"), w("net_out", "Net out"), w("fine_out", "Fine out"),
                                          _col("dia_out", "Diamonds out", "carat"), w("fine_net", "Fine in − out")],
         "rows": karat_rows,
         "total": {"karat": "Total", "pcs_in": int(inward.pcs.sum()), "net_in": grams(inward.net_mg.sum()), "fine_in": grams(fine_in),
                   "pcs_out": int(outward.pcs.sum()), "net_out": grams(outward.net_mg.sum()), "fine_out": grams(fine_out),
                   "dia_out": int(outward.dia_mct.sum()) / 1000, "fine_net": grams(fine_in - fine_out)}},
        {"title": "Items that went out", "columns": [_col("item", "Item", "text"), _col("karat", "Karat", "text"), _col("pcs", "Pcs", "count"),
                                                     w("gross", "Gross"), w("net", "Net"), w("fine", "Fine"),
                                                     _col("dia", "Diamonds", "carat"), _col("stn", "Stones", "carat")],
         "rows": item_rows, "total": None},
    ], options={"metals": metals_in_use(company["id"]) or [metal]})
    ok = opening + fine_in - fine_out == closing
    report["checks"].append({"level": "ok" if ok else "warning",
                             "message": f"Opening {_g(opening)} + in {_g(fine_in)} − out {_g(fine_out)} = closing {_g(closing)} (fine)."})
    if closing < 0:
        report["checks"].append({"level": "warning", "message": f"Closing stock is {_g(-closing)} fine below zero: the books have sales but not the "
                                 "purchases or opening stock they came from. Enter the opening stock under Ledgers → Gold Stock."})
    report["checks"].append({"level": "info", "message": "Karat is read from the purity code (G14KY → 14K). Net = gross − (diamond + stone ct) × 0.2; "
                             "fine = net × tunch ÷ 100. Opening stock is one fine figure, not split by karat."})
    return report
