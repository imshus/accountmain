# Bank Reconciliation Matching and GSTR-1 / GSTR-3B Preparation (India, as of Oct 2026)

Scope: (a) matching uploaded bank statement lines to bank-ledger entries and producing the Bank Reconciliation Statement (BRS); (b) preparing GSTR-1 and GSTR-3B summaries from sales, purchase, credit-note and debit-note vouchers. Research date 22 Oct 2026. This builds on `research_notes/Accurate AI accounting features/gst_rules.md`, which already covers rate slabs, the Rule 88A ITC utilisation order, RCM, s.17(5), GSTIN validation and register validations. Those points are not repeated here.

Labels used below:
- **[knowledge, not fetched]**: from my general knowledge, not confirmed from a source this session. Verify before hard-coding.
- **[design]**: my own design choice or default. Not taken from any vendor or statute.
- **(snippet)**: taken from a search-result summary, not from a fetched page. Attribution is less certain.

---

## 1. How Tally Prime, Zoho Books, QuickBooks and Xero match bank statement lines to book entries

### Takeaway
All four products use a tiered approach:
1. **Exact amount** is the gate.
2. **Reference** (cheque/instrument number, UTR) is the strongest tie-breaker.
3. **Date proximity** and **party/payee** rank the remaining candidates.

Tally Prime is the closest model for an Indian SME app. It separates **Exact Matches**, which it links automatically and the user confirms with one key, from **Potential Matches**, which are rule-based suggestions on instrument date, amount and party within a 30-day window by default. It supports one-to-one, many-to-one and one-to-many matches. Xero and QuickBooks rank by amount first and leave everything else as suggestions. Xero auto-reconciles only at high confidence.

