# Pitfalls of Importing Accounting Data from Excel/CSV Exports (Indian SME context, 2026) and How Robust Importers Handle Them

Scope: Accounts.ai reads uploaded .xlsx/.xls/.csv files (Tally Prime, Busy, Vyapar, Zoho Books, bank net-banking exports) with pandas + openpyxl, detects the header row, converts amounts and dates, and stores in SQLite. Goal: every rupee read correctly, provably.

Conventions in these notes: "Cited Findings" are facts from sources fetched or searched in this session. "Inferences" contain engineering rules, regexes and code derived from those findings (and from general Python/Excel knowledge where flagged). Anything not verified is in "Gaps". Severity labels used in the rules: **BLOCK** (import must not commit), **WARN** (import may commit but the user must see it), **INFO**.

---

## 1. Typical layouts of Tally Prime exports and Indian bank statement exports

### Takeaway
No export can be parsed with a fixed `skiprows`: Tally lets users toggle company/header details, and bank layouts change without notice (SBI changed its format in 2026). The most dangerous Tally fact is that **the "Dr"/"Cr" on balances is held in the cell's number format, not the cell value**. The stored number is unsigned, so `pandas.read_excel` silently loses the sign. Bank "XLS" downloads are often not real Excel files: SBI's legacy ".xls" is tab-separated text, and the SBI YONO .xlsx is password-protected.

### Cited Findings

