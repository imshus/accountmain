"""The chosen company's books as tables the chat can query (run_sql / analyse), so a question about sales, purchases,
stock or earlier chats is answered from the books without sharing a file again.

The entries and stock are read from the database once per version of the company's books (a few queries and up to
MAX_VOUCHERS rows over the network, on every message otherwise); earlier chats are read every time."""

from __future__ import annotations

import logging

import pandas as pd

from sqlalchemy import func, select

from .. import database
from ..accounts import metal, service
from ..accounts.db import audit_log, metal_lines, vouchers
from .common import _Memo

log = logging.getLogger(__name__)

# Enough for any one shop's books; the screens page through the same list.
MAX_VOUCHERS = 20_000
MAX_CHAT_TURNS = 200
_ANSWER_CHARS = 700

_PARTY_GROUPS = ("Sundry Debtors", "Sundry Creditors")

_ENTRY_COLUMNS = {  # column -> (label, kind)
    "date": ("Date", "date"), "type": ("Type", "text"), "bill_no": ("Bill no.", "text"), "party": ("Party", "text"),
    "items": ("Items", "text"), "net_g": ("Net weight (g)", "number"), "amount": ("Amount (₹)", "number"),
    "narration": ("Narration", "text"),
}
_STOCK_COLUMNS = {
    "metal": ("Metal", "text"), "item": ("Item", "text"), "net_in_g": ("Net in (g)", "number"),
    "net_out_g": ("Net out (g)", "number"), "net_g": ("Net in stock (g)", "number"), "fine_g": ("Fine in stock (g)", "number"),
    "diamond_ct": ("Diamonds in stock (ct)", "number"),
}
# One row per item of a sales / purchase bill, with every detail the books keep for it (entered on the form, typed in the
# chat or read from an added sheet), so a question about any of them is answered (asked for on 2026-11-06).
_ITEM_COLUMNS = {
    "date": ("Date", "date"), "type": ("Type", "text"), "bill_no": ("Bill no.", "text"), "party": ("Party", "text"),
    "item": ("Item", "text"), "jewell_code": ("Jewell code / tag", "text"), "design_no": ("Design no.", "text"),
    "huid": ("HUID", "text"), "metal": ("Metal", "text"), "karat": ("Karat / purity code", "text"),
    "purity_pct": ("Purity %", "number"), "gross_g": ("Gross weight (g)", "number"), "net_g": ("Net weight (g)", "number"),
    "fine_g": ("Fine weight (g)", "number"), "pieces": ("Pieces", "number"), "diamond_ct": ("Diamond weight (ct)", "number"),
    "diamond_shape": ("Diamond shape", "text"), "diamond_colour": ("Diamond colour", "text"),
    "diamond_clarity": ("Diamond clarity", "text"), "diamond_value": ("Diamond value (₹)", "number"),
    "stone_ct": ("Colour stone weight (ct)", "number"), "stone_shape": ("Colour stone shape", "text"),
    "stone_colour": ("Colour stone colour", "text"), "stone_clarity": ("Colour stone clarity", "text"),
    "stone_value": ("Colour stone value (₹)", "number"), "labour_amount": ("Labour amount (₹)", "number"),
    "metal_value": ("Metal value (₹)", "number"), "amount": ("Item amount (₹)", "number"),
}
_CHAT_COLUMNS = {
    "chat": ("Chat", "text"), "asked_on": ("Asked on", "date"), "question": ("Question", "text"),
    "answer": ("Answer (start)", "text"),
}

