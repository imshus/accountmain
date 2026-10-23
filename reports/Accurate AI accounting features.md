# Prove every rupee before the AI speaks

**A better model or a better prompt will not make Accounts.ai 100% accurate. It gets as close as possible by taking arithmetic, accounting logic and file parsing away from the LLM entirely. The model's job becomes routing questions, cross-checking and explaining numbers that code has already proven.** The evidence leaves little room for any other approach. The best text-to-SQL systems in 2026 reach about **80–82% execution accuracy** on the BIRD benchmark, against **93% for humans** ([AI Weekly](https://aiweekly.co/alerts/googles-gemini-sql2-tops-bird-text-to-sql-at-8004)). In one test, Claude Opus 4.7, Claude Sonnet 4.6 and GPT-5.4 each answered 100 business questions single-shot over an unfamiliar schema. They scored only **45.5–50.5%**. With a 4 KB hand-written document of business definitions added, they reached **67.7–68.7%**, and the three models were statistically indistinguishable ([arXiv 2604.25149](https://arxiv.org/abs/2604.25149)). The design that follows from this has three layers. First, an importer proves that each uploaded Excel/CSV file matches its own control totals to the paisa, and stores money as integer paise. Second, a deterministic double-entry engine produces the ledger, day/cash/bank books, voucher checks, trial balance, P&L, balance sheet, GST summaries, ageing and bank reconciliation from fixed formulas, each with a self-check that must hold exactly. Third, the LLM calls those verified reports first. It writes free-form SQL only for the long tail, inside a retry-and-cross-check loop, and code blocks it from displaying any number that did not come from an executed query. This design can guarantee that every displayed figure is computed by code from the user's own data, reconciled and open to inspection. It cannot guarantee that the model read an ambiguous question the way the user meant, or that the uploaded sheet is complete. In those cases the product must ask a question, label its confidence or decline to answer. The biggest practical threats are mundane:
- Tally stores Dr/Cr in each cell's number format, which pandas silently drops.
- DD/MM dates flip when someone re-saves a CSV.
- Binary floating-point numbers drift.
- GST rates changed on 22 September 2025, so a rate table without effective dates will wrongly flag a large part of FY 2025-26.

## Free-form AI tops out near 70–80%, so accuracy has to be built around it