**Tally Prime / Tally.ERP 9**
- TallyPrime's export lists **Excel (.xlsx)** among its formats, alongside ASCII, HTML, JPEG, PDF, XML and JSON. Export configuration (Alt+E > Configuration) includes "Export base currency symbol along with the amount" (recommended "Yes" for multi-currency), "Open file after export", "Location of Import/Export Files", and configurable "Header Information" and "Company Details". For a single report (Ctrl+E, then C), "Report Details" and "Export Settings" vary by report. — [TallyPrime Help: Export Data](https://help.tallysolutions.com/tally-prime/data-management/export-data-in-tally/)
- The Sales Register can be exported via Alt+E with File Format "Excel (Spreadsheet)", and Tally documents a pivot-table extraction workflow built on that export. — [TallyPrime Help: Extract Data Through Pivot Table](https://help.tallysolutions.com/tally-prime/extract-share-data/extracting-data-through-pivot-table-tally/)
- When data is exported to Excel from TallyPrime Server, **three sheets** are exported. — [TallyPrime Help: Export Data in TallyPrime Server](https://help.tallysolutions.com/export-data-in-tallyprime-server/) (search snippet; page not fully read)
- Older Tally.ERP 9 exported ledgers as **Microsoft Excel 97-2003 (.xls)**. The "Ledgers of All Accounts" export path is Gateway of Tally > Multi Account Printing > Account Books > Ledger > All Accounts > Export. — [ExcelDemy: Export All Ledgers from Tally in Excel](https://www.exceldemy.com/export-all-ledgers-from-tally-in-excel/) (search snippet)
- A Tally.ERP 9 release note records a fix so that the **"Vch Type, Vch No., Debit, and Credit" columns** of the ledger export "are aligned correctly". Earlier releases produced misaligned columns. — [Tally Help: Release 5.0 Export/Import notes](https://help.tallysolutions.com/article/te9rel50/Release_Notes/Technical_Features/Export___Import.htm) (search snippet)
- **Dr/Cr is a display format, not data.** On a Chandoo forum thread about Tally-exported trial balances: "the 'Cr' and 'Dr' aren't actually part of the cell value, but are in the cell's format." A user reported that AutoSum "consider[s] all the numeric values as positive irrespective of Dr or Cr". The accepted fix reads the cell's displayed text and multiplies by -1 when it ends in "Cr". Another workaround saves the file as CSV so the suffix becomes literal text. — [Chandoo Forum: How to convert Cr amount as negative](https://chandoo.org/forum/threads/how-to-convert-cr-amount-as-negative.26849)
- The same behaviour is reported on CAclubindia: Dr/Cr is "visible in excel however while selecting the respective cell it only shows the numeric amount". The suggested fix is a VBA function that checks whether the displayed text ends in "Cr". — [CAclubindia: Convert Tally exported Cr as negative](https://www.caclubindia.com/forum/convert-tally-exported-cr-as-negative-in-excel-344117.asp)
- On the import side, Tally's own Excel import supports either separate Debit and Credit columns or a single amount column, using a "Compute Value" mapping that specifies whether the value is Debit or Credit. Both conventions are first-class in Tally's world. — [TallyPrime Help: Map Nett Amount Values](https://help.tallysolutions.com/map-nett-amount-values/) (search snippet)
- Some MS Office versions refuse to open TallyPrime exports as unsafe. The fix is to upgrade Office or add the TallyPrime folder to Excel's Trusted Locations. Users may therefore re-save, convert or copy-paste exports before uploading. — [TallyPrime Help: Unable to Export to MS Excel](https://help.tallysolutions.com/unable-to-export-to-ms-excel-tally/) (search snippet)

**Bank statements**
- **SBI (legacy OnlineSBI ".xls")**: the README of a maintained open-source preprocessor says these files are "actually plaintext CSV files". The script reads them with `pd.read_csv(..., sep='\t', skiprows=20, skipfooter=2, engine='python')`. It probes row 7 for a cell starting "Account Number". Columns are `'Txn Date'` and `'Value Date'`, parsed with `format='%d %b %Y'` (e.g. "05 Jan 2024"). The Debit header literally has **leading spaces** (`'        Debit'`), and an empty trailing column `"Unnamed: 7"` must be dropped. Commas are stripped and values are converted with `pd.to_numeric(..., errors='coerce')`. — [gnucash_statement_preprocessors: SBICSV2Gnucash.py](https://raw.githubusercontent.com/abhijit86k/gnucash_statement_preprocessors/main/SBICSV2Gnucash.py); [README](https://github.com/abhijit86k/gnucash_statement_preprocessors)
- **SBI (YONO .xlsx)**: these are **password-protected**. The script decrypts them in memory with `msoffcrypto` and reads with `header=None`. It validates fixed cells ("Account Number" at row 9; "IFSC Code  :  SBIN" at B11). It finds the data start as the row after a column-A cell starting "Statement From", which is expected at row 17 and only warned about if different. It finds the end as two rows above "Statement Summary". Columns are `Date` (format `'%d/%m/%Y'`), `Details` (contains embedded newlines that are stripped) and `Ref No/Cheque No`. — [SBIXLS2Gnucash.py](https://raw.githubusercontent.com/abhijit86k/gnucash_statement_preprocessors/main/SBIXLS2Gnucash.py)
- The same author reported on the GnuCash mailing list (13 July 2026) that SBI "recently changed the export format for their statement" and the scripts had to be updated. — [gnucash-user list, July 2026](https://lists.gnucash.org/pipermail/gnucash-user/2026-July/121136.html)
- The same repository supports Canara Bank as CSV from online banking. — [README](https://github.com/abhijit86k/gnucash_statement_preprocessors)
- **HDFC-style layout**: an exact-phrase search for the column set `Narration | Chq./Ref.No. | Value Dt | Withdrawal Amt. | Deposit Amt. | Closing Balance` matched about 10 publicly posted statement copies, mostly HDFC-style statements. (Links are deliberately omitted because they are private individuals' financial documents. Treat this as corroborating evidence, not an official spec.)
- ICICI statements list transactions chronologically, each with date, transaction type, amount, and balance after the transaction. — [Upstox: ICICI Bank Statement guide](https://upstox.com/?p=39170) (search snippet)
- Commercial and open-source parsers exist (e.g. Xfina, which reads HDFC/ICICI/SBI Excel files and outputs ReBIT-style JSON), which indicates the per-bank template approach is standard. — [Xfina on PyPI](https://pypi.org/project/xfina/) (search snippet; page failed to load)

### Inferences

#### 1a. File-type sniffing before choosing a reader (BLOCK on unknown)
Never trust the extension. Read the first 8 bytes:
| Magic bytes | Real format | Reader |
|---|---|---|
| `50 4B 03 04` (`PK..`) | .xlsx/.xlsm (ZIP) | openpyxl |
| `D0 CF 11 E0 A1 B1 1A E1` | OLE2/CFB: real .xls **or an encrypted .xlsx** (Office encryption wraps the file in an OLE container) | try xlrd; if it fails, check `msoffcrypto.OfficeFile(f).is_encrypted()` and ask the user for the password, never guess |
| starts with `<` / `<html` / `<?xml` after BOM/whitespace | HTML or SpreadsheetML disguised as .xls | `pandas.read_html` or lxml, with a WARN |
| `FF FE` / `FE FF` | UTF-16 text (Excel "Unicode Text" saves TSV this way) | csv with utf-16 |
| anything else | text CSV/TSV (SBI legacy ".xls") | `csv.Sniffer` on the first ~20 KB to pick `,`/`\t`/`;`/`|` |

xlrd will not read password-protected files and reads only .xls ([xlrd docs](https://xlrd.readthedocs.io/en/latest/)), so encryption must be detected first.

#### 1b. Header detection by scoring, never by fixed row number
```python
import re
HEADER_SYNONYMS = {
    "date":      {"date", "txn date", "tran date", "transaction date", "posting date", "vch date"},
    "value_date":{"value date", "value dt"},
    "narration": {"narration", "particulars", "description", "details", "transaction remarks", "remarks"},
    "ref":       {"chq./ref.no.", "ref no./cheque no.", "ref no/cheque no", "cheque number", "chq no",
                  "chqno", "vch no.", "vch no", "voucher no.", "utr", "reference"},
    "vch_type":  {"vch type", "voucher type"},
    "debit":     {"debit", "withdrawal amt.", "withdrawal amount", "withdrawals", "dr", "debit amount", "outwards"},
    "credit":    {"credit", "deposit amt.", "deposit amount", "deposits", "cr", "credit amount", "inwards"},
    "amount":    {"amount", "transaction amount", "txn amount", "value"},
    "drcr_flag": {"dr/cr", "cr/dr", "dr / cr", "type", "txn type"},
    "balance":   {"balance", "closing balance", "bal", "running balance"},
}
def norm_header(x) -> str:
    s = re.sub(r"\s+", " ", str(x or "")).strip().lower()
    s = re.sub(r"\((inr|rs\.?|₹)\s*\)", "", s).strip()   # "Withdrawal Amount (INR )" -> "withdrawal amount"
    return s
def score_row(cells) -> set[str]:
    found = set()
    for c in cells:
        h = norm_header(c)
        for canon, syns in HEADER_SYNONYMS.items():
            if h in syns:
                found.add(canon)
    return found
# Scan the first ~60 rows. The header is the first row whose matches include
# a date field and (debit+credit | amount+drcr_flag | balance), with >= 3 matches.
# If the next row also scores (two-row header, e.g. "Closing Balance" over "Debit | Credit"),
# merge them: forward-fill the upper row across merged ranges, then join "upper|lower".
```
- Normalise headers before matching: strip leading/trailing spaces (SBI's `'        Debit'`), collapse internal whitespace and newlines, lowercase, and drop "(INR )".
- Save the detected header row index, the raw header strings and the column mapping in an import manifest (see section 6).
- Everything above the header row is "preamble". Parse it with regexes for company name, account number (mask it), `Statement From ... To ...` / `Period`, `From 1-Apr-25 to 31-Mar-26`, and "Opening Balance". These are the **expected period and opening balance**, used later for validation.

#### 1c. Tally-specific handling
- **Read Dr/Cr from `cell.number_format` with openpyxl. pandas cannot see it.** pandas returns only the value ("any numeric columns will automatically be parsed, regardless of display format" — [pandas.read_excel](https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html)). Code:
```python
def split_format_sections(fmt: str) -> list[str]:
    """Split an Excel number format on ';' outside quotes/escapes (pos;neg;zero;text)."""
    out, cur, in_q, i = [], [], False, 0
    while i < len(fmt):
        ch = fmt[i]
        if ch == '\\' and not in_q and i + 1 < len(fmt):
            cur.append(fmt[i:i+2]); i += 2; continue
        if ch == '"':
            in_q = not in_q
        if ch == ';' and not in_q:
            out.append(''.join(cur)); cur = []
        else:
            cur.append(ch)
        i += 1
    out.append(''.join(cur))
    return out

DRCR_IN_FMT = re.compile(r'(?i)(?<![a-z])(dr|cr)\.?(?![a-z])')
def drcr_from_format(fmt: str, value: float) -> str | None:
    secs = split_format_sections(fmt or "General")
    sec = secs[1] if (value < 0 and len(secs) > 1) else secs[0]
    m = DRCR_IN_FMT.search(sec.replace('\\', ''))
    return m.group(1).upper() if m else None
```
  - Rule: in a Tally "balance" column, every non-zero numeric cell must yield `DR` or `CR` from its format, or the file must have separate Debit and Credit columns. Otherwise **BLOCK** with "sign of balances cannot be determined; re-export with Debit/Credit columns".
  - Handle both encodings, since the exact format string Tally writes was not verified (see Gaps): (a) the per-cell literal `#,##0.00 "Cr"` with a positive value, and (b) a two-section format `0.00 "Dr";0.00 "Cr"` where the value's sign selects the section. If a value is negative **and** its chosen section contains Dr/Cr, sign the amount from Dr/Cr only and do not also apply the minus. Also WARN on such cells.
  - If a user re-saved the Tally file as CSV, the suffix becomes literal text (the Chandoo workaround). The text parser in section 2 handles "1,234.00 Cr".
- **Multiple sheets** (TallyPrime Server writes three): score every visible sheet with the header scorer and pick by content, not `sheet_name=0`. If more than one sheet scores, ask the user.
- **Title rows vary** with the "Company Details"/"Header Information" toggles, so derive them from header detection.
- **Currency symbol inside amounts** when "Export base currency symbol along with the amount" is on. This may come as text ("₹ 1,000.00") or as number format; handle both.
- **Column misalignment** (older ERP 9 bug): after mapping, check that ≥95% of non-blank cells in the "debit"/"credit" columns parse as amounts and that "vch_no" is not mostly numeric amounts. Otherwise BLOCK with "columns appear shifted".
- **Grouped/indented reports** (Trial Balance, Balance Sheet, Group Summary, Outstanding by group) — *inference, verify with samples*: in "Detailed" mode, group rows (e.g. "Current Assets", "Sundry Debtors") carry their own totals and child ledgers appear below them. Importing both **double counts**. Detect hierarchy with `cell.alignment.indent`, leading spaces in the name cell, and `cell.font.b` (bold group rows). Prove it by checking that the children's sum equals the group row. Import only leaf ledgers; keep group rows as control totals.
- **Opening/closing/total rows** inside ledger and register exports must be classified and excluded from transactions but kept as control figures (section 6).

#### 1d. Bank-specific handling
- Keep a **template registry**, a small YAML/JSON per bank and layout version: header synonyms, date format(s), amount layout (`debit_credit_columns` | `amount_plus_drcr_flag` | `signed_amount`), preamble regexes, and footer markers (`Statement Summary`, `**End of Statement`, `Opening Balance ... Closing Balance` summary lines). Fall back to generic scoring when no template matches. **WARN** when a known bank's file no longer matches its template, since layouts change (SBI 2026).
- Clean narrations: remove embedded `\n` (SBI YONO `Details`). Detect **continuation rows**: blank date, blank amounts and non-blank narration should be appended to the previous transaction, never imported as a zero transaction.
- Withdrawal/Deposit layout: exactly one of the two must be non-zero per transaction row. If both are filled or both are empty, **BLOCK** that row (or WARN if the bank emits zero-value rows such as charges reversed).
- Single amount + Dr/Cr indicator column: map `DR`, `Dr.`, `Debit`, `W`/`Withdrawal` to debit and `CR`, `Cr.`, `Credit`, `Deposit` to credit. Single letters are ambiguous (`D` can mean Debit or Deposit), so they must come from the bank template and never be guessed. Validate the mapping with the running-balance check (section 6).
- Account numbers, IFSC, cheque numbers, UTR/reference numbers: always read as **text** (`dtype=str` / openpyxl value as-is), never numeric. They lose leading zeros and digits beyond 15 (see section 2).

### Gaps
- **Exact Excel number-format string Tally Prime writes for Dr/Cr** (literal per-cell vs two-section format) was not confirmed. Forum evidence only says it is "in the cell's format" and values are unsigned. Action: export Ledger, Trial Balance, Day Book, Sales Register and Outstanding reports from TallyPrime 5.x/6.x and inspect `cell.number_format`.
- No official or sample layouts found for Tally **Day Book, Trial Balance, Sales/Purchase Register, Bills Outstanding** exports. Exact row labels ("Opening Balance", "Current Total", "Closing Balance", "Grand Total"), column headers, date display format (e.g. "1-Apr-25"), and whether group rows are bold/indented in the xlsx all need verification on real exports.
- **ICICI, Axis, Kotak** exact column headers, preamble length, date formats and sort order were not verified. Commonly reported but **unverified** headers: ICICI "Transaction Date / Value Date / Cheque Number / Transaction Remarks / Withdrawal Amount (INR ) / Deposit Amount (INR ) / Balance (INR )"; Axis "Tran Date / CHQNO / PARTICULARS / DR / CR / BAL / SOL". Build these templates from real customer files.
- **Busy, Vyapar, Zoho Books** export layouts: no sources found in this session.
- Whether HDFC's ".xls" download is a true BIFF .xls, HTML, or text was not verified. The sniffing rule in 1a covers all cases.

---

## 2. Number formats: lakh grouping, negatives, Dr/Cr, currency, text-numbers, scientific notation, percentages

### Takeaway
Treat a numeric Excel cell and a text cell as two different parsing paths. Numeric cells are IEEE doubles with 15 significant digits whose display (Dr/Cr, parentheses, lakh commas) lives in the format string. Text cells need a strict parser that accepts Indian and Western grouping, parentheses, leading or trailing minus, Dr/Cr and currency tokens, and **rejects** everything else rather than coercing it to NaN.

### Cited Findings
- `thousands`/`decimal` in `read_excel` are "only necessary for columns stored as TEXT in Excel, any numeric columns will automatically be parsed, regardless of display format". — [pandas.read_excel](https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html)
- `dtype=object` preserves "data as stored in Excel and not interpret dtype". Converters are applied "INSTEAD of dtype conversion". — [pandas.read_excel](https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html)
- Default NA strings in pandas include `''`, `'#N/A'`, `'NA'`, `'N/A'`, `'n/a'`, `'NULL'`, `'null'`, `'None'`, `'NaN'`, `'nan'`, `'<NA>'`, `'-NaN'`, `'1.#IND'` and others. `keep_default_na=False` without `na_values` means "no strings will be parsed as NaN". — [pandas.read_excel](https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html)
- In pandas examples, a numeric column with a missing value becomes float (`1.0, 2.0, NaN`). — [pandas.read_excel](https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html)
- Excel stores numbers as IEEE 754 doubles and "can only do so within 15 digits of precision". For example, 0.000123456789012345 + 1 yields 1.00012345678901. Summing 0.0001 ten thousand times prints 0.999999999999996. — [Microsoft Learn: Floating-point arithmetic may give inaccurate result in Excel](https://learn.microsoft.com/en-us/troubleshoot/microsoft-365-apps/excel/floating-point-arithmetic-inaccurate-result)
- Excel's "Set precision as displayed" option permanently discards precision beyond the displayed decimals ("You can't undo this option"). Without it, displayed and stored values can differ. — [Microsoft Learn](https://learn.microsoft.com/en-us/troubleshoot/microsoft-365-apps/excel/floating-point-arithmetic-inaccurate-result)
- A real-world SBI preprocessor converts amounts with `pd.to_numeric(..., errors='coerce')` and then `replace(np.nan, '')`. Any unparseable amount silently becomes blank. — [SBICSV2Gnucash.py](https://raw.githubusercontent.com/abhijit86k/gnucash_statement_preprocessors/main/SBICSV2Gnucash.py)
- Tally exports put Dr/Cr in number formats with unsigned values. After a CSV round trip, the suffix becomes literal text. — [Chandoo Forum](https://chandoo.org/forum/threads/how-to-convert-cr-amount-as-negative.26849)

### Inferences

#### 2a. Pitfall catalogue -> rule
| # | Pitfall | Example | Rule |
|---|---|---|---|
| N1 | Indian lakh grouping as text | `1,23,45,678.00` | Accept only if it matches `INDIAN` or `WESTERN` grouping regex below; strip commas. Reject malformed grouping (`1,2345.00`) as BLOCK. |
| N2 | Parentheses negative | `(12,500.00)` | negative. Also as a number format `#,##0.00;(#,##0.00)`: value already negative, nothing to do. |
| N3 | Trailing minus | `12,500.00-` | negative (common in mainframe-style bank exports). |
| N4 | Unicode minus/dashes | `−500` (U+2212), `–500` | normalise to `-` before parsing. |
| N5 | Dr/Cr suffix/prefix text | `1,234.00 Dr`, `Cr 500`, `500.00CR` | Return the Dr/Cr marker separately. The caller maps it to sign per column semantics (ledger balance vs bank balance). |
| N6 | Dr/Cr in number format | Tally balances | section 1c `drcr_from_format`. |
| N7 | Conflicting sign markers | `(1,000.00) Cr`, `-500 Dr` | BLOCK row ("ambiguous sign"). |
| N8 | Currency tokens | `₹1,000`, `Rs. 1,000`, `INR 1000`, `Rs1000/-` | strip `₹`, `Rs.`, `Rs`, `INR`, trailing `/-`. Any other remaining letters means reject. |
| N9 | Mojibake rupee | `â‚¹1,000` (UTF-8 read as cp1252) | detect `â‚¹`, re-decode the file as UTF-8 (WARN). |
| N10 | NBSP / thin spaces | `1,000.00 ` | NFKC normalise + strip `    `. Never remove *internal* spaces between digits (`1 000`): reject instead. |
| N11 | Numbers stored as text | Excel green-triangle cells, format `@` | openpyxl gives `str` with `data_type == 's'`: route to text parser, record WARN "text-stored number". |
| N12 | Scientific notation in text | `1.23457E+11` (CSV opened and re-saved in Excel) | **BLOCK** for amounts and IDs: digits are already lost (15-digit limit). For a numeric cell, scientific display is harmless. |
| N13 | Long IDs as numbers | UTR/account no. `123456789012345678` → `123456789012345000` | read ID columns as text. If an ID cell is numeric with ≥ 16 digits, BLOCK (corrupted upstream). |
| N14 | Blank vs zero vs dash | `''`, `-`, `--`, `Nil`, `0.00` | Distinguish "explicitly zero" from "missing". For Withdrawal/Deposit pairs, the blank side means 0 **only if** the other side is non-zero. |
| N15 | pandas NA strings | narration `"NA"` / party named `"None"` → NaN | `keep_default_na=False, na_filter=False` for text columns; or read via openpyxl directly. |
| N16 | Hidden decimals | displays `1,234.57`, stores `1234.5678` (formula result) | After converting a float, if it has more than 2 decimal places, WARN/BLOCK "sub-paise value"; show both. |
| N17 | Magnitude beyond 15 sig. digits | ≥ ₹10,00,00,00,00,000 (1e13) with paise | BLOCK. Not representable exactly in Excel. |
| N18 | Percent cells | `18%` as text, or 0.18 with format `0%` | Only in rate columns. Text `18%` → Decimal('18'), stored as rate; numeric 0.18 with `%` in format → 18. Never treat as an amount. |
| N19 | Booleans/errors in amount col | `TRUE`, `#VALUE!`, `#REF!`, `#DIV/0!` | BLOCK. openpyxl `data_type == 'e'` for error cells. |
| N20 | Integer columns turned float by NaN | cheque no. `123456.0` | read as text; never `astype(str)` a float column (gives `"123456.0"`). |

#### 2b. Strict text-amount parser
```python
import re, unicodedata
from decimal import Decimal

INDIAN  = re.compile(r'^\d{1,2}(?:,\d{2})*,\d{3}(?:\.\d+)?$')   # 1,23,45,678.00 / 12,345 / 1,234
WESTERN = re.compile(r'^\d{1,3}(?:,\d{3})+(?:\.\d+)?$')         # 12,345,678.00
PLAIN   = re.compile(r'^(?:\d+(?:\.\d+)?|\.\d+)$')
SCI     = re.compile(r'^\d+(?:\.\d+)?[eE][+-]?\d+$')
CURRENCY= re.compile(r'(?i)₹|\bINR\b\.?|\bINR(?=\d)|\bRs\.?|/-$')
DRCR_SUF= re.compile(r'(?i)(?<![a-z])(dr|cr)\.?$')
DRCR_PRE= re.compile(r'(?i)^(dr|cr)\.?(?![a-z])')
SPACES  = re.compile(r'[\s    ]+')
NULLISH = {'', '-', '--', '—', 'nil', 'na', 'n/a', 'null', 'none'}

class AmountError(ValueError):
    pass

def parse_amount_text(raw: str):
    """-> (Decimal | None, drcr: 'DR'|'CR'|None, sign_markers: list[str]). Never guesses."""
    s = unicodedata.normalize('NFKC', str(raw))
    if 'â‚¹' in s:
        raise AmountError('mojibake rupee sign: file decoded with wrong encoding')
    s = s.replace('−', '-').replace('–', '-').replace('—', '-')
    s = SPACES.sub(' ', s).strip()
    if s.lower() in NULLISH:
        return None, None, []
    s = CURRENCY.sub('', s).strip()
    markers = []
    drcr = None
    m = DRCR_SUF.search(s) or DRCR_PRE.search(s)
    if m:
        drcr = m.group(1).upper()
        s = (s[:m.start()] + s[m.end():]).strip()
    if s.startswith('(') and s.endswith(')'):
        s = s[1:-1].strip(); markers.append('parentheses')
    if s.startswith('-'):
        s = s[1:].strip(); markers.append('leading_minus')
    elif s.endswith('-'):
        s = s[:-1].strip(); markers.append('trailing_minus')
    elif s.startswith('+'):
        s = s[1:].strip()
    if len(markers) > 1 or (markers and drcr):
        raise AmountError(f'conflicting sign markers in {raw!r}')
    if ',' in s:
        if not (INDIAN.match(s) or WESTERN.match(s)):
            raise AmountError(f'invalid digit grouping in {raw!r}')
        s = s.replace(',', '')
    elif SCI.match(s):
        raise AmountError(f'scientific notation in text {raw!r}: digits may be lost')
    if not PLAIN.match(s):
        raise AmountError(f'not an amount: {raw!r}')
    d = Decimal(s)
    if markers:
        d = -d
    if d.as_tuple().exponent < -2:
        raise AmountError(f'more than 2 decimal places: {raw!r}')   # or WARN, per policy
    return d, drcr, markers
```
Unit-test it with: `1,23,45,678.00`, `12,345,678.00`, `(1,000.50)`, `1000.50-`, `₹ 1,000`, `Rs.1,000/-`, `INR1000`, `1,234.00 Dr`, `Cr 99.99`, `−5`, `1,2345` (reject), `1.2E+11` (reject), `(5) Cr` (reject), `NA` (None), `1 000` (reject), `0.005` (reject).

#### 2c. Numeric (float) cell to integer paise without float error
```python
from decimal import Decimal
def float_cell_to_paise(v) -> int:
    if isinstance(v, bool):
        raise AmountError('boolean in amount column')
    if isinstance(v, int):
        return v * 100
    if v != v or v in (float('inf'), float('-inf')):
        raise AmountError('NaN/inf')
    if abs(v) >= 1e13:
        raise AmountError('exceeds 15 significant digits; cannot be exact in Excel')
    d = Decimal(repr(v))           # repr = shortest round-trip string: 1234.57 -> '1234.57'
    q = d.quantize(Decimal('0.01'))
    if d != q:
        raise AmountError(f'sub-paise value {d} (display may show {q})')  # N16
    return int(q * 100)
```
Use `Decimal(repr(v))`, **not** `Decimal(v)`. `Decimal(1.1)` expands to `1.100000000000000088817841970012523233890533447265625` ([Python decimal docs](https://docs.python.org/3/library/decimal.html)), which would make every value look like it has sub-paise digits. `repr()` returns the shortest decimal string that round-trips (standard CPython behaviour; not re-verified this session). For values with at most 15 significant digits, which Excel guarantees, it returns the digits the user typed.

#### 2d. pandas settings if pandas is kept in the pipeline
- `.xlsx`: prefer openpyxl cell iteration (value + `data_type` + `number_format` + hidden + merged) over `read_excel`, because `read_excel` drops formats. If `read_excel` is used, pass `header=None, dtype=object, keep_default_na=False, na_filter=False` and do all conversion yourself.
- `.csv`: `pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False, encoding=..., sep=...)`. Never pass `thousands=','` and trust it. Use the strict parser so malformed grouping is caught.
- Never `pd.to_numeric(errors='coerce')` on money. If you must use it, compare the NaN count before and after and BLOCK on any new NaN.

### Gaps
- Whether Tally writes lakh grouping as a number format (e.g. `#,##,##0.00`) or as text in xlsx exports was not verified. It doesn't matter for numeric cells (the value is a number either way) but should be confirmed.
- Exact trailing-minus or "CR" conventions of specific Indian bank exports (e.g. balance shown as `12,345.00 CR`) were not verified from primary samples.

---

## 3. Dates: DD/MM vs MM/DD, Excel serials, two-digit years, text months, April–March financial year

### Takeaway
Pick **one explicit format per column** from a whitelist, validate that 100% of cells parse, and resolve DD/MM vs MM/DD ambiguity using evidence (values > 12, the statement period in the preamble, monotonic ordering). Never use per-cell guessing (`dayfirst=True` is explicitly "not strict"; `format='mixed'` is "risky").

### Cited Findings
- pandas `to_datetime`: "`dayfirst=True` is not strict, but will prefer to parse with day first". `format='mixed'` infers per element: "This is risky, and you should probably use it along with dayfirst". `errors='coerce'` turns unparseable or out-of-bounds values into NaT. — [pandas.to_datetime](https://pandas.pydata.org/docs/reference/api/pandas.to_datetime.html)
- `read_excel(parse_dates=...)`: "If a column or index contains an unparsable date, the entire column or index will be returned unaltered as an object data type". The docs recommend reading as object and applying `to_datetime` for non-standard formats. — [pandas.read_excel](https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html)
- Excel deliberately treats 1900 as a leap year for Lotus 1-2-3 compatibility. Only dates before 1 March 1900 are affected (e.g. WEEKDAY results), and all other leap years are handled correctly. — [Microsoft Learn: Excel incorrectly assumes 1900 is a leap year](https://learn.microsoft.com/en-us/troubleshoot/microsoft-365-apps/excel/wrongly-assumes-1900-is-leap-year)
- Real bank formats observed in code: SBI legacy uses `'%d %b %Y'` ("05 Jan 2024") and SBI YONO uses `'%d/%m/%Y'`. Both banks put `Txn Date` and `Value Date` side by side. — [SBICSV2Gnucash.py](https://raw.githubusercontent.com/abhijit86k/gnucash_statement_preprocessors/main/SBICSV2Gnucash.py); [SBIXLS2Gnucash.py](https://raw.githubusercontent.com/abhijit86k/gnucash_statement_preprocessors/main/SBIXLS2Gnucash.py)

### Inferences

#### 3a. Cell-type branches
1. **openpyxl `datetime`/`date` value** (cell has a date number format): take `.date()`. If a non-midnight time component appears in a date column, WARN, because the value may be a time-stamped or float-mangled serial.
2. **Numeric value in a date column** (date stored as a General-formatted serial, or pasted as values): convert with `pd.to_datetime(v, unit='D', origin='1899-12-30')` for the 1900 date system. The 1899-12-30 origin absorbs the fake 29 Feb 1900 and is correct for all dates from 1 March 1900, which covers all accounting data. If the workbook uses the 1904 system, the origin is `1904-01-01`. openpyxl exposes the workbook epoch (`wb.epoch`; verify attribute name for your openpyxl version). Plausibility window for serials: 36526 (2000-01-01) to 73415 (2100-12-31). Outside that range, BLOCK. Note that a numeric cell such as `20250401` (yyyymmdd as a number) or `1042025` must not be treated as a serial.
3. **Text value**: choose a column-level format from a whitelist, tried strictly (`datetime.strptime`, exact match after whitespace normalisation):
```python
DATE_FORMATS = ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%d %b %Y', '%d-%b-%Y', '%d-%b-%y',
                '%d %B %Y', '%d/%m/%y', '%d-%m-%y', '%Y-%m-%d', '%m/%d/%Y']   # %m/%d last, never default
def infer_column_format(values):
    ok = [f for f in DATE_FORMATS if all(_try(v, f) for v in values if v)]
    return ok   # 0 -> BLOCK with list of failing cells; 1 -> use; >1 -> resolve ambiguity
```
   - **Ambiguity resolution** when both `%d/%m/%Y` and `%m/%d/%Y` fit (all day values ≤ 12): (a) prefer the format under which every date falls inside the preamble's statement period or FY; (b) prefer the format under which the transaction order is monotonic (bank statements are sorted); (c) default to DD/MM (Indian convention) but **WARN** and show the first ambiguous rows to the user. If one value has a first field > 12, DD/MM is proven for the whole column.
   - Text months: normalise case (`APR`, `Apr`, `apr`), and accept `Sept` by mapping it to `Sep` before `%b`. `%b` is locale-dependent, so force the C/English locale or map month names yourself.
   - Excel can turn a CSV's `01/04/2025` into a real date **in the user's Windows locale** when someone opens and re-saves the CSV. On a US-locale PC, `01/04/2025` (1 April) becomes 4 January. Defence: cross-check against the statement period and the Value Date column. A fully swapped column fails the period or monotonic check, so BLOCK.
4. **Two-digit years** (`01-Apr-25`, `01/04/25`): Python `%y` maps 69–99 to 1969–1999 and 00–68 to 2000–2068 (POSIX convention per Python `time` docs; not re-fetched this session). For Indian SME data, explicitly map `yy` to `2000 + yy` and validate against the expected period. BLOCK if outside the period by more than the allowed tolerance.
5. **Mixed per-row formats in one column** (some cells real dates, some text): parse each branch, then require that the text cells' inferred format produces dates consistent with neighbouring real-date cells. Otherwise BLOCK.

#### 3b. Financial-year logic (India: 1 April – 31 March)
```python
def fy_of(d):            # FY label "2025-26"
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{str(start + 1)[-2:]}"
```
- Parse the preamble period (`From 1-Apr-2025 to 31-Mar-2026`, `Statement From : 01/04/2025 To : 30/09/2025`). WARN if any transaction falls outside it; BLOCK if more than a small fraction falls outside, which usually means a day/month swap.
- Tally reports are per period: a Day Book can span several FYs, but a Trial Balance is "as at" a date. Store `period_from`/`period_to` on the import batch.
- Keep **Txn Date and Value Date** separately (bank), and use Txn Date for ordering and running-balance checks.

### Gaps
- Tally Prime's default date display in exported xlsx (real date cells vs text like "1-Apr-25") was not verified.
- The exact openpyxl attribute for the 1904 epoch should be confirmed against the installed openpyxl version.

---

## 4. Floating-point money errors, storage options (Decimal / integer paise / SQLite), summing and rounding

### Takeaway
Store money in SQLite as **INTEGER paise** (exact 64-bit integers) in a STRICT table. Convert to and from `decimal.Decimal` at the edges, and never let a binary float participate in a stored value or a control total. Imports should **not round at all**: a value needing rounding is a data-quality finding. When rounding is legitimately required (computed GST), Indian law specifies **half-up to the nearest rupee** for tax payable (CGST s.170). That is *not* Python's default banker's rounding.

### Cited Findings
- Decimal: "In decimal floating point, `0.1 + 0.1 + 0.1 - 0.3` is exactly equal to zero. In binary floating point, the result is `5.5511151231257827e-017`." Default precision is 28 places. — [Python decimal docs](https://docs.python.org/3/library/decimal.html)
- Default context: "`prec=28`, `rounding=ROUND_HALF_EVEN`", with traps on Overflow, InvalidOperation and DivisionByZero. — [Python decimal docs](https://docs.python.org/3/library/decimal.html)
- `ROUND_HALF_UP`: "Round to nearest with ties going away from zero." `quantize()` "is useful for monetary applications that often round results to a fixed number of places", e.g. `Decimal('7.325').quantize(Decimal('.01'), rounding=ROUND_DOWN)` gives `Decimal('7.32')`. — [Python decimal docs](https://docs.python.org/3/library/decimal.html)
- `Decimal(float('1.1'))` gives `Decimal('1.100000000000000088817841970012523233890533447265625')`; construct from strings instead. Trapping `FloatOperation` makes "accidental mixing of decimals and floats in constructors or ordering comparisons" raise an exception. — [Python decimal docs](https://docs.python.org/3/library/decimal.html)
- SQLite REAL "is a floating point value, stored as an 8-byte IEEE floating point number". INTEGER is a signed integer of up to 8 bytes. — [SQLite Datatypes](https://www.sqlite.org/datatype3.html)
- SQLite type affinity: a declared type such as `DECIMAL(10,5)` gets **NUMERIC** affinity, and "numeric arguments in parentheses ... are ignored by SQLite". Text that looks like a real number inserted into a NUMERIC column is converted to INTEGER or REAL. TEXT↔REAL conversions preserve "about 15.95 significant decimal digits". In practice `DECIMAL(12,2)` in SQLite is a binary float column. — [SQLite Datatypes](https://www.sqlite.org/datatype3.html)
- "As of version 3.37.0 (2021-11-27), SQLite provides STRICT tables that do rigid type enforcement." — [SQLite Datatypes](https://www.sqlite.org/datatype3.html)
- SQLite: "Floating point values are approximate." "If you need an exact answer, you should not use binary-64 floating-point values, in SQLite or in any other product." The **decimal extension** offers exact text-based decimal arithmetic (`decimal_add`, `decimal_sum`, ...), but "is not (currently) part of the SQLite amalgamation", only the CLI. — [SQLite: Floating Point Numbers](https://sqlite.org/floatingpoint.html)
- Excel stores doubles with 15 significant digits. — [Microsoft Learn](https://learn.microsoft.com/en-us/troubleshoot/microsoft-365-apps/excel/floating-point-arithmetic-inaccurate-result)
- **GST rounding**: CGST Act 2017 s.170 ("Rounding off of tax, etc."). Tax, interest, penalty, fine or other sum payable, and refunds, are rounded to the **nearest rupee**: fifty paise or more is increased to one rupee, less than fifty paise is ignored. In force from 1 July 2017 (Notification 9/2017-CT). — [KnowYourGST: Section 170](https://www.knowyourgst.com/gstlaw/cgst-act/170-rounding-off-of-tax-etc-170/); [TaxHeal: Section 170](https://taxheal.com/section-170-cgst-act-2017-rounding-off-tax-etc.html)
- Commentary notes that this differs from the Income-tax Act ss.288A/288B, which round total income and tax payable/refundable to the **nearest multiple of ten rupees**. — [CAclub: Section 170](https://www.caclub.in/section-170-of-cgst-act-2017-rounding-off-of-tax-etc) (via search summary)

### Inferences

#### 4a. Storage schema (SQLite)
```sql
CREATE TABLE txn (
  id              INTEGER PRIMARY KEY,
  batch_id        INTEGER NOT NULL REFERENCES import_batch(id),
  src_sheet       TEXT    NOT NULL,
  src_row         INTEGER NOT NULL,          -- 1-based Excel row: lineage for every rupee
  txn_date        TEXT    NOT NULL CHECK (txn_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
  value_date      TEXT,
  narration       TEXT,
  ref_no          TEXT,                      -- always TEXT (cheque/UTR/voucher no.)
  debit_paise     INTEGER NOT NULL DEFAULT 0 CHECK (debit_paise  >= 0),
  credit_paise    INTEGER NOT NULL DEFAULT 0 CHECK (credit_paise >= 0),
  balance_paise   INTEGER,                   -- signed: + = Cr for bank / Dr for ledger (document the convention)
  raw_amount_text TEXT,                      -- original cell text/format for audit
  CHECK (NOT (debit_paise > 0 AND credit_paise > 0))
) STRICT;
```
- **INTEGER paise** is exact. Signed 64-bit gives ±9.22×10^18 paise (about ±₹9.2×10^16), which is ample. With integers, SQL `SUM()` is exact integer arithmetic. (SQLite's `sum()` returns an integer when all inputs are integers and raises an overflow error rather than losing precision. That is from SQLite's aggregate-function docs, not re-fetched this session.)
- **TEXT decimal strings** are also exact, but `SUM()` would coerce them to REAL. The decimal extension that fixes this is not in the amalgamation, and Python's bundled `sqlite3` is built from the amalgamation, so it is unavailable unless loaded. Not recommended.
- **REAL / `DECIMAL(p,s)`** must never be used for money (NUMERIC affinity means binary doubles).
- `STRICT` stops a string such as `'1,234.00'` or a float such as `1234.5` from being silently stored in an INTEGER column.
- Register adapters so Decimal never reaches SQLite as float: `sqlite3.register_adapter(Decimal, lambda d: ...)` should raise unless `d == d.quantize(Decimal('0.01'))`, then store `int(d * 100)`.

#### 4b. Python discipline
```python
import decimal
ctx = decimal.getcontext()
ctx.traps[decimal.FloatOperation] = True    # any Decimal(float) or Decimal<float comparison raises
ctx.prec = 28                                # fine for paise up to ~10^26
PAISA = decimal.Decimal('0.01')
def to_paise(d: decimal.Decimal) -> int:
    if d != d.quantize(PAISA):
        raise ValueError(f'sub-paise amount {d}')
    return int(d.scaleb(2))
```
- Sum in Python `int` (paise) or `Decimal`. Never `df['amt'].sum()` on float64 for a control total. If pandas is used for display, keep an `int64` paise column (exact up to about 9.2e18).
- Python's built-in `round()` also rounds half to even, and `round(2.675, 2) == 2.67` because 2.675 is not representable in binary. Both are documented in the Python built-in functions reference (not fetched this session). Never use `round()` on money.

#### 4c. Rounding policy
| Situation | Mode | Code |
|---|---|---|
| Importing amounts from files | **No rounding.** Over-precise values are flagged (N16) | `d == d.quantize(PAISA)` else WARN/BLOCK |
| GST tax payable / refunds / interest / penalty (CGST s.170) | Half-up to nearest ₹1 | `d.quantize(Decimal('1'), rounding=ROUND_HALF_UP)` |
| Income-tax amounts (ss.288A/288B) | nearest ₹10 (per commentary; verify the exact rule for "total income" vs "tax" before implementing) | e.g. `(d/10).quantize(Decimal('1'), ROUND_HALF_UP)*10` after checking statute |
| Invoice line tax computed to paise (rate × taxable value) | Half-up to 0.01 is the common commercial convention (unverified as a legal requirement) | `quantize(PAISA, ROUND_HALF_UP)` |
| Invoice "Round Off" line | Recompute and compare to the file's own Round Off ledger. Never re-derive silently | reconciliation item |

- `ROUND_HALF_UP` in Python rounds ties *away from zero*, so credit notes (negative values) round symmetrically (−2.50 → −3), which matches "50 paise or more is increased".
- Never apply banker's rounding (the Decimal default) to statutory Indian amounts. Set the rounding mode explicitly on every `quantize` call instead of relying on the context.

### Gaps
- No authoritative source found mandating a rounding mode for *paise-level* GST computation on individual invoice lines (as opposed to s.170 nearest-rupee for amounts payable). Practice in Tally/e-invoice schemas should be checked (e.g. GST e-invoice JSON tolerance rules) by the GST-focused research thread.
- The exact Income-tax 288A/288B text was not fetched. The "nearest ten" rule is via commentary only.

---

## 5. Detecting and reporting data-quality issues

### Takeaway
A robust importer gives **every source row a disposition** (transaction, opening, closing, subtotal, total, header, blank, continuation, error) and every finding a severity. It inspects the workbook structure through openpyxl (cached vs formula values, hidden sheets/rows, merged cells, error cells, number formats) before trusting any value. Silent coercion (`errors='coerce'`, default NA strings, `parse_dates` fallback to object) is the main way rupees disappear.

### Cited Findings
- openpyxl `data_only` "controls whether cells with formulae have either the formula (default) or the value stored the last time Excel read the sheet". `read_only` mode "uses much less memory and is faster but not all features are available". — [openpyxl tutorial](https://openpyxl.readthedocs.io/en/stable/tutorial.html)
- In a merged range, only the top-left cell holds the value. Other cells are `MergedCell` objects whose value is always `None`. — [openpyxl.cell.cell API (3.1)](https://openpyxl.readthedocs.io/en/3.1/api/openpyxl.cell.cell.html); [openpyxl merge request 244](https://foss.heptapod.net/openpyxl/openpyxl/-/merge_requests/244)
- openpyxl supports row grouping/hiding via `ws.row_dimensions.group(1, 10, hidden=True)` (documented for writing). — [openpyxl 2.6 usage](https://openpyxl.readthedocs.io/en/2.6/usage.html)
- pandas: unparsable dates leave the whole column as object, default NA strings convert `"NA"`/`"None"`/`"null"` to NaN, and converters replace dtype conversion. — [pandas.read_excel](https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html)
- `errors='coerce'` in `to_datetime` turns invalid and out-of-bounds values into NaT. — [pandas.to_datetime](https://pandas.pydata.org/docs/reference/api/pandas.to_datetime.html)
- The SBI preprocessor fails "in a non-elegant way" on statements with no transactions, and "99% of issues can be diagnosed by looking at the source XLS or CSV". This is why importers should keep source-row lineage. — [gnucash_statement_preprocessors README](https://github.com/abhijit86k/gnucash_statement_preprocessors)
- xlrd reads only .xls and does not support password-protected files. — [xlrd docs](https://xlrd.readthedocs.io/en/latest/)

### Inferences

#### 5a. Workbook-structure checks (openpyxl, before reading values)
```python
from openpyxl import load_workbook
wb_v = load_workbook(path, data_only=True)    # cached values
wb_f = load_workbook(path, data_only=False)   # formulas  (not read_only: we need merged/hidden info)
for ws in wb_v.worksheets:
    wsf = wb_f[ws.title]
    if ws.sheet_state != 'visible':                    # 'hidden' / 'veryHidden'
        issue('WARN', f'hidden sheet {ws.title}')       # never auto-import; ask
    hidden_rows = [r for r, dim in ws.row_dimensions.items() if dim.hidden]
    hidden_cols = [c for c, dim in ws.column_dimensions.items() if dim.hidden]
    if ws.auto_filter and ws.auto_filter.ref:
        issue('WARN', 'autofilter active: some rows may be filtered out of view')
    merged = list(ws.merged_cells.ranges)
    for row_f, row_v in zip(wsf.iter_rows(), ws.iter_rows()):
        for cf, cv in zip(row_f, row_v):
            if cf.data_type == 'f' and cv.value is None:
                issue('BLOCK', f'{cf.coordinate}: formula with no cached value '
                               '(file generated by a program and never recalculated; open & save in Excel)')
            if cv.data_type == 'e':
                issue('BLOCK', f'{cv.coordinate}: Excel error {cv.value}')
```
Rules derived:
| Check | Detection | Severity / handling |
|---|---|---|
| Formula without cached value | `data_only=False` shows formula, `data_only=True` gives `None` | BLOCK. openpyxl cannot calculate. |
| Formula cells in a data export | any `data_type=='f'` in amount columns | WARN. The user edited the export, so the values are no longer the system-of-record. |
| Error cells | `data_type=='e'` (`#REF!`, `#VALUE!`, `#N/A`) | BLOCK in amount/date columns. |
| Hidden sheets | `sheet_state in ('hidden','veryHidden')` | Do not import silently. List them for the user. |
| Hidden rows/cols | `row_dimensions[r].hidden`, `column_dimensions[c].hidden` | pandas reads hidden rows as normal rows. WARN and show count. Policy: import them (the export's totals usually include them), but ask. Users often hide rows they consider "wrong". |
| Filtered rows | `ws.auto_filter.ref` set + hidden rows | WARN as above. |
| Merged cells | `ws.merged_cells.ranges` | Header area: forward-fill the top-left value across the range. Data area: a merged amount or date spanning rows means it applies to one row only. Never forward-fill amounts; WARN. |
| Multiple candidate sheets | header scorer matches more than one sheet | Ask. Never default to sheet 0. |
| Mixed types in a column | count `data_type` per column (n/s/d/b/e) | Numbers + text-numbers: parse both, WARN "text-stored numbers". Numbers + dates in amount column: BLOCK. |
| Text in amount column | strict parser raises | BLOCK the row and show cell, raw value, reason. |
| Blank amount | both debit and credit empty on a dated row | BLOCK the row, unless it is a continuation row (no date, narration only). |
| Number format carries sign | Dr/Cr in `number_format` | Apply the sign (1c). If a balance column has no Dr/Cr and no separate columns, BLOCK. |
| Sub-paise values | N16 | WARN; BLOCK if they affect totals. |
| Duplicate transactions | see 5b | WARN, never auto-drop. |
| Encoding | mojibake `â‚¹`, `Ã`, U+FFFD in text | Re-decode and WARN. |
| Encrypted file | OLE container + `msoffcrypto.is_encrypted()` | Ask for password. Never store it; decrypt in memory. |
| Template drift | known bank detected but headers differ | WARN "format changed", then fall back to generic scoring + user confirmation of column mapping. |

#### 5b. Duplicate detection (flag, never auto-delete)
- **File level**: SHA-256 of the raw bytes means the same file was uploaded twice, so BLOCK the second upload unless the user confirms.
- **Period overlap**: a new bank statement whose date range overlaps an already-imported batch for the same account triggers WARN and an overlap report.
- **Row level fingerprint**: `(account, txn_date, debit_paise, credit_paise, normalised_ref, normalised_narration)`. Bank statements legitimately contain identical rows (two ₹500 UPI payments to the same merchant on the same day), so include **running balance** and **source row order** in the fingerprint. Two rows with identical fingerprints *including balance* are true duplicates (WARN). Identical except balance means the rows are distinct.
- Normalise narration for matching: uppercase, collapse whitespace, strip `\n`, and remove volatile tokens only if verified safe.

#### 5c. Row classification regexes (applied to the narration/particulars cell and to column A)
```python
OPENING  = re.compile(r'(?i)^\s*(opening\s+balance|op\.?\s*bal|balance\s+b/?f|b/?f|brought\s+forward)\b')
CLOSING  = re.compile(r'(?i)^\s*(closing\s+balance|cl\.?\s*bal|balance\s+c/?[fd]|c/?f|carried\s+(forward|over))\b')
SUBTOTAL = re.compile(r'(?i)^\s*(sub[\s-]*total|current\s+total|page\s+total|total\s+for\b)')
TOTAL    = re.compile(r'(?i)^\s*(grand\s+total|total)\s*[:\-]?\s*$')
FOOTER   = re.compile(r'(?i)(statement\s+summary|end\s+of\s+statement|this\s+is\s+a\s+computer[\s-]generated|'
                      r'unless\s+the\s+constituent|dr\s+count|cr\s+count|\*{2,})')
```
- A row is a **transaction** only if it has a valid date (or is a voucher row in a Tally register), at least one parsed amount, and no total/balance label.
- Rows with amounts but no date and a total/balance label are **control rows**. Keep them for reconciliation (section 6). Never import them as transactions.
- Unlabelled rows with amounts but no date (e.g. bold total row with an empty label) count as a total row if their amount equals the sum of the preceding block. Otherwise BLOCK as "unexplained amount row".

#### 5d. Issue report format (shown to the user and stored)
Each issue records: `severity`, `code` (e.g. `AMOUNT_UNPARSEABLE`, `DATE_AMBIGUOUS`, `FORMULA_NO_CACHE`, `HIDDEN_ROWS`, `TOTAL_MISMATCH`), `sheet`, `cell/row`, `raw_value`, `number_format`, `message`, `suggested_fix`. The import commits only if there are zero BLOCK issues (or the user explicitly overrides with a recorded reason). Run the whole import inside one SQLite transaction and roll back on BLOCK.

### Gaps
- Reading hidden-row state back via `row_dimensions[r].hidden` is standard openpyxl API but was only verified for writing in the fetched docs. Test it on real files.
- openpyxl `read_only=True` worksheets likely do not expose `merged_cells`/`row_dimensions` fully. Use normal mode for structure checks (uploads are small) and verify.
- No sources found on how Busy/Vyapar/Zoho exports use hidden rows, merged cells, or formulas.

---

## 6. Reconciling an imported file against its own totals to prove nothing was lost

### Takeaway
Treat every file as carrying its own **control totals**: opening balance, closing balance, column totals/grand totals, Dr = Cr equality, row counts, and running balances. An import is "proven" only when the sums of what was stored (in integer paise, queried back from SQLite) equal those control figures **exactly**, every source row has a disposition, and the result is saved in an immutable import manifest.

### Cited Findings
- Tally export amounts in Dr/Cr-formatted columns are unsigned, so a naive SUM adds debits and credits together ("consider all the numeric values as positive irrespective of Dr or Cr"). Totals checks must apply the Dr/Cr sign first. — [Chandoo Forum](https://chandoo.org/forum/threads/how-to-convert-cr-amount-as-negative.26849)
- SBI statement exports end with a "Statement Summary" block located two rows below the transactions, which carries the statement's own summary figures. — [SBIXLS2Gnucash.py](https://raw.githubusercontent.com/abhijit86k/gnucash_statement_preprocessors/main/SBIXLS2Gnucash.py)
- Statements record the account balance after each transaction (ICICI guide), which enables row-by-row running-balance verification. — [Upstox: ICICI Bank Statement guide](https://upstox.com/?p=39170) (search snippet)
- Exact integer/decimal arithmetic is required for exact equality checks. Binary floats are approximate ("If you need an exact answer, you should not use binary-64 floating-point values"). — [SQLite: Floating Point Numbers](https://sqlite.org/floatingpoint.html)

### Inferences

#### 6a. Control checks (all in integer paise, all must be exact: tolerance 0)
| # | Check | Applies to | On failure |
|---|---|---|---|
| R1 | **Row accounting**: `count(non-empty source rows) == Σ dispositions` (txn + opening + closing + subtotal + total + header + preamble + footer + continuation + error) | all | BLOCK |
| R2 | **Column totals**: `Σ debit_paise(txn rows) == file's Total/Grand Total debit`, same for credit | registers, day book, ledger, bank (if a summary exists) | BLOCK |
| R3 | **Subtotals**: each `Sub Total`/`Current Total` equals the sum of its block | Tally ledgers/registers | BLOCK |
| R4 | **Balance equation**: `opening + Σcredit − Σdebit == closing` (bank, customer's view: deposits add) or `opening_dr + Σdr − Σcr == closing_dr` (ledger, Dr-positive convention) | bank statements, ledgers | BLOCK |
| R5 | **Running balance**: for each txn row i, `bal[i] == bal[i−1] + credit[i] − debit[i]`. If it fails in file order, retry in reverse order (newest-first statements). The first failing row pinpoints a missing, duplicated, misparsed or sign-flipped row. | bank statements, Tally ledger with running balance | BLOCK with row number |
| R6 | **Trial-balance equality**: `Σ Dr closing == Σ Cr closing` and equals the TB grand total row | Trial Balance | BLOCK |
| R7 | **Group integrity**: children sum to the group row; import leaves only | grouped Tally reports | BLOCK |
| R8 | **Voucher balance**: within each voucher (Vch No. + Vch Type + date), `Σ Dr == Σ Cr` | Day Book / journal exports with ledger-level lines | BLOCK |
| R9 | **Tax arithmetic** (registers): `taxable + CGST + SGST + IGST + cess ± round-off == invoice total` per row | Sales/Purchase Register | WARN (rounding conventions vary), BLOCK if off by > ₹1 |
| R10 | **Period**: all txn dates within the preamble period | all | WARN/BLOCK (section 3) |
| R11 | **Round trip**: after commit, `SELECT SUM(debit_paise), SUM(credit_paise), COUNT(*) FROM txn WHERE batch_id=?` equals the in-memory figures and the file's control totals | all | BLOCK + rollback |
| R12 | **Cross-file continuity**: this statement's opening balance equals the previous statement's closing balance for the same account | bank | WARN (gap or overlap) |

```python
def check_running_balance(rows):
    """rows: list of dicts with int paise 'dr', 'cr', 'bal', and 'src_row'. Returns first break or None."""
    def scan(seq):
        for prev, cur in zip(seq, seq[1:]):
            if prev['bal'] + cur['cr'] - cur['dr'] != cur['bal']:
                return cur['src_row'], prev['bal'] + cur['cr'] - cur['dr'], cur['bal']
        return None
    fwd = scan(rows)
    if fwd is None:
        return None, 'ascending'
    rev = scan(rows[::-1])
    return (None, 'descending') if rev is None else (fwd, 'broken')
```
- If R5 fails for *every* row in both directions, the likely causes are Debit/Credit columns swapped, a balance sign convention that differs (overdraft shown as positive with "Dr"), or a wrong amount scale. Report this as a mapping error, not a row error.
- A single failing row with an exact difference equal to one row's amount means a dropped or duplicated row. A difference equal to twice an amount means a sign flip. Include this diagnosis in the message.

#### 6b. Import manifest (persist per batch; immutable)
`import_batch(id, file_name, file_sha256, file_size, detected_format, encrypted, sheet_name, header_row, column_map_json, template_id, template_version, period_from, period_to, opening_paise, closing_paise, file_total_dr_paise, file_total_cr_paise, imported_dr_paise, imported_cr_paise, row_dispositions_json, issues_json, status, created_at, created_by)`
- The manifest is the "proof" artifact. It shows, for that file, that the stored sums equal the file's own totals, and lists every skipped row with its reason.
- Keep `src_sheet` + `src_row` + `raw_amount_text`/`number_format` on every stored transaction so any rupee can be traced to its cell.
- Make batches immutable. A correction means delete-batch-and-reimport (logically) or an adjustment entry, never in-place edits of imported amounts.

#### 6c. When a file has no control totals
Some exports (plain CSV from portals, user-trimmed sheets) have no total row. Then: (1) bank: the running balance (R5) plus opening/closing from the first/last balance is still a full proof. (2) No balance column and no totals: show the user the computed Σ Dr, Σ Cr and row count, and require **explicit confirmation** against the source system's on-screen totals (record who confirmed). Mark the batch `unverified` until then.

### Gaps
- No published source was found describing how commercial Indian tools (Tally's own import, Zoho Books bank-feed import, Vyapar) report reconciliation failures. These rules are engineering inference from accounting control principles plus the cited file-format facts.
- Whether Tally Day Book exports include ledger-level lines (enabling R8) or only voucher-level amounts depends on the report configuration ("Detailed" vs "Condensed") and was not verified.
