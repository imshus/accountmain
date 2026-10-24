"""Classify account / ledger / category names into Tally-style groups.

No vendor publishes a classifier, so this follows Tally's predefined groups and their
descriptions (researched Oct 2026). Every account gets a group plus where the group came
from: the user's own choice, a keyword rule, the account's balance direction for words
that can mean either (rent, interest, commission...), a party-name pattern, or
"Unclassified" when nothing fits. Unknown accounts are never silently treated as expenses.
"""

from __future__ import annotations

import re

# Group -> (statement, nature). Nature is the normal balance side.
GROUPS = {
    "Sales Accounts": ("pl", "income"),
    "Direct Incomes": ("pl", "income"),
    "Indirect Incomes": ("pl", "income"),
    "Purchase Accounts": ("pl", "expense"),
    "Direct Expenses": ("pl", "expense"),
    "Indirect Expenses": ("pl", "expense"),
    "Capital Account": ("bs", "liability"),
    "Reserves & Surplus": ("bs", "liability"),
    "Secured Loans": ("bs", "liability"),
    "Unsecured Loans": ("bs", "liability"),
    "Bank OD A/c": ("bs", "liability"),
    "Sundry Creditors": ("bs", "liability"),
    "Duties & Taxes": ("bs", "liability"),
    "Provisions": ("bs", "liability"),
    "Current Liabilities": ("bs", "liability"),
    "Fixed Assets": ("bs", "asset"),
    "Investments": ("bs", "asset"),
    "Deposits (Asset)": ("bs", "asset"),
    "Loans & Advances (Asset)": ("bs", "asset"),
    "Stock-in-Hand": ("bs", "asset"),
    "Sundry Debtors": ("bs", "asset"),
    "Cash-in-Hand": ("bs", "asset"),
    "Bank Accounts": ("bs", "asset"),
    "Suspense A/c": ("bs", "suspense"),
}
UNCLASSIFIED = "Unclassified"

# Tally's own group names (and common spellings of them), e.g. from a file's "Group" column.
_GROUP_NAMES = {name.lower(): name for name in GROUPS} | {
    "sundry debtor": "Sundry Debtors", "debtors": "Sundry Debtors", "trade receivables": "Sundry Debtors",
    "sundry creditor": "Sundry Creditors", "creditors": "Sundry Creditors", "trade payables": "Sundry Creditors",
    "direct expense": "Direct Expenses", "expenses (direct)": "Direct Expenses",
    "indirect expense": "Indirect Expenses", "expenses (indirect)": "Indirect Expenses",
    "direct income": "Direct Incomes", "income (direct)": "Direct Incomes",
    "indirect income": "Indirect Incomes", "income (indirect)": "Indirect Incomes",
    "sales account": "Sales Accounts", "purchase account": "Purchase Accounts", "duties and taxes": "Duties & Taxes",
    "reserves and surplus": "Reserves & Surplus", "bank od a/c": "Bank OD A/c", "bank occ a/c": "Bank OD A/c",
    "loans and advances (asset)": "Loans & Advances (Asset)", "loans & advances": "Loans & Advances (Asset)",
    "deposits": "Deposits (Asset)", "cash in hand": "Cash-in-Hand", "stock in hand": "Stock-in-Hand",
    "suspense": "Suspense A/c", "suspense account": "Suspense A/c", "capital": "Capital Account",
}

# Words that make a lending or deposit ledger a P&L item instead (interest on a loan, OD renewal fees...).
_COST_OF = r"interest|charges|fees?\b|processing|renewal"

