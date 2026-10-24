"""Chart of accounts: Tally Prime's 28 predefined groups and the default ledgers of a new company.

Group -> (parent primary group or None, nature). Nature decides the statement and the normal
balance: assets and expenses normally carry Dr balances, liabilities, capital and income Cr.
"""

from __future__ import annotations

GROUPS: dict[str, tuple[str | None, str]] = {
    # Balance sheet: liabilities
    "Capital Account": (None, "liability"),
    "Reserves & Surplus": ("Capital Account", "liability"),
    "Loans (Liability)": (None, "liability"),
    "Bank OD A/c": ("Loans (Liability)", "liability"),
    "Secured Loans": ("Loans (Liability)", "liability"),
    "Unsecured Loans": ("Loans (Liability)", "liability"),
    "Current Liabilities": (None, "liability"),
    "Duties & Taxes": ("Current Liabilities", "liability"),
    "Provisions": ("Current Liabilities", "liability"),
    "Sundry Creditors": ("Current Liabilities", "liability"),
    "Branch / Divisions": (None, "liability"),
    "Suspense A/c": (None, "liability"),
    # Balance sheet: assets
    "Fixed Assets": (None, "asset"),
    "Investments": (None, "asset"),
    "Current Assets": (None, "asset"),
    "Bank Accounts": ("Current Assets", "asset"),
    "Cash-in-Hand": ("Current Assets", "asset"),
    "Deposits (Asset)": ("Current Assets", "asset"),
    "Loans & Advances (Asset)": ("Current Assets", "asset"),
    "Stock-in-Hand": ("Current Assets", "asset"),
    "Sundry Debtors": ("Current Assets", "asset"),
    "Misc. Expenses (ASSET)": (None, "asset"),
    # Profit & loss
    "Sales Accounts": (None, "income"),
    "Direct Incomes": (None, "income"),
    "Indirect Incomes": (None, "income"),
    "Purchase Accounts": (None, "expense"),
    "Direct Expenses": (None, "expense"),
    "Indirect Expenses": (None, "expense"),
}

CASH_BANK = {"Cash-in-Hand", "Bank Accounts", "Bank OD A/c"}
PARTY_GROUPS = {"Sundry Debtors", "Sundry Creditors"}

VOUCHER_TYPES = ["Sales", "Purchase", "Receipt", "Payment", "Contra", "Journal", "Credit Note", "Debit Note",
                 "Metal Receipt", "Metal Issue"]
METAL_VOUCHERS = {"Metal Receipt", "Metal Issue"}  # move fine metal only, no rupees

METALS = ("gold", "silver")
# Ledger that holds the metal in hand (stock), created when a company first moves that metal.
STOCK_LEDGERS = {"gold": "Gold Stock", "silver": "Silver Stock"}

# name -> (group, tax kind). Tax kind tags GST ledgers so returns can be built from the books.
DEFAULT_LEDGERS: dict[str, tuple[str, str | None]] = {
    "Cash": ("Cash-in-Hand", None),
    "Capital": ("Capital Account", None),
    "Sales": ("Sales Accounts", None),
    "Purchase": ("Purchase Accounts", None),
    "Output CGST": ("Duties & Taxes", "output_cgst"),
    "Output SGST": ("Duties & Taxes", "output_sgst"),
    "Output IGST": ("Duties & Taxes", "output_igst"),
    "Output Cess": ("Duties & Taxes", "output_cess"),
    "Input CGST": ("Duties & Taxes", "input_cgst"),
    "Input SGST": ("Duties & Taxes", "input_sgst"),
    "Input IGST": ("Duties & Taxes", "input_igst"),
    "Input Cess": ("Duties & Taxes", "input_cess"),
    "TDS Payable": ("Duties & Taxes", "tds_payable"),
    "Round Off": ("Indirect Expenses", None),
}


def primary(group: str) -> str:
    parent = GROUPS.get(group, (None, None))[0]
    return parent or group


def nature(group: str) -> str | None:
    return GROUPS.get(group, (None, None))[1]


def statement(group: str) -> str | None:
    n = nature(group)
    if n in ("asset", "liability"):
        return "bs"
    if n in ("income", "expense"):
        return "pl"
    return None
