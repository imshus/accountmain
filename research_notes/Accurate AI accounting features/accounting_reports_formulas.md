# Core Accounting Reports in Indian SME Software (Tally Prime, Zoho Books, Busy, Vyapar): Definitions, Formulas, Dr/Cr Conventions and Checks

Scope note: research done 22 Oct 2026. Primary sources are Tally help pages (help.tallysolutions.com), Zoho Books help, the Busy and Vyapar sites, KPMG India, ICAI-hosted material and NIOS/NCERT-level textbooks. Many Tally help pages describe *how to open* a report but not its arithmetic. Where the arithmetic is standard double-entry practice and was not stated in a fetched source, it is listed under **Inferences**, not Cited Findings. GST is mentioned only where it changes these reports.

---

## 1. Ledger / account statement: layout, opening/closing balance, running balance and Dr/Cr suffix

### Takeaway
A ledger statement is the date-ordered list of every voucher line that hits one ledger: Date, Particulars (the contra ledger), Voucher Type, Voucher No., Debit, Credit, plus an optional running balance. The balance is a single signed number, Opening + ΣDr − ΣCr, displayed as an absolute value with a "Dr" or "Cr" suffix. The arithmetic does **not** flip by account nature. Nature only decides which suffix is "normal": Dr for assets and expenses, Cr for liabilities, capital and income.