# Checked in order; the first match wins. Every alternative matches only at a word start ("salar" matches Salaries,
# "cess" does not match Processing). The optional third item is an "unless" pattern: a name that also matches it skips
# the rule and goes on to the next ones. Specific multi-word phrases come first so that, say, "Salary Advance" is an
# advance and "Salary Payable" a liability before the plain "salar" expense rule sees them.
_RULES: list[tuple[str, str] | tuple[str, str, str]] = [
    ("Suspense A/c", r"suspense|difference in opening|opening balance difference"),
    ("Current Liabilities", r"advances? (from|received|against)|customers? advances?|deposits? (received|from)"),
    ("Loans & Advances (Asset)", r"(tds|tcs|income ?tax|it) (refund|receivable|recoverable)|advance tax|"
                                 r"capital advance|advances?\b|prepaid|pre-paid|loans? to\b|staff loan|"
                                 r"loans? (and|&) advances|(interest|income) accrued|accrued (interest|income)",
     r"interest on"),
    ("Indirect Incomes", r"written back|(profit|gain) (on|from) (sale|disposal)|capital gain"),
    ("Indirect Expenses", r"(loss) (on|from) (sale|disposal)|late fees?|penalt|interest on (late|delayed)|"
                          r"interest on (gst|tds|tcs)|(gst|tds|tcs) interest"),
    ("Fixed Assets", r"capital (wip|work)|cwip\b|accumulated depreciation|fixed assets?"),
    ("Deposits (Asset)", r"deposits?\b|fd\b|fdr\b|emd\b|margin money|bank guarantee|bg margin", _COST_OF),
    ("Sales Accounts", r"sales?\b|revenue|turnover",
     r"promotion|commission|incentive|discount|freight|carriage|cartage|on sales?\b|sales? tax|tax on|gst on|"
     r"tds|tcs|output|payable|of (fixed |capital )?assets?"),
    ("Purchase Accounts", r"purchases?\b",
     r"freight|carriage|cartage|commission|discount|tax on|gst on|tds|tcs|input|payable|of (fixed |capital )?assets?"),
    ("Duties & Taxes", r"[cis]gst|utgst|gst\b|cess\b|tds\b|tcs\b|rcm\b|output tax|input tax|professional tax payable|"
                       r"vat\b|cst\b|sales tax|service tax|tax payable|electronic (cash|credit) ledger"),
    ("Bank OD A/c", r"overdraft|od\b|od a/?c|cash credit|cc a/?c|cc limit|occ\b|hypothecation", _COST_OF),
    ("Secured Loans", r"term loan|vehicle loan|car loan|machinery loan|debentures?\b|secured loans?|bank loan|"
                      r"home loan|housing loan|gold loan|mortgage|loan against|working capital loan|wc loan|"
                      r"loans? from [\w .&]*bank\b", _COST_OF),
    ("Unsecured Loans", r"loans? from|unsecured|directors?'?s? loan|loans? \(liability\)", _COST_OF),
    ("Capital Account", r"capital|drawings?\b|proprietor|partner'?s?'?\b",
     r"interest|salary|remuneration|commission|reserve|ltd\b|limited|finance|engineering|technical|design|architect"),
    ("Reserves & Surplus", r"reserves?\b|surplus|retained|securities premium|share premium|profit (and|&) loss a/?c|"
                           r"p ?& ?l a/?c"),
    ("Provisions", r"provisions?\b(?! (stores?|traders?|mart|shop|merchants?|suppliers?)\b)"),
    ("Sundry Debtors", r"sundry debtors?|debtors?\b|trade receivables?"),
    ("Sundry Creditors", r"sundry creditors?|creditors?\b|trade payables?"),
    ("Current Liabilities", r"outstanding|payable|unpaid"),
    ("Indirect Incomes", r"interest (received|earned|income|on (fd|fixed deposit|savings|sb|deposits?|income ?tax|"
                         r"it refund))|discount received|commission received|commission income|rent received|"
                         r"rent income|rental income|dividends?\b|misc(ellaneous)? income|other income|bank interest"),
    ("Direct Incomes", r"job ?work income|service charges received|labour charges received|labor charges received|"
                       r"making charges received"),
    ("Direct Expenses", r"freight inward|carriage inward|cartage|freight on purchases?|carriage on purchases?|wages|"
                        r"factory|power (and|&) fuel|job ?work|manufactur|packing material|octroi|import duty|"
                        r"customs duty|coal\b|consumables|stores (and|&) spares|making charges|karigar|"
                        r"labou?r charges|hamali|loading",
     r"building|shed|land\b|plant\b|machinery|equipment|payable"),
    ("Indirect Expenses", r"salar|electricity|electric (charges|bill|exp)|telephone|internet|mobile|printing|"
                          r"stationery|postage|courier|"
                          r"office(?! (equipment|furniture|building|premises|computers?|laptops?|vehicles?|car)\b)|"
                          r"conveyance|travel|advertis|discount allowed|bank charge|audit fee|legal|professional|"
                          r"repair|insurance(?! claim)|depreciation|bad debt|freight outward|"
                          r"carriage outward|round(ing)? ?off|staff|maintenance|utilit|fuel|petrol|diesel|"
                          r"remuneration|rates (and|&) taxes|donation|promotion|(car|vehicle|motor) (expenses?|exp|"
                          r"running|hire)|tea\b|refreshment|food\b|canteen|bonus|gratuity|subscription|"
                          r"expenses?\b|exps?\b"),
    ("Fixed Assets", r"land\b|building|shed\b|plant\b|machinery|furniture|fixtures?|computers?\b|laptops?|vehicles?|"
                     r"motor (car|cycle|vehicle)|equipment|air condition|electrical (fittings|installation)|"
                     r"goodwill|trademark|patent|copyright"),
    ("Investments", r"investments?\b|shares (of|in)|mutual funds?|nsc\b|kvp\b|bonds?\b"),
    ("Loans & Advances (Asset)", r"receivables?|recoverable"),
    ("Stock-in-Hand", r"stocks?\b|stock-in|inventor(y|ies)"),
    ("Cash-in-Hand", r"cash\b|petty cash", r"discount|credit"),
    ("Bank Accounts", r"bank\b|hdfc|sbi\b|icici|axis\b|kotak|pnb\b|canara|indusind|yes bank|idfc|current a/?c|"
                      r"sb a/?c|savings a/?c", r"interest|charges|commission|guarantee"),
]