Published benchmarks set a hard ceiling on what an LLM writing SQL can do alone. Huawei's DataGallery-Text2SQL topped the BIRD leaderboard in September 2026 with **82.39% execution accuracy**, a vendor-reported figure ([Technology Magazine](https://technologymagazine.com/news/huawei-datagallery-tops-benchmark-for-enterprise-text2sql-ai)). Google's Gemini-SQL2 reportedly reached 80.04% on the single-model track, while humans score **92.96%** ([AI Weekly](https://aiweekly.co/alerts/googles-gemini-sql2-tops-bird-text-to-sql-at-8004)). Numerical questions over financial tables are harder still. On TableBench the best 2024-era model, GPT-4-Turbo, managed **51.32%** overall against roughly **86%** for humans ([arXiv 2408.09174](https://arxiv.org/html/2408.09174v2)). No benchmark yet covers small-business ledgers, invoices or bank statements in SQLite. The benchmarks that do exist are noisy themselves. An expert audit found annotation errors in **52.8%** of BIRD Mini-Dev examples and **62.8%** of Spider 2.0-Snow examples. Correcting them moved agents' relative scores by −7% to +31% ([arXiv 2601.08778](https://arxiv.org/abs/2601.08778)). Leaderboard rank therefore says little about how Accounts.ai will perform. Only an in-house evaluation set built on real Indian SME files can tell.

The errors that remain are mostly about meaning, not syntax. Snowflake describes the core difficulty as inferring "how tables relate and the hidden caveats" ([Snowflake](https://snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes)). An analysis of GPT-4 errors on FinQA found that only 9% were retrieval failures. Most of the rest were logical slips, such as computing a signed difference when the question asked for an absolute change ([arXiv 2510.13157](https://arxiv.org/pdf/2510.13157)). In accounting, the "hidden caveats" are domain conventions:
- whether "outstanding" nets off advances;
- whether "sales" includes GST;
- which side a credit balance belongs on;
- which date column defines the period.

Arithmetic done in prose is a second error class, and an avoidable one. A fine-tuned 7B model that handed its calculations to an external executor beat GPT-4 on FinQA, TAT-QA and TAT-DQA ([arXiv 2401.13223](https://arxiv.org/html/2401.13223v3)). Older work found that moving computation into executed code gave about a **12%** average gain over chain-of-thought ([arXiv 2211.12588](https://arxiv.org/abs/2211.12588)). The model also cannot reliably check its own work: state-of-the-art LLMs spot only about **75%** of semantically wrong SQL ([arXiv 2503.11984](https://arxiv.org/pdf/2503.11984)). One caution: a widely repeated claim that program-of-thought removes 88% of arithmetic errors comes from a paper withdrawn in July 2026 for methodological errors ([arXiv 2605.05409](https://arxiv.org/abs/2605.05409)). Do not use it in sales material.

| Technique | Reported effect | Evidence quality |
|---|---|---|
| Semantic document of measures, conventions and disambiguation rules | **+17 to +23 pp** (to ~68%) | Controlled 2026 study, three frontier models ([arXiv 2604.25149](https://arxiv.org/abs/2604.25149)) |
| Execution-feedback refiner (feed SQL errors back, retry) | **−9.3 pp when removed** (57.62 → 48.31 on BIRD dev) | 2024 ablation with GPT-3.5 ([arXiv 2408.07930](https://arxiv.org/pdf/2408.07930)) |
| Computation in executed code instead of prose | ~+12% average over chain-of-thought | 2022, older models ([arXiv 2211.12588](https://arxiv.org/abs/2211.12588)) |
| Several SQL candidates plus self-consistency voting | ~+1.5 pp overall, ~+7.6 pp on hard questions | 2025, taken from a summary of the paper ([arXiv 2502.14913](https://arxiv.org/pdf/2502.14913)) |
| Ambiguity detection and question rewriting | 87.2% detection precision; ~50% relative gain in exact match | 2025 research system ([arXiv 2508.15276](https://arxiv.org/html/2508.15276v1)) |
| Full production pipeline (classify, verified queries, multi-LLM generation, compiler-checked correction) | >90% on an internal set, ~2× single-shot GPT-4o | Snowflake self-report, 2024 ([Snowflake](https://snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes)) |

These gains overlap and do not simply add up. No study has measured the error that remains after combining all of them on ledger data. The practical conclusion is to redefine what "100%" means. Accounts.ai faces three separate accuracy problems:
- **Data fidelity:** did every rupee in the file reach the database with the right sign and date?
- **Accounting semantics:** is the trial balance or P&L computed correctly from that data?
- **Question interpretation:** did the model understand what the user asked?

Deterministic code with built-in invariants can make the first two provably exact. Only the third is probabilistic. The client's requirement of "100% accurate" should therefore become five commitments:
- No number appears unless SQL or code computed it from the uploaded data.
- Every import reconciles exactly to the file's own totals.
- Every standard report passes its invariants.
- The SQL and the source rows behind any figure can be inspected.
- Ambiguous questions get a clarifying question back, not a guess.

## Most lost rupees disappear at import, before any model runs

The current pipeline loads files with pandas and NumPy into SQLite. This is where silent corruption is most likely, because pandas defaults are built for convenience, not proof. Three defaults cause trouble:
- `read_excel` parses numeric columns "regardless of display format".
- It converts strings such as "NA", "None" and "null" to NaN.
- With `parse_dates`, one unparseable cell leaves the whole column as unconverted text ([pandas read_excel](https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html)).

A real, maintained open-source SBI statement preprocessor converts amounts with `pd.to_numeric(..., errors='coerce')` and then blanks the NaNs, so any amount it cannot parse simply disappears ([SBICSV2Gnucash.py](https://raw.githubusercontent.com/abhijit86k/gnucash_statement_preprocessors/main/SBICSV2Gnucash.py)). Accounts.ai should follow a different rule: no conversion may fail silently. Every source row gets a disposition: transaction, opening balance, closing balance, subtotal, total, header, footer, continuation or error. Every finding gets a severity: BLOCK, WARN or INFO. The import commits only when there are zero BLOCK findings, and it runs inside a single SQLite transaction that rolls back on failure.

### Tally hides the sign of every balance in the cell format

The most dangerous India-specific trap is in Tally exports: the "Dr" and "Cr" suffixes "aren't actually part of the cell value, but are in the cell's format". Users report that Excel's AutoSum treats every value as positive whether it is Dr or Cr ([Chandoo Forum](https://chandoo.org/forum/threads/how-to-convert-cr-amount-as-negative.26849); [CAclubindia](https://www.caclubindia.com/forum/convert-tally-exported-cr-as-negative-in-excel-344117.asp)). pandas returns only the stored value, so a naive import of a Tally trial balance or ledger adds debits and credits together, and nothing looks wrong. The fix:
1. For `.xlsx` files, iterate the cells with openpyxl and read `cell.number_format`.
2. Split the format on unquoted semicolons into its positive and negative sections.
3. Take Dr/Cr from whichever section applies to the value.
4. If a balance column has non-zero cells with no Dr/Cr marker, and the file has no separate Debit and Credit columns, BLOCK the import with the message "sign cannot be determined; re-export with Debit/Credit columns".

The exact format string Tally writes has not been confirmed. The parser should handle both a literal per-cell format such as `#,##0.00 "Cr"` and a two-section format such as `0.00 "Dr";0.00 "Cr"`, and this must be checked against real TallyPrime exports. If a user re-saved the file as CSV, the suffix becomes literal text, which the text parser below handles.

Tally exports have four more quirks:
- **Several sheets.** TallyPrime Server exports three sheets ([TallyPrime Help](https://help.tallysolutions.com/export-data-in-tallyprime-server/)), so pick sheets by header scoring, never `sheet_name=0`.
- **Variable title rows.** Export settings can turn "Company Details" and "Header Information" on or off ([TallyPrime Help: Export](https://help.tallysolutions.com/tally-prime/data-management/export-data-in-tally/)), so the number of title rows changes. A fixed `skiprows` will break; detect the header row by scoring instead.
- **Shifted columns.** Older Tally.ERP 9 releases misaligned the Vch Type, Vch No., Debit and Credit columns ([Tally release note](https://help.tallysolutions.com/article/te9rel50/Release_Notes/Technical_Features/Export___Import.htm)). The importer should require that at least 95% of non-blank debit/credit cells parse as amounts, or BLOCK as "columns appear shifted".
- **Two amount layouts.** Tally's own Excel import accepts either separate Debit and Credit columns or one amount column with a Dr/Cr indicator ([TallyPrime Help](https://help.tallysolutions.com/map-nett-amount-values/)), so Accounts.ai must support both.

Grouped reports carry a further risk that still needs checking against sample files. In a detailed trial balance, group rows such as "Sundry Debtors" carry totals above their child ledgers, so importing both counts every rupee twice. The importer should detect the hierarchy from indentation, bold font and leading spaces, import only the leaf ledgers, and keep group rows as control totals that the children must sum to.

### Bank "Excel" files are often not Excel at all

Indian bank downloads often lie about their own format. SBI's legacy OnlineSBI ".xls" is really a tab-separated text file. Its Debit header carries leading spaces, and its dates look like "05 Jan 2024" ([SBICSV2Gnucash.py](https://raw.githubusercontent.com/abhijit86k/gnucash_statement_preprocessors/main/SBICSV2Gnucash.py)). SBI's YONO `.xlsx` is **password-protected**. Its dates are dd/mm/yyyy, and the data starts relative to a "Statement From" marker and ends above a "Statement Summary" block ([SBIXLS2Gnucash.py](https://raw.githubusercontent.com/abhijit86k/gnucash_statement_preprocessors/main/SBIXLS2Gnucash.py)). In July 2026 the same maintainer reported that **SBI had changed its export format again** ([gnucash-user list](https://lists.gnucash.org/pipermail/gnucash-user/2026-July/121136.html)). xlrd reads only `.xls` and cannot open password-protected files ([xlrd docs](https://xlrd.readthedocs.io/en/latest/)). The importer should therefore check the file's first bytes before choosing a reader. It should keep a small template registry per bank and layout version: header names, date format, amount layout, and preamble and footer markers. When a known bank's file stops matching its template, it should WARN, then fall back to generic header scoring that normalises whitespace and suffixes such as "(INR )".

| First bytes | Actual format | Reader |
|---|---|---|
| `50 4B 03 04` | .xlsx/.xlsm (ZIP) | openpyxl |
| `D0 CF 11 E0 A1 B1 1A E1` | Real .xls, or an encrypted .xlsx in an OLE wrapper | xlrd. If that fails, test encryption with msoffcrypto, ask the user for the password, decrypt in memory, never store it |
| `<html` / `<?xml` | HTML or SpreadsheetML renamed to .xls | `read_html`/lxml, with WARN |
| `FF FE` / `FE FF` | UTF-16 text | csv reader with utf-16 |
| Anything else | CSV/TSV (e.g. SBI legacy ".xls") | `csv.Sniffer` on the first ~20 KB to pick the delimiter |

Four bank-specific rules follow:
- In Withdrawal/Deposit layouts, exactly one of the two columns may be non-zero on a transaction row.
- A row with no date and no amount but with narration text continues the previous transaction's narration. Append it; never import it as a zero transaction.
- Read account numbers, cheque numbers and UTRs as text. Excel keeps only **15 significant digits** ([Microsoft Learn](https://learn.microsoft.com/en-us/troubleshoot/microsoft-365-apps/excel/floating-point-arithmetic-inaccurate-result)), so an 18-digit UTR stored as a number has already lost its tail.
- Map single-letter Dr/Cr indicators ("D" can mean Debit or Deposit) only from a bank template, never by guessing.

### Number and date formats need strict parsers, not coercion

Excel numeric cells and text cells need separate parsing paths. A numeric cell is an IEEE double, and its display (lakh commas, parentheses, Dr/Cr) lives in the format string. A text cell needs a strict parser that accepts every legitimate Indian convention and **rejects** everything else rather than turning it into NaN. Indian grouping is 3:2:2: the first comma comes after three digits, then one after every two, so 1,00,000 is one lakh and 1,00,00,000 is one crore ([BrightChamps](https://brightchamps.com/math/numbers/indian-numeral-system)).

| Pitfall | Example | Rule |
|---|---|---|
| Lakh grouping as text | `1,23,45,678.00` | Accept only valid Indian (`^\d{1,2}(,\d{2})*,\d{3}`) or Western grouping; BLOCK malformed groups such as `1,2345.00` |
| Negatives | `(12,500.00)`, `12,500.00-`, `−500` (Unicode minus) | Treat all as negative; normalise dashes first. BLOCK conflicting markers such as `(1,000) Cr` |
| Dr/Cr as text | `1,234.00 Dr`, `Cr 500` | Return the marker separately; the column's meaning decides the sign |
| Currency tokens | `₹1,000`, `Rs. 1,000/-`, `INR1000` | Strip these tokens; any other letters left over mean reject |
| Wrong encoding | `â‚¹1,000` | Re-decode the file as UTF-8 and WARN |
| Scientific notation in text | `1.23457E+11` | BLOCK: digits were lost when Excel re-saved a CSV |
| Blank, dash or "Nil" vs zero | `''`, `-`, `Nil`, `0.00` | Keep "missing" distinct from "zero". A blank side of Withdrawal/Deposit counts as 0 only if the other side is filled |
| pandas NA strings | A party literally named "None" | `keep_default_na=False, na_filter=False` |
| Hidden decimals | Shows `1,234.57`, stores `1234.5678` | WARN or BLOCK as a sub-paise value; show both |
| Excel error cells | `#REF!`, `#VALUE!` | BLOCK in amount and date columns |
| Percent cells | `18%` as text, or 0.18 with a `%` format | Only in rate columns. Store as 18; never treat as an amount |

Dates need the same strictness. pandas warns that `dayfirst=True` "is not strict" and that `format='mixed'` "is risky" ([pandas to_datetime](https://pandas.pydata.org/docs/reference/api/pandas.to_datetime.html)). Accounts.ai should pick one format per column from a whitelist, and that format must parse 100% of the column's cells. When both DD/MM and MM/DD fit, because every day value is 12 or less, resolve it with evidence:
- A single day value above 12 anywhere in the column proves DD/MM.
- Every date should fall inside the statement period printed above the data.
- Bank statements should be in date order.
- If none of these settles it, default to DD/MM (the Indian convention) and WARN.

These checks also catch the classic re-save accident: a CSV opened in Excel on a US-locale PC turns 01/04/2025 (1 April) into 4 January. Dates stored as plain numbers (Excel serials) should be converted from the origin 1899-12-30, which absorbs the fictitious 29 February 1900 that Excel keeps for Lotus 1-2-3 compatibility ([Microsoft Learn](https://learn.microsoft.com/en-us/troubleshoot/microsoft-365-apps/excel/wrongly-assumes-1900-is-leap-year)). Values outside the 2000–2100 range should be blocked. Two-digit years should map explicitly to 2000 + yy. Every batch should store its period and its Indian financial year (1 April to 31 March, labelled "2025-26"). Bank imports should keep the transaction date and the value date as separate fields.

### Money belongs in integer paise, in STRICT tables

SQLite REAL is an 8-byte IEEE float, and declaring `DECIMAL(12,2)` does not help. SQLite gives that column NUMERIC affinity and ignores the precision, so it is still a binary float ([SQLite Datatypes](https://www.sqlite.org/datatype3.html)). SQLite's own documentation is explicit: "If you need an exact answer, you should not use binary-64 floating-point values." Its exact-decimal extension is not part of the amalgamation build, which is the build Python's `sqlite3` module ships with ([SQLite Floating Point](https://sqlite.org/floatingpoint.html)). Since version 3.37.0, SQLite supports **STRICT tables** that enforce column types rigidly ([SQLite Datatypes](https://www.sqlite.org/datatype3.html)). The schema should therefore store `debit_paise` and `credit_paise` as non-negative INTEGER columns in STRICT tables. A CHECK constraint should stop both from being positive on the same row. Every row should keep its `src_sheet`, `src_row` and raw cell text, so any rupee can be traced back to its cell.

Python needs the same discipline. `Decimal(1.1)` expands to `1.100000000000000088817841970012523233890533447265625`. Python's default decimal rounding is ROUND_HALF_EVEN, which is banker's rounding. Trapping `FloatOperation` makes any accidental mixing of floats and Decimals raise an error ([Python decimal](https://docs.python.org/3/library/decimal.html)). Imports should never round: a value with more than two decimal places is a data-quality finding. Rounding applies only where the law requires it. CGST Act section 170 rounds tax payable to the nearest rupee, with fifty paise or more rounded up ([KnowYourGST s.170](https://www.knowyourgst.com/gstlaw/cgst-act/170-rounding-off-of-tax-etc-170/)). That means an explicit `ROUND_HALF_UP` on every `quantize` call, never the default.

```python
def float_cell_to_paise(v) -> int:
    if isinstance(v, bool): raise AmountError('boolean in amount column')
    if isinstance(v, int):  return v * 100
    if v != v or abs(v) >= 1e13: raise AmountError('NaN or beyond 15 significant digits')
    d = Decimal(repr(v))                  # shortest round-trip string, not Decimal(v)
    q = d.quantize(Decimal('0.01'))
    if d != q: raise AmountError(f'sub-paise value {d}')
    return int(q * 100)
```

### Every file must reconcile to its own control totals

An import is "proven" only when the stored sums, queried back from SQLite in paise, exactly equal the control figures the file carries about itself. The tolerance is **zero**, except for tax arithmetic, where rounding conventions vary.

| Check | Rule | Applies to |
|---|---|---|
| Row accounting | Source rows = sum of all dispositions | All files |
| Column totals | ΣDebit and ΣCredit of transaction rows = the file's Total/Grand Total rows | Registers, day book, ledgers |
| Subtotals | Each "Sub Total"/"Current Total" = the sum of its block | Tally ledgers and registers |
| Balance equation | Bank: opening + Σcredit − Σdebit = closing. Ledger: opening + ΣDr − ΣCr = closing | Bank statements, ledgers |
| Running balance | bal[i] = bal[i−1] + cr[i] − dr[i] on every row. If it fails, retry in reverse order for newest-first statements | Bank, ledger with balance |
| Trial balance | ΣDr closing = ΣCr closing = the grand total row | Trial balance |
| Group integrity | Child ledgers sum to their group row | Grouped Tally reports |
| Voucher balance | ΣDr = ΣCr within each (date, type, number) | Day book, journal exports |
| Tax arithmetic | taxable + CGST + SGST + IGST + cess ± round-off = invoice total. WARN; BLOCK if off by more than ₹1 | Sales/purchase registers |
| Round trip | After commit, `SUM`/`COUNT` from SQLite = the in-memory figures = the file's controls | All files |
| Continuity | This statement's opening = the previous statement's closing for the same account | Bank |

The running-balance check also diagnoses what went wrong. If the break equals exactly one row's amount, a row was dropped or duplicated. If it equals twice an amount, a sign was flipped. If every row fails in both directions, the Debit and Credit columns were mapped the wrong way round. Before reading any values, the importer should also inspect the workbook's structure with openpyxl:
- **Formula cells with no cached value.** openpyxl's `data_only` mode returns the value "stored the last time Excel read the sheet" ([openpyxl tutorial](https://openpyxl.readthedocs.io/en/stable/tutorial.html)), and openpyxl cannot calculate formulas itself. A formula with no cached value means the file was never recalculated: BLOCK.
- **Merged cells.** Only the top-left cell holds the value ([openpyxl API](https://openpyxl.readthedocs.io/en/3.1/api/openpyxl.cell.cell.html)). Forward-fill merged ranges in the header area, but never forward-fill amounts.
- **Hidden sheets, hidden rows and active filters.** WARN, and ask the user how to treat them.
- **Duplicate uploads.** Detect a re-uploaded file with a SHA-256 hash of its bytes. Detect duplicate rows with a fingerprint that includes the running balance, because two identical ₹500 UPI payments on the same day are legitimate.

Each batch writes an immutable import manifest: file hash, detected format, header row, column map, period, opening and closing balances, file totals, imported totals, row dispositions and issues. If a file has no totals and no balance column, show the user the computed ΣDr, ΣCr and row count, and mark the batch "unverified" until they confirm the figures against their source system.

## One signed-balance rule produces every core report and its own proof

The accounting engine should rest on one convention: store each voucher line as `signed = debit − credit` in paise, and compute every balance as opening plus the sum of `signed`. Display the absolute value with a "Dr" suffix when it is positive and "Cr" when it is negative. This arithmetic never changes with the type of account. Account type only decides which side is normal: assets and expenses increase with debits, and liabilities, capital and income increase with credits ([Wikipedia: Debits and credits](https://en.wikipedia.org/wiki/Debits_and_credits)). Indian accountants read the Dr/Cr suffix, not a minus sign, so the engine must never compute "credit − debit" for liability accounts. The chart of accounts should follow Tally's **28 predefined groups**: 15 primary groups (9 for the balance sheet, 6 for P&L) and 13 sub-groups ([Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)). Amounts should display in 3:2:2 grouping, for example ₹1,23,45,678.90, and periods should default to the April–March financial year.

| Feature | Exact formula (paise; signed = Dr − Cr) | Invariant that must hold exactly |
|---|---|---|
| Ledger statement | opening(from) = FY opening + Σsigned over [1 April, from−1]; P&L ledgers open each FY at 0. running = opening + cumulative Σsigned, ordered by (date, voucher sequence). closing = opening + ΣDr − ΣCr | Closing = the file's closing row; a party's closing = the sum of its ageing buckets |
| Day Book | Every voucher in [from, to], grouped by (date, type, number), showing Dr and Cr totals | ΣDr = ΣCr for each voucher and for the period |
| Cash Book | Ledgers under Cash-in-Hand: Closing_m = Closing_{m−1} + Dr_m − Cr_m; Closing_0 = 1 April opening | Closing ≥ 0 on every day; equals the Cash closing in the trial balance |
| Bank Book | Same calculation for ledgers under Bank Accounts; OD/CC ledgers under Bank OD A/c (normally Cr) shown separately | Equals the bank ledger in the trial balance; feeds the BRS |
| Journal / vouchers | A flat sales register row expands to Dr Party = invoice total; Cr Sales = taxable value; Cr Output CGST/SGST/IGST; ± Round Off | ΣDr = ΣCr; voucher type matches ledger groups |
| Trial Balance | Dr column = max(bal, 0); Cr column = max(−bal, 0). Groups roll up signed child balances | ΣDr = ΣCr (Σsigned = 0). Any remainder appears as "Difference in opening balances" |
| Profit & Loss | GP = (Sales + DirectInc + ClosingStock) − (OpeningStock + Purchases + DirectExp); NP = GP + IndirectInc − IndirectExp | NP = −Σsigned(P&L ledgers) + ClosingStock − OpeningStock |
| Balance Sheet | Assets (including closing stock) = Capital + Reserves + P&L A/c (opening + NP) + Liabilities | Balances to the paisa once the trial balance balances and closing stock is counted once |
| Receivables/payables ageing | Open bill = bill amount − receipts and credit notes allocated to it; age = as-of date − bill date or due date | Σbuckets + on-account = the party's closing; Σparties = the Sundry Debtors/Creditors group |
| Bank reconciliation | Derived bank balance = book balance − unmatched book Dr + unmatched book Cr | Derived balance − statement balance = Σ unmatched statement items |

### Ledgers and the three books

TallyPrime's ledger statement is the "Ledger Vouchers" report, and its "Show Running Balance" option adds a running balance after every entry ([Tally Help: Ledger Vouchers](https://help.tallysolutions.com/ledger-vouchers/)). Accounts.ai should mirror its columns: Date, Particulars (the ledger on the other side of the voucher), Voucher Type, Voucher No., Debit, Credit and Balance. Opening balances come from the previous balance sheet. When opening debits and credits do not match, Tally shows a "Difference in Opening Balances" line ([Teachoo](https://www.teachoo.com/758/232/Difference-in-Opening-Balances-in-Tally/category/Common-Errors-in-Tally)). The predefined "Profit & Loss A/c" ledger carries the previous year's profit as its opening balance ([Tally Help](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)). The engine should flag balances on the wrong side, even though they are legal:
- A Cr balance on cash is physically impossible. Tally shows negative cash as a Cr balance in red ([Tally Help: Cash/Bank Book](https://help.tallysolutions.com/tally/cash-bank-book-tally/)).
- A Dr balance on a creditor means an advance was paid.
- A Cr balance on a debtor means an advance was received.

Entries should be sorted within each date by voucher sequence, so the running balance is deterministic. Footer labels such as "Opening Balance", "Current Total" and "Closing Balance" come from practitioners' experience of Tally and need confirming on a real export.

The Day Book lists every voucher for a day or period ([Tally Help: Day Book](https://help.tallysolutions.com/?p=101490)). The Cash and Bank Books record receipts on the debit side and payments on the credit side. They show monthly debit and credit totals with a closing balance, a daily breakdown, and the highest and lowest balance in each month ([Tally Help: Cash/Bank Book](https://help.tallysolutions.com/tally/cash-bank-book-tally/)). Overdraft and cash-credit accounts belong under Bank OD A/c, which sits under Loans (Liability), not Current Assets ([Tally Help: Default Groups](https://help.tallysolutions.com/docs/te9rel53/Creating_Masters/Accounts_Info/Default_Groups.htm)). Imported bank statements also need their signs flipped. A withdrawal is a debit from the bank's point of view, but a deposit is a Dr in the company's Bank Book. So `book_signed = deposit − withdrawal`.

### Vouchers and the trial balance

Tally's predefined accounting vouchers are Contra, Payment, Receipt, Journal, Sales, Purchase, Credit Note and Debit Note ([TallySolutions: Vouchers](https://tallysolutions.com/tally/accounting-vouchers-in-tally-prime/)). Memorandum vouchers "will not affect your accounts" ([Tally Help: Memorandum Voucher](https://help.tallysolutions.com/docs/te9rel65/Voucher_Entry/Optional_Non-Accounting_Vouchers/Memorandum_Voucher.htm)), so the engine must exclude them, along with optional and cancelled vouchers. The table below is a practitioner mapping derived from standard Indian practice. A chartered accountant should review it before it is hard-coded as a set of validation rules.

| Voucher | Typical debit | Typical credit | Validation |
|---|---|---|---|
| Contra | Bank (deposit) or Cash (withdrawal) | Cash or Bank | Every line is a Cash, Bank or Bank OD ledger |
| Payment | Party, expense or asset | Cash or Bank | At least one credit line is cash/bank |
| Receipt | Cash or Bank | Party or income | At least one debit line is cash/bank |
| Journal | Any non-cash ledger | Any non-cash ledger | Flag any cash/bank line |
| Sales | Debtor or Cash/Bank | Sales + Output GST (Duties & Taxes) | GST never posted to Sales |
| Purchase | Purchase + Input GST | Creditor or Cash/Bank | GST never posted to Purchase |
| Credit Note | Sales (returns) + Output GST | Debtor | Reduces both sales and receivable |
| Debit Note | Creditor | Purchase (returns) + Input GST | Reduces both purchases and payable |

The trial balance rolls ledger closings into the 9 balance-sheet primary groups and the 6 P&L primary groups:
- **Balance-sheet groups:** Capital Account, Loans (Liability), Current Liabilities, Fixed Assets, Investments, Current Assets, Branch/Divisions, Misc. Expenses (ASSET) and Suspense A/c.
- **P&L groups:** Sales Accounts, Purchase Accounts, Direct Incomes, Direct Expenses, Indirect Incomes and Indirect Expenses.

Source: [Tally Help](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/). Tally states that "as per accounting principles, the Trial Balance does not display the closing stock" ([Tally Help: Trial Balance](https://help.tallysolutions.com/tally-prime/accounting-financial-reports/trial-balance-tally/)). Tally lists the causes of a "Difference in opening balances" line: manual errors, data carried from a previous company, removed openings, split data, and imports that overwrote balances ([Tally Help](https://help.tallysolutions.com/trial-balance-tally/)). These describe exactly what goes wrong with Excel uploads, so the engine should show the difference rather than absorb it. Indian textbooks also give diagnostics worth automating when a trial balance does not agree ([Vedantu NCERT Ch. 6](https://www.vedantu.com/ncert-solutions/ncert-solutions-class-11-accountancy-chapter-6); [NIOS](https://digital.nios.ac.in/content/224en/ch_11.pdf)):
- A difference of ₹1, 10, 100 or 1,000 suggests a totalling error.
- A difference divisible by 2 suggests an amount of half that size posted to the wrong side.
- A difference divisible by 9 suggests transposed digits.

The Suspense A/c should be zero at year end.

### Profit & loss and the balance sheet

Tally's P&L is horizontal by default, with a vertical option ([Tally Help: P&L](https://help.tallysolutions.com/docs/te9rel66/Reports/intro_profit_loss_accounts.htm)). Its trading section uses only cost of sales and direct expenses, and indirect expenses come off gross profit to give net profit ([Tally Help: Configure P&L](https://help.tallysolutions.com/docs/te9rel65/Reports/Display_Financial_Statements/Config_Profit_Loss_Account.htm)). Direct incomes and expenses affect gross profit; indirect ones do not ([Tally Help: Default Groups](https://help.tallysolutions.com/docs/te9rel53/Creating_Masters/Accounts_Info/Default_Groups.htm)). Tally's own formula article defines COGS as "Opening Stock + Purchases During the Period – Closing Stock" ([TallySolutions](https://tallysolutions.com/accounting/profit-loss-statement-format-formula/)), but Tally's report includes direct expenses in the trading section, and the engine should follow the report:

```
Sales_net   = −Σsigned(Sales Accounts)            # returns inside the group reduce it
Purchases   =  Σsigned(Purchase Accounts)
DirectExp   =  Σsigned(Direct Expenses)    DirectInc   = −Σsigned(Direct Incomes)
IndirectExp =  Σsigned(Indirect Expenses)  IndirectInc = −Σsigned(Indirect Incomes)
COGS        =  OpeningStock + Purchases + DirectExp − ClosingStock
GrossProfit =  Sales_net + DirectInc − COGS
NetProfit   =  GrossProfit + IndirectInc − IndirectExp
```

**Closing stock cannot be derived from ledgers.** When inventory is not integrated, Tally asks the user to enter the closing-stock amount on the Stock-in-Hand ledger ([Tally Help: Stock valuation FAQ](https://help.tallysolutions.com/tally-prime/inventory/stock-valuation-faq/)). Accounts.ai must therefore ask for closing stock or label the result "gross profit before closing stock". If the data already contains a closing-stock journal, it must not add closing stock again. Non-trading entities can use an Income & Expenditure statement instead ([Tally Help](https://help.tallysolutions.com/docs/te9rel66/Reports/intro_profit_loss_accounts.htm)).

Companies need the Schedule III layout as well. Its Statement of Profit and Loss runs: Revenue from operations; Other income; total revenue; expenses by nature (materials consumed, purchases of stock-in-trade, changes in inventories, employee benefits, finance costs, depreciation, other expenses); profit before tax; tax; profit for the period ([ICAI Palakkad](https://palakkad.icai.org/detail/4476.aspx)). Because Schedule III classifies expenses by nature, Tally's direct/indirect split has to be remapped ledger by ledger.

For companies the balance sheet must be vertical. The Schedule III Division I heads are ([CorpLawUpdates](https://www.corplawupdates.in/tools/financial-statements/balance-sheet)):
- **Equity and liabilities:** shareholders' funds; share application money pending allotment; non-current liabilities; current liabilities.
- **Assets:** non-current assets; current assets.

Division I applies to companies that do not follow Ind AS ([KPMG India](https://assets.kpmg.com/content/dam/kpmg/in/pdf/2021/05/chap-1-aau-schedule-III-to-the-companies-act-2013.pdf)). Four details matter for the mapping:
- Since the 2021 amendments, current maturities of long-term borrowings go under **short-term borrowings**. The same amendments added receivable and payable ageing schedules and eight ratio disclosures ([KPMG India](https://assets.kpmg.com/content/dam/kpmg/in/pdf/2021/05/chap-1-aau-schedule-III-to-the-companies-act-2013.pdf)).
- A debit (loss) balance in P&L is shown as a negative figure under Reserves and Surplus.
- A ₹10,00,000 loan repayable in ten half-yearly instalments splits into ₹8,00,000 long-term and ₹2,00,000 current ([Taxmann](https://www.taxmann.com/post/blog/schedule-iii-of-the-companies-act)).
- Sources disagree on the turnover thresholds for rounding. Vyapar uses ₹100 crore ([Vyapar](https://vyaparapp.in/balance-sheet-formats/schedule-3)); TallySolutions cites ₹100 crore and ₹1,000 crore ([TallySolutions](https://tallysolutions.com/accounting/schedule-iii-division-i-meaning-applicability-and-financial-statement-format-for-companies/)). Leave rounding configurable until the MCA text is checked.

Most Tally and Vyapar users are proprietorships and partnerships. They need the traditional horizontal Liabilities | Assets format, with capital shown as opening plus net profit minus drawings. The ICAI guidance note that governs non-corporate formats was not researched and should be reviewed. The group mapping below is a practitioner mapping that needs a chartered accountant's sign-off:

| Tally group | Schedule III Division I head |
|---|---|
| Capital Account; Reserves & Surplus + P&L A/c | Share capital; Reserves and surplus (a loss is shown negative) |
| Secured / Unsecured Loans | Long-term borrowings; the part due within 12 months goes to short-term borrowings |
| Bank OD A/c | Short-term borrowings |
| Sundry Creditors | Trade payables (MSME / others); creditors with a Dr balance go to advances / other current assets |
| Duties & Taxes | Other current liabilities (Cr) or other current assets (Dr, i.e. input tax credit) |
| Fixed Assets; Investments | PPE, intangibles, CWIP; non-current or current investments |
| Stock-in-Hand / closing stock | Inventories |
| Sundry Debtors | Trade receivables; debtors with a Cr balance go to other current liabilities |
| Cash-in-Hand + Bank Accounts | Cash and cash equivalents |
| Deposits (Asset); Loans & Advances (Asset) | Other non-current assets (security deposits); loans and advances |
| Suspense A/c | No head: must be zero, so flag any balance |

### Ageing and bank reconciliation

Ageing groups each open bill by the days between the as-of date and either the bill date or the due date, where due date = bill date + credit period. Defaults differ by product:

| Source | Default buckets | Basis and notes |
|---|---|---|
| TallyPrime | 0–45, 45–90, 90–180 and over 180 days | Bill date or due date. Bill-by-bill tracking uses "New Ref" and "Agst Ref". Credit entries made before bill-wise tracking was switched on appear as "On Account" ([TallySolutions](https://tallysolutions.com/tally/how-to-track-customer-pending-payments-in-tallyprime/)) |
| Zoho Books | Current, 1–15, 16–30, 31–45 and over 45 days | Due date by default ([Zoho Books Help](https://www.zoho.com/books/help/reports/receivables.html)) |
| Schedule III (2021) receivables | Under 6 months, 6 months–1 year, 1–2, 2–3, over 3 years | From due date. Rows split into undisputed and disputed, each considered good or doubtful ([KPMG India](https://assets.kpmg.com/content/dam/kpmg/in/pdf/2021/05/chap-1-aau-schedule-III-to-the-companies-act-2013.pdf)) |
| Schedule III (2021) payables | Under 1 year, 1–2, 2–3, over 3 years | Rows: MSME, Others and disputed dues. Ageing runs from the transaction date when there is no due date ([KPMG India](https://assets.kpmg.com/content/dam/kpmg/in/pdf/2021/05/chap-1-aau-schedule-III-to-the-companies-act-2013.pdf)) |

Accounts.ai should offer all four as presets, with four design rules:
- **Non-overlapping edges.** Tally's "0–45, 45–90" labels overlap at day 45, so the app must state which bucket day 45 falls in.
- **A "Not due" column** for bills that are not yet due on a due-date basis.
- **Unreferenced receipts stay "On Account" by default**, as Tally does. FIFO allocation against the oldest bills should be optional and labelled in the interface as an assumption.
- **Reconciliation to the ledger.** Every party's buckets must sum to its ledger closing balance.

Tally's bank reconciliation starts from the "Balance as per Company Books". It then adjusts for "Amounts not reflected in Bank" to reach a balance that "should be equal to the balance in the bank statement". Bank-side items such as charges and interest appear separately as "Amount not reflected in Company Books" ([Tally Help: Bank Reconciliation](https://help.tallysolutions.com/bank-recon-reports/)). Starting from the cash book balance, the adjustments are ([Busy](https://busy.in/accounting/bank-reconciliation-statement-explained-purpose-format-and-common-errors/)):
- **Add** cheques issued but not yet presented, and credits the bank has made that are not yet in the books.
- **Subtract** deposits the bank has not yet credited, and bank charges or ECS debits not yet in the books.

A NIOS worksheet gives a worked example. Starting from a cash book balance of ₹57,000: subtract ₹5,500 of deposits not yet credited, add ₹12,200 of cheques not yet presented, add a ₹5,800 ECS dividend, and subtract ₹600 of bank charges. The result is **₹68,900** per the pass book ([NIOS worksheet](https://www.nios.ac.in/media/documents/Seccour224New/Accountacy_worksheet_224/ws_224_E_L8.pdf)); the arithmetic was re-checked for this report. Busy's own published format table does not add up (its items total 99,000 but it shows 93,000), which shows why these features should be tested against invariants rather than vendor examples. Busy also recommends reviewing cheques that are more than three months old as stale ([Busy](https://busy.in/accounting/bank-reconciliation-statement-explained-purpose-format-and-common-errors/)). Matching should run in stages:
1. Match on cheque number, UTR or reference.
2. Match the remaining lines on amount within a ±N-day date window.
3. Leave everything else unmatched for the user.

Because the engine uses signed balances, overdraft accounts need no special case.

### Classifying free-text ledger names without guessing

Uploads often lack Tally's "Group" or "Under" column, so ledgers must be classified from their names. No vendor publishes a classifier. The best ground truth is Tally's own group descriptions, which give examples such as rent and interest received under Indirect Incomes, and loans from directors under Unsecured Loans ([Tally Help: Default Groups](https://help.tallysolutions.com/docs/te9rel53/Creating_Masters/Accounts_Info/Default_Groups.htm)). Zoho's account types offer an alternative taxonomy ([Zoho Books API](https://www.zoho.com/books/api/v3/chart-of-accounts)). Tally warns that altering predefined groups "may cause ledger grouping, reporting, and data interchange issues" ([Tally Help: Groups](https://help.tallysolutions.com/tally-prime/accounting/groups-in-tallyprime/)). The proposed classifier, which is a design proposal and not an industry standard, combines five signals:
1. An exact match on a group name.
2. The voucher context the ledger appears in. For example, the cash/bank side of a Receipt voucher.
3. Keywords seeded from Tally's descriptions.
4. Party-name patterns, such as "Pvt Ltd", "Traders" or a 15-character GSTIN.
5. A check that the balance sign makes sense for the proposed group.

Anything below about 0.7 confidence goes into a visible **"Unclassified" bucket that blocks P&L and balance-sheet publication** until the user answers. The user's answers are saved per company for later imports. Four rules guard against silent misclassification:
- Never default an unknown ledger to Indirect Expenses, which overstates costs.
- Never park an unknown ledger in Suspense without a warning, which would let the balance sheet balance while hiding a P&L error.
- Never classify GST ledgers as Sales or Purchase.
- Settle direct-versus-indirect for wages, freight, power and packing by asking whether the business trades, manufactures or provides services.

## GST 2.0 makes invoice date and place of supply part of every check

The tax type depends on comparing the supplier's location with the place of supply (POS). If both are in the same State or UT, the supply is intra-state and attracts CGST plus SGST (or UTGST), each at half the rate. If they differ, the supply is inter-state and attracts IGST at the full rate. Supplies to or by an SEZ are always inter-state ([CBIC IGST s.7](https://taxinformation.cbic.gov.in/content/html/tax_repository/gst/acts/2017_IGST_Act/active/chapteriv/section7_v1.00.html); [KnowYourGST s.8](https://www.knowyourgst.com/gstlaw/igst-act/8-intra-state-supply-182/); [ClearTax](https://cleartax.in/s/gst-calculator)). In software terms:
- The supplier's state is the first two digits of the company's own GSTIN.
- The POS should be normalised to a two-digit code. It may arrive as a state name, an alpha code, a two-digit code or "27-Maharashtra". Accept both TS and TG for Telangana, and both AP and AD for Andhra Pradesh, because vendors differ.
- The buyer's GSTIN state is only a stand-in for the POS. A mismatch is a warning, not an error, because bill-to/ship-to sales and some services legitimately differ.

The state codes below come from [Zoho Books India](https://www.zoho.com/in/books/kb/gst/valid-state-codes-list.html), cross-checked against [myBillBook](https://mybillbook.in/blog/state-gst-codes/). Codes 25 (old Daman & Diu) and 28 (pre-bifurcation Andhra Pradesh) are retired.

| Code | State/UT | Code | State/UT | Code | State/UT |
|---|---|---|---|---|---|
| 01 | Jammu & Kashmir | 14 | Manipur | 27 | Maharashtra |
| 02 | Himachal Pradesh | 15 | Mizoram | 29 | Karnataka |
| 03 | Punjab | 16 | Tripura | 30 | Goa |
| 04 | Chandigarh | 17 | Meghalaya | 31 | Lakshadweep |
| 05 | Uttarakhand | 18 | Assam | 32 | Kerala |
| 06 | Haryana | 19 | West Bengal | 33 | Tamil Nadu |
| 07 | Delhi | 20 | Jharkhand | 34 | Puducherry |
| 08 | Rajasthan | 21 | Odisha | 35 | Andaman & Nicobar |
| 09 | Uttar Pradesh | 22 | Chhattisgarh | 36 | Telangana |
| 10 | Bihar | 23 | Madhya Pradesh | 37 | Andhra Pradesh |
| 11 | Sikkim | 24 | Gujarat | 38 | Ladakh |
| 12 | Arunachal Pradesh | 26 | DNH and Daman & Diu | 97 | Other Territory |
| 13 | Nagaland | | | | |

### Rates must be effective-dated because GST 2.0 split FY 2025-26

From **22 September 2025**, the 56th GST Council replaced the 5/12/18/28% structure with a **5% merit rate, an 18% standard rate and a 40% de-merit rate** ([GST Council press release](https://gstcouncil.gov.in/sites/default/files/2025-09/press_release_press_information_bureau.pdf)). Examples of the moves:
- **To 5%:** soap, toothpaste, most packaged foods, and hotel rooms up to ₹7,500 a day.
- **To 18%:** small cars, ACs and cement.
- **To 40%:** larger cars, aerated drinks and online money gaming.
- **To nil:** UHT milk and 33 lifesaving drugs.

Tobacco and pan masala kept the old 28% rate plus compensation cess until **1 February 2026**. From that date they moved to 40% (bidis to 18%), the compensation cess ended, and a new Health and National Security Cess on pan masala and additional excise on tobacco took effect. Both are levied **outside GST** ([Deccan Herald](https://www.deccanherald.com/amp/story/india%2Fadditional-excise-duty-on-tobacco-health-cess-on-pan-masala-to-be-effective-february-1-3848089)), so they must never be added into GST totals. Special rates remain: 3% on gold, silver and jewellery, 0.25% on rough diamonds and 1.5% on cut and polished diamonds ([Tally](https://tallysolutions.com/gst/gst-on-silver-diamond-precious-stones-tax-guide-for-jewellery-retailers/)).

A register covering FY 2025-26 therefore legitimately contains both regimes, so valid rates must be looked up by invoice date:
- **Before 22 September 2025:** 0, 0.25, 1.5, 3, 5, 12, 18 and 28%.
- **From 22 September 2025:** 0, 0.25, 1.5, 3, 5, 18 and 40%.
- **Tobacco exception:** 28% plus cess remains valid for tobacco HSN codes until 31 January 2026.

The Council release itself says it does not have force of law. The HSN-wise CBIC rate notifications were not fetched and must be loaded before the rate master is final.

| Quantity | Formula | Note |
|---|---|---|
| Tax on an exclusive value | taxable × rate / 100 | ([ClearTax](https://cleartax.in/s/gst-calculator)) |
| Taxable value from an inclusive amount | inclusive × 100 / (100 + rate) | Tax = inclusive − taxable |
| Intra-state split | CGST = round(tax/2, 2); SGST = tax − CGST | The leftover paisa goes to SGST so totals stay exact |
| Inter-state | IGST = tax | Also for exports and SEZ, or zero-rated under LUT |
| Line validation | \|tax − round(taxable × rate/100, 2)\| ≤ ₹0.05 per line, ≤ ₹1 per invoice | Design tolerance, not statutory |
| Payable per tax head | Round half-up to the nearest rupee | CGST s.170 ([Busy](https://busy.in/gst/rounding-off-rules-in-gst-invoices/)) |

Section 170 does not require each invoice line to be rounded to whole rupees. The portal accepts amounts to two decimals, and e-invoices carry a separate `RndOffAmt` field. That reading is a vendor interpretation ([Gimbooks](https://www.gimbooks.com/blog/gst-invoice-round-off-differences/)). Practitioners also disagree on whether rounding should apply per invoice or to the monthly total ([Masters India](https://www.mastersindia.co/blog/rounding-off-tax-under-gst/)). Accounts.ai should keep amounts to two decimals and round only each final payable head.

### Returns, set-off order and input tax credit

GSTR-1 reports outward supplies, and GSTR-3B is the summary return that pays the tax ([ClearTax GSTR-1](https://cleartax.in/s/details-mentioned-return-gstr-1); [Zoho GSTR-3B](https://www.zoho.com/en-in/erp/kb/filing-and-compliance/sections-gstr-3b.html)). The table maps register conditions to both returns:

| Register condition | GSTR-1 table | GSTR-3B |
|---|---|---|
| Valid buyer GSTIN, forward charge | 4A (B2B) | 3.1(a) |
| Valid buyer GSTIN, reverse charge | 4B | Excluded from the supplier's 3.1(a) |
| No GSTIN, inter-state, invoice over ₹1 lakh | 5 (B2C Large) | 3.1(a) and 3.2 |
| Other sales with no GSTIN | 7 (B2C small, by POS × rate) | 3.1(a); the inter-state part also in 3.2 |
| Exports and SEZ | 6 | 3.1(b) |
| Nil-rated, exempt, non-GST | 8 | 3.1(c) / 3.1(e) |
| Credit and debit notes | 9B | Netted in 3.1 |
| HSN summary | 12 (separate B2B and B2C tabs) | — |
| Purchases under reverse charge | — | Liability in 3.1(d); credit in 4(A)(3) |

Three of these rules have open questions:
- **B2C Large threshold.** Notification 12/2024 cut the threshold from ₹2.5 lakh to **₹1 lakh** from 1 August 2024. A September 2024 GSTN advisory told taxpayers to keep using ₹2.5 lakh until the portal was updated ([Cashflo](https://www.cashflo.io/magazine/gst-alert-reduced-b2c-invoice-reporting-threshold-in-gstr-1); [Tally Help](https://help.tallysolutions.com/tally-prime/gstr-1/b2c-large-invoices-5a-5b/)). Make the threshold a setting.
- **HSN digits.** Taxpayers with turnover above ₹5 crore must report at least six digits ([West Bengal CT](https://comtax.wb.gov.in/GST/Functionality_Taxpayer/functionality_Return_20220525_2.pdf)).
- **Hard-locking.** From the **July 2025 tax period**, the liability auto-filled into GSTR-3B from GSTR-1 can no longer be edited. Corrections go through GSTR-1A ([GSTN advisory](https://www.mahagst.gov.in/public/uploads/gstnadvisory/1760596521_352%20Advisory%20regarding%20non-editable%20of%20auto-populated%20liability%20in%20GSTR-3B.pdf)), which can be filed only once per period ([ELP](https://elplaw.in/leadership/advisory-issued-by-goods-service-tax-network/)). Sources conflict on whether Table 3.2 is also locked ([SCC Online](https://www.scconline.com/blog/?p=351217) vs [Taxmann](https://www.taxmann.com/post/blog/gstr-3b-table-3-2-to-be-auto-populated-and-non-editable)).

The practical consequence of hard-locking: Accounts.ai's "3B liability" must always equal its GSTR-1 view for the same period. Any later edit to the sales data must be flagged as needing an amendment, never silently re-computed.

Net payable follows Rule 88A ([TaxAdda](https://taxadda.com/order-of-utilisation-of-input-tax-credit-under-gst/); [Taxmann](https://www.taxmann.com/post/blog/clarifications-on-rule-88a-order-of-utilization-of-input-tax-credit-issued-by-cbic/)):
1. IGST credit pays IGST liability first.
2. Any IGST credit left over pays CGST and SGST in any order and proportion. Software should choose the split that minimises cash.
3. CGST credit pays CGST, then any remaining IGST.
4. SGST credit pays SGST, then any remaining IGST. CGST credit can never pay SGST, and SGST credit can never pay CGST.
5. Reverse-charge tax is paid **only in cash**. "Output tax" excludes reverse-charge tax, and the credit ledger can pay only output tax ([TaxHeal](https://taxheal.com/pay-output-tax-cash-reverse-charge-gst-gst-itc-cant-claimed.html); [ClearTax CGST Rules Ch. 9](https://cleartax.in/s/cgst-rules-chapter-9-payment-of-tax)).
6. Round each head's final cash payable to the nearest rupee.

An illustrative example: liability is IGST 500, CGST 300 and SGST 300, with credit of IGST 1,000, CGST 300 and SGST 300. IGST credit pays the IGST 500 and then 250 each of CGST and SGST. Own CGST and SGST credit then pays the remaining 50 on each head. Cash payable is zero, and CGST 250 and SGST 250 carry forward. One further detail was not verified against the statute and should be checked before coding: whether the section 49(5) proviso requires CGST credit to be applied to leftover IGST before SGST credit.

Input tax credit can be claimed only if all of these hold:
- The buyer holds a tax invoice.
- The invoice appears in GSTR-2B (s.16(2)(aa)).
- The goods or services have been received.
- The supplier has paid the tax.
- The claim is made by 30 November after the year ends, or by the annual return if filed earlier (s.16(4)) ([AI Accountant](https://www.aiaccountant.com/blog/gstr-2b-means-itc-rules)).

The Invoice Management System (IMS) feeds GSTR-2B. Records the buyer accepts flow into 2B, rejected records are excluded, pending records wait, and records with no action are deemed accepted ([IRIS](https://irisgst.com/guidance-note-on-invoice-management-system-ims/); [GSTN FAQ](https://gstgyaan.com/pdf/additional-faq-on-ims-17-10-2024.pdf)). One blog says IMS became mandatory from 1 April 2026; this comes from a single source and is unverified ([LegalRaasta](https://www.legalraasta.com/blog/?p=36605)). Credit taken on a bill not paid to the supplier within 180 days is a temporary reversal under Rule 37, reported in 4(B)(2) ([ClearTax Table 4](https://cleartax.in/s/table-4-of-gstr-3b)). Section 17(5) blocks credit on several categories ([TaxGuru](https://taxguru.in/goods-and-service-tax/input-tax-credit-claimed-itc-blocked-transactions-reg.html); [Razorpay](https://razorpay.com/learn/section-17-5-cgst-act/)):
- passenger vehicles seating 13 or fewer;
- food and beverages, beauty treatment and health services;
- club and gym memberships;
- construction of immovable property on own account;
- personal consumption;
- gifts, free samples, and goods lost or written off;
- CSR spending (since 1 October 2023).

Purchase-register matching against 2B should use a key of supplier GSTIN, normalised invoice number, date, taxable value and tax, with a ±₹1 tolerance. Results fall into four buckets: matched; in books but not in 2B; in 2B but not in books; and mismatched.

### GSTIN validation and the rule table

A regular GSTIN has 15 characters ([AI Accountant](https://www.aiaccountant.com/blog/gstin-format)):

| Positions | Content |
|---|---|
| 1–2 | State code |
| 3–12 | PAN |
| 13 | Entity number |
| 14 | "Z" by default |
| 15 | Mod-36 check character |

No official GSTN specification of the checksum was found. The algorithm below is the widely used reverse-engineered version ([Commmerce](https://commmerce.com/tools/gstin-validator.md)). Re-run for this report, it reproduces the check character "V" of the published sample 27AAPFU0939F1ZV. Use the regex `^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$` for regular taxpayers. Fall back to a checksum-only test, labelled "special registration", for registration types such as UIN and OIDAR, since their patterns were not sourced.

```python
CS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14.upper()):
        prod = CS.index(ch) * (1 if i % 2 == 0 else 2)
        total += prod // 36 + prod % 36
    return CS[(36 - total % 36) % 36]
```

The rules below should run as vectorised pandas boolean columns, so every flag can be explained and counted by party. The thresholds are design choices; GSTN publishes no tolerance. Auto-repairs, such as back-calculating an inclusive amount or splitting IGST into CGST/SGST halves, are always suggested to the user and never applied silently.

| Check | Condition | Severity |
|---|---|---|
| Both tax types on one supply | IGST > 0 and (CGST > 0 or SGST > 0) | Error |
| Unequal halves | \|CGST − SGST\| > ₹0.05 | Error |
| IGST on an intra-state sale | POS = supplier state, IGST > 0, not SEZ or export | Error (warn if a POS override is recorded) |
| CGST/SGST on an inter-state sale | POS ≠ supplier state and CGST + SGST > 0 | Error |
| Tax ≠ rate × value | \|tax − taxable × rate/100\| > max(₹1, 0.05% of taxable) | Error |
| "Taxable" column is really inclusive | tax ≈ taxable × rate/(100 + rate) | Warn; suggest back-calculation |
| Rate not valid for the invoice date | e.g. 12% or 28% after 21 September 2025 (except tobacco until 31 January 2026) | Error |
| Cess after the cut-off | Cess on non-tobacco items from 22 September 2025, or any compensation cess from 1 February 2026 | Warn |
| Zero rate with tax | Rate 0 or exempt, but tax > 0 | Error |
| Invalid GSTIN | Fails the regex, state code or checksum; or supplier GSTIN = own GSTIN | Error |
| Buyer state ≠ POS | buyer_GSTIN[:2] ≠ POS | Warn |
| Duplicate invoice | Same (GSTIN, invoice number, FY) appears twice | Error |
| Credit-note sign | Credit note is positive, or larger than the original invoice | Warn |
| Out-of-state input credit | CGST/SGST on a purchase from a supplier in another state | Warn (credit not available, 4(D)(2)) |
| Blocked credit claimed | Purchase mapped to a s.17(5) category with credit claimed | Warn |
| Books vs GSTR-2B | Purchase missing from 2B, or 2B record missing from books | Warn |

## The LLM should route, cross-check and refuse, never compute

Once the importer and engine exist, the LLM's remaining job is narrow: choose the right verified computation, fill in its parameters, state its assumptions, and handle the long tail with checked SQL. The highest-evidence lever is a **per-upload semantic document**, editable by the user. It is worth **+17 to +23 points** across three frontier models, and with it the choice of model stopped mattering statistically ([arXiv 2604.25149](https://arxiv.org/abs/2604.25149)). It should list:
- each column's meaning, units and sign convention;
- the distinct values of low-cardinality columns (ledger names, voucher types, GST rates);
- date and amount ranges;
- row counts and a few sample rows;
- the accounting rules, for example "Outstanding = bill amount − allocated receipts" and "Revenue excludes GST".

Production systems do the same. Snowflake's semantic model holds synonyms, metric definitions and literal-value retrieval, so "USA" maps to "United States of America" ([Snowflake](https://snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes)). Databricks advises adding descriptions and synonyms, hiding duplicate columns, declaring primary and foreign keys, and growing the instructions from observed failures ([Databricks](https://docs.databricks.com/aws/en/genie/tune-quality)). Uber found that **accuracy fell as more tables were onboarded** ([Uber](https://www.uber.com/blog/query-gpt)). The model should therefore see the engine's clean canonical tables (vouchers, voucher lines, ledgers, groups, bills, GST lines, bank lines), not raw uploaded sheets.

The features in the two previous sections should become tools: ledger, trial balance, P&L, balance sheet, GST summary, ageing and BRS. Free-form `run_sql` is the fallback. This mirrors Snowflake's verified queries and Databricks' "trusted assets", which Databricks labels "verified" only when the response matches a trusted asset exactly ([Databricks](https://docs.databricks.com/aws/en/genie/tune-quality)). Both model vendors give relevant tool guidance:
- **OpenAI** recommends "always enabling strict mode". It advises keeping to fewer than 20 functions and not making the model fill in arguments the code already knows, such as the database handle or row limits ([OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)).
- **Anthropic** calls detailed tool descriptions "by far the most important factor in tool performance", and offers `strict: true` for schema-constrained tool inputs ([Anthropic: Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use); [Anthropic: Strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)).
- **On Claude as the alternative model:** forcing a tool call returns a 400 error on Claude Opus 5.5 and Sonnet 5.5. Accounts.ai must use `auto` tool choice and enforce the "numbers only from tools" rule in code.

Strict mode guarantees the shape of a tool call, not the correctness of the SQL.

The free-form SQL path needs four guardrails:
1. **Sandboxed execution.** Open SQLite read-only, allow only SELECT/WITH, and enforce a timeout and a row cap. This is engineering judgement rather than a sourced finding.
2. **An execution-feedback loop.** Return SQLite errors, empty results, NULL sums and suspicious row counts from join fan-out to the model, with a budget of two or three retries. Removing such a refiner cost 9.3 points in one ablation ([arXiv 2408.07930](https://arxiv.org/pdf/2408.07930)). Without retries, GPT-4-Turbo's generated code ran only **78.67%** of the time on TableBench ([arXiv 2408.09174](https://arxiv.org/html/2408.09174v2)).
3. **A cross-check on money questions.** Generate two or three candidates, at different temperatures or from GPT plus Claude, run them all, and compare **result values, not SQL text** ([arXiv 2503.24364](https://arxiv.org/pdf/2503.24364)). Agreement raises confidence. Disagreement exposes a hidden assumption to show the user or ask about. The gains concentrate on hard questions, which is where ageing, reconciliation and period comparisons sit ([arXiv 2502.14913](https://arxiv.org/pdf/2502.14913)).
4. **A fail-closed grounding gate.** The final answer comes back as structured output: answer text, each figure with the query and cell it came from, the SQL, the assumptions, and a `needs_clarification` flag. Code then checks every number in the prose against tool outputs under a declared rounding rule, and blocks or marks unverified any number that fails. This follows the Proof-Carrying Numbers approach, where verification sits in the renderer rather than the model ([arXiv 2509.06902](https://arxiv.org/abs/2509.06902v1)), and practitioner reports of models narrating a 4.2% figure when the query returned 6.8% ([tianpan.co](https://tianpan.co/blog/2026/05/17/agent-narrated-a-number-it-should-have-computed)). No study has measured the gate's effect on its own, but it mechanically removes a whole error class.

Ambiguity should trigger a question, not a guess. Snowflake's first agent rejects ambiguous or non-data questions and offers answerable alternatives ([Snowflake](https://snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes)), and AmbiSQL's interactive rewriting improved exact-match accuracy by about 50% in relative terms ([arXiv 2508.15276](https://arxiv.org/html/2508.15276v1)). In accounting, the usual triggers are:
- financial year versus calendar period;
- GST-inclusive versus exclusive amounts;
- gross versus net of returns;
- bill-date versus due-date ageing;
- which branch or entity.

When the data cannot answer at all, for example net profit with no closing stock, the answer should say exactly what is missing. Every answer should carry a confidence label derived from checks, never from the model's self-report:
- **Verified:** a tested report template produced it.
- **Cross-checked:** independent queries agreed.
- **Unverified:** a single query, or the gate needed a retry.
- **Needs clarification.**

The executed SQL, the result rows and a drill-down to the source Excel row should always be one click away.

On model settings, OpenAI calls reasoning effort "a tuning knob, not the primary way to recover quality". It recommends `xhigh` only when evaluations show a benefit, reserving at least 25,000 tokens for reasoning and output, and passing reasoning items back across tool calls with `previous_response_id` ([OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)). It also notes that examples in prompts may hurt reasoning models ([OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)). No model-specific guidance for GPT-6 Luna was found; the guide names GPT-5.5, GPT-5.6, GPT-6 Astra and GPT-6.1 Sol. Start Luna at medium effort and A/B-test high effort on the evaluation set. That evaluation set should hold 100–300 real questions over representative uploads, each with a gold result, scored on values and re-run on every prompt, model or effort change, as Databricks does with its benchmarks ([Databricks](https://docs.databricks.com/aws/en/genie/tune-quality)). Given the audited error rates in public benchmarks, every gold answer needs genuine human review ([arXiv 2601.08778](https://arxiv.org/abs/2601.08778)).

| Build order | Component | What it removes |
|---|---|---|
| 1 | Import proof: integer paise, strict parsers, Tally Dr/Cr from formats, control totals, manifest | Silent data loss that no model can detect |
| 2 | Double-entry engine with invariants and an "Unclassified" gate | Wrong standard reports |
| 3 | GST rule engine with effective-dated rates and the validation table | Statutory errors that, from July 2025, flow straight into GSTR-3B |
| 4 | Semantic document, verified report tools, strict schemas | The +17–23 pp semantic gap |
| 5 | Retry loop and grounding gate | Broken SQL and misquoted numbers |
| 6 | Clarify/abstain path and dual-candidate cross-check | Silent misreadings of hard or ambiguous questions |
| 7 | Evaluation harness on real customer files | Unmeasured regressions |

## Conclusion

The accuracy problem looked like an AI problem, but most of it is data engineering and Indian accounting rules. Once the importer proves each file and the engine computes reports that must satisfy invariants, the LLM is left with one job: deciding which verified computation answers the question and saying what it assumed. That is the one task where the evidence shows models plateau, so the product should prefer asking a question to answering. Model choice was statistically irrelevant once domain documentation was supplied. The durable asset is therefore Accounts.ai's Indian accounting engine and semantic layer, which work the same with GPT-6 Luna or Claude. Switching model vendors becomes a lever on cost, not on accuracy. "100% accurate" also becomes something that can be measured and published every release:
- the share of imports that reconcile exactly;
- the share of reports that pass their invariants;
- the share of free-form answers labelled verified or cross-checked.

Exactness still depends on facts that are not yet confirmed:
- the format string Tally writes for Dr/Cr;
- the layouts of Tally Day Book, trial balance and register exports;
- export formats from Busy, Vyapar and Zoho Books;
- statement templates for ICICI, Axis and Kotak;
- the HSN-wise CBIC rate notifications;
- whether the portal enforces the ₹1 lakh B2C Large threshold;
- whether GSTR-3B Table 3.2 is locked.

The most valuable next step is not more research. It is collecting 20–30 real exports from pilot customers and turning each into a regression fixture with known control totals. That fixture set becomes both the importer's test suite and the first version of the evaluation harness.