BOOKS_TABLES_TEXT = """The chosen company's books (kept up to date by the app; amounts in rupees, weights in grams). Use them for any question about the business's sales, purchases, parties, items, stock or earlier chats, even when no file is shared:
- Table "book_sales": one row per sales bill: date, type, bill_no, party, items (item names, comma-separated), net_g, amount (bill total), narration. Sales returns (type Credit Note) are in it with minus amount and weight, so sum(amount) is net sales.
- Table "book_purchases": the same for purchase bills, with purchase returns (type Debit Note) as minus amounts.
- Table "book_entries": every entry in the books (type is Sales, Purchase, Receipt, Payment, Journal, Contra, Credit Note, Debit Note, ...), same columns.
- Table "book_items": one row per item of every sales and purchase bill (and their returns), with every detail kept for it: date, type, bill_no, party, item, jewell_code (tag no.), design_no, huid, metal, karat (purity code, e.g. 22K), purity_pct, gross_g, net_g, fine_g, pieces, diamond_ct, diamond_shape, diamond_colour, diamond_clarity, diamond_value, stone_ct, stone_shape, stone_colour, stone_clarity, stone_value (colour stones), labour_amount, metal_value, amount (the item's billed value). Use it for any question about an item, a tag, a design, a HUID, karat or purity, weights, diamonds, stones or labour; book_sales / book_purchases are one row per bill, so a bill of several items has several rows here: count bills with COUNT(DISTINCT bill_no). Text columns are matched as typed: compare with lower(...) LIKE '%...%'.
- Table "book_stock": stock by item (purchases in less sales out): metal, item, net_in_g, net_out_g, net_g (in stock), fine_g, diamond_ct.
- Table "past_chats": earlier questions in this app and the start of each answer: chat, asked_on, question, answer. Use it when the person refers to something asked or answered before; figures in it are not checked, so take figures from the book tables.
Total Spent means purchases; Total Income means sales minus purchases. A table with no rows means nothing of that kind is in the books yet: say so.

Bills typed in the chat ("Input by chat"): you have add_bill only when the app read that the person asks to save a bill they typed (party, item, gross weight, purity, and any diamond weight and rate, labour rate). Then save it at once with add_bill, one call per bill, without asking anything, and give its bill number and total. Sale or purchase: as the app's note says; else from their wording (bought from someone: purchase; sold to someone: sale); else sale, and say so in one line. A name in any wording ("in trpl", "trpl se", "from X", "X ko") is the party; no name at all: leave it empty (a cash bill). Purity and rates may be left out (null): save the bill as given, never invent a figure. A price or total the person gives ("price 600000", "for ₹1,200", "1,00,000 ka") is the bill's amount: always pass it, and give the saved total. A bill needs its weight or its amount; with neither, say in one line that one is needed. A price or purity given after the bill was saved: call add_bill again with the same details and the new figure, and it updates that bill. Without add_bill, never say a bill was saved."""


def _frame(rows: list[dict] | None, columns: dict[str, tuple[str, str]], name: str, company_id: int):
    """A Session extra table. ``rows`` None: that part of the books could not be read, so the table is empty and marked
    so (unreadable_note tells the model), never passed off as books with nothing in them."""
    frame = pd.DataFrame(rows or [], columns=list(columns))
    for col, (_label, kind) in columns.items():
        if kind == "number":
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        elif kind == "date":
            frame[col] = pd.to_datetime(frame[col], errors="coerce")
        else:
            frame[col] = frame[col].astype("string")
    # Same rows -> same key: the DuckDB copy is prepared once, and a remembered answer is reused only while they last.
    digest = int(pd.util.hash_pandas_object(frame, index=False).sum()) if len(frame) else 0
    frame.attrs["cache_key"] = ("books", name, company_id, len(frame), digest) if rows is not None else ("books", name, company_id, "unreadable")
    if rows is None:
        frame.attrs["unreadable"] = True
    return frame, {c: k for c, (_l, k) in columns.items()}, {c: label for c, (label, _k) in columns.items()}


def _item_names(company_id: int) -> dict[int, list[str]]:
    """Every item name of each bill, in bill order (the voucher list keeps only the first three)."""
    names: dict[int, list[str]] = {}
    head = database.columns_of(vouchers)
    with database.engine.connect() as conn:
        for vid, text in conn.execute(select(vouchers.c.id, head["items_text"]).where(vouchers.c.company_id == company_id)):
            names[vid] = [n for n in (text or "").split("\n") if n.strip()]
        for vid, item in conn.execute(
            select(metal_lines.c.voucher_id, metal_lines.c.item).join(vouchers, vouchers.c.id == metal_lines.c.voucher_id)
            .where(vouchers.c.company_id == company_id, metal_lines.c.item.isnot(None))
            .group_by(metal_lines.c.voucher_id, metal_lines.c.item).order_by(func.min(metal_lines.c.position))
        ):
            if item not in names.setdefault(vid, []):
                names[vid].append(item)
    return names