def _word_start(pattern: str) -> re.Pattern:
    # The group makes the word-start guard apply to every alternative, not only the first one.
    return re.compile(rf"(?i)(?<![a-z])(?:{pattern})")


_COMPILED = [(rule[0], _word_start(rule[1]), _word_start(rule[2]) if len(rule) > 2 else None) for rule in _RULES]
# Only the specific phrases before the sales rule ("Advance to Suppliers") outrank a party name.
_PARTY_FIRST = next(i for i, rule in enumerate(_RULES) if rule[0] == "Sales Accounts")

# Words that can be income or expense; the balance direction decides.
_EITHER_WAY = _word_start(r"rent|interest|commission|discount|freight|charges|fees?\b|brokerage|kasar|vatav|"
                          r"incentive|royalty|hire")
# A plain "loan" is money borrowed (credit balance) or lent (debit balance).
_LOAN = _word_start(r"loans?\b")
# A party's business name: the marker follows at least one other word ("Mahalaxmi Agencies", not "Agency Commission").
_PARTY = re.compile(
    r"(?i)^m/s\b|\S\s.*?(?<![a-z])(?:pvt|private|ltd|limited|llp|& ?co\b|traders?\b|trading|enterprises?|industries|"
    r"agenc|stores?\b|sons\b|brothers|bros\b|corporation|jewell?ers?\b|associates|suppliers?\b|distributors?\b|"
    r"mart\b|company)"
)
# Banks, lenders and holdings whose names carry "Ltd" are not trading parties.
_NOT_PARTY = _word_start(r"bank\b|loans?\b|shares?\b|investments?\b|debentures?\b|bonds?\b|mutual funds?")


def _normal(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"(?i)\band\b", "&", name)).strip().lower()


def classify(name: str, net_paise: int) -> tuple[str, str]:
    """(group, source) for one account name; net_paise > 0 means a debit balance."""
    text = name.strip()
    group = _GROUP_NAMES.get(text.lower()) or _GROUP_NAMES.get(_normal(text))
    if group:
        return group, "keyword"
    # A trading party's name decides before the expense / asset words in it ("Sai Computers Pvt Ltd").
    party = net_paise and _PARTY.search(text) and not _NOT_PARTY.search(text)
    for index, (group, pattern, unless) in enumerate(_COMPILED):
        if party and index >= _PARTY_FIRST:
            break
        if pattern.search(text) and not (unless and unless.search(text)):
            return group, "keyword"
    if party:
        return ("Sundry Debtors" if net_paise > 0 else "Sundry Creditors"), "party name"
    if _EITHER_WAY.search(text) and net_paise:
        return ("Indirect Expenses" if net_paise > 0 else "Indirect Incomes"), "direction"
    if _LOAN.search(text) and net_paise:
        return ("Loans & Advances (Asset)" if net_paise > 0 else "Unsecured Loans"), "direction"
    return UNCLASSIFIED, "unclassified"


def statement_of(group: str) -> str | None:
    return GROUPS.get(group, (None, None))[0]


def nature_of(group: str) -> str | None:
    return GROUPS.get(group, (None, None))[1]