### Cited Findings
**Tally Prime (Auto Bank Reconciliation)**
- **Exact matches** are linked automatically: "The transactions under the Exact Match section get linked." The user then selects them and presses F8 to reconcile. — [Tally Help: Auto Bank Reconciliation](https://help.tallysolutions.com/bank-recon/auto-bank-reconciliation/)
- Tally's marketing page says exact matching uses the instrument number and the precise amount. Its "Smart Match" handles rounding differences, date mismatches and multiple entries for one transaction, including records with no instrument number. — [Tally MENA page](https://tallysolutions.com/mena/tally/uae-bank-reconciliation-tallyprime/) (snippet; marketing copy)
- **Potential matches** are identified "based on various aspects of transactions such as Instrument Date, Amount, and Party". The rules are configured with Alt+S, all default rules are enabled, and suggestions can be grouped by rule or by transaction. — [Tally Help](https://help.tallysolutions.com/bank-recon/auto-bank-reconciliation/)
- **Reference normalisation option:** ignore leading zeroes and special characters in instrument numbers. — [Tally Help](https://help.tallysolutions.com/bank-recon/auto-bank-reconciliation/)
- **Cardinality:**
  - Supported: one book entry to one bank entry, multiple book entries to one bank entry, and one book entry to multiple bank entries.
  - A manual match whose amounts disagree is only *partly* reconciled.
  - On the Modify Matches screen the user can alter the book voucher (for example, to add a charge) or press F7 (Create Vch) to create a voucher and add it to the match.
  - Set Status (F9) writes the statement date into the voucher's Bank Date and copies the instrument number into the book entry if it is missing.
  - Source: [Tally Help](https://help.tallysolutions.com/bank-recon/auto-bank-reconciliation/)
- **Prerequisites:** auto-reconciliation must be enabled on the bank ledger, and the statement must be dated after the Reconciliation Beginning Date. Statement import is supported for 145+ banks. — [Tally Help (search summary)](https://help.tallysolutions.com/auto-bank-reconciliation/) (snippet)
- A 2025–26 Tally guide says statements can be fetched through Connected Banking or imported with Alt+O, and that missing book entries such as bank charges can be auto-created from the statement. — [Tally business guide](https://tallysolutions.com/business-guides/how-to-auto-import-bank-statements-for-faster-reconciliation-in-tallyprime/) (snippet)

**Zoho Books**
- When an uncategorised bank line meets the match criteria, Zoho shows a "Match found" tag. Otherwise it suggests **Best Matches** and **Possible Matches** using "the date, amount, and transaction rules you have configured". — [Zoho Books Help: Match & Categorize Transactions](https://www.zoho.com/us/books/help/banking/matching-transactions.html) (snippet)
- In Possible Matches the user can tick several book transactions whose total equals the bank amount and match them together (many-to-one). Zoho has a separate KB article on matching multiple bank feed lines to one invoice or bill (one-to-many). — [Zoho Books Help](https://www.zoho.com/us/books/help/banking/matching-transactions.html) (snippet); [Zoho India KB: Match multiple bank feeds with invoice/bill](https://www.zoho.com/in/books/kb/banking/multiple-feeds-one-transaction.html) (title only)
- **Bank rules** are a separate mechanism that auto-categorise lines by criteria such as "description contains keyword". — [Patron Accounting, Apr 2026](https://www.patronaccounting.com/blog/zoho-books-bank-reconciliation-india-guide) (snippet; third party)
- Zoho support has said a statement line that is unmatched stays "uncategorized" even if the corresponding book transaction was reconciled by other means. — [Zoho community thread](https://help.zoho.com/portal/en/community/topic/removing-old-imported-transactions-from-best-matches-and-possible-matches-list) (about two years old)

**QuickBooks Online**
- Intuit staff: "QuickBooks will automatically search for matching transactions based on the amount and date." The original poster says the default lookback is "about a 1 year"; staff say the default cannot be changed. — [QuickBooks community](https://quickbooks.intuit.com/learn-support/en-us/banking/matching-transactions-default-date-range/00/1496546)
- Another Intuit help result describes suggested matches as covering **90 days before and 20 days after** the downloaded transaction. — [QuickBooks: Turn on suggestions](https://quickbooks.intuit.com/learn-support/en-us/banking/bank-feed-matching/00/949100) (snippet). **Conflict:** this does not agree with the ~1-year lookback above. Older community posts cite a 180-day limit, which later posts deny.
- **Multi-match:** select several book transactions that add up to the downloaded amount, then use "Resolve the difference" for leftovers such as fees. For foreign currency the system reportedly searches within a 10% range of the amount. — [QBO Banking chapter (Intuit Education PDF)](https://intuitglobal.intuit.com/delivery/cms/prod/sites/default/education.intuit.ca/downloads/qbo/Chapter-6-Banking-in-QuickBooks-Online.pdf) (snippet; attribution within the search results not verified)

**Xero**
- A Xero staff explanation on the product-ideas forum says matching starts with an exact-amount search, then compares supplier name and reference to rank candidates. Ties are ordered by nearest due date. Xero said it had no plans to match by invoice number at the time. — [Xero Product Ideas: matching by invoice number](https://productideas.xero.com/forums/939198-for-small-businesses/suggestions/46600471-bank-reconciliation-suggestions-matching-by-in); [Xero Product Ideas: suggest the most recent bill](https://productideas.xero.com/forums/967139-purchase-orders-bills-inventory/suggestions/51046234-bank-reconciliation-suggest-the-most-recent-bill) (snippets)
- Xero's automatic bank reconciliation (JAX) reconciles using four methods: bank rules, matching to existing documents (same payee and amount), the user's past reconciliations, and patterns from other Xero users. Each reconciled line is labelled with the method used. — [Xero Product Ideas: auto bank rec](https://productideas.xero.com/forums/966939-automatic-bank-reconciliation-beta/suggestions/51046744-auto-bank-rec-improve-matching-to-existing-trans) (snippet)
- A third-party blog says JAX auto-reconciles only when confidence is high and leaves the rest as suggestions. — [Sagnik Bhattacharya blog](https://sagnikbhattacharya.com/blog/automate-bank-reconciliation-ai-check-matches) (snippet; not confirmed on Xero's own help)
- For near-amount cases, such as a receipt net of a bank charge, users are pointed to "Find & Match", which shows close matches and lets the user add an adjustment line. — [1st Formations Xero guide](https://help.1stformations.co.uk/accounting-service/how-to-reconcile-your-bank-in-xero-step-by-step) (snippet)
- A user reported that a feed putting the description into the payee field forced amount-only matching and produced wrong matches. Payee/narration quality matters. — [Xero Product Ideas](https://productideas.xero.com/forums/939198-for-small-businesses/suggestions/50637662-allocating-payments-to-invoices-based-on-customer) (snippet)

### Inferences
**Recommended matching engine [design, modelled on Tally's exact/potential split and Xero's amount-first ranking]**

Normalise both sides first:
- Amounts as integer paise.
- Direction: a bank credit matches a book debit to the bank ledger (receipt); a bank debit matches a book credit (payment).
- `ref_norm`: uppercase, strip non-alphanumerics, strip leading zeros (as in Tally's option).
- `party_norm`: uppercase, drop M/S, PVT, LTD, LIMITED, PRIVATE, ENTERPRISES, TRADERS and similar; collapse spaces.
- The book side includes only bank-ledger voucher lines with no bank date (unreconciled) dated on or after the reconciliation beginning date.

Run the passes in order. Each pass sees only items still unmatched.

| Pass | Rule | Output |
|---|---|---|
| P1 Exact | same direction, `amount_paise` equal, `ref_norm` equal (cheque no. = instrument no., or UTR/RRN found in book narration or instrument field), date inside window (§2) | **Auto-linked** (confidence 100). Confirm in bulk, as with Tally F8 |
| P2 Amount + party | amount equal, party similarity ≥ 0.80 (token-set ratio), date inside window | Suggested |
| P3 Amount + date, unique | amount equal and exactly one candidate on each side within the window | Suggested (high) |
| P4 Group | many book → one bank (a deposit slip of several cheques; one bulk-payment debit) or one book → many bank (split credit; payment plus separate charge). Bounded subset-sum within the same party or a ±3-day cluster, k ≤ 6, candidates ≤ 25 | Suggested |
| P5 Near-amount | \|diff\| ≤ user tolerance (default ₹0), or the diff equals a separate charge line on the same date | Suggested with "post difference to Bank Charges" |
| P6 Classify leftovers | keyword and narration rules (§2, §4) | "Create voucher" suggestions (charges, interest, TDS, reversals) |

**Scoring for suggestions [design]:**
- `score = 50·amount_exact + 25·ref_match + 15·date_score + 10·party_score`, where `date_score = max(0, 1 − |Δdays|/window)` and `party_score` is the fuzzy ratio in [0, 1].
- **Auto-link** only when score ≥ 90 *and* the runner-up for either item is ≥ 10 points lower. Otherwise suggest when score ≥ 60, and hide below 60.
- Always keep the user's confirm or undo step. Tally and Xero keep the user in the loop for anything except exact or high-confidence matches.

**One-to-one assignment:**
1. Build all candidate pairs, using `merge` on (direction, amount_paise) and then a date-window filter.
2. Resolve them globally: greedy by descending score, or `scipy.optimize.linear_sum_assignment` on `cost = 100 − score`.

This handles "same amount on nearby dates" (for example, three ₹5,000 rent cheques) without double-assigning.

**Persistence:**
- Table `recon_match(group_id, bank_line_id, book_line_id, pass, score, rule, status[auto|suggested|confirmed|rejected], user, ts)`.
- On confirm, write `bank_date = bank txn_date` on the book line, mirroring Tally's Bank Date.
- Store rejected pairs so the same pair is not suggested again.

**Learning rules:**
- When a user confirms a match, remember `VPA/IFSC+account/narration token → party ledger`. Use it as a P2 party hint next time.
- This mirrors Xero's "previous reconciliations" and Zoho's bank rules.

### Gaps
- No vendor publishes its exact scoring weights or thresholds. The weights above are a design proposal.
- I did not find Zoho Books' official date window or amount tolerance for "Best Matches".
- The QuickBooks date window is contradictory (90/20 days vs ~1 year vs 180 days). It was not confirmed on a primary Intuit help page in this session.
- The Tally page's example for "Ignore difference in Amount for Potential Match" was unclear, so the semantics of its tolerance setting are not confirmed.

---

## 2. Date windows, tolerances, and handling of bank charges, interest, reversals and duplicate amounts

### Takeaway
- **Date window:** Tally's default is **30 days**, and setting it to 0 means same date only. QBO reportedly uses about 90 days back and 20 days forward. Xero and Zoho rank by date closeness rather than a published window.
- **Amount:** an exact match is the norm. Differences are handled by a configurable tolerance (Tally), "Resolve the difference" (QBO) or adding an adjustment line (Xero).
- **Leftover bank lines:** charges, interest, direct credits and reversals should become "create voucher" suggestions. Tally's F7, the auto-create in Tally's guide and Xero's bank rules all work this way.

### Cited Findings
- **Tally:**
  - Potential matches search within **30 days** by default; setting 0 requires the same date.
  - There is an "Ignore difference in Amount for Potential Match" setting with a greater-than/less-than threshold.
  - Instrument numbers can be compared while ignoring leading zeroes and special characters.
  - Source: [Tally Help](https://help.tallysolutions.com/bank-recon/auto-bank-reconciliation/)
- **Tally Smart Match** covers "rounding differences, date mismatches, and even multiple entries for a single transaction". — [Tally MENA page](https://tallysolutions.com/mena/tally/uae-bank-reconciliation-tallyprime/) (snippet)
- **QBO:** 90 days before / 20 days after for suggestions (snippet). "Resolve the difference" posts a leftover such as a fee. FX amounts are matched within a 10% range. — [QuickBooks: Turn on suggestions](https://quickbooks.intuit.com/learn-support/en-us/banking/bank-feed-matching/00/949100); [QBO banking chapter](https://intuitglobal.intuit.com/delivery/cms/prod/sites/default/education.intuit.ca/downloads/qbo/Chapter-6-Banking-in-QuickBooks-Online.pdf) (snippets)
- **Unrecorded bank charges** debited by the bank are deducted from the cash-book balance in a BRS, and the cash book should then be corrected. — [ICAI BoS: Bank Reconciliation Statement](https://live.icai.org/bos/vcc/pdf/Bank_Reconcilation_Statement.pdf) (snippet)
- **Reversal and refund markers** seen in Indian narrations: REV and RVS (refunds), CHG and COMM (fees). — [AI Accountant narration guide](https://aiaccountant.com/blog/smart-narration-parsing-indian-statements)
- **UPI reversal lines** appear as "BY TRANSFER-UPI/REV/…" in an SBI-style statement. — [Statement in Allahabad HC filing](https://dc.allahabadhighcourt.in/assets/documents/request/objection_document17271740633.pdf) (snippet; format only)
- The same guide recommends sending ties between candidates to a review queue rather than forcing a match. — [AI Accountant](https://aiaccountant.com/blog/smart-narration-parsing-indian-statements)

### Inferences
**Default date windows by instrument [design; banking timings are knowledge, not fetched]**

| Instrument (from narration or book voucher mode) | Window: bank date − book date |
|---|---|
| Cheque issued (payment) | −3 to +90 days. A cheque is valid for 3 months [knowledge, not fetched]. Beyond 90 days, flag "stale cheque, consider reversal" |
| Cheque deposited (receipt) | −2 to +7 days (CTS clearing is typically T+1 or T+2 [knowledge]) |
| NEFT / RTGS / IMPS / UPI | −3 to +3 days. Allow +1 for weekend NEFT batches |
| Card / POS / payment-gateway settlement | 0 to +5 days. Settlement is net of MDR, so expect P4/P5 group or near-amount matches |
| Unknown | ±7 days in P2/P3; Tally-style 30 days only in a manual "widen search" |

**Amount tolerance [design]:**
- Exact (0 paise) for P1–P4.
- P5 only: a user-configurable tolerance (default ₹0; suggest ≤ ₹10 or ≤ 0.1%), or a difference exactly equal to a same-day charge line or a known fee (NEFT/IMPS charge plus 18% GST).

**Leftover classification rules [design; keywords from Indian statements, partly knowledge]:**

| Class | Narration keywords (case-insensitive) | Suggested voucher |
|---|---|---|
| Bank charges | CHG, CHGS, CHRG, CHARGES, COMM, COMMISSION, SMS ALERT, MIN BAL, NON MAINT, AMC, ANNUAL FEE, DEBIT CARD FEE, CHQ BOOK, STOP PMT, IMPS CHG, NEFT CHG, PROCESSING FEE | Payment: Dr Bank Charges, Dr input GST (if a GST line or 18% component is present), Cr Bank |
| GST on charges | IGST, CGST, SGST next to a charge line, same date | Merge with the charge line into one voucher |
| Interest credited | INT.PD, INT PD, INT CR, CREDIT INTEREST, SB INT, INTEREST CAPITALISED, FD INT | Receipt: Dr Bank, Cr Interest Income |
| TDS on interest | TDS, TAX DEDUCTED | Dr TDS Receivable, Cr Bank |
| Interest debited (OD/CC) | INT DR, INTEREST CHARGED, OD INT | Dr Interest Expense, Cr Bank |
| Reversal / failed | REV, RVSL, REVERSAL, RET, RTN, RETURN, REFUND, I/W RTN, O/W RTN, CHQ RET, UPI/REV | Pair logic (below) |
| Cheque bounce charge | RTN CHG, CHQ RET CHG, BOUNCE | Dr Bank Charges (or recover from party), Cr Bank |
| Direct credit or debit | NEFT/RTGS/IMPS/UPI with an identifiable party but no book entry | Receipt or payment voucher against the party (party found by §4 extraction) |

**Reversed and failed transactions [design]:**
1. Inside the statement, pair a debit and a credit with the same amount, the same UTR/RRN (or a REV/RET keyword), within 7 days.
2. Mark the pair as a **self-cancelling pair**. Match them to each other, so no BRS line is needed.
3. If the book also recorded the original payment, propose a reversal voucher. For a bounced customer cheque, the book should reverse the receipt (Dr Party, Cr Bank) and optionally post bounce charges.

**Duplicate amounts on nearby dates [design]:**
- Never auto-link when more than one same-amount candidate falls in the window, unless the reference matches (P1).
- Otherwise use the global assignment from §1, with nearest date and then party similarity as tie-breakers.
- Surface "ambiguous: N candidates" in the UI.
- Detect **duplicate statement uploads** by hashing `(account, txn_date, amount, direction, ref_norm, narration_norm, running_balance)`. Overlapping statement periods are common.

### Gaps
- No official RBI or NPCI source was fetched for clearing timings (CTS T+1, NEFT half-hourly batches) or the 3-month cheque validity. Window defaults should be tuned on real data.
- Published tolerance values for Zoho and Xero were not found.

---

## 3. Bank Reconciliation Statement (BRS) layout and the check against the statement's closing balance

### Takeaway
The Indian BRS starts from the **balance as per cash book/books** (Dr = favourable). It then **adds** cheques issued but not presented and credits made by the bank but not in the books, and **less**es cheques deposited but not cleared and debits made by the bank but not in the books. The result is the **balance as per pass book/bank**. Tally's report uses four lines ("Balance as per Company Books", "Amounts not reflected in Bank", "Amounts not reflected in Company Books", "Balance as per Bank") and also shows the imported statement balance and the **difference**, which must be zero.

### Cited Findings
- **Tally's reconciliation screen:**
  - "Balance as per company books" is the book balance as at the last date of the period.
  - "Amount not reflected in bank" totals vouchers whose Bank Date is blank or later than the period end.
  - "Amount not reflected in company books" covers bank-statement entries not recorded in books.
  - "Balance as per bank" is the book balance adjusted for these items.
  - The imported statement balance and the difference are shown on the same screen. Bank dates fill in automatically after a statement import.
  - Source: [Tally Help: Bank Reconciliation report](https://help.tallysolutions.com/article/te9rel63/Reports/Display_Registers_Ledgers/Bank_Reconciliation.htm); [Tally Help: Reconciliation of Bank Statements](https://help.tallysolutions.com/?p=103033) (snippets)
- **Cheques issued** are entered on the credit side of the cash book immediately, but the bank debits them only when they are paid. Unpresented cheques are therefore added back when starting from the cash book. Bank charges not in the cash book are deducted. — [ICAI BoS study material](https://live.icai.org/bos/vcc/pdf/Bank_Reconcilation_Statement.pdf) (snippet)
- **Cheques deposited but not credited** are deducted. All unpresented cheques belong in the reconciliation statement. — [Prasar Bharati Revised Accounting Instructions 2023-24](https://pbcorp.prasarbharati.org/wp-content/uploads/2024/04/Revised-Accounting-Instructions-2023-24.pdf) (snippet)
- **Standard form:** balance as per cash book, + cheques issued not presented, − cheques deposited not collected, − bank charges/interest debited not recorded, = balance as per pass book. Prepare one BRS per bank account at period end. — [Terra Insight: BRS India](https://www.terra-insight.com/insights/bank-reconciliation-statement-brs-india/) (snippet)

### Inferences
**BRS report layout [design, consistent with the sources above]** (for a bank account with a debit balance in books):

| # | Line | Source of items | Sign |
|---|---|---|---|
| A | Balance as per Books (Bank ledger) as on *statement end date* | ledger closing balance (Dr +, Cr/OD −) | |
| B1 | Add: Cheques issued / payments made but not yet debited by bank | book credits to bank, unmatched, voucher date ≤ end date | + |
| B2 | Add: Amounts credited by bank but not recorded in books (interest, direct NEFT/UPI receipts, refunds) | bank credits, unmatched | + |
| C1 | Less: Cheques deposited / receipts recorded but not yet credited by bank | book debits to bank, unmatched, date ≤ end date | − |
| C2 | Less: Amounts debited by bank but not recorded in books (charges, GST on charges, TDS, NACH/ECS debits, interest on OD) | bank debits, unmatched | − |
| D | **Balance as per Bank (computed)** = A + B1 + B2 − C1 − C2 | | |
| E | Balance as per Bank Statement (closing balance of the uploaded statement) | last running balance, or opening + credits − debits | |
| F | **Difference = D − E** (must be 0.00 to mark the period "reconciled") | | |

- **Item detail:** each B/C line lists its items with date, voucher or statement reference, party, instrument number and amount, plus an age in days. Ages beyond the §2 windows (for example, a cheque older than 90 days) are highlighted.
- **Overdraft or credit balance:** keep the same formulas with signed numbers (OD shown as negative), and label the result "Overdraft as per bank". Textbook BRS formats reverse add/less when starting from an overdraft. Using signed arithmetic avoids that branch [design].
- **Alternative presentation:** Tally-style four lines: A, "Amounts not reflected in Bank" (= B1 − C1), "Amounts not reflected in Company Books" (= B2 − C2), D, plus E and F.
- **Statement integrity checks before matching [design]:**
  1. Row check: `prev_balance + credit − debit == balance` for every row, with paise tolerance 0. Rows that break this usually mean bad parsing (merged or multiline narrations, or reversed Dr/Cr columns).
  2. `opening + Σcredit − Σdebit == closing`.
  3. The statement opening equals the previous reconciled statement's closing for that account. Gaps or overlaps are flagged.
  4. The statement covers the BRS end date.
- **Period closure:** after F = 0, lock the matched bank dates up to the end date. Later edits to vouchers dated ≤ end date with a bank date set should warn [design].
- **Book items for C2/B2:** once the user accepts "create voucher" suggestions (§2), they move out of B2/C2, and A changes. The BRS must be recomputed live.

### Gaps
- I could not fetch Tally's BRS report page in full. The four-line labels come from search snippets of Tally help.
- No Indian standard (ICAI AS/Ind AS) prescribes a BRS format. It is a working paper, so the layout is a convention, not a requirement.

---

## 4. Indian bank statement narration patterns (NEFT/RTGS/IMPS/UPI/CHQ) for extracting references and party names

### Takeaway
Narrations are rail-prefixed and delimited (`/`, `-` or `*`), but the field order **differs by bank**. Parse with per-bank templates first, then fall back to generic regexes:
- 22-character RTGS UTR;
- 16-character NEFT UTR;
- 12-digit IMPS/UPI RRN;
- 11-character IFSC;
- VPA `x@y`.

Then fuzzy-match the extracted name against the party master. No bank publishes an official narration specification; the patterns below come from real statements and vendor guides.

### Cited Findings
- **Reference length as a mode signal:** "16 means NEFT, 22 means RTGS, and 12 digits means IMPS or UPI". The RTGS UTR format is given as `XXXXRCYYYYMMDD########`: the first 4 characters are the sender bank's IFSC prefix and "R" denotes RTGS. — [Eximpe: UTR for NEFT/RTGS/IMPS/UPI](https://eximpe.com/blog/banking-payments/utr-number-neft-rtgs-imps-upi-payment-modes); [Eximpe: what is UTR](https://eximpe.com/blog/banking-payments/what-is-utr-number-in-banking) (snippets; blog sources, and attribution between these two pages not verified)
- **Caveats:** the UTR layout "can vary slightly depending on the bank". IMPS and UPI use an RRN or UPI transaction ID rather than a formal UTR. Sources disagree on whether UPI references are always 12 digits. — [SBNRI](https://sbnri.com/blog/nri-bank-accounts/utr-number-meaning-importance-tracking-and-how-to-use); [Xe](https://www.Xe.com/blog/money-transfer/what-is-a-unique-transaction-reference-utr-number/) (snippets)
- **SBI-style formats observed in real statements:**
  - `TO TRANSFER-UPI/DR/<ref>/<payee name>/<payee bank code>/…/<remark>` (debit)
  - `BY TRANSFER-UPI/CR/…` (credit)
  - `BY TRANSFER-UPI/REV/…` (reversal)
  - `BY TRANSFER-NEFT*<IFSC>*<ref>*<remitter>`
  - `CHQ TRANSFER-NEFT UTR NO: <UTR>-<name>`
  - Source: [Allahabad HC filing (statement)](https://dc.allahabadhighcourt.in/assets/documents/request/objection_document17271740633.pdf); [UP govt statement PDF](https://urise.up.gov.in/resources/profile_image/tu/1660286777_act_stmnt_all.pdf) (snippets; the bank is inferred from the format, and the statements contain personal data, so only patterns are recorded)
- **HDFC-style formats observed:**
  - `UPI-<payee name>-<VPA>-<IFSC>-<reference>-<remark>`
  - `NEFT CR-<IFSC>-<sender name>-…-<UTR>`
  - Source: [Scribd-hosted statement](https://www.scribd.com/document/794133891/full-statement-nitu-rani); [Allahabad HC filing](https://dc.allahabadhighcourt.in/assets/documents/request/request_document16202099025.pdf) (snippets)
- **Vendor guide examples** (these look illustrative or synthetic, not real bank templates):
  - `NEFT CR UTR … FROM <name> IFSC …`
  - `RTGS DR UTR … TO <name> PURPOSE …`
  - `IMPS P2A RRN <12 digits> FROM <name> …`
  - `UPI/<vpa>/<name>/<ref>/<txn id>/SUCCESS`
  - Party names usually follow FROM/TO tokens or sit in the UPI name slot. Masked mobile and account numbers mean matching should fall back to VPA, IFSC, amount and date. Party aliases should be kept in the vendor master. Ties go to a review queue. Run OCR substitution passes (O↔0, I↔1, B↔8) before the regexes.
  - Source: [AI Accountant](https://aiaccountant.com/blog/smart-narration-parsing-indian-statements)
- **Hybrid parsing approach:** regex for strict identifiers (UTR, RRN, IFSC, GSTIN, PAN), fuzzy or ML matching for entities, and validators for checksums. — [AI Accountant](https://aiaccountant.com/blog/smart-narration-parsing-indian-statements)

### Inferences
**Per-bank templates.** Rows marked [knowledge, not fetched] are from my experience of these banks' statements and must be validated against real sample files before shipping.

| Bank | Pattern (`<…>` = capture) | Status |
|---|---|---|
| SBI | `(TO\|BY) TRANSFER-UPI/(DR\|CR\|REV)/<rrn 12d>/<name>/<bank4>/<vpa>/<remark>` | seen (order partly verified) |
| SBI | `BY TRANSFER-NEFT*<ifsc>*<utr>*<name>`, `TO TRANSFER-NEFT*…`, `…RTGS*…`, `…IMPS/<rrn>/…` | NEFT seen; RTGS/IMPS [knowledge] |
| SBI | `TO CLEARING-…`/`CHQ PAID-…` (cheque paid), `BY CLEARING-…` (cheque deposit), `ATM WDL`, `CSH DEP`, `DEBIT- … INT.PD`, `CREDIT INTEREST` | [knowledge, not fetched] |
| HDFC | `UPI-<name>-<vpa>-<ifsc>-<rrn>-<remark>` | seen |
| HDFC | `NEFT CR-<ifsc>-<name>-<beneficiary>-<utr>`, `NEFT DR-<ifsc>-<name>-…-<utr>`, `RTGS CR-…`, `IMPS-<rrn>-<name>-<bank>-<masked a/c>-<remark>`, `CHQ PAID-MICR CTS-…-<name>`, `ACH D- <mandate org>-<ref>`, `POS <card> <merchant>` | NEFT CR seen; rest [knowledge] |
| ICICI | `UPI/<rrn>/<remark>/<vpa>/<bank>/…`, `MMT/IMPS/<rrn>/<remark>/<name>/<bank>`, `NEFT-<utr>-<name>-…`, `RTGS-<utr>-<name>-…`, `CLG/<name>/<chq>/…`, `INF/INFT/<ref>/<name>`, `BIL/ONL/…`, `ACH/<org>/<ref>` | [knowledge, not fetched] |
| Axis | `UPI/P2A/<rrn>/<name>/<bank>/<remark>`, `UPI/P2M/<rrn>/<merchant>/…`, `NEFT/<utr>/<name>/<bank>`, `IMPS/P2A/<rrn>/<name>/…`, `CLG/<chq>/<name>`, `ECS/ACH …` | [knowledge, not fetched] |

**Generic extraction order [design]:**
1. **Mode:** first token or prefix in {UPI, NEFT, RTGS, IMPS, MMT, CHQ, CLG, CTS, ACH, NACH, ECS, ATM/ATW/NWD, POS, INT, CHG, TRF/INFT/INF, CASH/CSH}.
2. **Identifiers:**
   - RTGS UTR `\b[A-Z]{4}R[A-Z0-9]{17}\b`, approximating `XXXXRCYYYYMMDD` + 8 digits;
   - NEFT UTR `\b[A-Z]{4}[A-Z0-9]{12}\b` (NEFT UTRs are commonly `XXXXN` + YY + day-of-year + sequence [knowledge, not fetched]);
   - RRN `(?<!\d)\d{12}(?!\d)`, accepted only when the mode is UPI/IMPS or the token "RRN" is present;
   - IFSC `\b[A-Z]{4}0[A-Z0-9]{6}\b`;
   - VPA `\b[\w.\-]{2,}@[a-z]{2,}\b`;
   - cheque number `\b\d{6}\b` near CHQ/CLG/CTS;
   - GSTIN and PAN as in gst_rules.md §5.
3. **Party name:** the token in the bank template's name slot. Otherwise text after FROM/TO/BY. Otherwise the longest alphabetic token run, after removing mode words, IFSC, VPA, numbers and noise words (TRANSFER, PAYMENT, SALARY, INV, BILL).
4. **Party resolution:** first look up learned mappings (VPA → party, IFSC + masked account → party). Then fuzzy-match (`rapidfuzz.token_set_ratio ≥ 85`) against party ledger names and aliases. A single best hit ≥ 85 with a runner-up < 75 is "resolved"; anything else is a "candidate list" [design].
5. **Store** `mode, utr, rrn, chq_no, ifsc, vpa, party_raw, party_id, confidence` on each bank line. These feed P1 (ref) and P2 (party) in §1.

**Upload parsing [design]:**
- Detect the header row by scanning the first ~30 rows for synonyms:
  - Date: "Txn Date", "Transaction Date", "Value Date", "Date";
  - Narration: "Description", "Narration", "Particulars", "Remarks";
  - Reference: "Chq./Ref.No.", "Ref No./Cheque No.", "Cheque No";
  - Debit: "Withdrawal Amt.", "Debit", "Withdrawals";
  - Credit: "Deposit Amt.", "Credit", "Deposits";
  - Balance: "Closing Balance", "Balance".
- Handle multi-line narrations (continuation rows with no date or amount: append them to the previous row).
- Handle a single amount column with Dr/Cr suffix, Indian digit grouping (1,23,456.78), and dd/mm/yy dates.
- Validate with the running-balance check in §3.

### Gaps
- No official narration specification exists for SBI, HDFC, ICICI, Axis or Kotak. The ICICI, Axis and most HDFC templates above are unverified.
- The NEFT UTR internal structure and the RRN composition (year digit + day-of-year + hour + sequence) were not confirmed from an RBI or NPCI source.
- No open-source, tested multi-bank Indian narration parser was found. A Hugging Face-hosted HDFC/ICICI/SBI PDF parser exists, but its narration logic was not reviewed. — [Hugging Face: finance-entity-extractor](https://huggingface.co/Ranjit0034/finance-entity-extractor/blob/main/src/finee/pdf_parser.py)

---

## 5. GSTR-1 tables and per-row data requirements (as of 2026)

### Takeaway
GSTR-1 has two kinds of table:
- **Invoice- or note-level tables:** 4 (B2B), 5 (B2CL), 6 (exports/SEZ/deemed), 9B (CDN).
- **Aggregated tables:** 7 (B2CS by POS × rate), 8 (nil/exempt/non-GST by 4 rows), 11 (advances by POS × rate), 12 (HSN by HSN × UQC × rate, **split into B2B and B2C tabs since 2025**), 13 (documents issued, by series; **mandatory from the May 2025 period**).

Invoice-level rows are **one row per tax rate within the invoice**. Invoice and note numbers are at most 16 characters, using only `-` and `/`. The B2CL threshold is **> ₹1,00,000 inter-state** from Aug 2024. Older Tally documentation still shows ₹2.5 lakh.

### Cited Findings
**Column layouts per the GSTR-1 Excel/offline-tool sheets** (from Tally's export documentation, ERP 9 release 6.6. The sheet names match the GSTN offline tool. Note the cdnr caveat below.) — [Tally Help: Exporting GSTR-1](https://help.tallysolutions.com/docs/te9rel66/Tax_India/gst/exporting_gstr-1.htm)
- **b2b** (tables 4A, 4B, 4C, 6B, 6C):
  - Columns: GSTIN/UIN of Recipient; Invoice Number; Invoice date; Invoice Value; Place Of Supply; Reverse Charge (Y/N); Applicable % of Tax Rate (normally blank); Invoice Type; E-Commerce GSTIN; Rate; Taxable Value; Cess Amount.
  - Invoice Type values: "Regular", "SEZ supplies with payment", "SEZ supplies without payment", "Deemed Exp".
  - Receiver Name is not mandatory.
- **b2cl** (5A/5B): Invoice Number; Invoice date; Invoice Value; Place Of Supply; Applicable % of Tax Rate; Rate; Taxable Value; Cess Amount; E-Commerce GSTIN.
- **b2cs** (7):
  - Columns: Type (E = through e-commerce operator, OE = others); Place Of Supply; Rate; Taxable Value; Cess Amount; E-Commerce GSTIN.
  - Values are **net** (credit and debit notes to B2C-small customers are netted here).
- **cdnr** (9B registered, as shown in Tally ERP 9 r6.6):
  - Columns: GSTIN/UIN; Invoice/Advance Receipt Number & date; Note/Refund Voucher Number & date; Document Type (C/D/R); Place Of Supply; Note Value; Applicable %; Rate; Taxable Value; Cess Amount; Pre GST (Y/N).
- **cdnur** (9B unregistered):
  - Columns: UR Type (B2CL / EXPWP / EXPWOP); note number/date; Document Type; original invoice number/date; Place Of Supply (97-Other Territory for exports); Note Value; Rate; Taxable Value; Cess; Pre GST.
- **exp** (6A):
  - Columns: Export Type (WPAY = with payment of IGST, WOPAY = under LUT/bond); Invoice Number; Invoice date; Invoice Value; Port Code (6 characters); Shipping Bill Number; Shipping Bill Date; Rate; Taxable Value; Cess Amount.
  - Rate is 0 for LUT.
- **at** (11A advances received) and **atadj** (11B advances adjusted): Place Of Supply; Rate; Gross Advance Received/Adjusted; Cess Amount.
- **exemp** (8):
  - 4 rows: Inter-State supplies to registered persons, Intra-State to registered, Inter-State to unregistered, Intra-State to unregistered.
  - Columns: Nil Rated Supplies; Exempted (other than nil rated/non-GST); Non-GST supplies.
- **hsn** (12):
  - Columns: HSN; Description; UQC; Total Quantity; Total Value; Taxable Value; Integrated Tax; Central Tax; State/UT Tax; Cess.
  - Aggregated by HSN/SAC and UQC. Tally uses UQC "OTH" for services.
- **docs** (13): Nature of Document; Sr. No. From; Sr. No. To; Total Number; Cancelled.
- **General rules:** invoice and voucher numbers may contain only "-" and "/" as special characters, with a maximum of 16 characters. The e-commerce operator GSTIN must differ from the buyer GSTIN. "Rate" is the full (integrated) rate.

**Thresholds and 2025 changes**
- **B2CL threshold:** reduced from ₹2.5 lakh to ₹1 lakh for inter-state B2C invoices from the Aug 2024 period (Notification 12/2024-CT). — [Tally Help: B2C Large 5A/5B](https://help.tallysolutions.com/tally-prime/gstr-1/b2c-large-invoices-5a-5b/)
  - A GSTN advisory at the time said to keep using ₹2.5 lakh until the portal was updated. — [TaxTMI](https://www.taxtmi.com/news?id=27853)
  - A later vendor changelog says the change was implemented on the portal. — [Octa GST changelog](https://octagst.com/octa/changelog/version-241105)
  - The Tally ERP 9 r6.6 export page still describes ₹2,50,000 (older documentation).
- **Table 12 Phase-III:**
  - Split into B2B and B2C tabs.
  - HSN is chosen from a dropdown; manual entry is not allowed, and the description auto-fills from the HSN master.
  - Values are cross-validated against other GSTR-1 tables, initially in warning mode.
  - The B2B tab cannot be empty if B2B supplies are reported elsewhere.
  - **Start period conflict:** sources give Jan, Feb, Apr or May 2025.
  - Source: [Taxmann: manual HSN entry not allowed](https://www.taxmann.com/post/blog/gstn-issued-new-advisory-on-table-12-of-gstr-1-or-gstr-1a-manual-entry-of-hsn-will-not-be-allowed/); [TaxGuru: Table 12 April 2025 advisory](https://taxguru.in/goods-and-service-tax/hsn-code-gstr-1-table-12-april-2025.html); [Taxmann: HSN dropdown & Table 13 mandatory from May 2025](https://www.taxmann.com/post/blog/hsn-dropdown-table-13-mandatory-in-gstr-1)
- **HSN digits:** 4 digits up to ₹5 crore AATO; 6 digits above ₹5 crore. — [Busy GSTR-1 guide](https://busy.in/gst/a-guide-to-gstr-1/); also gst_rules.md §3
- **Table 13:**
  - A GSTN advisory dated 1 May 2025 made it mandatory from the May 2025 return period.
  - It applies where data is reported in Tables 4, 5, 6, 7, 8, 9, 10, 14 or 15 (one secondary source).
  - Columns: Sr. No. From/To, Total Number, Cancelled, Net Issued.
  - Rows are document natures, including invoices for outward supply, delivery challan for job work and receipt voucher.
  - Source: [Taxmann](https://www.taxmann.com/post/blog/hsn-dropdown-table-13-mandatory-in-gstr-1); [Tally GSTR-1 guide](https://tallysolutions.com/gst/gstr1-filing-format-due-date/); [Webtel GSTR-1 form PDF](https://webtel.in/image/GSTR-1.pdf) (snippets)
- **GSTN clarification, 11 June 2025:** a B2C-only taxpayer must still put one entry in Table 12A (B2B tab), with zero values. — already recorded in gst_rules.md §3 ([ClearTax](https://cleartax.in/s/details-mentioned-return-gstr-1))

### Inferences
**Bucketing a sales/CN/DN voucher [design; extends gst_rules.md §3 inferences]**

| Voucher condition | GSTR-1 table | Row granularity | Required fields |
|---|---|---|---|
| Valid buyer GSTIN/UIN, not SEZ, not RCM | 4A | invoice × rate | GSTIN, inv no (≤16, `-`/`/` only), date, invoice value (incl. tax), POS (2-digit + name), RCM=N, invoice type=Regular, rate, taxable, IGST/CGST/SGST, cess |
| Same, but recipient pays under RCM | 4B | invoice × rate | as 4A, RCM=Y (taxable value shown; supplier collects no tax) |
| Through ECO collecting TCS (s.52) | 4A with ECO GSTIN, plus Table 14 by ECO | invoice × rate | as 4A + ECO GSTIN |
| Buyer is SEZ unit/developer | 6B (in b2b sheet) | invoice × rate | invoice type "SEZ with payment" (IGST) or "without payment" (LUT) |
| Deemed export | 6C (in b2b sheet) | invoice × rate | invoice type "Deemed Exp" |
| No GSTIN, POS ≠ own state, invoice value > ₹1,00,000 | 5 (B2CL) | invoice × rate | inv no, date, value, POS, rate, taxable, IGST, cess, ECO GSTIN |
| No GSTIN, other cases (intra-state any value; inter-state ≤ ₹1 lakh) | 7 (B2CS) | POS × rate × type(E/OE) × ECO | POS, rate, taxable (net of B2CS CN/DN), IGST or CGST+SGST, cess |
| Export of goods/services | 6A | invoice × rate | WPAY/WOPAY, inv no, date, value, port code (goods), shipping bill no/date (if available), rate, taxable, IGST, cess |
| Nil-rated / exempt / non-GST lines | 8 | 4 fixed rows × 3 columns | net value only (no tax) |
| CN/DN to registered buyer | 9B CDNR | note × rate | GSTIN, note no, note date, note type C/D, POS, RCM flag, note supply type, note value, rate, taxable, tax, cess |
| CN/DN to unregistered against B2CL or export invoice | 9B CDNUR | note × rate | UR type (B2CL/EXPWP/EXPWOP), note no/date, type, POS, value, rate, taxable, tax |
| CN/DN to unregistered against B2CS | net into Table 7 | | |
| Advance received, no invoice in same period (services; goods are exempt from GST on advances [knowledge, not fetched]) | 11A | POS × rate | gross advance (tax-inclusive treatment per portal), tax |
| Invoice issued this period against an earlier advance | 11B | POS × rate | advance adjusted, tax |
| All of 4–7, 9 lines by HSN | 12 (B2B tab for GSTIN buyers, B2C tab otherwise) | HSN × UQC × rate | HSN (4/6 digits by AATO), description (from master), UQC, qty, taxable, IGST, CGST, SGST, cess |
| Document series | 13 | nature × series | from, to, total, cancelled, net issued |

**Implementation notes [design]:**
- Compute **invoice value** as the voucher grand total (including tax and round-off). Taxable value and tax are computed per rate. Store both so B2CL threshold tests use invoice value, not taxable value.
- **Rate-wise split:** `groupby([invoice_id, rate])`. One invoice with 5% and 18% lines yields two rows sharing the same invoice number, date and value.
- **Table 12 vs other tables:** require `Σ Table12.taxable == Σ(4A+4B+5+6+7) taxable ± 9B net` per tab and per tax head. GSTN now cross-validates this, in warning mode at least.
- **Table 13:**
  - Derive from the voucher-numbering master, per series and per nature: outward invoices, debit notes, credit notes, receipt vouchers, refund vouchers, delivery challans and so on.
  - `total = to − from + 1` (when numbering is contiguous); `cancelled` = count of cancelled vouchers; `net = total − cancelled`.
  - Gaps in numbering should be flagged.
- **Cancelled invoices:** exclude them from 4–7 and 12, but count them in Table 13.
- **Amendments:** edits after filing go to 9A (B2B/B2CL/export invoices), 9C (CDN) and 10 (B2CS) in a later period, or to GSTR-1A for the same period before 3B is filed. The app must keep a "filed snapshot" per period to generate amendment rows by diffing [design].

### Gaps
- **cdnr/cdnur columns:** the Tally page is for ERP 9 r6.6 and shows the legacy layout with original invoice number and "Pre GST". The current GSTN offline tool is believed to use Note Number, Note Date, Note Type, Place of Supply, Reverse Charge, **Note Supply Type**, Note Value, Rate, Taxable Value and Cess, *without* original invoice reference [knowledge, not fetched]. Check against the current offline-tool template before building exports.
- The current HSN sheet is believed to include a **Rate** column (added around 2022) [knowledge, not fetched]. The Tally page does not show it.
- The exact Phase-III start period for the Table 12 split (Jan/Feb/Apr/May 2025) is unresolved.
- The full official list of Table 13 document natures was not fetched. My recollection of 12 natures (outward invoices, inward invoices from unregistered persons, revised invoices, debit notes, credit notes, receipt vouchers, payment vouchers, refund vouchers, and four delivery-challan types) is [knowledge, not fetched].
- I did not confirm the portal's current treatment of advances (tax-inclusive gross advance) or the UQC for services ("NA" vs "OTH").

---

## 6. GSTR-3B tables: computing each from the books, and auto-population and hard-locking status in 2025-26

### Takeaway
GSTR-3B is now largely **system-populated**:
- Table **3.1** (except 3.1(d) RCM inward) and **3.2** come from GSTR-1/IFF/GSTR-1A.
- Table **4(A)** comes from GSTR-2B as shaped by IMS actions.
- Table **4(B)(2)** receives credit notes and negative 4A values.

Lock status:
- Outward liability in 3.1 is **non-editable from the July 2025 period**.
- Table 3.2 locking was announced for Apr 2025, **deferred** (May 2025), then **re-announced from the Nov 2025 period** (Dec 2025 advisory).
- Table 4 ITC remains editable as far as I could verify. A full lock to 2B/IMS is reported as targeted for around July 2026 but **unconfirmed**.
- GSTN Advisory 643 (29 Dec 2025) announced hard validations on ITC reclaim and RCM ITC against the ECRRS and RCM statements, with no activation date given.
- GSTR-3B cannot be filed more than 3 years after its due date, from the July 2025 period.

The app should still compute every table from its books and **diff** against what the portal will auto-populate.

### Cited Findings
**Auto-population mapping** (ClearTax; third party):

| GSTR-3B | Source |
|---|---|
| 3.1(a) | GSTR-1 Tables 4A, 4B, 4C, 5A, 5B, 6C, 7A-1, 7B-1, 9A, 9B, 9C, 10A, 10B, 11 |
| 3.1(b) | GSTR-1 6A, 6B, 9A, 9B, 9C |
| 3.1(c) | GSTR-1 Table 8 |
| 3.2 | unregistered: 5A, 7B, 9A, 9B, 9C, 10B, 11; composition and UIN holders: 4A, 4C, 9A, 9B, 9C. By POS |
| 3.1(d) | GSTR-2B Table 3 Part A Section III and Table 4 Part A Section III |
| 4A | GSTR-2B Table 3 Part A Sections I–IV (positive values only) |
| 4B(2) | GSTR-2B Table 3 Part B Section I (credit notes) plus negative 4A amounts |

- Net negative values in GSTR-1 appear as zero.
- **3.1(d) excludes RCM on purchases from unregistered persons and on imports of services**, which the taxpayer must add manually.
- Source: [ClearTax: GSTR-3B auto-population](https://cleartax.in/s/gstr-3b-auto-population)
- The system-generated GSTR-3B PDF has drawn 3.1(a), (b), (c), (e) and 3.2 from GSTR-1 since the Oct 2020 period. — [West Bengal CT functionality note, Nov 2020](https://comtax.wb.gov.in/GST/Functionality_Taxpayer/functionality_return_20201112_2.pdf); [IRIS KB](https://irisgst.com/kb/gstr-3b-auto-compute/) (snippets)
- **Table 4 section mapping conflict:**
  - One source maps 4A(1) (import of goods) to GSTR-2B Table 3 Part A **Section IV**.
  - Another maps 4A(1), (3), (4), (5) to Sections I, II, III, IV respectively, which puts imports in Section I.
  - Negative 4A values are treated as reversal in 4B(2).
  - Source: [TaxGuru: Table 4 auto-population FAQs](https://taxguru.in/goods-and-service-tax/gstr-3b-table-4-itc-gstr-2b-auto-population-rectification-faqs.html) (snippet)
- Reversals under Rules 42/43 and "for any other reasons" are made by the taxpayer "on his own ascertainment" in Table 4(B). Net ITC in 4(C) is credited to the electronic credit ledger. — [CBIC Circular 170/02/2022-GST](https://www.gstcouncil.gov.in/sites/default/files/2024-06/cir-170-02-2022-cgst.pdf) (snippet)

**Locking timeline**
- **3.1 liability:** non-editable from the July 2025 period (GSTN advisory, 7 June 2025); corrections go through GSTR-1A before 3B is filed. — gst_rules.md §3 ([GSTN advisory copy](https://www.mahagst.gov.in/public/uploads/gstnadvisory/1760596521_352%20Advisory%20regarding%20non-editable%20of%20auto-populated%20liability%20in%20GSTR-3B.pdf)); restated in [ClearTax](https://cleartax.in/s/gstr-3b-auto-population)
- **Table 3.2:**
  - **11 Apr 2025:** "from April-2025 tax period, inter-state supplies auto-populated in Table 3.2 of GSTR-3B will be made non-editable". The values come from GSTR-1, GSTR-1A and IFF. Corrections go through GSTR-1A or later GSTR-1/IFF. — [TaxHeal (advisory text)](https://www.taxheal.com/advisory-on-reporting-values-in-table-3-2-of-gstr-3b.html)
  - **16 May 2025:** "Table 3.2 shall remain editable for the time being." — [Taxmann](https://www.taxmann.com/post/blog/gstr-3b-table-3-2-to-stay-editable-for-now-gstn) (snippet)
  - **5 Dec 2025:** non-editable from the **Nov 2025** period; "The GSTR-3B shall be filed henceforth with the system generated auto-populated values only in table 3.2." — [Taxmann: Table 3.2 non-editable from Nov 2025](https://www.taxmann.com/post/blog/gstn-makes-gstr-3b-table-3-2-auto-populated-and-non-editable) (snippet)
  - **Conflict:** a Taxscan report says GSTN shelved a Table 3.2 lock. That likely refers to the May 2025 deferral, but this is unclear. — [Taxscan](https://www.taxscan.in/?p=518540)
  - A July 2026 vendor blog says Tables 3.1 and 3.2 have been non-editable "since July 2025" (Advisory 606), which conflates the dates. — [Computax, 9 Jul 2026](https://www.computaxonline.com/blog/post/2026/07/09/gst-itc-auto-restriction-gstr-2b-gstr-3b-hard-locking)
- **Table 4 ITC** (Computax, July 2026, single source):
  - Auto-populated from GSTR-2B based on IMS actions since the **Oct 2025** period (cites "CBIC Notification 16/2025"), but still manually adjustable.
  - Removal of manual editing is "reported as targeted" for around July 2026, "not independently confirmed by us via an official advisory".
  - Table 3.1(d) is not auto-populated for all RCM and must be entered manually.
  - IMS records not actioned are deemed accepted.
  - Source: [Computax](https://www.computaxonline.com/blog/post/2026/07/09/gst-itc-auto-restriction-gstr-2b-gstr-3b-hard-locking)
- **GSTN Advisory No. 643 (29 Dec 2025):**
  - Announced **hard validation** for the **Electronic Credit Reversal and Re-claimed Statement** and the **RCM Liability/ITC Statement**, to be introduced "shortly". No activation date was given.
  - The reclaim statement started in Aug 2023 and the RCM statement in Aug 2024 (monthly filers).
  - 4B(2) holds temporary reversals, 4A(5) reclaimed ITC, and 4D(1) is disclosure only.
  - RCM liability is in 3.1(d) and paid in cash; RCM ITC is in 4A(2)/4A(3).
  - Source: [Busy: GSTR-3B hard block guide, July 2026](https://busy.in/business-updates/how-to-fix-gstr-3b-hard-block/)
- **Time-bar:** GSTR-3B filing is barred more than three years after the due date, from the July 2025 tax period. — [ClearTax](https://cleartax.in/s/gstr-3b-auto-population)
- **GSTR-1A** can be filed only once per period. — gst_rules.md §3

### Inferences
**GSTR-3B computed from books [design; table structure per gst_rules.md §3 and the mapping above].** All values are net of CN/DN for the period. The columns are Taxable value, IGST, CGST, SGST/UTGST and Cess.

| Table | Row | Computation from vouchers |
|---|---|---|
| 3.1(a) | Outward taxable (other than zero/nil/exempt) | Σ sales + DN − CN where rate > 0, not export/SEZ, not RCM-by-recipient; + 11A tax on advances − 11B adjustments. **Treatment of 4B (RCM) outward supplies:** ClearTax lists 4B among the sources of 3.1(a), but no tax is payable by the supplier. Include the value with zero tax [verify; see gaps] |
| 3.1(b) | Zero-rated | exports (6A) + SEZ (6B): value, plus IGST where WPAY / with payment |
| 3.1(c) | Nil-rated, exempt | Table 8 nil + exempt columns (value only) |
| 3.1(d) | Inward supplies liable to RCM | purchase vouchers flagged RCM (registered supplier 4B; unregistered s.9(4) notified cases; import of services). The tax is self-computed. **Not fully auto-populated: the app must supply it** |
| 3.1(e) | Non-GST outward | Table 8 non-GST column |
| 3.1.1 | ECO s.9(5) supplies | (i) as ECO paying tax; (ii) as supplier through ECO (value only) |
| 3.2 | Inter-state to unregistered / composition / UIN, by POS | subset of 3.1(a)/(b) where POS ≠ own state, grouped by POS × recipient type; taxable + IGST |
| 4(A)(1) | Import of goods | Bill-of-entry purchase vouchers (IGST + cess), matched to 2B ICEGATE section |
| 4(A)(2) | Import of services | RCM IGST paid on imported services (same period 3.1(d)) |
| 4(A)(3) | Inward RCM (other than imports) | eligible portion of 3.1(d) domestic RCM |
| 4(A)(4) | From ISD | ISD invoices received |
| 4(A)(5) | All other ITC | eligible forward-charge purchase tax **that is in 2B/IMS-accepted** (gst_rules.md §4) + reclaims of earlier 4(B)(2) |
| 4(B)(1) | Reversals: Rules 38, 42, 43, s.17(5) | blocked-credit lines (if included in 4A because 2B includes them) + Rule 42/43 computed reversal |
| 4(B)(2) | Other reversals | Rule 37 (180-day unpaid), CN received from suppliers, temporary reversals |
| 4(C) | Net ITC | 4(A) − 4(B) |
| 4(D)(1) | ITC reclaimed (disclosure) | reclaims included in 4A(5) |
| 4(D)(2) | Ineligible (s.16(4), POS) | time-barred ITC; out-of-state CGST/SGST |
| 5 | Exempt/nil/non-GST inward | purchases from composition dealers + exempt + nil (inter/intra), non-GST (inter/intra) |
| 5.1 | Interest & late fee | interest under s.50 on delayed cash payment; late fee by days |
| 6.1 | Payment of tax | per head: liability (3.1 + 3.1.1), paid via ITC per Rule 88A (gst_rules.md §3 algorithm), cash; **RCM row is cash only** |

**Using auto-population as a check [design]:**
- Import the portal's system-generated 3B JSON/PDF values, or compute them from the filed GSTR-1 snapshot and the downloaded 2B, into a `gstr3b_portal` table.
- Diff against `gstr3b_books` per cell.
- Because 3.1/3.2 are locked, any non-zero 3.1/3.2 diff means: fix via **GSTR-1A** (only once per period) before filing 3B, or carry to the next GSTR-1 as an amendment.
- Table 4 diffs should be explained by bucket (§7).

**Lock flags as configuration [design]:** make lock status data-driven (`lock_from_period` per table), because GSTN has changed these dates several times:
- 3.1: Jul-2025
- 3.2: Nov-2025 (per Dec 2025 advisory)
- 4: unconfirmed

### Gaps
- I could not fetch the official GSTN advisory PDFs for Table 3.2 (Dec 2025) or Advisory 643. The mahagst copy failed on a certificate error. Both dates rest on secondary sources.
- "CBIC Notification 16/2025" as the basis for IMS-based Table 4 auto-population is single-source and unverified.
- Whether a full Table 4 lock went live in or after July 2026 is unconfirmed.
- The ClearTax mapping includes 4B in 3.1(a) and 6B in 3.1(b). Whether 6B (SEZ with payment) appears in 3.1(b) or 3.1(a) on the current portal, and whether 4B values carry tax in the system-generated 3B, were not confirmed from GSTN.
- The 2B section numbering for 4A(1) is in conflict (Section I vs IV).

---

## 7. Practical pre-filing checks: GSTR-1 vs GSTR-3B liability, and GSTR-2B vs purchase register ITC matching

### Takeaway
Two reconciliations matter before filing.

**Books → GSTR-1 → GSTR-3B (outward).** This should tie exactly, since 3B 3.1/3.2 are now locked to GSTR-1/1A.

**Purchase register ↔ GSTR-2B (inward):**
- **Key:** supplier GSTIN + normalised invoice number + document type (+ FY).
- **Compare:** date, taxable value, tax per head and POS, within a per-invoice rupee tolerance.
- **Output buckets:** Exact / Suggested (probable) / Mismatch / Missing in 2B / Missing in PR.
- **ITC rule:** claim only 2B-backed ITC (s.16(2)(aa)).

Vendors do not publish their fuzzy thresholds. ClearTax uses exactly these five buckets, and one tool exposes a "₹ per invoice, on tax" tolerance (example ±₹10).

### Cited Findings
- **ClearTax 2B vs PR categories:**
  - Exact Match: "identical details across both sources".
  - Suggested Match: "minor mismatches".
  - Mismatch: "significant discrepancies" in taxable value, tax or invoice details, with field filters for taxable value, tax amount and POS.
  - Missing in PR (possibly "unrecorded purchases").
  - Missing in 2B ("supplier non-reporting or incorrect GSTIN entries").
- **ClearTax exact-match fields:** invoice date, invoice number, taxable amount, tax amount, document value, return period.
- **ClearTax actions:** Claim ITC ("Accept My Value" or "Accept Supplier Value", or a partial %), ITC Pending (claim in a future period), ITC Reversed, ITC Ineligible.
- ClearTax publishes no numeric tolerance or normalisation rule.
- Source: [ClearTax docs: GSTR-2B vs Purchase Register](https://docs.cleartax.in/product-help-and-support/for-small-businesses/gst-compliance/gstr-3b/gstr-2b-vs-purchase-register-reconciliation-a-step-by-step-guide)
- **Other tools:**
  - Tools match on supplier GSTIN + invoice number with a user-set tax tolerance ("Match tolerance (₹ per invoice, on tax)"; example ±₹10).
  - Another approach keys on GSTIN + Invoice Number + Invoice Date.
  - Typos like "INV/001" vs "INV-001" and small rounding differences break naive matching.
  - Some tools add a GSTIN-level netting bucket.
  - Source: [Excel ITC reconciliation tool](https://excel-utilities1.odoo.com/itc-reconciliation-tool-2-0); [ICAI AI prompt library](https://ai.icai.org/prompt_details.php?id=60); [ICAI AI use case](https://ai.icai.org/usecases_details.php?id=183); [Kestra blueprint](https://kestra.io/blueprints/gstr2b-purchase-itc-reconciliation) (snippets; attribution within the search results approximate)
- GSTR-2B does not update retrospectively, so a supplier's late filing defers ITC visibility to a later period. Timing differences are a main cause of mismatches. — [Tally: GSTR-2B reconciliation mismatches](https://tallysolutions.com/gst/gstr-2b-reconciliation-mismatches-how-to-fix/) (snippet)
- Table 12 Phase-III validations cross-check HSN B2B/B2C values against other GSTR-1 tables (warning mode initially). — [TaxGuru](https://taxguru.in/goods-and-service-tax/hsn-code-gstr-1-table-12-april-2025.html) (snippet)
- Before filing, reconcile Table 12 with outward-supply records and make sure every document series is in Table 13. — [Tally GSTR-1 guide](https://tallysolutions.com/gst/gstr1-filing-format-due-date/) (snippet)

### Inferences
**A. Outward pre-filing checklist [design].** Errors block filing; warnings show for review.

| # | Check | Formula | Tolerance | Severity |
|---|---|---|---|---|
| O1 | Books vs GSTR-1 totals | Σ sales/CN/DN vouchers in period (taxable, each tax head) == Σ GSTR-1 tables 4+5+6+7+8+9B+11 (net) | ₹0 at paise level; ≤ ₹1 per head after rounding | Error |
| O2 | GSTR-1 vs computed 3B | 3.1(a)…(e), 3.1.1, 3.2 recomputed from the GSTR-1 dataset == books-based 3B | ₹0 | Error (fix via GSTR-1A before 3B) |
| O3 | Filed GSTR-1 snapshot vs current books | diff of vouchers edited/added/deleted after GSTR-1 filing | any | Warn → route to GSTR-1A (once) or next-period 9A/9C/10 |
| O4 | HSN (12) vs tables | Σ Table 12 B2B tab == B2B tables; B2C tab == B2C tables, per tax head | ≤ ₹1 | Warn (portal warning mode) |
| O5 | Table 13 vs register | count of invoices/CN/DN per series == Table 13 total − cancelled; no numbering gaps | exact | Warn |
| O6 | 3.2 subset | Σ 3.2 ≤ 3.1(a)+3.1(b) inter-state unregistered/composition/UIN portion; POS ≠ own state | exact | Error |
| O7 | B2CL threshold | inter-state, no GSTIN, invoice value > ₹1,00,000 → must be in Table 5, not 7 | exact | Error |
| O8 | E-invoice IRN | if AATO > e-invoice threshold, every B2B/export invoice has an IRN; amounts == IRP values | ₹0 | Error [threshold not re-verified this session] |
| O9 | Period and time-bar | no 3B being prepared for a period more than 3 years past its due date | | Error |

**B. GSTR-2B ↔ purchase register matching algorithm [design]**

*Normalisation:*
- `gstin`: uppercase, trim, checksum-validated (gst_rules.md §5).
- `doc_type`: INV / CN / DN.
- `inv_norm`, applied in order:
  1. uppercase;
  2. remove spaces and all characters except A–Z and 0–9;
  3. remove FY tokens matching `(20)?\d{2}[-/]?(20)?\d{2}` when they look like a FY such as 2025-26, 25-26, 2526 or 202526;
  4. remove common prefixes INV, INVOICE, TI, TAX, BILL, GST when followed by digits;
  5. strip leading zeros from the remaining numeric runs.
- Keep `inv_digits` = concatenated digit runs as a secondary key.
- Amounts in paise. Dates as dates.
- FY derived from the invoice date (an invoice number is unique per FY per supplier).

*Passes* (each pass sees only items still unmatched):
1. **Exact key:** (gstin, doc_type, FY, inv_norm) equal. Then compare fields:
   - date equal;
   - |taxable diff| ≤ tol_v;
   - |tax diff per head| ≤ tol_t;
   - same tax type (IGST vs CGST/SGST, i.e. POS consistency).
   - All OK → **Exact**. Any field off → **Mismatch**, recording which fields (date / taxable / tax / POS / tax type).
2. **Probable key:** (gstin, doc_type, FY) equal and either `inv_digits` equal or Levenshtein similarity of `inv_norm` ≥ 0.85, *and* |total tax diff| ≤ tol_t, *and* |date diff| ≤ 7 days → **Suggested** (user confirms).
3. **Amount key:** (gstin, doc_type) equal, invoice number different, taxable and tax equal within tolerance, date within ±3 days, unique candidate → **Suggested (number mismatch)**.
4. **PAN-level:** `gstin[2:12]` equal (same PAN, different state GSTIN) with an exact inv_norm and amount → **Suggested (wrong GSTIN/branch)**. ITC is available only if the 2B GSTIN is correct, so prompt a vendor correction.
5. **Cross-period:** search unmatched PR items against 2B of the next 1–2 periods, and unmatched 2B items against PR of the previous periods → label **Timing** (claim in the later period).
6. **Leftovers:**
   - **Missing in 2B:** ITC pending; do not claim; chase the supplier.
   - **Missing in PR:** book the purchase, or reject/keep pending in IMS.

*Tolerances [design]:*
- `tol_t = ₹1` per tax head per invoice by default. This is configurable up to ₹10, as in the Excel tool example.
- `tol_v = max(₹1, 0.01% of taxable)`.

*Many-to-one:* occasionally a supplier reports one invoice that the books split, or the reverse. Allow a GSTIN-level subset-sum suggestion within the period (k ≤ 4) [design].

*IMS action suggestions [design]:*
- Exact or Suggested-accepted → **Accept**.
- Missing in PR, or a wrong amount where the supplier is at fault → **Pending** (or **Reject** if not received or not ours).
- A record pending beyond the s.16(4) cut-off → warn.

*ITC claim ceiling check:*
- `4(A)(5) claimed ≤ Σ eligible tax of (Exact + confirmed Suggested + accepted-with-supplier-value)`;
- `4(A)(2)+(3) ≤ RCM tax paid in 3.1(d)`, the RCM statement logic now being hard-validated under Advisory 643;
- `4(A)(5) reclaim component ≤ ECRRS balance`.

**Output report layout for 2B reco [design]:**

| GSTIN | Supplier | Doc type | Inv no (PR) | Inv no (2B) | Date PR | Date 2B | Taxable PR | Taxable 2B | IGST PR/2B | CGST PR/2B | SGST PR/2B | Cess PR/2B | Diff (tax) | Status | Mismatch fields | Suggested action | IMS action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

Add summary rows by status and by supplier: count, taxable, tax, and ITC at risk.

### Gaps
- No official GSTN or CBIC tolerance exists for 2B-vs-books matching. All tolerances above are design choices; ClearTax's thresholds are unpublished.
- The current e-invoicing AATO threshold (₹5 crore since Aug 2023) and the 30-day IRN reporting window for larger taxpayers were not re-verified in 2026 [knowledge, not fetched].
- I did not confirm whether IMS action is mandatory (vs deemed acceptance) for all filers from April 2026. That remains single-source (see gst_rules.md §4).
- Activation of Advisory 643's hard validations (ECRRS/RCM statement) is not confirmed. Implement the ceiling checks as warnings until confirmed.
