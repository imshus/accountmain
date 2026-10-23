# Voucher Posting Rules, Data Model and Validation for an Indian SME Double-Entry Core (GST, TDS, Round-off, Bill-wise) — current to Oct 2026

Scope note. This builds on two earlier notes in `research_notes/Accurate AI accounting features/`:
- `accounting_reports_formulas.md`: Tally voucher types, the TB/P&L/BS formulas, the 28 groups and the ageing buckets.
- `gst_rules.md`: GST 2.0 rates from 22-Sep-2025, end of compensation cess on 1-Feb-2026, s.170 rounding, RCM paid only in cash, ITC/blocked credits.

Those points are referenced here, not repeated.

Conventions used in every example:
- Amounts are in ₹ to 2 decimals. Store them as integer paise.
- Dr lines are listed first. ΣDr = ΣCr was checked in a script for every example below.
- "Intra" means the place of supply is in the company's own state, so tax is CGST+SGST. "Inter" means IGST.
- The worked journal entries are standard Indian accounting practice that I composed and arithmetically verified. They are not copied from one source, so they sit under **Inferences**. The rules that drive them (rates, TDS sections, ITC order, Rule 46 and so on) are cited.

---

## 1. Sales and purchase invoices: intra-state, inter-state, cess, round-off, input tax credit

### Takeaway
A sales invoice is:
- **Dr** party (or cash/bank) for the invoice total;
- **Cr** a Sales ledger (Sales Accounts group) for the taxable value;
- **Cr** Output CGST + Output SGST (intra) or Output IGST (inter), plus Output Cess where applicable. These ledgers sit under **Duties & Taxes**;
- **Cr or Dr** a Round Off ledger for the paise difference.

A purchase invoice is the mirror image, with **Input** GST ledgers debited where ITC is eligible. Where ITC is blocked under s.17(5), the GST is added to the cost or expense and no input ledger is used.