### Cited Findings
- In TallyPrime the ledger statement is the "Ledger Vouchers" report: Gateway of Tally > Display > Account Books > Ledger (or Alt+G > Ledger Vouchers). F12 Configure > "Show Running Balance" = Yes adds a running-balance column. The help page says the running balance updates after every entry recorded or altered. — [Tally Help: Ledger Vouchers](https://help.tallysolutions.com/docs/te9rel66/Reports/Display_Registers_Ledgers/Display_Ledger_Vouchers.htm); [Tally Help: ledger-vouchers](https://help.tallysolutions.com/ledger-vouchers/)
- Ledger Vouchers options: F8 = columnar view, with voucher details in separate columns. Ctrl+B (Basis of Values) limits the report to debit-only, credit-only or all vouchers. F5 (Bill-wise) shows pending bills for a party ledger. For purchase, payment, journal, debit-note and credit-note vouchers the supplier reference no. and date can also be shown. — [Tally Help: Ledger Vouchers (multiple releases)](https://help.tallysolutions.com/article/te9rel65/Reports/Display_Registers_Ledgers/Display_Ledger_Vouchers.htm)
- Modern (accounting-equation) rules of debit and credit: assets and expenses increase with debits; liabilities, equity/capital and revenue/income increase with credits. Expenses carry a debit normal balance because they reduce owner's equity. — [Wikipedia: Debits and credits](https://en.wikipedia.org/wiki/Debits_and_credits); [UNG: Normal Balances of Accounts](https://faculty.ung.edu/aduke/Chapter%202/NormalBalancesofAccounts.htm)
- Indian textbooks teach two equivalent methods: the modern accounting-equation approach (five rules) and the classical approach, the three "golden rules" by Personal/Real/Nominal account type. — [Unacademy: Rules of Debit and Credit](https://unacademy.com/content/rules-of-debit-and-credit/)
- Manual balancing of a T-ledger: total both sides, put the larger total on both sides, and carry the balancing figure down as "Balance c/d" (c/f) and up as "Balance b/d" (b/f) for the next period. — [Brainscape ledger accounting flashcards (textbook-level)](https://brainscape.com/flashcards/ledger-accounting-10870726/packs/19343405)
- Opening balances are entered on ledger masters from the previous period's balance sheet. If the Dr and Cr opening balances do not match, Tally shows a "Difference in Opening Balances" line, meaning a missing or incorrect opening balance. — [Teachoo: Difference in Opening Balances in Tally](https://www.teachoo.com/758/232/Difference-in-Opening-Balances-in-Tally/category/Common-Errors-in-Tally)
- The predefined "Profit & Loss A/c" ledger in Tally carries the previous year's profit or loss forward as its opening balance, shown on the liabilities side of the Balance Sheet. — [Tally Help: Ledgers and Groups in TallyPrime](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)
- Tally's group master has a "Nett Debit/Credit Balances for Reporting" option. It shows the net of a group's debit and credit balances in reports instead of separate gross Dr and Cr totals. — [Tally Help: Groups in TallyPrime](https://help.tallysolutions.com/tally-prime/accounting/groups-in-tallyprime/)
- Indian digit grouping is 3:2:2. The first comma comes after three digits from the right, then one after every two digits: 1,00,000 = one lakh; 1,00,00,000 = one crore; 10 lakh = 1 million; 1 crore = 10 million. — [BrightChamps: Indian numeral system](https://brightchamps.com/math/numbers/indian-numeral-system)

### Inferences
These are standard double-entry practice and observed Tally behaviour, not stated verbatim in the sources above. They should be validated against a real Tally export.
- **Signed-balance convention for the engine.** Store every line as `signed = debit − credit`. Then `running_balance = opening_signed + cumsum(signed)` over lines sorted by (date, voucher sequence). Display `abs(x)` with suffix `"Dr"` if `x > 0`, `"Cr"` if `x < 0`, and nothing (or "Nil") if 0. The same formula works for every account type. **Do not** use "credit − debit" for liability/income accounts: Tally and Indian accountants read the Dr/Cr suffix, not a sign.
- **What counts as "abnormal".** A Cr balance on an asset or expense ledger, or a Dr balance on a liability, capital or income ledger, is legal but worth flagging:
  - Cr balance in Cash-in-Hand is impossible in reality. Tally shows it in red.
  - Dr balance in a Sundry Creditor means an advance has been paid to the supplier.
  - Cr balance in a Sundry Debtor means an advance has been received from the customer.
- **Opening balance for an arbitrary period** [from, to] inside a financial year:
  - Balance-sheet ledgers: opening(from) = FY-start opening + Σsigned for dates in [FY start, from − 1].
  - P&L ledgers (Sales, Purchase, Direct/Indirect Income/Expense): FY-start opening is 0, because these are closed into the P&L A/c at year end. Their opening at `from` is just Σsigned since 1 April.
  - Closing(to) = opening(from) + Σsigned in [from, to].
- **Typical bottom rows on Tally's Ledger Vouchers screen.** From practitioner familiarity, not a fetched source: "Opening Balance", "Current Total" (ΣDr and ΣCr for the period) and "Closing Balance". The closing balance is placed in the column of its nature. Check: Opening + Current Total Dr − Current Total Cr = Closing (signed). Verify against a real export.
- **"Particulars" column.** It shows the *other* ledger in the voucher. When the voucher has more than one contra ledger, Tally typically shows the first or principal one, or "(as per details)". In T-ledger textbook style, debit-side lines are prefixed "To <ledger>" and credit-side lines "By <ledger>".
- **Sort order.** Sort within a date by voucher type order or voucher number, so that the running balance is deterministic and matches Tally's order (Tally shows entries in entry order within a date).
- **Financial year.** The Indian FY runs 1 April to 31 March. This is the Companies Act 2013 definition and the Income-tax "previous year"; the statute text was not fetched in this session. FY labels are written "FY 2025-26". Use a helper like `fy_start = date(y if m >= 4 else y-1, 4, 1)`.
- **Lakh/crore formatting.** Format the integer part as last 3 digits, then groups of 2, with 2 decimals and the ₹ symbol, e.g. ₹1,23,45,678.90. Negative or credit balances are better shown with a "Cr" suffix than a minus sign.

### Gaps
- No fetched Tally source states the exact column order or the labels of the footer rows in the Ledger Vouchers report, or how "Particulars" reads for multi-ledger vouchers. These need checking against a live TallyPrime screen or Excel export.
- Busy and Vyapar ledger-statement layouts were not fetched.

---

## 2. Day Book, Cash Book and Bank Book

### Takeaway
- **Day Book:** every voucher of every type for a date or period, in chronological order. It has no single running balance, but each voucher must balance.
- **Cash Book / Bank Book:** the ledger statement of Cash-in-Hand and Bank ledgers. Receipts are Dr, payments are Cr. Closing = Opening + Receipts − Payments, shown monthly and daily.

### Cited Findings
- TallyPrime's Day Book is modelled on the manual daybook. It lists the day's (or period's) vouchers and allows cancelling, deleting or inserting vouchers and checking sales profitability from the report. — [Tally Help: Day Book](https://help.tallysolutions.com/?p=101490)
- Tally's Cash/Bank Book records cash or bank receipts on the debit side and payments on the credit side. — [Tally Help: Cash/Bank Book](https://help.tallysolutions.com/tally/cash-bank-book-tally/)
- The Cash/Bank Book drills down as Cash/Bank Summary > ledger > Ledger Monthly Summary, which shows Debit and Credit totals per month and a Closing Balance. Ctrl+F6 gives a Daily Breakup, and F12 "Show Highest Balance & Lowest Balance" shows the month's extremes. A negative cash balance appears as a credit closing balance in red. — [Tally Help: Cash/Bank Book](https://help.tallysolutions.com/tally/cash-bank-book-tally/)
- Path: Alt+G > "Cash/Bank Book", or Gateway of Tally > Display More Reports > Account Books > Cash/Bank Book(s). Highlighting a month in the summary and pressing Enter opens that month's Ledger Vouchers. — [Tally Help](https://help.tallysolutions.com/?p=101488); [Tally Help: Display Cash Book](https://help.tallysolutions.com/article/te9rel51/Reports/Display_Registers_Ledgers/Display_Cash_Book.htm)
- Ledgers under the **Bank OD A/c** group ("Bank OCC A/c") are overdraft or cash-credit accounts. They sit under Loans (Liability), not Current Assets, and are printed as a separate Cash Book. — [Tally Help: Default Groups](https://help.tallysolutions.com/docs/te9rel53/Creating_Masters/Accounts_Info/Default_Groups.htm)
- Tally creates a "Cash" ledger automatically under Cash-in-Hand. — [Tally Help: Default Groups](https://help.tallysolutions.com/docs/te9rel53/Creating_Masters/Accounts_Info/Default_Groups.htm); [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)

### Inferences
- **Day Book build.** Take all voucher lines in [from, to], grouped by voucher (date, type, number). Show per voucher: date, first or principal ledger as Particulars, voucher type, number, and Dr and Cr totals. Checks:
  - per voucher, ΣDr = ΣCr;
  - for the whole Day Book, ΣDr = ΣCr.
- **Cash Book.** Filter lines whose ledger's group resolves to Cash-in-Hand. Monthly summary per month m: Dr_m = Σdebit, Cr_m = Σcredit, Closing_m = Closing_{m−1} + Dr_m − Cr_m, with Closing_0 = opening on 1 April. Flag any day where cash closing < 0. It is physically impossible and usually means a missing receipt or a mis-dated entry.
- **Bank Book.** Same build per Bank Accounts ledger. Bank OD/CC ledgers follow the same arithmetic, but their normal balance is Cr (the amount owed to the bank). Show them separately. A Bank Accounts ledger with a Cr balance is effectively an overdraft.
- **Two-column / three-column textbook cash book** (Cash, Bank, Discount). Contra entries appear on both sides and are marked "C". Cash Book closing must equal the Cash ledger closing in the trial balance.
- **Imported data.** In bank statements, a withdrawal is a *debit* and a deposit is a *credit* from the bank's point of view. In the company's Bank Book a deposit is Dr and a withdrawal is Cr. The importer must flip signs when converting a bank statement into Bank Book entries (see Section 8).

### Gaps
- No fetched source gives Busy or Vyapar Day Book or Cash Book layouts.
- Tally's exact Day Book columns and the treatment of optional or memorandum vouchers in it were not confirmed.

---

## 3. Journal entries / vouchers: Tally voucher types and the double-entry rule

### Takeaway
Tally's predefined accounting vouchers are Contra, Payment, Receipt, Journal, Sales, Purchase, Credit Note and Debit Note. Each voucher must satisfy ΣDr = ΣCr. Memorandum vouchers do not post to ledgers. Reversing journals affect only reports up to their applicability date. Optional vouchers are excluded unless included.

### Cited Findings
- Predefined voucher types include Contra, Payment, Receipt, Journal, Sales/Invoice, Debit Note, Credit Note and Purchase/Invoice. User-defined voucher types can also be created. — [Tally Help: Predefined Vouchers](https://help.tallysolutions.com/article/te9rel64/Voucher_Entry/Accounting_Vouchers/Predefined_Vouchers_in_TallyERP.htm); [TallySolutions: Vouchers in TallyPrime](https://tallysolutions.com/tally/accounting-vouchers-in-tally-prime/)
- Voucher purposes per Tally:
  - **Contra:** cash withdrawal from or deposit into a bank.
  - **Payment:** paying parties, with instrument details and cheque printing.
  - **Receipt:** customer payments against pending invoices, with mode cash, cheque or NEFT/RTGS.
  - **Journal:** adjustments and other multi-purpose entries.
  - **Sales:** invoice mode for inventory, accounting-invoice mode for services, or voucher (Dr/Cr) mode.
  - **Purchase:** voucher or invoice mode.
  - **Credit Note:** sales returns, linked to the original invoice.
  - **Debit Note:** purchase returns, as a voucher or as an invoice affecting inventory.
  — [TallySolutions: Vouchers in TallyPrime](https://tallysolutions.com/tally/accounting-vouchers-in-tally-prime/)
- Shortcut keys: Contra F4, Payment F5, Receipt F6, Journal F7, Sales F8, Purchase F9, Credit Note Ctrl+F8, Debit Note Ctrl+F9. — [BAOU course material BBASEC405](https://baou.edu.in/assets/pdf/BBASEC405.pdf) (secondary, academic)
- Memorandum vouchers "will not affect your accounts". Tally does not post them to ledgers; they are kept in a separate Memorandum Register and can later be converted to regular vouchers. They are enabled through F11 "Use Reversing Journals & Optional Vouchers" and the register is under Display > Exception Reports. — [Tally Help: Memorandum Voucher](https://help.tallysolutions.com/docs/te9rel65/Voucher_Entry/Optional_Non-Accounting_Vouchers/Memorandum_Voucher.htm)
- Reversing journals are reversed automatically after a specified date and take effect only when included in reports. — [Scribd course chapter (secondary, low authority)](https://www.scribd.com/document/668439774/Chapter-4)
- Order and inventory vouchers (Purchase/Sales Order, Delivery Note, Receipt Note, Material In/Out, Physical Stock) track inventory and order flow. Delivery and Receipt Notes are inventory movements. — [TallySolutions: Vouchers in TallyPrime](https://tallysolutions.com/tally/accounting-vouchers-in-tally-prime/)

### Inferences
These are standard Indian practice, not quoted from a fetched source.

**Typical ledger effects**

| Voucher | Dr | Cr | Constraint to validate |
|---|---|---|---|
| Contra | Bank (deposit) / Cash (withdrawal) / Bank B (transfer) | Cash / Bank / Bank A | Every line's ledger ∈ {Cash-in-Hand, Bank Accounts, Bank OD A/c} |
| Payment | Party / expense / asset | Cash or Bank | ≥1 Cr line is cash/bank |
| Receipt | Cash or Bank | Party / income | ≥1 Dr line is cash/bank |
| Journal | Any non-cash | Any non-cash | Conventionally no cash/bank line (Tally allows it; flag) |
| Sales | Debtor or Cash/Bank | Sales A/c + Output CGST/SGST/IGST (Duties & Taxes) | Taxable value to Sales, GST to Duties & Taxes |
| Purchase | Purchase A/c + Input CGST/SGST/IGST | Creditor or Cash/Bank | as above |
| Credit Note (sales return/discount) | Sales (or Sales Returns under Sales Accounts) + Output GST | Debtor | Reduces sales and receivable |
| Debit Note (purchase return) | Creditor | Purchase (or Purchase Returns) + Input GST | Reduces purchases and payable |

**Validation rules for the engine**
- For every voucher id, `abs(ΣDr − ΣCr) < 0.005`. A ±1-paisa round-off is often booked to a "Round Off" ledger, usually under Indirect Expenses or Indirect Incomes.
- Voucher type ↔ ledger group consistency, as in the table above.
- No posting to a ledger outside the FY being reported.
- Exclude memorandum, optional and cancelled vouchers. Tally Day Book exports show cancelled vouchers with zero amounts.

**Reconstructing vouchers from flat registers.** A sales register row with Party, Taxable Value, CGST, SGST, IGST and Invoice Total expands to:
- Dr Party = Invoice Total;
- Cr Sales = Taxable;
- Cr Output CGST / SGST / IGST = tax amounts;
- Cr or Dr Round Off = difference.

The check is Invoice Total = Taxable + taxes ± round-off.

### Gaps
- The official Tally page listing predefined vouchers timed out or truncated. Exact restrictions (e.g., whether Journal vouchers can use cash/bank) were not confirmed from Tally.
- Busy and Vyapar voucher taxonomies were not researched. Vyapar uses transaction types such as Sale, Purchase, Payment-In, Payment-Out, Expense and Sale Return, which will need mapping (not verified).

---

## 4. Trial Balance: construction, Tally grouping, Dr total = Cr total

### Takeaway
The trial balance lists the closing balance of every ledger, rolled up into Tally's 28 predefined groups (15 primary and 13 sub-groups), in Debit and Credit columns. Total Dr must equal total Cr. Closing stock is excluded by design. An opening-balance mismatch shows as "Difference in opening balances".

### Cited Findings
- TallyPrime has 28 predefined groups: 15 primary and 13 sub-groups. Nine primary groups are Balance Sheet (capital) items and six are P&L (revenue) items. Predefined groups cannot be deleted. — [Tally Help: Groups](https://help.tallysolutions.com/tally-prime/accounting/groups-in-tallyprime/); [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/); [Tally Help: Default Groups](https://help.tallysolutions.com/docs/te9rel53/Creating_Masters/Accounts_Info/Default_Groups.htm)
- **Balance-sheet primary groups (9):** Capital Account, Loans (Liability), Current Liabilities, Fixed Assets, Investments, Current Assets, Branch/Divisions, Misc. Expenses (ASSET), Suspense A/c. — [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)
- **P&L primary groups (6):** Sales Accounts, Purchase Accounts, Direct Incomes, Direct Expenses, Indirect Incomes, Indirect Expenses. — [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)
- **Sub-groups (13) and parents:** — [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/); [Tally Help: Default Groups](https://help.tallysolutions.com/docs/te9rel53/Creating_Masters/Accounts_Info/Default_Groups.htm)
  - under Capital Account: Reserves & Surplus;
  - under Loans (Liability): Bank OD A/c, Secured Loans, Unsecured Loans;
  - under Current Assets: Bank Accounts, Cash-in-Hand, Deposits (Asset), Loans & Advances (Asset), Stock-in-Hand, Sundry Debtors;
  - under Current Liabilities: Duties & Taxes, Provisions, Sundry Creditors.
- A group created under Primary needs a "Nature of Group". Assets or Liabilities put it in the Balance Sheet; Income or Expenses put it in P&L. "Does it affect Gross Profits" = Yes makes it a direct (trading) item. — [Tally Help: Groups](https://help.tallysolutions.com/tally-prime/accounting/groups-in-tallyprime/)
- **Group contents per Tally:** — [Tally Help: Default Groups](https://help.tallysolutions.com/docs/te9rel53/Creating_Masters/Accounts_Info/Default_Groups.htm)
  - Capital Account: share, partners' or proprietor's capital.
  - Reserves & Surplus: general or capital reserve.
  - Deposits (Asset): FDs, security deposits.
  - Loans & Advances (Asset): loans given, salary advances. Supplier advances should not go here.
  - Stock-in-Hand: raw materials, WIP, finished goods.
  - Duties & Taxes: tax liabilities or advances.
  - Provisions: provision for tax or depreciation.
  - Investments: shares, bonds, long-term deposits.
  - Secured Loans: debentures, term loans.
  - Unsecured Loans: loans from directors, partners or others.
  - Suspense A/c: amounts of unknown nature, e.g., a travel advance awaiting the bill.
  - Misc. Expenses (ASSET): preliminary or pre-operative expenses written off gradually.
  - Branch/Divisions: own branches, subsidiaries and related concerns.
  - Sales Accounts: domestic, export or tax-slab sales. Sales returns may sit here.
  - Direct Incomes: e.g., servicing charges. Affects gross profit.
  - Direct Expenses: manufacturing or direct trading costs. Affects gross profit.
  - Indirect Incomes: e.g., rent or interest received. Does not affect gross profit.
  - Indirect Expenses: e.g., rates and taxes, administration and selling expenses.
- The Tally Trial Balance is "a summary of all the ledger balances". It is group-wise by default, and F5 switches to ledger-wise. F12 options:
  - "Show Opening Balance": opening and closing side by side.
  - "Show Transactions": Dr and Cr movements.
  - "Nett Transactions": offsets Dr against Cr.
  If total Dr equals total Cr, the books are balanced. — [Tally Help: Trial Balance](https://help.tallysolutions.com/tally-prime/accounting-financial-reports/trial-balance-tally/)
- "As per accounting principles, the Trial Balance does not display the closing stock." Including it would double the effect. — [Tally Help: Trial Balance](https://help.tallysolutions.com/tally-prime/accounting-financial-reports/trial-balance-tally/)
- When opening Dr ≠ opening Cr, a "Difference in opening balances" line appears. Listed causes: manual entry errors, data carried from a previous company, removed opening balances, split data, and imports or syncs overwriting balances. Fix by checking each ledger's opening against last year's balance sheet, or by offsetting against another ledger's opening. — [Tally Help: Trial Balance](https://help.tallysolutions.com/trial-balance-tally/)
- Textbook checks when the TB does not agree:
  - a difference of ₹1, 10, 100 or 1000 suggests a casting (totalling) error in subsidiary books;
  - a difference divisible by 2: look for an amount of half the difference posted to the wrong side;
  - a difference divisible by 9 suggests transposed digits.
  An untraced difference is parked in a Suspense account until rectified. Errors of principle and compensating errors do not disturb TB totals. — [Vedantu: NCERT Class 11 Ch. 6](https://www.vedantu.com/ncert-solutions/ncert-solutions-class-11-accountancy-chapter-6); [NIOS Accountancy Ch. 11](https://digital.nios.ac.in/content/224en/ch_11.pdf)

### Inferences
**Algorithm**
1. Closing signed balance per ledger = opening_signed + Σ(debit − credit) up to the as-of date.
2. TB row: Dr column = max(bal, 0), Cr column = max(−bal, 0).
3. Group roll-up: sum the *signed* balances of child ledgers, then split into Dr or Cr. This is Tally's net presentation. Gross presentation (separate Dr and Cr totals inside a group) is optional.
4. Check: Σ Dr column = Σ Cr column, i.e., Σ signed = 0. With unbalanced opening balances, show the residual as "Difference in opening balances" rather than hiding it.

**Treatment of stock in the TB**
- The TB carries **opening stock** (Dr), via the Stock-in-Hand opening or a P&L opening-stock figure.
- Closing stock is supplied outside the TB (inventory valuation or user input) and enters the Trading A/c (Cr) and the Balance Sheet (asset).
- If the source data already contains a "Closing Stock" journal (Dr Closing Stock, Cr Trading/Purchases), do not add closing stock again. This is the double-counting Tally warns about.

**Other TB checks**
- Suspense A/c balance should be 0 at year end.
- Every ledger must map to exactly one group.
- Cash is never a Cr balance.
- TB totals for the current period must equal Day Book ΣDr for the period plus opening TB totals. This is only true on a gross basis, so use it as a reconciliation diagnostic.

**GST effect.** The Duties & Taxes group holds the Output GST (Cr) and Input GST/ITC (Dr) ledgers. The net TB balance is GST payable (Cr) or carried-forward ITC (Dr).

**Tally's net-balance group display.** Showing a group as one net Dr or Cr figure means a Sundry Debtors group that contains some Cr-balance customers (advances) shows a smaller net Dr. Schedule III presentation may require un-netting: advances from customers go under Other current liabilities.

### Gaps
- Whether Tally's TB shows an explicit "Opening Stock" line, and how the "Profit & Loss A/c" (previous-year) line appears in it, was not confirmed from a fetched page.
- Busy's and Zoho's default trial-balance groupings were not fetched. Zoho uses account types rather than Tally groups (see Section 9).

---

## 5. Profit & Loss: Tally trading + P&L layout vs Schedule III, gross vs net profit, stock treatment

### Takeaway
- Tally's default P&L is horizontal (T-form). The top section is the Trading Account:
  - Opening Stock, Purchase Accounts and Direct Expenses against Sales Accounts, Direct Incomes and Closing Stock;
  - the balancing figure is Gross Profit or Gross Loss.
- The bottom section takes Gross Profit plus Indirect Incomes less Indirect Expenses to reach Nett Profit.
- Schedule III (companies) instead uses a vertical Statement of Profit and Loss: Revenue from operations, Other income, Total income, expenses by nature, PBT, tax, profit for the period.

### Cited Findings
- Tally's P&L A/c is horizontal by default. "Show Vertical Profit & Loss" = Yes gives a vertical form in which "the Trading Account and the Income Statements" are shown separately. — [Tally Help: Profit & Loss Account](https://help.tallysolutions.com/docs/te9rel66/Reports/intro_profit_loss_accounts.htm)
- "Show with Gross Profit" (horizontal form only) splits the statement to show trading profit. Trading profit considers only Cost of Sales and Direct Expenses; Indirect Expenses are then deducted from Gross Profit to arrive at Nett Profit. Extra columns can show the P&L under another stock valuation method (e.g., LIFO Annual). — [Tally Help: Configuring P&L](https://help.tallysolutions.com/docs/te9rel65/Reports/Display_Financial_Statements/Config_Profit_Loss_Account.htm); [Tally Help: P&L](https://help.tallysolutions.com/docs/te9rel66/Reports/intro_profit_loss_accounts.htm)
- Direct Incomes and Direct Expenses affect gross profit; Indirect Incomes and Indirect Expenses do not. — [Tally Help: Default Groups](https://help.tallysolutions.com/docs/te9rel53/Creating_Masters/Accounts_Info/Default_Groups.htm); [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)
- **Non-trading entities.** Tally can show an Income & Expenditure statement instead of a P&L via F11 "Income & Expense A/c instead of Profit & Loss A/c". — [Tally Help: P&L](https://help.tallysolutions.com/docs/te9rel66/Reports/intro_profit_loss_accounts.htm)
- **Stock.** With integrated inventory, stock values come from inventory records and flow into the Balance Sheet. Without integration (F11 "Integrate Accounts with Inventory" = No), the user creates a Stock-in-Hand ledger with the opening amount and enters closing-stock date and amount on that ledger. The P&L then shows those manual figures. — [Tally Help: Stock valuation FAQ](https://help.tallysolutions.com/tally-prime/inventory/stock-valuation-faq/); [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)
- The Stock Group Summary (non-integrated mode) takes opening and closing stock from the ledger master, not inventory, so it can differ from Stock Summary. — [Tally Help: Stock Group Summary](https://help.tallysolutions.com/article/te9rel53/Reports/Display_Inventory_Reports/Stock_Group_Summary.htm)
- In Tally's Sales Register, gross profit = sales value − cost. To match the P&L and Stock Summary, enable "Show Cost based on Stock Valuation". — [Tally Help: Sales Register](https://help.tallysolutions.com/tally-prime/sales-process/how-to-work-with-sales-register-in-tallyprime/)
- Tally's general formulas: Gross Profit = Revenue − COGS; Operating Profit = Gross Profit − Operating Expenses; Net Profit = Operating Profit − (Interest + Taxes); "COGS = Opening Stock + Purchases During the Period – Closing Stock". This article's COGS omits direct expenses, but Tally's own report includes them in trading profit (previous finding). — [TallySolutions: P&L format & formula](https://tallysolutions.com/accounting/profit-loss-statement-format-formula/)
- **Statement of Profit and Loss line items** (Revised Schedule VI Part II, carried into Schedule III Division I):
  - I Revenue from operations; II Other income; III Total Revenue (I+II).
  - IV Expenses: Cost of materials consumed; Purchases of Stock-in-Trade; Changes in inventories of finished goods, work-in-progress and Stock-in-Trade; Employee benefits expense; Finance costs; Depreciation and amortization expense; Other expenses; Total expenses.
  - V Profit before exceptional and extraordinary items and tax (III−IV); VI Exceptional items; VII Profit before extraordinary items and tax (V−VI); VIII Extraordinary items; IX Profit before tax (VII−VIII).
  - X Tax expense: current tax and deferred tax; XI Profit/(Loss) for the period from continuing operations.
  - XII–XIV Discontinuing operations.
  - XV Profit (Loss) for the period (XI+XIV); XVI Earnings per equity share: Basic and Diluted.
  — [ICAI Palakkad: Schedule VI Part II](https://palakkad.icai.org/detail/4476.aspx)
- **Schedule note disclosures:** — [ICAI Palakkad](https://palakkad.icai.org/detail/4476.aspx)
  - Revenue from operations (non-finance companies) is split into sale of products, sale of services and other operating revenues, less excise duty.
  - Other income is split into interest income, dividend income, net gain/loss on sale of investments, and other non-operating income net of directly attributable expenses.
  - Other expenses that must be disclosed include stores and spares, power and fuel, rent, repairs to buildings and machinery, insurance, rates and taxes, and miscellaneous.
- The "extraordinary items" line appears in older or Division I versions and is absent in some later formats. Sources differ; the current MCA text is the authority. — [WebSearch synthesis of inflibnet and ICAI pages](https://ebooks.inflibnet.ac.in/mgmtp02/chapter/form-of-companys-profit-loss-account-and-profit-loss-appropriation-account/)
- 2021 Schedule III amendments added P&L-note disclosures for undisclosed income surrendered in tax assessments, CSR, and crypto or virtual-currency trading. Effective from 1 April 2021. — [KPMG India: Key revisions to Schedule III (May 2021)](https://assets.kpmg.com/content/dam/kpmg/in/pdf/2021/05/chap-1-aau-schedule-III-to-the-companies-act-2013.pdf)

### Inferences
**Exact Tally-style horizontal P&L.** The labels follow Tally convention from practitioner familiarity; the group placement is sourced above.

```
TRADING SECTION
Dr side                              Cr side
Opening Stock                        Sales Accounts (net of returns)
Purchase Accounts (net of returns)   Direct Incomes
Direct Expenses                      Closing Stock
Gross Profit c/o   (if Cr > Dr)      Gross Loss c/o (if Dr > Cr)
-----------------------------------  ------------------------------
P&L SECTION
Gross Loss b/f                       Gross Profit b/f
Indirect Expenses                    Indirect Incomes
Nett Profit        (balancing)       Nett Loss (balancing)
```

**Formulas** (use income-positive sign: income = −signed balance, expense = +signed balance):
- `Sales_net = −Σsigned(Sales Accounts)`. Returns booked in Sales Accounts carry Dr signs and reduce the total automatically.
- `Purchases_net = Σsigned(Purchase Accounts)`
- `DirectExp = Σsigned(Direct Expenses)`
- `DirectInc = −Σsigned(Direct Incomes)`
- `GP = (Sales_net + DirectInc + ClosingStock) − (OpeningStock + Purchases_net + DirectExp)`
- `COGS = OpeningStock + Purchases_net + DirectExp − ClosingStock`, so `GP = Sales_net + DirectInc − COGS`
- `NP = GP + IndirectInc − IndirectExp`, where `IndirectInc = −Σsigned(Indirect Incomes)` and `IndirectExp = Σsigned(Indirect Expenses)`
- Check: NP must equal −Σsigned of all P&L ledgers + (ClosingStock − OpeningStock). It must also equal the balancing figure that makes the Balance Sheet tally (Section 6).

**Stock**
- Opening stock = last year's closing stock (Stock-in-Hand opening on 1 April).
- Closing stock comes from inventory valuation (Tally integrated mode) or user input. It is not derivable from ledgers alone. If the Excel import has no stock data, the app must ask for it or show "GP before closing stock adjustment". A P&L without closing stock overstates COGS.

**Mapping the Tally layout to Schedule III vertical form** (company reporting):
- Revenue from operations = Sales_net + operating Direct Incomes.
- Other income = Indirect Incomes (interest, dividend, rent, discount received, profit on sale of assets).
- Cost of materials consumed (manufacturer) or Purchases of stock-in-trade (trader) = Purchase Accounts.
- Changes in inventories = Opening − Closing (FG/WIP/stock-in-trade). A positive value is an expense.
- Employee benefits = salary, wages, bonus, PF/ESI employer contribution, staff welfare, from Direct or Indirect Expenses.
- Finance costs = interest on loans or OD and bank charges on borrowings.
- Depreciation = depreciation ledgers.
- Other expenses = all remaining Direct and Indirect Expenses.

Because Schedule III classifies by nature, Tally's Direct/Indirect split is lost.

**GST.** Purchases and sales should be net of GST when GST is creditable: GST sits in Duties & Taxes. Ineligible ITC (blocked credits) should be added to the expense or asset cost. That rule belongs to the GST researcher's scope.

### Gaps
- The verbatim current Schedule III Division I Part II text was not fetched from MCA. The ICAI page is the Revised Schedule VI (2011) version, whose structure Division I inherited. Confirm on the MCA site whether the "extraordinary items" lines remain in Division I.
- No fetched Tally page shows the literal "Gross Profit c/o / b/f" and "Nett Profit" labels or where Opening and Closing Stock print.
- Busy, Vyapar and Zoho Books P&L layouts were not fetched. Zoho uses Operating Income, Cost of Goods Sold, Operating Expense, Non-Operating Income/Expense sections; this is general knowledge, not verified here.

---

## 6. Balance Sheet: Schedule III structure, group mapping, Assets = Liabilities + Capital, net profit flow

### Takeaway
- Tally's Balance Sheet is the primary BS groups plus a "Profit & Loss A/c" line (opening balance + current-period net profit) and closing stock under Current Assets. It balances when the TB balances and closing stock is included.
- Companies must present the vertical Schedule III Division I format:
  - Equity & Liabilities: Shareholders' funds, Share application money, Non-current liabilities, Current liabilities;
  - Assets: Non-current assets, Current assets.

### Cited Findings
- **Schedule III Division I Balance Sheet heads:** — [CorpLawUpdates: Schedule III Balance Sheet](https://www.corplawupdates.in/tools/financial-statements/balance-sheet)
  - I. EQUITY AND LIABILITIES
    1. Shareholders' funds: Share capital; Reserves and surplus; Money received against share warrants.
    2. Share application money pending allotment.
    3. Non-current liabilities: Long-term borrowings; Deferred tax liabilities (Net); Other long-term liabilities; Long-term provisions.
    4. Current liabilities: Short-term borrowings; Trade payables (MSME / others); Other current liabilities; Short-term provisions.
  - II. ASSETS
    1. Non-current assets: Property, Plant & Equipment and Intangible assets (PPE, Intangibles, CWIP, Intangibles under development); Non-current investments; Deferred tax assets (Net); Long-term loans and advances; Other non-current assets.
    2. Current assets: Current investments; Inventories; Trade receivables; Cash and cash equivalents; Short-term loans and advances; Other current assets.
- Vertical format is mandatory. Horizontal T-form balance sheets are not permitted for companies. Totals balancing shows arithmetic correctness only, not compliance. — [CorpLawUpdates](https://www.corplawupdates.in/tools/financial-statements/balance-sheet); [TallySolutions: Schedule III Division I](https://tallysolutions.com/accounting/schedule-iii-division-i-meaning-applicability-and-financial-statement-format-for-companies/)
- **Applicability.** Division I applies to companies following Companies (Accounting Standards) Rules 2006 (non-Ind AS). Division II applies to Ind AS companies other than NBFCs. Division III applies to NBFCs. — [KPMG India May 2021](https://assets.kpmg.com/content/dam/kpmg/in/pdf/2021/05/chap-1-aau-schedule-III-to-the-companies-act-2013.pdf)
- **Current/non-current test for liabilities.** A liability is current if any of these holds:
  - it is expected to be settled in the normal operating cycle;
  - it is held for trading;
  - it is due within 12 months of the reporting date;
  - there is no unconditional right to defer settlement for at least 12 months.
  The operating cycle is the time from acquiring assets to realisation in cash. It is 12 months for most companies and can be longer, e.g., a 15-month worked example. — [Taxmann: Schedule III](https://www.taxmann.com/post/blog/schedule-iii-of-the-companies-act); [TallySolutions: Schedule III Div I](https://tallysolutions.com/accounting/schedule-iii-division-i-meaning-applicability-and-financial-statement-format-for-companies/)
- **Instalment loans.** A ₹10,00,000 loan repayable in ten half-yearly instalments of ₹1,00,000 splits into ₹8,00,000 long-term borrowings and ₹2,00,000 current maturities. — [Taxmann](https://www.taxmann.com/post/blog/schedule-iii-of-the-companies-act)
- **Placement of current maturities.** Since the 2021 amendment, current maturities of long-term borrowings go under Short-term borrowings (previously Other current liabilities), and security deposits go under Other non-current assets (previously long-term loans and advances). — [KPMG India May 2021](https://assets.kpmg.com/content/dam/kpmg/in/pdf/2021/05/chap-1-aau-schedule-III-to-the-companies-act-2013.pdf); [CorpLawUpdates](https://www.corplawupdates.in/tools/financial-statements/balance-sheet). Taxmann's older example still places current maturities under Other current liabilities ([Taxmann](https://www.taxmann.com/post/blog/schedule-iii-of-the-companies-act)). The post-2021 rule supersedes it.
- **Debit P&L balance.** A debit (loss) balance in P&L is shown as a negative figure under Reserves and Surplus, even if net reserves become negative. Share application money in excess of issued capital, or refundable, goes to Other current liabilities. — [Taxmann](https://www.taxmann.com/post/blog/schedule-iii-of-the-companies-act); [CAclubindia/Sultan Chand via search](https://www.caclubindia.com/articles/revised-schedule-vi-head-wise-classification-concepts-15338.asp)
- **2021 additions to Division I notes:**
  - trade payables and receivables ageing (Section 7);
  - promoter shareholding;
  - eight ratios: current ratio, debt service coverage ratio, return on equity, trade payables turnover, net capital turnover, net profit ratio, return on capital employed, return on investment;
  - title deeds, benami property, wilful defaulter, struck-off company relationships, and others.
  — [KPMG India May 2021](https://assets.kpmg.com/content/dam/kpmg/in/pdf/2021/05/chap-1-aau-schedule-III-to-the-companies-act-2013.pdf)
- **Rounding.** Turnover below ₹100 crore: round to the nearest hundreds, thousands, lakhs or millions (or decimals). Turnover ₹100 crore or more: round to lakhs, millions or crores (or decimals). — [Vyapar: Schedule 3 format](https://vyaparapp.in/balance-sheet-formats/schedule-3). This conflicts with [TallySolutions](https://tallysolutions.com/accounting/schedule-iii-division-i-meaning-applicability-and-financial-statement-format-for-companies/), which gives ₹100 crore and ₹1,000 crore thresholds. The Vyapar version matches the commonly cited Schedule III General Instruction, but verify against MCA text.
- Every line item must show the previous year's comparative. Notes to accounts are mandatory. — [TallySolutions: Schedule III Div I](https://tallysolutions.com/accounting/schedule-iii-division-i-meaning-applicability-and-financial-statement-format-for-companies/)
- In Tally, Profit & Loss A/c is a predefined ledger under Primary. Its balance is shown separately in the Balance Sheet, carrying the prior year's profit as opening balance. With integrated inventory, stock values flow from inventory into the Balance Sheet. — [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)

### Inferences
**Balance check**
- Total Assets (Dr-nature BS groups + closing stock) = Capital + Reserves + P&L A/c (opening + current NP) + Liabilities.
- Equivalent signed form: Σ signed(BS ledgers, with the stock ledger at its *opening* value removed) + ClosingStock − NP = 0, where NP is a positive number for a profit. This holds because Σ signed(all ledgers) = 0 when the TB balances, and NP = −Σ signed(P&L ledgers) + ClosingStock − OpeningStock.
- Simplest implementation: compute NP from Section 5, then assert `Σ Dr-side BS + ClosingStock == Σ Cr-side BS + NP` with signed arithmetic. If it fails, the cause is one of:
  - TB imbalance or opening difference;
  - missing or double-counted closing stock;
  - a ledger mapped to no group.

**Tally group → Schedule III mapping** (practitioner mapping, needs CA review):

| Tally group | Schedule III head |
|---|---|
| Capital Account (company) | Share capital |
| Capital Account (proprietor/partner) | Capital A/c (non-company format) |
| Reserves & Surplus + P&L A/c balance | Reserves and surplus ("Surplus in Statement of P&L") |
| Secured/Unsecured Loans | Long-term borrowings (portion due > 12 m); Short-term borrowings (≤ 12 m and current maturities) |
| Bank OD A/c | Short-term borrowings |
| Sundry Creditors | Trade payables (split MSME/others); Dr-balance creditors → Short-term loans & advances / Other current assets |
| Duties & Taxes (Cr) | Other current liabilities (statutory dues); Dr balance (ITC) → Other current assets |
| Provisions | Short-term or Long-term provisions |
| Fixed Assets | PPE / Intangible assets (net of accumulated depreciation), CWIP |
| Investments | Non-current or Current investments |
| Stock-in-Hand / closing stock | Inventories |
| Sundry Debtors | Trade receivables; Cr-balance debtors → Other current liabilities (advance from customers) |
| Cash-in-Hand + Bank Accounts | Cash and cash equivalents (FDs > 3 m → other bank balances / other assets) |
| Deposits (Asset) | Other non-current assets (security deposits) / Other current assets |
| Loans & Advances (Asset) | Short-term / Long-term loans and advances |
| Misc. Expenses (ASSET) | Other non-current / current assets |
| Suspense A/c | Should be zero; if not, flag (no Schedule III head) |
| Branch/Divisions | Eliminate on consolidation; otherwise other current assets/liabilities by sign |

**Non-company SMEs** (proprietorships, partnerships, which are most Tally/Vyapar users) typically use the traditional horizontal Liabilities | Assets balance sheet:
- Liabilities side: Capital (opening + NP − drawings), Loans, Current Liabilities.
- Assets side: Fixed Assets, Investments, Current Assets.

Drawings is normally a ledger under Capital Account with a Dr balance that reduces capital.

**Tally displays.** Tally's BS shows Current Assets including Closing Stock and a "Profit & Loss A/c" line with sub-rows "Opening Balance" and "Current Period". A loss reduces the line, which can turn negative. A "Difference in opening balances" line appears if openings did not tally. Confirm these against a live screen.

### Gaps
- The MCA's verbatim Schedule III PDF was not retrievable (ca2013.com refused the connection; MCA not fetched). Line items come from secondary sources that agree with each other.
- ICAI's Guidance Note on financial statements of non-corporate entities, which would govern proprietorship and partnership formats, was not fetched. Its applicability and format should be researched separately.
- How Tally shows a net loss in the Balance Sheet (liability side negative vs asset side) was not confirmed.

---

## 7. Receivables and payables ageing: buckets, bill-wise vs on-account, due-date vs bill-date basis

### Takeaway
Ageing groups each *open bill* (invoice amount less receipts or credit notes adjusted against it) by days elapsed from either the bill date or the due date (bill date + credit period) up to the as-of date. Default buckets differ by product:
- Tally: 0-45 / 45-90 / 90-180 / >180;
- Zoho: Current / 1-15 / 16-30 / 31-45 / >45;
- Schedule III receivables: <6 m / 6 m-1 y / 1-2 / 2-3 / >3 y from due date;
- Schedule III payables: <1 / 1-2 / 2-3 / >3 y.

Buckets are user-configurable, so 0-30 / 31-60 / 61-90 / 90+ is a valid custom choice.

### Cited Findings
- Tally offers "Ageing by Bill Date" ("Counts from the invoice creation date") and "Ageing by Due Date" ("Counts from the expiry of the credit period"). The due date = invoice date + the credit period set on the party ledger. "TallyPrime provides default ageing slabs of 0-45 days, 45-90 days, 90-180 days and over 180 days", customisable via F6. — [TallySolutions: Track customer pending payments](https://tallysolutions.com/tally/how-to-track-customer-pending-payments-in-tallyprime/)
- Bill-wise tracking requires "Maintain balances bill-by-bill" = Yes on the party ledger. In vouchers, "New Ref" creates a new bill reference and "Agst Ref" adjusts an existing outstanding bill. Credit transactions recorded before bill-wise tracking was enabled appear as "On Account" entries, not linked to invoices unless manually allocated. Nett Pending Receivables nets advances received against outstanding bills. — [TallySolutions: Track customer pending payments](https://tallysolutions.com/tally/how-to-track-customer-pending-payments-in-tallyprime/)
- Ageing is available from Outstandings > Ledger, Group (e.g., Sundry Debtors) or Bills Receivable/Payable via F6 (Age-wise). For groups, F12 "Show Nett Balances" = Yes. Purpose: identify long-overdue bills for bad-debt write-off or provisioning. — [Tally Help: Ageing Analysis](https://help.tallysolutions.com/docs/te9rel55/Reports/MIS_Reports/Ageing_Analysis_Report.htm)
- If no due date is entered, the bill date is treated as the due date. — Search-result synthesis attributing this to Tally help; not confirmed on a fetched page ([Tally Help: Ageing Analysis](https://help.tallysolutions.com/docs/te9rel55/Reports/MIS_Reports/Ageing_Analysis_Report.htm))
- Zoho Books AR Aging Summary:
  - default intervals: "Current (on the same day)", 1-15, 16-30, 31-45 and >45 days;
  - "Aging By" invoice due date (default) or invoice date;
  - the number and length of intervals are configurable;
  - credit notes and manual journals can optionally be included.
  AR Aging Details lists each transaction with Age = "Number of days passed the due date". — [Zoho Books Help: Receivables reports](https://www.zoho.com/books/help/reports/receivables.html)
- **Schedule III (2021) trade receivables ageing.** Columns: Less than 6 months, 6 months-1 year, 1-2 years, 2-3 years, More than 3 years, Total, "from due date of payment". Rows: Undisputed considered good / considered doubtful; Disputed considered good / considered doubtful. — [KPMG India May 2021](https://assets.kpmg.com/content/dam/kpmg/in/pdf/2021/05/chap-1-aau-schedule-III-to-the-companies-act-2013.pdf)
- **Schedule III (2021) trade payables ageing.** Columns: Less than 1 year, 1-2 years, 2-3 years, More than 3 years, Total, from due date of payment. Rows: MSME, Others, Disputed dues-MSME, Disputed dues-Others. "In the absence of due date of payment", ageing runs "from the date of the transaction". Unbilled dues are disclosed separately. — [KPMG India May 2021](https://assets.kpmg.com/content/dam/kpmg/in/pdf/2021/05/chap-1-aau-schedule-III-to-the-companies-act-2013.pdf)

### Inferences
**Algorithm** (bill-wise, FIFO fallback):
1. Each sales invoice (or purchase bill for AP) is a bill with `bill_date`, `due_date = bill_date + credit_days` (or `bill_date` if unknown) and `amount`.
2. Receipts, credit notes and journals carrying a bill reference reduce that bill.
3. Unreferenced receipts are either:
   - (a) kept as "On Account" credit in the party's row, which is Tally's behaviour; or
   - (b) allocated FIFO to the oldest open bills. This is a common accountant expectation when exports lack bill references, but it is an assumption and should be labelled as such in the UI.
4. `age_days = as_of − basis_date`, where basis_date = due_date or bill_date. Bucket with explicit, non-overlapping edges, e.g. `[0,30],[31,60],[61,90],[91,∞)`. "Not yet due" (age < 0 on due-date basis) gets its own "Current/Not due" column, as Zoho does.
5. Tally's label "0-45, 45-90" overlaps at 45. Document which side the boundary falls on.

**Checks**
- Σ(all buckets + on-account/advances) per party = party ledger closing balance.
- Σ over parties = Sundry Debtors (or Sundry Creditors) group closing balance.
- Advances (Cr balances on debtors) are shown as negative or in a separate column, not dropped.

**Sign.** AR ageing shows Dr balances as positive and AP ageing shows Cr balances as positive. Convert via `−signed` for creditors.

**Indian accountant use.** MSME vendors must be paid within 45 days. A 0-45 / 45+ payables split is valuable for the Section 43B(h) income-tax disallowance (GST and tax researcher's scope; mentioned only because it affects the ageing design). Not sourced here.

### Gaps
- Busy and Vyapar ageing defaults were not found.
- The exact Tally treatment of "Advance" bill type and on-account amounts within age buckets (which column they appear in) was not confirmed.
- Whether Tally computes age inclusive or exclusive of the as-of date was not documented.

---

## 8. Bank Reconciliation Statement (BRS)

### Takeaway
The BRS starts from the bank balance per company books (Bank Book) and adjusts for:
- items the bank has not yet processed: cheques issued but not presented, deposits not yet credited;
- items the books have not yet recorded: bank charges, interest, direct credits, ECS debits, dishonoured cheques.

The result must equal the bank statement balance. Signs are opposite between the two records: a deposit is Dr in the Bank Book and Cr in the bank statement.

### Cited Findings
- **Tally's BRS (Bank Reconciliation Summary):**
  - "Balance as per Company Books" = book balance as of the report date.
  - "Amounts not reflected in Bank" = Dr and Cr totals of vouchers whose Bank Date is blank or later than the period end.
  - "Balance as per Bank" = book balance offset by those amounts, which "should be equal to the balance in the bank statement unless there are some discrepancies".
  - "Amount not reflected in Company Books" = entries such as bank charges or interest done at the bank's end but not booked. These can be recorded directly from the reconciliation screen.
  — [Tally Help: Bank Reconciliation reports](https://help.tallysolutions.com/bank-recon-reports/); [Tally Help: Bank Reconciliation](https://help.tallysolutions.com/bank-reconciliation-tally/)
- **Busy's BRS adjustments, starting from the cash book balance:**
  - Add: cheques issued but not presented; interest credited and direct credits not yet in books.
  - Less: deposits not yet credited by bank; bank charges and ECS/NACH debits not yet in books.
  - Add/less: errors.
  Starting from the bank statement balance, the signs reverse. "Both approaches must arrive at the same reconciled figure." For overdraft accounts the direction of adjustments reverses. — [Busy: BRS explained](https://busy.in/accounting/bank-reconciliation-statement-explained-purpose-format-and-common-errors/)
- **Busy's treatment of items:**
  - unpresented cheques and deposits in transit need no journal entry;
  - bank charges, interest and direct credits must be booked;
  - a dishonoured cheque requires reversing the receipt entry.
  Stale cheques (older than 3 months from the instrument date) should be reviewed and reversed or reissued. A difference divisible by 9 suggests a transposition error. — [Busy: BRS explained](https://busy.in/accounting/bank-reconciliation-statement-explained-purpose-format-and-common-errors/)
- Busy's own format table contains an arithmetic inconsistency: its items sum to 99,000 but it shows 93,000. Use it for logic, not numbers. — [Busy: BRS explained](https://busy.in/accounting/bank-reconciliation-statement-explained-purpose-format-and-common-errors/)
- **NIOS method.** Take the balance as per Cash Book. Add all transactions that increased the pass-book balance, deduct those that decreased it, and the net equals the pass-book balance. ICAI notes: decide which book is the target, then add items that increase the target balance and deduct items that decrease it. — [NIOS Sr Sec Accountancy L10](https://www.nios.ac.in/media/documents/SrSec320NEW/320_LG_E/320_LG_E_L10.pdf); [ICAI BoS PPT notes ch. 3](https://live.icai.org/bos/vcc-2nd-batch-recorded-lectures/pdf/PPT_notes_chapter%203.pdf)
- **Worked example** (NIOS worksheet, M/s Ankita Industries, 31 July 2020):
  - Cash book ₹57,000;
  - cheques deposited not credited ₹5,500;
  - cheques issued not presented ₹12,200;
  - ECS dividend credited by bank ₹5,800;
  - bank charges ₹600.
  57,000 − 5,500 + 12,200 + 5,800 − 600 = ₹68,900 per pass book. The arithmetic was computed by the search tool from the worksheet's figures, so verify. — [NIOS worksheet L8](https://www.nios.ac.in/media/documents/Seccour224New/Accountacy_worksheet_224/ws_224_E_L8.pdf)

### Inferences
**Engine design**, mirroring Tally:
1. Import the bank statement and convert it to book sign: `book_signed = deposit − withdrawal`, i.e., statement credit → Dr in books.
2. Match each Bank-ledger voucher line to a statement line in stages:
   - (a) same cheque/UTR/reference no.;
   - (b) same amount and date within ±N days (typically 3-7 for cheques);
   - (c) the remainder is left unmatched.
   Set `bank_date` = statement date on match.
3. BRS as on date D:
   - `Balance as per books(D)`
   - − Σ unmatched book Dr (deposits not yet credited)
   - + Σ unmatched book Cr (cheques issued not presented)
   - = `Balance as per bank (derived)`.
4. Compare with the actual statement closing balance on D. The residual must be fully explained by unmatched *statement* lines: charges, interest, direct credits, ECS debits, returns. These form the "Amount not reflected in company books", and the app should propose entries for them.

**Overdraft accounts.** With the signed approach, no special-casing is needed. The add/less reversal in textbooks is only a presentation artefact of positive-number formats.

**Checks**
- After booking all "not in books" items, `books − in-transit adjustments == statement balance` to the paisa.
- Flag cheques unpresented for more than 3 months as stale.
- Flag duplicate matches.
- The opening balance must equal the previous BRS's reconciled figure.

### Gaps
- Busy's and Vyapar's specific reconciliation screens and auto-matching rules were not documented in fetched sources.
- Zoho Books' bank-matching tolerance rules were not researched.
- The ICAI BoS BRS PDF found by search returned 404.

---

## 9. Classifying accounts automatically from free-text ledger or category names

### Takeaway
No vendor publishes a keyword classifier. The best available ground truth is Tally's predefined group descriptions and examples, plus Zoho's account types. A practical classifier combines four signals:
- keyword rules derived from those descriptions;
- the voucher-type context the ledger appears in;
- balance sign;
- party-name patterns.

Anything below a confidence threshold should go to a visible "Unclassified – needs review" bucket that blocks final reports. Silently posting to Suspense is the wrong choice.

### Cited Findings
- **Tally's own group descriptions and examples** (the authoritative keyword source):
  - Capital Account: Share Capital, Partners' Capital, Proprietor's Capital.
  - Reserves & Surplus: Capital Reserve, General Reserve, Reserve for Depreciation.
  - Bank Accounts: current, savings, short-term deposit accounts.
  - Cash-in-Hand: Cash A/c.
  - Deposits (Asset): fixed deposits, security deposits.
  - Loans & Advances (Asset): loans given, salary advances (supplier advances should not go here).
  - Stock-in-Hand: raw materials, WIP, finished goods.
  - Sundry Debtors: customers. Sundry Creditors: suppliers/trade creditors.
  - Duties & Taxes: VAT, CENVAT, excise, sales tax (today GST/TDS).
  - Provisions: provision for taxation or depreciation.
  - Investments: shares, bonds, government securities, long-term bank deposits.
  - Bank OD A/c: bill discounted A/c, hypothecation A/c.
  - Secured Loans: debentures, term loans. Unsecured Loans: loans from directors, partners or outside parties.
  - Suspense A/c: travel advances awaiting a bill.
  - Misc. Expenses (ASSET): incorporation and pre-operative expenses.
  - Sales Accounts: Domestic Sales, Export Sales, Sales (exempt), and sales returns.
  - Direct Incomes: servicing and contract charges, professional fees.
  - Direct Expenses: direct manufacturing or trading expenses.
  - Indirect Incomes: rent received, interest received.
  - Indirect Expenses: Rates & Taxes, administrative and selling expenses.
  — [Tally Help: Default Groups](https://help.tallysolutions.com/docs/te9rel53/Creating_Masters/Accounts_Info/Default_Groups.htm)
- Tally advises against altering predefined groups because doing so "may cause ledger grouping, reporting, and data interchange issues". — [Tally Help: Groups](https://help.tallysolutions.com/tally-prime/accounting/groups-in-tallyprime/)
- **Suspense A/c in Tally** is designed for money "whose nature is not yet known". The textbook view is a temporary account that must be cleared once errors are rectified. — [Tally Help: Default Groups](https://help.tallysolutions.com/docs/te9rel53/Creating_Masters/Accounts_Info/Default_Groups.htm); [Vedantu NCERT Ch 6](https://www.vedantu.com/ncert-solutions/ncert-solutions-class-11-accountancy-chapter-6)
- **Zoho Books account types** (alternative taxonomy):
  - Assets: Other Asset, Other Current Asset, Cash, Bank, Fixed Asset, Stock, Payment Clearing, Accounts Receivable, Deferred Tax Asset.
  - Liabilities: Other Current Liability, Credit Card, Long Term Liability, Other Liability, Overseas Tax Payable, Accounts Payable, Deferred Tax Liability.
  - Equity.
  - Income: Income, Other Income.
  - Expense: Expense, Cost of Goods Sold, Other Expense.
  The API filters on Asset, Liability, Equity, Income and Expense. — [Zoho Books Help: Chart of Accounts](https://zstatic.zohostatic.com/books/help/accountant/chart-of-accounts.md); [Zoho Books API: Chart of Accounts](https://www.zoho.com/books/api/v3/chart-of-accounts)

### Inferences
This is a design proposal; no fetched source prescribes it.

**Classification signals, in priority order**
1. **Exact or near-exact match to a Tally group name**, when the data has a "Group"/"Under" column (Tally exports often do). Normalise case and punctuation. Map synonyms: "Sundry Debtors" = "Trade Receivables" = "Debtors" = "Accounts Receivable".
2. **Voucher-type context** from the Day Book or Ledger export:
   - A ledger debited in Sales vouchers alongside a Sales ledger is a debtor, cash or bank.
   - A ledger credited in Purchase vouchers is a creditor.
   - The cash/bank side of Payment, Receipt and Contra is Cash-in-Hand or Bank.
   - The non-cash side of Payment is expense, asset or party.
   - Ledgers that only ever appear in Contra are cash or bank.
3. **Keyword rules** (case-insensitive, word-boundary), seeded from Tally's descriptions plus common Indian ledger names:

| Target group | Keywords |
|---|---|
| Cash-in-Hand | cash, petty cash, cash in hand |
| Bank Accounts | bank, a/c no, sb a/c, current a/c, HDFC, SBI, ICICI, Axis, Kotak, PNB, BoB, Canara, Union, IndusInd, Yes Bank, IDFC |
| Bank OD A/c | od, overdraft, cc a/c, cash credit, occ, hypothecation (overrides Bank Accounts) |
| Duties & Taxes | cgst, sgst, igst, utgst, gst, cess, tds, tcs, input, output, rcm, professional tax payable |
| Capital Account | capital, drawings, proprietor, partner |
| Reserves & Surplus | reserve, surplus, retained |
| Secured Loans | term loan, vehicle loan, car loan, machinery loan, debenture, secured |
| Unsecured Loans | loan from, unsecured, director loan |
| Provisions | provision for |
| Current Liabilities | outstanding, payable, expenses payable, salary payable, audit fee payable |
| Fixed Assets | land, building, plant, machinery, furniture, fixture, computer, laptop, vehicle, car, motor, equipment, air conditioner, software (intangible), accumulated depreciation |
| Investments | investment, shares of, mutual fund, NSC, bonds |
| Deposits (Asset) | deposit, FD, security deposit, rent deposit, EMD |
| Loans & Advances (Asset) | advance to, staff advance, salary advance, prepaid, loan to |
| Stock-in-Hand | stock, inventory, closing stock, opening stock |
| Sales Accounts | sales, sale, revenue, turnover, export sales, sales return |
| Purchase Accounts | purchase, purchases, purchase return |
| Direct Expenses | freight inward, carriage inward, cartage inward, wages (mfg), factory, power & fuel, job work, manufacturing, packing material (direct), octroi, import duty, customs duty, coal |
| Indirect Expenses | salary, rent, electricity, telephone, internet, mobile, printing, stationery, postage, courier, office, conveyance, travelling, advertisement, commission paid, discount allowed, bank charges, interest paid, audit fee, legal, professional fees paid, repairs, insurance, depreciation, bad debts, freight outward, carriage outward, round off |
| Direct Incomes | job work income, service charges, labour charges received |
| Indirect Incomes | interest received, interest on FD, discount received, commission received, rent received, dividend, misc income, profit on sale |
| Suspense A/c | suspense |

4. **Party-name patterns.** Names containing Pvt Ltd, Private Limited, Ltd, LLP, & Co, Traders, Enterprises, Industries, Agencies, Stores, Sons, Brothers, Corporation, or a GSTIN-like 15-character code are parties. Debtor vs creditor is decided by signal 2 (Sales vs Purchase vouchers) or by normal balance sign.
5. **Balance-sign sanity check.** If the keyword says "expense" but the ledger is net Cr and appears mainly in Receipt vouchers, lower confidence. Income may be mis-keyed, e.g., "commission" could be paid or received. Words that need disambiguation by direction: commission, discount, interest, rent, freight, wages.

**Uncertainty handling**
- Each rule emits (group, confidence).
- Exact group match ≈ 1.0; voucher-context ≈ 0.8–0.9; keyword-only ≈ 0.6–0.7; sign-only ≈ 0.3.
- Below the threshold (~0.7), put the ledger in an "Unclassified" bucket. Keep it visible on the TB, block BS and P&L publication (or watermark it "provisional"), and ask the user with the top-3 suggestions.
- Persist the user's answers as a per-company mapping table so they are reused on later imports.

**Do not**
- default unknowns to Indirect Expenses (overstates expenses);
- default unknowns to Suspense without a warning. Tally semantics would make the BS balance while hiding a P&L error.

**Direct vs Indirect split.** This is the most error-prone decision: wages, freight, power, packing. The default per Tally's descriptions is that items directly tied to production or purchase are Direct. Ask the user whether the business is trading, manufacturing or service, because it changes the defaults: a service business usually has no Trading Account.

**GST ledgers** must never be classified as Sales or Purchase. Mixing them inflates turnover and COGS.

### Gaps
- No published, authoritative keyword list or ML benchmark for Indian ledger-name classification was found. The keyword table above is a practitioner-style inference and should be validated on real client data (Tally/Busy/Vyapar exports).
- Vyapar's and Busy's default chart of accounts and group names were not fetched. They would be useful synonyms for the mapper.
- No Tally source gives confidence or fallback guidance. The "Unclassified bucket" policy is a design recommendation, not an industry standard.