def _entries(company_id: int) -> list[dict]:
    parties = {r["name"] for r in service.list_ledgers(company_id) if r.get("group_name") in _PARTY_GROUPS}
    rows = service.list_vouchers(company_id, None, None, None, None, 0, MAX_VOUCHERS)["rows"]
    every = _item_names(company_id)
    out = []
    for v in rows:
        if v.get("cancelled"):
            continue
        names = v.get("ledgers") or []
        party = next((n for n in names if n in parties), names[0] if names else "")
        # int(): a Postgres SUM of whole numbers may arrive as a Decimal; mg and paise are whole either way.
        out.append({"date": v["date"], "type": v["vtype"], "bill_no": v.get("number") or v.get("reference") or "",
                    "party": party, "items": ", ".join(every.get(v["id"]) or v.get("items") or []),
                    "net_g": (int(v["net_mg"]) / 1000) if v.get("net_mg") is not None else None,
                    "amount": int(v.get("amount") or 0) / 100, "narration": v.get("narration") or ""})
    return out


def _stock(company_id: int) -> list[dict]:
    company = service.get_company(company_id)
    out = []
    for kind in metal.metals_in_use(company_id) or ["gold"]:
        report = metal.stock_grams(company, kind, None, None)
        # The stock of each item (purchases in less sales out), not the by-karat table, which has net_in too.
        table = next((t for t in report["tables"] if t["rows"] and {"item", "net_in", "net_out"} <= set(t["rows"][0])), None)
        for r in (table or {}).get("rows", []):
            out.append({"metal": kind, "item": r["item"], "net_in_g": r["net_in"], "net_out_g": r["net_out"],
                        "net_g": r["net"], "fine_g": r["fine"], "diamond_ct": r["dia"]})
    return out


def _items(company_id: int) -> list[dict]:
    """Every item of the sales and purchase bills with all its details (metal.stock_items), in grams, carats, % and ₹."""
    g = lambda mg: int(mg) / 1000 if mg else None  # noqa: E731
    rs = lambda paise: int(paise) / 100 if paise else None  # noqa: E731
    return [{
        "date": r["date"], "type": r["vtype"], "bill_no": r["number"], "party": r.get("party") or "", "item": r.get("item") or "",
        "jewell_code": r.get("tag_no") or "", "design_no": r.get("design_no") or "", "huid": r.get("huid") or "",
        "metal": r.get("metal") or "", "karat": r.get("purity") or "",
        "purity_pct": int(r["tunch_bp"]) / 100 if r.get("tunch_bp") else None,
        "gross_g": g(r.get("gross_mg")), "net_g": g(r.get("net_mg")), "fine_g": g(r.get("fine_mg")), "pieces": r.get("pieces"),
        "diamond_ct": g(r.get("dia_mct")), "diamond_shape": r.get("dia_shape") or "", "diamond_colour": r.get("colour") or "",
        "diamond_clarity": r.get("clarity") or "", "diamond_value": rs(r.get("dia_paise")),
        "stone_ct": g(r.get("stn_mct")), "stone_shape": r.get("stn_shape") or "", "stone_colour": r.get("stn_colour") or "",
        "stone_clarity": r.get("stn_clarity") or "", "stone_value": rs(r.get("stn_paise")),
        "labour_amount": rs(r.get("labour_paise")), "metal_value": rs(r.get("metal_paise")), "amount": rs(r.get("amount_paise")),
    } for r in metal.stock_items(company_id)]


def _past_chats() -> list[dict]:
    chats, _gone = database.list_chats("home", limit=30)
    out = []
    for chat in chats:
        for turn in chat.get("turns") or []:
            result = turn.get("result") if isinstance(turn, dict) else None
            question = (turn.get("question") or "").strip() if isinstance(turn, dict) else ""
            if not result or not question:
                continue
            out.append({"chat": chat.get("title") or "", "asked_on": pd.to_datetime(chat.get("updated"), unit="ms", errors="coerce"),
                        "question": question[:300], "answer": (result.get("answer") or "")[:_ANSWER_CHARS]})
            if len(out) >= MAX_CHAT_TURNS:
                return out
    return out