### Cited Findings
- Tally's round-off ledger is created under **Indirect Expenses** (Direct Expenses is also allowed), with "Type of Ledger = Invoice Rounding" and a chosen rounding method and limit. Its GST applicability is fixed at "Not Applicable". — [Tally Help: Invoice Rounding ledgers (GST)](https://help.tallysolutions.com/tally-prime/gst-master-setup/india-gst-expense-income-non-revenue-invoice-round-off-ledgers-tally/)
- Tally's rounding methods are Not Applicable, **Downward**, **Normal** and **Upward**:
  - Normal: 125.30 → 125 and 125.60 → 126, a round-off of 0.40.
  - Downward: 125.60 → 125, a round-off of (−)0.60.
  - Upward: 125.30 → 126, a round-off of 0.70.
  - The rounding limit is the multiple rounded to. With a limit of 5, the value 14 goes to 15 (Normal), 20 (Upward) or 10 (Downward).
  - The difference "is displayed as a positive or negative number".
  - The ledger can be attached to a voucher class with "As Total Amount Rounding" and "Remove if Zero".
  - Tax ledgers "created under Duties and Taxes" can also carry their own rounding method.
  — [Tally Help: Round off invoice and ledger values](https://help.tallysolutions.com/round-off-invoice-and-ledger-values/)
- Section 170 rounds tax *payable* to the nearest rupee. Invoices and returns carry 2-decimal amounts, and the e-invoice schema has a separate `RndOffAmt` field. — see `gst_rules.md` §2 ([Busy](https://busy.in/gst/rounding-off-rules-in-gst-invoices/); [Gimbooks](https://www.gimbooks.com/blog/gst-invoice-round-off-differences/))
- Rule 46 requires a tax invoice to show, among other things:
  - the taxable value after discount;
  - the rate and amount of tax split into central tax, state tax, integrated tax, UT tax and cess;
  - the place of supply with state name for inter-state supplies;
  - whether tax is payable on reverse charge.
  — [GSTZen: CGST Rule 46](https://gstzen.in/a/tax-invoice-cgst-rule-46.html)
- GST 2.0 slabs from 22-Sep-2025 are 5 / 18 / 40%, plus special rates. Compensation cess survived only on tobacco and pan masala until 31-Jan-2026. — see `gst_rules.md` §2 ([GST Council press release](https://gstcouncil.gov.in/sites/default/files/2025-09/press_release_press_information_bureau.pdf))

### Inferences

#### Sales invoices: worked postings

**S1. Intra-state, 18%.** Taxable ₹10,000. CGST 9% = 900, SGST 9% = 900.

| Ledger (group) | Dr | Cr |
|---|---|---|
| Customer A (Sundry Debtors) – bill-wise New Ref INV/26-27/00001 | 11,800.00 | |
| Sales @18% (Sales Accounts) | | 10,000.00 |
| Output CGST (Duties & Taxes) | | 900.00 |
| Output SGST (Duties & Taxes) | | 900.00 |

**S2. Intra-state with upward round-off.** Taxable ₹12,345.60. CGST = 12,345.60 × 9% = 1,111.104, rounded to 1,111.10. SGST is the same, 1,111.10. The raw total is 14,567.80. Normal rounding gives 14,568.00, so the round-off is +0.20.

| Ledger | Dr | Cr |
|---|---|---|
| Customer A | 14,568.00 | |
| Sales @18% | | 12,345.60 |
| Output CGST | | 1,111.10 |
| Output SGST | | 1,111.10 |
| Round Off (Indirect Expenses) | | 0.20 |

**S3. Inter-state, 18% IGST.** Taxable ₹50,000.

| Ledger | Dr | Cr |
|---|---|---|
| Customer B (other state) | 59,000.00 | |
| Sales @18% | | 50,000.00 |
| Output IGST | | 9,000.00 |

**S4. Downward round-off.** Taxable ₹1,059.68. CGST is 95.37 and SGST is 95.37, giving a raw total of 1,250.42. Rounding gives 1,250.00, so the round-off is −0.42.

| Ledger | Dr | Cr |
|---|---|---|
| Customer A | 1,250.00 | |
| Round Off | 0.42 | |
| Sales @18% | | 1,059.68 |
| Output CGST | | 95.37 |
| Output SGST | | 95.37 |

**S5. With compensation cess (historical).** This is only valid for invoices dated **before 22-Sep-2025**, e.g. aerated waters at 28% GST + 12% cess. The 28% + 12% figure is my recollection of the pre-GST-2.0 schedule and was not fetched. Tobacco and pan masala kept 28% + cess until 31-Jan-2026, and no compensation cess applies from 1-Feb-2026.

Taxable ₹20,000, intra-state: CGST 14% = 2,800, SGST 14% = 2,800, Cess 12% = 2,400.

| Ledger | Dr | Cr |
|---|---|---|
| Customer A | 28,000.00 | |
| Sales @28% | | 20,000.00 |
| Output CGST | | 2,800.00 |
| Output SGST | | 2,800.00 |
| Output Cess (Duties & Taxes, tax type Cess) | | 2,400.00 |

**S6. Mixed-rate invoice, intra-state.** Two items: ₹4,000 at 5% and ₹6,000 at 18%.

| Ledger | Dr | Cr |
|---|---|---|
| Customer A | 11,280.00 | |
| Sales @5% | | 4,000.00 |
| Sales @18% | | 6,000.00 |
| Output CGST (100 + 540) | | 640.00 |
| Output SGST (100 + 540) | | 640.00 |

The table merges the two CGST lines and the two SGST lines into one ledger each. The engine must still keep the rate-wise tax per item line for the GSTR-1 rate-wise and HSN summaries.

Other sales cases:
- **Cash sale:** replace the Customer line with Cash (Cash-in-Hand) or a bank ledger. B2C invoices below the Rule 46 threshold may omit the recipient's address.
- **Discounts:** a trade discount shown on the invoice reduces the taxable value, so it is never posted to a Discount ledger.

#### Purchase invoices: worked postings

**P1. Intra-state, 18%, ITC eligible.**

| Ledger | Dr | Cr |
|---|---|---|
| Purchase @18% (Purchase Accounts) | 40,000.00 | |
| Input CGST (Duties & Taxes) | 3,600.00 | |
| Input SGST (Duties & Taxes) | 3,600.00 | |
| Supplier X (Sundry Creditors) – New Ref = supplier's invoice no. | | 47,200.00 |

**P2. Inter-state, 5%.**
- Dr Purchase @5% 1,00,000
- Dr Input IGST 5,000
- Cr Supplier Y 1,05,000

**P3. Blocked credit under s.17(5)** (e.g. food and beverages for staff, ₹1,000 + 18%).
- Dr Staff Welfare 1,180
- Cr Cash 1,180

No Input GST line is posted. The voucher is still tagged "ITC ineligible" so that GSTR-3B Table 4(D) can be reported.

**Fixed-asset purchase with GST.**
- Dr Plant & Machinery (Fixed Assets) for the taxable value
- Dr Input GST
- Cr Supplier

If ITC is claimed, depreciation must not be charged on the GST component.

#### Conventions for the posting engine
- Use **separate Input and Output ledgers** per tax head (CGST/SGST/IGST/Cess), all under Duties & Taxes.
  - Tally can work with a single "CGST" ledger for both directions. Separate ledgers make GSTR-3B and the set-off journal (§5) much easier to audit.
  - In the TB the Input ledgers show Dr balances and the Output ledgers show Cr balances. Their net is the GST payable or credit carried forward.
- Use **rate-wise Sales and Purchase ledgers** ("Sales @5%", "Sales @18%", "Sales – Exempt/Nil", "Sales – Export (LUT)"). This is a common Tally practice and simplifies mapping from Excel registers. The alternative is one Sales ledger, with rate held on the item line.
- **Excel register → voucher.** Group rows by (invoice no, date, party):
  - one Dr party line = invoice total;
  - Cr Sales by rate = Σ taxable;
  - Cr Output tax heads = Σ tax;
  - round-off = invoice total − (taxable + tax). Reject the row if |round-off| ≥ ₹1.00. With Normal rounding it should be ≤ 0.50, and a larger value usually means a data error.

### Gaps
- I did not fetch an official Tally page that says explicitly which side the round-off posts on. The Dr/Cr above follows from the double-entry identity: a positive round-off increases the total receivable, so it is credited on a sales voucher.
- The 28% + 12% cess example rate is from memory and is only illustrative.

---

## 2. Sales returns / Credit Notes and Purchase returns / Debit Notes

### Takeaway
- **Credit Note (sales return or price reduction):** reverses the sales posting. Dr Sales (or Sales Returns) and Dr Output GST; Cr Customer, linked with **Agst Ref** to the original invoice.
- **Debit Note (purchase return):** Dr Supplier; Cr Purchase (or Purchase Returns) and Cr **Input** GST, which reverses the ITC.

Both carry the original invoice number and date, and the original invoice's tax rate.

### Cited Findings
- In Tally, a Credit Note records sales returns linked to the original invoice. A Debit Note records purchase returns, in voucher mode or in invoice mode affecting inventory. — [TallySolutions: Vouchers in TallyPrime](https://tallysolutions.com/tally/accounting-vouchers-in-tally-prime/) (from earlier notes)
- Credit and debit notes against invoices dated before 22-Sep-2025 should carry the original rate. — inference in `gst_rules.md` §2 (unverified against s.14 CGST Act)

### Inferences

**CN1. Goods returned against INV/26-27/00001, taxable ₹2,000 at 18%, intra-state.**

| Ledger | Dr | Cr |
|---|---|---|
| Sales Returns @18% (Sales Accounts) – or Sales @18% directly | 2,000.00 | |
| Output CGST | 180.00 | |
| Output SGST | 180.00 | |
| Customer A – **Agst Ref INV/26-27/00001** | | 2,360.00 |

Effect: the bill's pending amount falls from 11,800 to 9,440.

**Post-sale discount.**
- **Financial credit note with GST:** Dr Discount Allowed (Indirect Expenses) or Sales, plus Dr Output GST; Cr Customer.
- **Commercial credit note without GST:** Dr Discount Allowed 1,000; Cr Customer 1,000.
- Use the commercial version when the s.15(3)(b) conditions (a discount agreed before supply and linked to invoices) are not met. [Statute knowledge, not fetched.]

**DN1. Goods returned to an inter-state supplier, taxable ₹5,000 at 18% IGST.**

| Ledger | Dr | Cr |
|---|---|---|
| Supplier Y – **Agst Ref** supplier invoice | 5,900.00 | |
| Purchase Returns @18% (Purchase Accounts) – or Purchase directly | | 5,000.00 |
| Input IGST | | 900.00 |

**Naming caution.** Some businesses issue a "debit note" to a *customer* to raise extra charges. That is a supplementary invoice under s.34(3) and posts like a sales invoice: Dr Customer, Cr Sales, Cr Output GST. The data model therefore needs `gst_note_type` (Credit/Debit) and `party_side` (customer/supplier) as independent fields. The voucher type name alone is not enough.

**Validation**
- The Credit Note's taxable value cannot exceed the original invoice's taxable value, net of earlier notes.
- The tax heads must match the original: an IGST invoice can only get an IGST CN.
- The rate must equal the original line rate.

### Gaps
- I did not re-verify the s.34(2) deadline for declaring credit notes. My recollection is that it is the earlier of 30 November after the FY end or the annual return filing date (Finance Act 2022). It needs confirming before the app enforces it.

---

## 3. Receipts and Payments, including TDS (Income-tax Act 2025 numbering from 1-Apr-2026)

### Takeaway
- **Receipt:** Dr Cash/Bank; Cr party. The bill-wise reference is Agst Ref (against an invoice), Advance, or On Account.
- **Payment:** Dr party or expense; Cr Cash/Bank.
- **TDS** is credited to a **TDS Payable** ledger (Duties & Taxes) when the expense is booked or paid, whichever is earlier. It is computed on the amount *excluding GST* when GST is shown separately. It is later cleared by a Payment voucher to the government.

From **1 April 2026** the Income-tax Act, 2025 replaces the 1961 Act, and the old sections 194C/194J/194I/194H/194Q/194A are now items in the **Section 393(1) table**.

### Cited Findings

**New TDS references** (tax year 2026-27, resident payees). Rates and thresholds per the TDSMAN rate chart — [TDSMAN TDS/TCS rate chart TY 2026-27](https://blog.tdsman.com/2026/03/tds-tcs-rate-chart-fy-2026-27/):

| Old section | New reference | Nature of payment | Rate | Threshold |
|---|---|---|---|---|
| 194C | 393(1) Table Sl. 6(i).D(a) | Contractor, individual/HUF | 1% | single sum ₹30,000 or aggregate ₹1,00,000 in the tax year |
| 194C | 393(1) Table Sl. 6(i).D(b) | Contractor, others | 2% | same |
| 194J(a) | 393(1) Table 6(iii).D(a) | Technical services, certain royalty, call centre | 2% | ₹50,000 |
| 194J(b) | 393(1) Table 6(iii).D(b) | Professional services | 10% | ₹50,000 |
| 194J(b) | 393(1) Table 6(iii).D(b) | Director's fees/commission | 10% | no threshold |
| 194I(a) | 393(1) Table 2(ii).D(a) | Rent, plant/machinery | 2% | ₹50,000 per month |
| 194I(b) | 393(1) Table 2(ii).D(b) | Rent, land/building/furniture | 10% | ₹50,000 per month |
| 194H | 393(1) Table 1(ii) | Commission/brokerage | 2% | ₹20,000 |
| 194Q | 393(1) Table 8(ii) | Purchase of goods | 0.1% | in excess of ₹50 lakh |
| 194A | 393(1) Table 5 | Interest other than securities | 10% | ₹10,000 / ₹50,000 / ₹1,00,000 depending on payer and payee |

Other cited TDS points:
- **No PAN:** s.397(2) requires deduction at the highest of the specified rate, the rate in force, or 20% (5% for Table 8(ii)/8(v)). — [TDSMAN rate chart TY 2026-27](https://blog.tdsman.com/2026/03/tds-tcs-rate-chart-fy-2026-27/)
- **Transition:** the old Act applies if the earlier of credit or payment was on or before 31-Mar-2026, and the new Act if it was on or after 1-Apr-2026. Quoting the old section for new-Act transactions causes system validation errors. — [TaxHeal: TDS on contractors w.e.f. 01.4.2026](https://www.taxheal.com/tds-on-contractors-w-e-f-01-4-2026.html)
- **Table 6(ii)** (replaces 194M): 2% on payments by individuals/HUFs not otherwise required to deduct, above ₹50 lakh aggregate. These deductors need no TAN. — [TaxHeal](https://www.taxheal.com/tds-on-contractors-w-e-f-01-4-2026.html)
- **Source quality caveat:** these are practitioner charts, not the gazette text. The TaxHeal page is internally inconsistent in its "exceeds / does not exceed" wording. — [TaxHeal](https://www.taxheal.com/tds-on-contractors-w-e-f-01-4-2026.html); [India Briefing on s.393](https://india-briefing.com/news/section-393-income-tax-act-2025-tds-rules-rates-compliance-guide-44450.html/)
- **TDS excludes GST:** CBDT Circular 23/2017 (19-Jul-2017) says that where GST on services is "indicated separately" in the agreement or invoice, TDS is deducted on the amount "without including 'GST on services' component". GST here covers IGST, CGST, SGST and UTGST. — [CBDT Circular 23/2017 (itatonline copy)](https://itatonline.org/info/wp-content/uploads/2017/07/CBDT-Circular-23-TDS-GST.pdf); [RSM India newsflash](https://www.rsm.global/india/sites/default/files/media/RSM%20India/Publications/2017/no_tds_on_gst_component_comprised_in_the_payments_made_to_residents_-_rsm_india_newsflash.pdf)
- **Receipt references in Tally:** "Against Reference" is used "when we pass receipt entries or payment entries". "Advance" is used "when any amount is received in advance". "On Account" is used when "we are unsure of as of against which bill the sum has been settled". — [TallySolutions: Bill-wise details in TallyPrime](https://tallysolutions.com/tally/bill-wise-details-report-in-tally-prime/)

### Inferences

#### Receipts

**R1. Bank receipt against a bill.**
- Dr Bank 11,800
- Cr Customer A, Agst Ref INV/26-27/00001, 11,800

The bill is closed.

**R2. Partial receipt.**
- Dr Bank 5,000
- Cr Customer A, Agst Ref, 5,000

Pending on the bill = 6,800.

**R3. Receipt where the customer deducted TDS** (10% professional on the ₹10,000 taxable value).
- Dr Bank 10,800
- Dr TDS Receivable (Current Assets / Loans & Advances (Asset)) 1,000
- Cr Customer A, Agst Ref, 11,800

The 1,000 must reconcile with Form 26AS/AIS.

**R4. Receipt with settlement discount.**
- Dr Bank 11,600
- Dr Discount Allowed 200
- Cr Customer A, Agst Ref, 11,800

**R5. Advance or on-account receipt.**
- Dr Bank 50,000
- Cr Customer A, 50,000, with ref type **Advance** (named, e.g. ADV/26-27/0001) or **On Account**.

For goods no GST arises (§5). For services, the GST-on-advance journal in §5 is also needed.

**Cash receipts.** Dr Cash instead of Bank. Flag any cash receipt of ₹2 lakh or more from one person in a day or transaction (old s.269ST). [Statute knowledge; the new-Act section number was not verified.]

#### Payments and TDS

**PF. Professional fees with GST and TDS** (CA firm, intra-state, ₹60,000 + 18%; TDS 10% on ₹60,000 = 6,000).

Step 1, booking (Journal or Purchase voucher):

| Ledger | Dr | Cr |
|---|---|---|
| Professional Fees (Indirect Expenses) | 60,000.00 | |
| Input CGST | 5,400.00 | |
| Input SGST | 5,400.00 | |
| CA Firm (Sundry Creditors) – New Ref their bill no. | | 64,800.00 |
| TDS Payable – Professional [393 T6(iii) / old 194J(b)] (Duties & Taxes) | | 6,000.00 |

Step 2, payment:
- Dr CA Firm, Agst Ref, 64,800
- Cr Bank 64,800

Step 3, TDS deposit (challan, by the monthly due date):
- Dr TDS Payable – Professional 6,000
- Cr Bank 6,000

**JW. Contractor (a firm), inter-state, ₹1,50,000 + 18% IGST; TDS 2% on 1,50,000 = 3,000.**
- Dr Job Work / Contract Charges 1,50,000
- Dr Input IGST 27,000
- Cr Contractor 1,74,000
- Cr TDS Payable – Contractor 3,000

**Direct payment with TDS, no prior booking.** Individual contractor, unregistered, single bill ₹40,000. This is above the ₹30,000 single-sum threshold, so TDS is 1% = 400.
- Dr Contract Labour 40,000
- Cr Bank 39,600
- Cr TDS Payable – Contractor 400

**Rent with GST and TDS.** Office rent ₹60,000 per month (above the ₹50,000 per month threshold) + 18% GST, intra-state. TDS 10% on 60,000 = 6,000.
- Dr Rent 60,000
- Dr Input CGST 5,400
- Dr Input SGST 5,400
- Cr Landlord 64,800
- Cr TDS Payable – Rent 6,000

**Engine rules for TDS**
- Each TDS ledger carries `tds_section_new` (e.g. "393(1) T6(iii).D(b)"), `tds_section_old` (e.g. "194J(b)") and the payment code (e.g. 1027). The section the app shows is chosen by transaction date: before 1-Apr-2026 → old section, otherwise the new one.
- On a party line with TDS applicable, compute `tds = round(assessable × rate)`, where `assessable = taxable value excl. GST`.
- Track the aggregate per party per tax year to apply the thresholds.
- Use 20% if the party has no PAN.
- Store a `tds_detail` row (section, assessable, rate, amount, PAN, deduction date) for the Form 140-series and 26Q-equivalent returns.

### Gaps
- I did not verify the official monthly TDS deposit due dates under the 2025 Act (historically the 7th of the next month, and 30 April for March) or the new return form numbers.
- The exact threshold wording ("exceeds" vs "reaches") under s.393 needs confirmation from the bare Act.
- Rent paid by individuals/HUFs not liable to audit (old 194-IB) was not researched.
- Whether the ₹50,000 194J threshold is aggregate or per-type under the new table was not confirmed beyond the chart.

---

## 4. Contra and Journal vouchers (cash/bank transfers, depreciation, provisions, adjustments)

### Takeaway
- **Contra** moves money only between Cash-in-Hand, Bank Accounts and Bank OD ledgers. The receiving account is debited and the giving account is credited.
- **Journal** carries all non-cash adjustments: depreciation, provisions, accruals and prepayments, write-offs, GST set-off and TDS bookings. Conventionally it should not touch cash or bank.

### Cited Findings
- Tally's purposes: "Contra: cash withdrawal from or deposit into a bank"; "Journal: adjustments and other multi-purpose entries". — [TallySolutions: Vouchers in TallyPrime](https://tallysolutions.com/tally/accounting-vouchers-in-tally-prime/) (earlier notes)
- Tally uses Journal > "Stat Adjustment" for GST liability and ITC adjustments, e.g. raising RCM liability. — [Tally Help: Inward supply of services under reverse charge](https://help.tallysolutions.com/docs/te9rel60/Tax_India/gst/accounting_for_inward_supply_of_services_under_reverse_charge_gst.htm)

### Inferences

**Contra**

| Transaction | Dr | Cr |
|---|---|---|
| Cash deposited into bank | HDFC Bank 50,000 | Cash 50,000 |
| Cash withdrawn for office use | Cash 20,000 | HDFC Bank 20,000 |
| Transfer between own banks | HDFC Bank 1,00,000 | SBI 1,00,000 |

Validation: every line's ledger must be in {Cash-in-Hand, Bank Accounts, Bank OD A/c}, and the voucher has exactly 2 or more such lines.

**Journal examples**

| Purpose | Dr | Cr |
|---|---|---|
| Depreciation, direct method (Tally style) | Depreciation (Indirect Expenses) 15,000 | Plant & Machinery (Fixed Assets) 15,000 |
| Depreciation, accumulated method (Schedule III friendly) | Depreciation 15,000 | Accumulated Depreciation – P&M (Fixed Assets, contra) 15,000 |
| Provision for audit fees | Audit Fees 25,000 | Audit Fees Payable (Provisions) 25,000 |
| Outstanding salary | Salaries 2,00,000 | Salary Payable (Current Liabilities) 2,00,000 |
| Prepaid insurance at year-end | Prepaid Insurance (Current Assets) 9,000 | Insurance 9,000 |
| Bad debt write-off | Bad Debts 10,000 | Customer C (Agst Ref the bill) 10,000 |
| Provision for income tax | Income Tax Expense 80,000 | Provision for Tax (Provisions) 80,000 |
| Interest on loan accrued | Interest on Loan 12,000 | Bank Loan / Interest Payable 12,000 |

- **Accrual reversal:** use an auto-reversing journal on the first day of the next period, linked by `reverses_voucher_id`.
- **Cash/bank in a Journal:** Tally permits cash or bank ledgers in a Journal only if configured. The app should warn ("use Payment/Receipt/Contra") rather than silently accept them, so Cash Book and Bank Book stay complete.

### Gaps
- I did not fetch the Tally help text that states whether cash/bank ledgers are excluded from the default Journal voucher. This is noted as a gap in the earlier notes too.

---

## 5. Reverse charge, GST on advances, GST on expenses, and the month-end GST set-off journal

### Takeaway
- **RCM purchase** has three postings:
  1. Expense Dr / supplier Cr, for the value without GST.
  2. A self-assessed liability: Dr Input GST (RCM); Cr RCM GST Payable.
  3. Payment in **cash only**: Dr RCM GST Payable; Cr Bank, or Cr the Electronic Cash Ledger.
- **Advance received for goods:** no GST, because Notification 66/2017-CT exempts it.
- **Advance received for services:** GST is due on receipt. Treat the advance as tax-inclusive, raise output tax by journal, and reverse it when the invoice is issued.
- **Month-end set-off journal:** Dr Output ledgers; Cr Input ledgers, following the s.49/49A order with IGST credit first. The balance is paid in cash.

### Cited Findings
- **Tally's RCM steps:**
  - Purchase voucher with reverse charge enabled.
  - Journal > Stat Adjustment, debiting the expense or a Current Assets ledger and crediting the GST ledgers, to raise the liability.
  - A journal to claim ITC, debiting the GST ledgers.
  - Payment > Stat Payment with "Payment Type = Recipient Liability", selecting the bank and the CGST/SGST ledgers.
  — [Tally Help: Inward supply of services under reverse charge](https://help.tallysolutions.com/docs/te9rel60/Tax_India/gst/accounting_for_inward_supply_of_services_under_reverse_charge_gst.htm)
- **Tally worked example (RCM with advance paid):**
  - An advance of ₹1,00,000 is paid on 5 July. A liability journal credits the GST ledgers and debits a "tax on advance" ledger by ₹18,000. The source calls this ledger Current Liabilities in one place and current assets in another.
  - The invoice on 2 August is ₹2,90,000 with GST of ₹52,200. The tax on the ₹1,90,000 balance is ₹34,200.
  - A combined journal debits the GST ledgers by ₹52,200 (credit claimed) and credits them by ₹34,200 (liability raised).
  — [Tally Help: RCM advance payment](https://help.tallysolutions.com/docs/te9rel65/Tax_India/gst/advance_pymt_supplier_gst_6_0_3.htm); [Tally Help (TE9 rel 6.0)](https://help.tallysolutions.com/docs/te9rel60/Tax_India/gst/accounting_for_inward_supply_of_services_under_reverse_charge_gst.htm)
- **RCM tax must be paid through the electronic cash ledger** and cannot be set off from the credit ledger. ITC is available after payment. — `gst_rules.md` §7 ([TaxHeal](https://taxheal.com/pay-output-tax-cash-reverse-charge-gst-gst-itc-cant-claimed.html); [ClearTax CGST Rules Ch. 9](https://cleartax.in/s/cgst-rules-chapter-9-payment-of-tax))
- **Advances:**
  - Notification 66/2017-Central Tax (15-Nov-2017) removed GST on advances for goods suppliers other than composition taxpayers. Tax arises at invoice time.
  - Service suppliers still pay GST on receipt of an advance.
  - Rule 50 requires a **receipt voucher** on receipt of an advance, showing the serial number, date, GSTIN, description, amount and rate of tax.
  — [GSTZen: GST on advances](https://gstzen.in/a/gst-on-advances-received-for-future-supplies.html); [TaxGuru: GST advance payment](https://taxguru.in/goods-and-service-tax/gst-advance-payment.html)
  - One source claims the goods exemption is turnover-based (₹1.5 crore). Other sources say it applies to all non-composition goods suppliers, and the turnover reading appears outdated.
- **ITC utilisation order:**
  - IGST ITC goes first against IGST, then against CGST and SGST/UTGST "in any order", before CGST or SGST credit is used.
  - CGST ITC goes against CGST, then IGST.
  - CGST ITC cannot be used against SGST, and SGST ITC cannot be used against CGST.
  — [ClearTax docs: ITC ledger reports](https://docs.cleartax.in/product-help-and-support/for-small-businesses/cleargst/generate-reports/itc-cash-ledger-reports/itc-ledger-reports); [Quicko: Electronic credit ledger](https://learn.quicko.com/electronic-credit-ledger-gst)

### Inferences

**RCM example.** Legal services from an advocate (a notified RCM service), ₹50,000, 18%, intra-state.

(a) Booking. The purchase voucher is flagged `is_reverse_charge = 1`.
- Dr Legal Fees 50,000
- Cr Advocate 50,000

(b) Raise the liability and the ITC (Journal, Stat Adjustment).

| Ledger | Dr | Cr |
|---|---|---|
| Input CGST – RCM (Duties & Taxes) | 4,500 | |
| Input SGST – RCM | 4,500 | |
| RCM CGST Payable (Duties & Taxes) | | 4,500 |
| RCM SGST Payable | | 4,500 |

(c) Pay in cash (challan).
- Dr RCM CGST Payable 4,500
- Dr RCM SGST Payable 4,500
- Cr Bank 9,000

**Variant:** first pay into the cash ledger with Dr Electronic Cash Ledger (Current Assets) / Cr Bank, then post Dr RCM Payable / Cr Electronic Cash Ledger when the return is filed.

**Net effect:** Expense 50,000, ITC 9,000 Dr, Bank −9,000, Advocate 50,000 Cr. The supplier's invoice total is ₹50,000, so the advocate is paid ₹50,000 less any TDS.

**Engine rule:** RCM Payable ledgers are excluded from the credit-ledger set-off journal and can only be cleared against Bank or the Electronic Cash Ledger.

**Advance received for services (consultancy, 18%, intra-state).** The advance is treated as tax-inclusive: tax = 1,18,000 × 18/118 = 18,000.

1. **Receipt voucher** (Rule 50 receipt voucher number, own series, at most 16 characters).
   - Dr Bank 1,18,000
   - Cr Customer D, ref type **Advance** "RV/26-27/0001", 1,18,000
2. **Tax-on-advance journal.**
   - Dr GST on Advance Received (Current Assets) 18,000
   - Cr Output CGST 9,000
   - Cr Output SGST 9,000

   Tax is now in the month's liability, reported in GSTR-1 Table 11A.
3. **Invoice for ₹2,00,000 + 18%.**
   - Dr Customer D 2,36,000
   - Cr Consultancy Income 2,00,000
   - Cr Output CGST 18,000
   - Cr Output SGST 18,000
   - Bill-wise on the Customer line: New Ref INV/26-27/00057 for 2,36,000. The advance is then adjusted Agst Ref, leaving 1,18,000 pending.
4. **Reverse the advance tax** (reported as the Table 11B adjustment).
   - Dr Output CGST 9,000
   - Dr Output SGST 9,000
   - Cr GST on Advance Received 18,000

**Net:** output tax is 36,000, as it would be with no advance. The 18,000 was simply paid one period earlier.

**Advance received for goods.** Only R5 is posted (Dr Bank / Cr Customer – Advance). There is no tax journal, but the receipt voucher is still issued.

**Expenses with GST** (registered supplier, eligible ITC). The shape is always: Dr Expense at taxable value + Dr Input tax heads; Cr Party/Bank for the total; Cr TDS Payable where applicable. Rent and professional fees are worked in §3. Telephone bill example:
- Dr Telephone 1,000
- Dr Input CGST 90
- Dr Input SGST 90
- Cr Bank 1,180

Blocked credits post the gross amount to the expense (§1 P3).

**Month-end set-off example.**
- Liabilities: Output CGST 20,000, SGST 20,000, IGST 9,000.
- Credits: Input CGST 8,000, SGST 8,000, IGST 15,000.
- IGST credit is used first: 9,000 against IGST, and the remaining 6,000 split 3,000 to CGST and 3,000 to SGST. CGST credit 8,000 goes against CGST and SGST credit 8,000 against SGST.

Set-off journal:

| Ledger | Dr | Cr |
|---|---|---|
| Output IGST | 9,000 | |
| Output CGST | 11,000 | |
| Output SGST | 11,000 | |
| Input IGST | | 15,000 |
| Input CGST | | 8,000 |
| Input SGST | | 8,000 |

Cash payment for the balance:
- Dr Output CGST 9,000
- Dr Output SGST 9,000
- Cr Bank 18,000

After this, all six ledgers are nil.
- **Excess credit:** if credit exceeds liability, leave the excess as a Dr balance on the Input ledgers. It carries forward.
- **Interest and late fee:** Dr Interest on GST / Late Fee (Indirect Expenses); Cr Bank. Neither is creditable.

### Gaps
- I did not verify the current RCM service list (Notification 13/2017-CT(Rate) as amended), or post-GST 2.0 changes such as GTA options or commercial rent from unregistered landlords.
- I did not confirm whether TallyPrime 5.x/6.x/7.x now computes tax on advance receipts automatically within the Receipt voucher (no separate journal). The Tally pages fetched describe the journal approach.

---

## 6. Bill-wise details: New Ref / Agst Ref / Advance / On Account, pending amounts, due date and ageing

### Takeaway
Every line on a party ledger with "Maintain balances bill-by-bill = Yes" is split into one or more **bill allocations**, each with (ref type, bill name, amount, due date/credit days).
- A **bill** is born with a New Ref (or Advance) and is reduced by Agst Ref allocations.
- **Pending per bill** = signed sum of all allocations sharing (party, bill name).
- **On Account** amounts affect only the party balance, not any bill.
- **Ageing** counts from the bill date or the due date (bill date + credit period).

### Cited Findings
- **The four reference types:**
  - New Reference "is used at the time of passing sales and purchase entries".
  - Against Reference is used "when we pass receipt entries or payment entries".
  - Advance is used "when any amount is received in advance".
  - On Account is used for interest entries and when "unsure ... against which bill the sum has been settled".
  — [TallySolutions: Bill-wise details in TallyPrime](https://tallysolutions.com/tally/bill-wise-details-report-in-tally-prime/)
- **Due dates and split bills:** Bill Allocations hold the bill reference "along with due dates", and a voucher amount can be broken into "multiple reference numbers with different due dates". The Receivables report shows bill-by-bill outstanding with pending amount and due date. — [TallySolutions: Bill-wise details](https://tallysolutions.com/tally/bill-wise-details-report-in-tally-prime/)
- **Advances and earlier entries:** a typical flow records an advance with Advance or On Account and adjusts it later against the invoice with Agst Ref. Credit transactions made before bill-wise tracking was enabled show as On Account. — [Tally Help: Adjusting advances against the bill](https://help.tallysolutions.com/docs/te9rel49/Tax_Deducted_at_Source/Adjusting_Advances_against_the_Bill.htm) (search snippet); [TallySolutions: pending payments](https://tallysolutions.com/tally/how-to-track-customer-pending-payments-in-tallyprime/)
- **Ageing basis:** "Ageing by Bill Date" or "Ageing by Due Date", where due = invoice date + the party's credit period. Default slabs are 0-45, 45-90, 90-180 and >180 days. — [TallySolutions: pending payments](https://tallysolutions.com/tally/how-to-track-customer-pending-payments-in-tallyprime/) (details in `accounting_reports_formulas.md` §7)

### Inferences

**Sign convention.** Store `bill_allocation.amount` signed the same way as the ledger line: Dr is +, Cr is −.

For a debtor:
- the invoice's New Ref is +11,800;
- a receipt's Agst Ref is −5,000;
- pending = Σ = +6,800, a Dr balance, meaning receivable.

For a creditor, signs are reversed and a pending balance is Cr.

**How each reference type behaves**

| Ref type | Created by | Effect |
|---|---|---|
| New Ref | Sales/Purchase invoice, opening bill, Debit Note to customer, Journal (e.g. interest charged) | Creates a bill: (party, bill_name, bill_date = voucher date, due_date = bill_date + credit_days, original amount) |
| Agst Ref | Receipt, Payment, Credit/Debit Note, Journal | Must point to an existing open bill of the same party. Validate \|amount\| ≤ \|pending\|; overpaying is an error unless the remainder goes to Advance/On Account |
| Advance | Receipt/Payment before the invoice | Creates a bill with the opposite sign: a Cr "bill" on a debtor. A later invoice adjusts it with an Agst Ref line pointing to the advance (Tally style), or the advance's pending is netted |
| On Account | Any | No bill is created. It sits in the party balance only and appears as "On Account" in outstanding and ageing reports |

**Invariants**
- **Per line:** Σ bill allocations = line amount when the party is bill-wise.
- **Per party at any date:** ledger balance = Σ pending of all bills (including advances) + Σ On Account.

The second invariant is the reconciliation check between the outstanding report and the ledger.

**Excel imports.**
- Each register row creates a New Ref named after the invoice number. For purchases this is the supplier's invoice number, not our own voucher number.
- Imported receipts without a reference become On Account.
- Optional "auto-adjust FIFO" is an explicit user action that converts On Account into Agst Ref allocations against the oldest bills. Never do it silently.

**Opening bill-wise balances.** If a party's opening balance is ₹45,000 Dr, the user (or importer) must split it into opening bills (e.g. INV-2025-881 of 30,000 dated 10-Feb-2026 and INV-2025-902 of 15,000 dated 20-Mar-2026), or put the remainder On Account. Σ opening bills = opening balance.

### Gaps
- I found no Tally page stating whether an "Advance" reference is shown in a separate ageing column or netted in the first bucket.
- The exact screen behaviour when an invoice adjusts an advance in TallyPrime (whether the invoice line holds two allocations, New Ref and Agst Ref, or one) was not confirmed from a fetched page. The Tally RCM page does describe selecting "Agst Ref" in the purchase invoice to link the advance.

---

## 7. Data model: voucher header, lines, items, bill allocations, cost centres, TDS, audit trail, numbering (Rule 46)

### Takeaway
Model a voucher as:
- a **header** (type, series, number, date, party, references, GST flags, status);
- N **ledger lines** (ledger, signed amount);
- optional **item/tax lines** (for GST returns);
- per-line **bill allocations**, **cost-centre allocations** and **TDS details**;
- an append-only **audit log**.

GST documents use a per-FY series of at most 16 characters, unique case-insensitively.

### Cited Findings
- **Rule 46(b):** the tax invoice must carry "a consecutive serial number not exceeding sixteen characters, in one or multiple series", using alphabets, numerals, hyphen "-" and/or slash "/", "unique for a financial year". — [GSTZen: CGST Rule 46](https://gstzen.in/a/tax-invoice-cgst-rule-46.html); [CBIC Rule 46 text](https://taxinformation.cbic.gov.in/content/html/tax_repository/gst/rules/cgst_rules/active/chapter6/rule46_v1.00.html) (CBIC page failed to load with a certificate error; the text was confirmed through the search snippet)
- **New series each year:** GSTN advised starting a new invoice series each financial year from 1-Apr-2019. Practitioners repeat this for FY 2026-27. — [IRIS GST: reset invoice series from 1 April 2026](https://irisgst.com/effective-1st-april-2026-reset-the-invoice-number-series/); [Taxscan](https://www.taxscan.in/?p=34898)
- **Counting characters:** the 16-character limit counts the whole number, including prefix, FY code, separators and running digits. — [Busy: invoice numbering mistakes](https://busy.in/gst/invoice-numbering-mistakes-under-gst-causes-corrections-and-prevention/)
- **Case-insensitivity:** from 1-Jun-2025 the IRP treats invoice numbers as **case-insensitive** for IRN generation, so "abc101" and "ABC101" are the same number. — [IRIS GST](https://irisgst.com/?p=54609) (search snippet)
- **Audit trail (companies):** the proviso to Rule 3(1) of the Companies (Accounts) Rules, 2014 applies for FYs starting on or after 1-Apr-2023. Companies using accounting software must use one that:
  - records an audit trail of **each transaction**;
  - creates an **edit log of each change** with the date of the change;
  - does not allow the audit trail to be **disabled**.

  Auditors report on this under Rule 11(g) of the Audit Rules, covering whether the feature operated all year, whether it was tampered with, and whether it was preserved. Books must be accessible in India, with daily backups on servers in India. — [ICAI CA Journal: Audit trail](https://cajournal.icai.org/article-details/audit-trail-requirements-responsibilities); [Taxmann FAQ](https://taxmann.com/post/blog/faqs-statutory-auditors-duty-to-report-audit-trails); [ClearTax News](https://news.cleartax.in/mandatory-to-use-accounting-software-with-audit-trail-mca/6016/amp)

### Inferences

#### Proposed SQLite schema

Amounts are INTEGER paise. Every table carries `company_id`.

```sql
financial_year(id, company_id, start_date, end_date, status CHECK(status IN('open','closed')),
               lock_upto_date)                       -- period lock; NULL = unlocked
ledger_group(id, name, parent_id, nature CHECK(nature IN('Asset','Liability','Income','Expense')),
             affects_gross_profit INT, is_predefined INT)           -- Tally's 28 groups seeded
ledger(id, name UNIQUE COLLATE NOCASE, group_id, opening_paise INT /*Dr+ Cr-*/,
       is_bill_wise INT, credit_days INT, is_cost_centre_applicable INT,
       party_gstin, party_state_code, party_pan, gst_registration_type /*Regular|Composition|Unregistered|Consumer|SEZ|Overseas*/,
       ledger_kind /*GENERAL|PARTY|CASH|BANK|GST|TDS|ROUND_OFF|PL_APPROPRIATION*/,
       gst_tax_head /*CGST|SGST|UTGST|IGST|CESS*/, gst_direction /*INPUT|OUTPUT|RCM_PAYABLE|RCM_INPUT|ADVANCE*/,
       default_gst_rate REAL, tds_section_old, tds_section_new, tds_rate REAL,
       is_predefined INT, is_active INT)
voucher_type(id, name, base_type /*Sales|Purchase|Receipt|Payment|Contra|Journal|CreditNote|DebitNote*/,
             gst_doc_type /*INVOICE|BILL_OF_SUPPLY|CREDIT_NOTE|DEBIT_NOTE|RECEIPT_VOUCHER|REFUND_VOUCHER|PAYMENT_VOUCHER|SELF_INVOICE|NONE*/)
number_series(id, voucher_type_id, fy_id, prefix, suffix, next_no, pad_width, numbering /*AUTO|MANUAL*/,
              max_len INT DEFAULT 16)
voucher(id, voucher_type_id, series_id, voucher_no, voucher_no_norm /*UPPER()*/, date, fy_id,
        party_ledger_id, supplier_invoice_no, supplier_invoice_date,   -- purchase references
        orig_invoice_no, orig_invoice_date,                            -- CN/DN link
        place_of_supply_state, is_reverse_charge INT, is_itc_eligible INT, gst_note_reason,
        narration, status /*ACTIVE|CANCELLED|OPTIONAL|MEMO*/, reverses_voucher_id,
        source /*MANUAL|EXCEL_IMPORT|API*/, import_batch_id, import_row_ref,
        created_by, created_at, modified_by, modified_at, version INT,
        UNIQUE(series_id, voucher_no_norm))
voucher_line(id, voucher_id, line_no, ledger_id, amount_paise INT /*Dr+ Cr-; never 0*/, line_narration)
voucher_item(id, voucher_id, line_no, description, hsn_sac, qty, uqc, rate, discount_paise,
             taxable_paise, gst_rate REAL, cgst_paise, sgst_paise, igst_paise, cess_paise,
             income_expense_ledger_id)                  -- drives GSTR-1 HSN & rate-wise tables
bill_allocation(id, voucher_line_id, party_ledger_id, ref_type /*NEW|AGST|ADVANCE|ON_ACCOUNT*/,
                bill_name, bill_date, due_date, amount_paise INT)   -- AGST: bill_name of target bill
cost_centre_allocation(id, voucher_line_id, cost_centre_id, amount_paise)
tds_detail(id, voucher_line_id, section_code, payment_code, deductee_pan, assessable_paise,
           rate REAL, tds_paise, deduction_date)
audit_log(id, entity, entity_id, action /*CREATE|UPDATE|CANCEL|DELETE|RESTORE*/, before_json, after_json,
          user_id, at_utc, client_ip, reason)            -- append-only; no UPDATE/DELETE grants
```

#### Design notes
- **Signed single-amount column vs separate Dr/Cr columns.** A signed column makes ΣDr = ΣCr a single `SUM(amount_paise) = 0` check and a TB a single `GROUP BY ledger_id`. The UI renders the Dr/Cr columns.
- **`voucher_line` is the only thing the TB reads.** `voucher_item` is descriptive and used for GST returns. A consistency check ties them together: Σ item taxable per income ledger = that ledger's line amount, and Σ item CGST = Output CGST line.
- **Edits.**
  - Every edit bumps `version` and writes `audit_log` with before and after JSON.
  - Enforce append-only with SQLite triggers: `BEFORE UPDATE/DELETE ON audit_log → RAISE(ABORT)`.
  - Provide no setting that disables the log. This is the Rule 3(1) requirement.
  - Prefer **cancel** (status = CANCELLED, lines zeroed or excluded, number retained) over delete for GST documents, so the series stays consecutive. Cancelled numbers are reported in the GSTR-1 documents-issued table.
- **Numbering.**
  - Use a per-(voucher type, FY) series. Example: `INV/26-27/00001` is 15 characters.
  - Validate `len ≤ 16` and `^[A-Za-z0-9/-]+$`, and keep uniqueness on `UPPER(voucher_no)` within the FY across all series of the same GST document type.
  - Purchase vouchers do not need a Rule 46 number of our own. Uniqueness is on (supplier GSTIN, `supplier_invoice_no_norm`, FY), which also catches duplicate imports.
  - Receipt vouchers, refund vouchers, CN/DN, self-invoices and RCM payment vouchers each need their own consecutive series. [Assumption: from my recollection of Rules 50-53, they carry the same "≤16 characters, unique per FY" wording. Not fetched.]
- **Cost centres.**
  - Only for lines whose ledger has `is_cost_centre_applicable = 1`, typically income and expense ledgers.
  - Σ allocations = line amount, with any unallocated remainder going to a "Primary Cost Category / Unallocated" bucket.
  - They have no effect on the TB.

### Gaps
- I could not open the CBIC rule pages for Rules 50, 51, 52 and 53 (receipt, refund and payment vouchers, credit/debit notes) to quote their numbering wording.
- I did not verify Tally's internal storage model, i.e. how Tally stores allocations in its XML: ALLLEDGERENTRIES.LIST / BILLALLOCATIONS.LIST. That is my recollection of Tally's XML export, not fetched, though it would be useful for import/export compatibility.

---

## 8. Validation rules (so the trial balance always tallies)

### Takeaway
Use hard errors to keep the double-entry invariant, the FY/lock boundaries, the GST structure and bill-wise integrity correct. Use soft warnings for the statutory red flags: cash limits, TDS thresholds, rate mismatches, negative cash.

### Cited Findings
- Each voucher must satisfy ΣDr = ΣCr. Memorandum, optional and cancelled vouchers are excluded from ledgers. — `accounting_reports_formulas.md` §3 ([Tally Help: Memorandum voucher](https://help.tallysolutions.com/docs/te9rel65/Voucher_Entry/Optional_Non-Accounting_Vouchers/Memorandum_Voucher.htm))
- Rule 46 particulars, including GSTIN, place of supply, taxable value, tax by head and the RCM flag. — [GSTZen Rule 46](https://gstzen.in/a/tax-invoice-cgst-rule-46.html)
- The round-off ledger is an Invoice Rounding type under Indirect Expenses, with a rounding limit. — [Tally Help](https://help.tallysolutions.com/round-off-invoice-and-ledger-values/)
- The ITC set-off order restricts CGST↔SGST cross-utilisation. — [ClearTax docs](https://docs.cleartax.in/product-help-and-support/for-small-businesses/cleargst/generate-reports/itc-cash-ledger-reports/itc-ledger-reports)

### Inferences

#### Hard errors (block save)
1. `SUM(amount_paise) = 0` per voucher, using integer paise so there is no float tolerance. There must be at least 2 lines, and no line can be 0.
2. `fy.start ≤ date ≤ fy.end` for an **open** FY. `date > lock_upto_date`. `date ≥ books_beginning_date`.
3. Voucher number:
   - unique within its series, case-insensitive;
   - for GST outward docs, ≤ 16 characters and charset `[A-Za-z0-9/-]`;
   - no reuse of a cancelled number.
4. Voucher-type ledger rules:
   - **Contra:** all lines are Cash/Bank/Bank OD.
   - **Receipt:** at least one Dr line is Cash/Bank.
   - **Payment:** at least one Cr line is Cash/Bank.
   - **Sales/CN:** exactly one party/cash line. Every other Cr line (Dr for a CN) is a Sales Accounts / Direct or Indirect Income ledger, an Output GST ledger, or Round Off.
   - **Purchase/DN:** mirrors Sales/CN.
5. GST structure:
   - (a) If POS state == company state: IGST = 0, CGST = SGST per rate, and CGST > 0 only if rate > 0.
   - (b) If POS ≠ company state, or SEZ/export: CGST = SGST = 0.
   - (c) GST lines must use ledgers in **Duties & Taxes** with `ledger_kind = GST` and a matching `gst_tax_head`.
   - (d) Direction: on Sales, Output ledgers are Cr only. On Purchase, Input ledgers are Dr only. CN/DN reverse these.
   - (e) Compensation cess on a non-tobacco item dated on or after 22-Sep-2025, or on any item dated on or after 1-Feb-2026, is an error (per `gst_rules.md`).
6. B2B sales need a valid party GSTIN. The checksum rules are in `gst_rules.md` §5.
7. Round-off line: `|amount| < 100 paise`, and ≤ 50 paise if the method is Normal. It must use the ROUND_OFF ledger, and at most one per voucher.
8. Bill-wise:
   - for a bill-wise party line, Σ allocations = line amount;
   - an Agst Ref must target an existing bill of the same party with enough pending;
   - New Ref names are unique per party per FY.
9. RCM:
   - a voucher with `is_reverse_charge = 1` must carry **no** supplier GST lines on the party side;
   - RCM Payable ledgers may only be debited against Bank or Electronic Cash Ledger lines, never in a set-off against Input ledgers.
10. GST set-off journal: no CGST credit → SGST liability, no SGST credit → CGST liability, and IGST credit is used before CGST/SGST credit.
11. Credit/Debit Note: `orig_invoice_no` is required for GST notes. Tax heads and rate match the original. Cumulative notes ≤ original value.

#### Soft warnings (allow, with acknowledgment)
- Tax amount ≠ round(taxable × rate) by more than ₹0.05 per line or ₹1 per invoice (tolerances from `gst_rules.md` §2).
- Rate not in the effective-dated valid set for the invoice date.
- Negative Cash-in-Hand balance on any date. This is physically impossible and a common audit observation.
- Cash payment to one person above ₹10,000 in a day (old s.40A(3) expense disallowance) and cash receipt ≥ ₹2 lakh (old s.269ST). [Statute knowledge; the new-Act section numbers were not verified.]
- A TDS-applicable ledger (contract, professional, rent, commission) booked to a party above the threshold without a TDS line.
- Journal voucher containing a cash or bank line.
- Edit to a voucher in a period whose GSTR-1/3B is already filed. Suggest a CN/DN instead.
- Duplicate purchase: the same supplier GSTIN + invoice no + FY.
- Voucher dated in the future, or in a different FY from the import batch.

#### Database-level invariants (run nightly or after import)
- Σ over all voucher_lines = 0 overall.
- TB Dr total = Cr total, including opening balances.
- Σ party bill pendings + On Account = party ledger balance.
- Σ voucher_item taxes = Σ GST ledger lines per voucher.

### Gaps
- No source fetched gives Tally's exact behaviour on locked periods. TallyPrime has "Lock Period" or "Allow modification of vouchers" style security controls, but I did not verify their names or behaviour.

---

## 9. Opening balances, "Difference in opening balances", and year-end closing

### Takeaway
- **Opening balances** are entered per ledger. If ΣDr opening ≠ ΣCr opening, Tally shows a balancing line **"Difference in opening balances"** at the foot of the Trial Balance, and it persists until the opening balances are corrected.
- **Year-end:** Tally needs no closing entries. Income and expense ledgers restart at zero in the new FY. Balance-sheet ledgers carry their closing balances forward. Cumulative profit sits in the predefined **Profit & Loss A/c** ledger (group: Primary). Any transfer to Capital or Reserves is an explicit Journal.

### Cited Findings
- **The balancing line:** when opening balances don't agree, the contrary amount "will appear as Difference in opening balances" in the Trial Balance. It often arises when migrating balances from manual books, or from a wrong or omitted opening balance. Passing an entry to clear it changes closing balances, but the TB still shows the opening difference. — [Tally Help: Trial Balance](https://help.tallysolutions.com/tally-prime/accounting-financial-reports/trial-balance-tally/); [Tally Help (TE9): Display Trial Balance](https://help.tallysolutions.com/docs/te9rel62/Reports/Display_Financial_Statements/Display_Trial_Balance.htm)
- **Predefined ledgers:** TallyPrime has two, **Cash** (under Cash-in-Hand) and **Profit & Loss A/c** (under Primary). The latter is "for reflecting the previous year's profit or loss as the opening balance". Both can be renamed but not deleted. There are 28 predefined groups. — [Tally Help: Ledgers in TallyPrime](https://help.tallysolutions.com/tally-prime/accounts/ledgers/); [Tally Help: Ledgers and groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)

### Inferences

**Opening balance example.** Going live on 1-Apr-2026 with these balances:

| Ledger | Dr | Cr |
|---|---|---|
| HDFC Bank | 5,00,000 | |
| Sundry debtors (split into opening bills) | 1,50,000 | |
| Furniture | 2,00,000 | |
| Cash | 75,000 | |
| Capital A/c | | 6,00,000 |
| Sundry creditors (split into opening bills) | | 1,80,000 |
| Bank loan | | 1,45,000 |
| **Total** | **9,25,000** | **9,25,000** |

If the loan is mis-keyed as 1,40,000, the Cr total is 9,20,000 and the TB shows "Difference in opening balances" Cr 5,000.

**Engine treatment**
- Compute `opening_diff = Σ ledger.opening_paise` (signed).
- Show it as a pseudo-row in the TB and BS so the reports still tally, exactly as Tally does. It goes on the Cr side when Dr openings exceed Cr openings (`opening_diff > 0`), and on the Dr side otherwise.
- Block year-end close, and show a red banner, while it is ≠ 0.
- **Do not** auto-post it to Suspense.
- Opening stock goes to a Stock-in-Hand ledger (for non-inventory mode) as part of the openings.

**Year-end without closing entries (Tally model)**
- For FY *n*+1, every Income/Expense ledger's opening = 0.
- Every Asset/Liability/Capital ledger's opening = its closing at the end of FY *n*.
- P&L A/c opening(*n*+1) = P&L A/c opening(*n*) + net profit(*n*), where profit is a Cr.
- This is computed on the fly from vouchers. Nothing is posted, so editing a prior-year voucher automatically flows forward.
- Closing stock(*n*) becomes opening stock(*n*+1) for the trading account.

**Optional appropriation journals** (dated the last day of FY *n*, or the first day of *n*+1, by policy):
- **Proprietor/partnership,** profit 3,20,000:
  - Dr Profit & Loss A/c 3,20,000; Cr Capital A/c 3,20,000.
  - Close drawings: Dr Capital A/c 60,000; Cr Drawings 60,000.
- **Company:** Dr Profit & Loss A/c; Cr Surplus in P&L / General Reserve (Reserves & Surplus). Dividends follow the same pattern.

**FY close in the app**
- Set `financial_year.status = 'closed'` and `lock_upto_date = end_date`.
- Snapshot closing balances into an audit table for comparison.
- Keep the vouchers editable only via an unlock that is itself audit-logged.

### Gaps
- I did not fetch Tally documentation on "split company data" or how Tally shows the P&L A/c ledger in the Balance Sheet when the current-year profit is unclosed. The earlier notes cover the BS presentation.

---

## 10. Default ledgers and groups for a new company

### Takeaway
- Seed the **28 Tally groups** (listed in `accounting_reports_formulas.md`) and the two Tally-predefined ledgers, **Cash** and **Profit & Loss A/c**.
- Then auto-create the GST, TDS, round-off and capital ledgers below, with fixed `ledger_kind`, tax head and direction, so that the posting engine never depends on free-text names.

### Cited Findings
- Tally's predefined ledgers are Cash (Cash-in-Hand) and Profit & Loss A/c (Primary), with 28 predefined groups. — [Tally Help: Ledgers in TallyPrime](https://help.tallysolutions.com/tally-prime/accounts/ledgers/)
- The round-off ledger sits under Indirect Expenses with Type = Invoice Rounding. — [Tally Help](https://help.tallysolutions.com/tally-prime/gst-master-setup/india-gst-expense-income-non-revenue-invoice-round-off-ledgers-tally/)
- Tax ledgers sit under "Duties and Taxes" with their own rounding method. — [Tally Help](https://help.tallysolutions.com/round-off-invoice-and-ledger-values/)

### Inferences

**Seed list.** The `ledger_kind`, tax head and direction attributes are our design. Tally itself sets "Type of duty/tax = GST" and "Tax type = Central Tax / State Tax / Integrated Tax / Cess" on Duties & Taxes ledgers; that is my recollection of Tally's GST ledger fields, not verified on a fetched page.

| Ledger | Group | ledger_kind / attributes |
|---|---|---|
| Cash | Cash-in-Hand | CASH (predefined, non-deletable) |
| Profit & Loss A/c | Primary | PL_APPROPRIATION (predefined, non-deletable) |
| Capital A/c (or Share Capital for companies) | Capital Account | GENERAL |
| Drawings (proprietor/partners) | Capital Account | GENERAL |
| Sales – GST @5% / @18% / @40% / Exempt / Nil / Export | Sales Accounts | GENERAL, default_gst_rate |
| Purchase – GST @5% / @18% / @40% / Exempt | Purchase Accounts | GENERAL |
| Sales Returns, Purchase Returns (optional) | Sales / Purchase Accounts | GENERAL |
| Output CGST, Output SGST (or UTGST), Output IGST, Output Cess | Duties & Taxes | GST, head, OUTPUT |
| Input CGST, Input SGST, Input IGST, Input Cess | Duties & Taxes | GST, head, INPUT |
| RCM CGST/SGST/IGST Payable; Input CGST/SGST/IGST – RCM | Duties & Taxes | GST, head, RCM_PAYABLE / RCM_INPUT |
| GST on Advance Received | Current Assets | GST, ADVANCE |
| Electronic Cash Ledger (GST) | Current Assets | GENERAL |
| TDS Payable – Contractor / Professional / Rent / Commission (one per section) | Duties & Taxes | TDS, section codes, rate |
| TDS Receivable | Loans & Advances (Asset) | GENERAL |
| Round Off | Indirect Expenses | ROUND_OFF, method = Normal, limit = 1 |
| Discount Allowed / Discount Received | Indirect Expenses / Indirect Incomes | GENERAL |
| Interest & Late Fee on GST/TDS | Indirect Expenses | GENERAL (flag non-deductible) |
| Depreciation | Indirect Expenses | GENERAL |
| Bad Debts | Indirect Expenses | GENERAL |
| Suspense A/c | Suspense A/c | GENERAL (import fallback; must be zero before close) |
| Bank (one per account) | Bank Accounts | BANK (user-created at onboarding) |

**Why Round Off is under Indirect Expenses.** Tally's convention puts it there even though its balance can be Cr. A net Cr balance then shows as negative expense. Placing it under Indirect Incomes is also seen. The app should keep one ledger and let the P&L sign decide.

**Composition dealers.** No Input or Output GST ledgers on invoices. They post "Composition Tax Payable" via journal on turnover. [Tally has a composition journal page that was not fetched; this is a gap.]

### Gaps
- Tally's exact field names for GST tax ledgers ("Type of Duty/Tax", "GST Tax Type") were not confirmed on a fetched page.
- I did not confirm whether TallyPrime auto-creates any GST ledgers when GST is enabled. I believe it does not, and the user creates them.