def _register(entries: list[dict], bill: str, ret: str) -> list[dict]:
    """A register's bills and its returns, the returns with minus amount and weight (so a sum is the net)."""
    minus = lambda x: -x if isinstance(x, (int, float)) else x  # noqa: E731
    return [e if e["type"] == bill else {**e, "amount": minus(e["amount"]), "net_g": minus(e["net_g"])}
            for e in entries if e["type"] in (bill, ret)]


def _books_version(company_id: int) -> tuple[int, int]:
    """Changes with every change to the company's books. Each change writes its audit-log row in the same transaction
    (vouchers saved, edited, imported or cancelled; ledgers and metal openings; the company's settings: Rule 3(1)),
    and the log only grows (database triggers), so its row count grows with every committed change, whatever order
    concurrent ones commit in. One small query instead of reading the books again."""
    with database.engine.connect() as conn:
        count, last = conn.execute(select(func.count(), func.max(audit_log.c.id))
                                   .where(audit_log.c.company_id == company_id)).one()
    return int(count), int(last or 0)


# The entries and stock tables of a company per version of its books. A read that failed is never kept here.
_BOOKS = _Memo(8)


def _book_frames(company_id: int, strict: bool) -> dict:
    """The entries and stock tables. A part that cannot be read raises when ``strict``, else is marked unreadable."""
    entries = stock = items = None
    try:
        entries = _entries(company_id)
    except Exception:  # noqa: BLE001 - the books are optional context for the answer
        if strict:
            raise
        log.exception("books_tables: entries")
    try:
        stock = _stock(company_id)
    except Exception:  # noqa: BLE001
        if strict:
            raise
        log.exception("books_tables: stock")
    try:
        items = _items(company_id)
    except Exception:  # noqa: BLE001
        if strict:
            raise
        log.exception("books_tables: items")
    read = entries is not None
    return {
        "book_sales": _frame(_register(entries, "Sales", "Credit Note") if read else None, _ENTRY_COLUMNS, "sales", company_id),
        "book_purchases": _frame(_register(entries, "Purchase", "Debit Note") if read else None, _ENTRY_COLUMNS, "purchases",
                                 company_id),
        "book_entries": _frame(entries, _ENTRY_COLUMNS, "entries", company_id),
        "book_items": _frame(items, _ITEM_COLUMNS, "items", company_id),
        "book_stock": _frame(stock, _STOCK_COLUMNS, "stock", company_id),
    }


def books_tables(company_id: int) -> dict:
    """{"book_sales", "book_purchases", "book_entries", "book_items", "book_stock", "past_chats"} as Session extra tables
    (frame, kinds, labels). A part that cannot be read is left empty and marked unreadable, so the chat still answers
    and says the books could not be read rather than that they hold nothing."""
    try:
        tables = _BOOKS.get((company_id, _books_version(company_id)), lambda: _book_frames(company_id, strict=True))
    except Exception:  # noqa: BLE001 - read once more, part by part, without keeping the result
        log.exception("books_tables")
        tables = _book_frames(company_id, strict=False)
    chats = None
    try:
        chats = _past_chats()
    except Exception:  # noqa: BLE001
        log.exception("books_tables: past chats")
    return {**tables, "past_chats": _frame(chats, _CHAT_COLUMNS, "chats", company_id)}


def unreadable_note(extra: dict | None) -> str:
    """For the model: the books tables that could not be read this time ("" when every one was read)."""
    names = [name for name, (frame, *_rest) in (extra or {}).items() if frame.attrs.get("unreadable")]
    if not names:
        return ""
    return (f"Could not be read just now, so they are empty although the books may hold entries: {', '.join(names)}. "
            "For a question they would answer, say the books could not be read this time and to ask again; never say "
            "there is nothing of that kind in the books.")
