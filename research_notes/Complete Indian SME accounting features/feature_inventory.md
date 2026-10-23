# Complete Indian SME Accounting Features: Prioritised Feature Inventory (as of October 2026)

Research date: 22 October 2026. Every threshold or rate below carries the date it applies from. Many sources are secondary (tax blogs, vendor pages). Where a primary source (GSTN advisory, incometaxindia.gov.in, Tally/Zoho help) was reachable it is cited first. Vendor comparison pages are marketing and are flagged as such.

---

## Q1. What accounting features do Tally Prime, Zoho Books (India), Busy, Vyapar, Marg ERP and myBillBook offer, and which are core vs advanced?

### Takeaway
All six products share a common core: GST billing, sales/purchase/receipt/payment/journal entries, party ledgers with receivables/payables, bank reconciliation, GST reports and the standard financial statements. Features like cost centres, budgets, multi-currency, interest calculation, custom roles, fixed assets and advanced inventory are add-ons. Tally ships them switched off by default (F11 company features). Zoho gates them behind higher-priced plans. The market splits into accounting-first desktop tools for accountants (Tally, Busy, Marg) and billing-first mobile apps for micro-businesses (Vyapar, myBillBook).

### Cited Findings

**TallyPrime (accounting-first; the de facto standard used by CAs)**
- Ships with 28 predefined groups (15 primary, 13 sub-groups) and 2 predefined ledgers, Cash and Profit & Loss A/c. Primary groups cannot be deleted. — [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)
- Cost centres, interest calculation and bill-by-bill tracking are optional features. Each is switched on from the Company Features screen (F11) and is set to "No" by default. — [Tally Help: Company Features (F11)](https://help.tallysolutions.com/company-features-f11-tally/)
- Cost centres allocate income and expenses to departments, branches or projects. Cost categories add a second dimension, for example department plus location. Each job can be its own cost centre for job costing. — [Tally: Cost Control and Cost Analysis](https://tallysolutions.com/ssa/features/cost-control-and-cost-analysis); [Tally: job costing](https://tallysolutions.com/tally/how-to-track-job-costs-and-profitability-in-tallyprime/)
- Budgets can be set per cost centre with income and expense figures, and several budgets can coexist. Variance (budget vs actual) reports drill down. "Scenarios" support forecasting. — [Tally Help: Creating Budgets for Cost Centres](https://help.tallysolutions.com/article/te9rel53/Advanced_Features/Advanced_Accounting_Features/Creating_Budgets_for_Cost_Centres.htm)
- With bill-wise details on, every sale or purchase is tagged with a bill reference. Payments are matched against that reference, which keeps outstanding balances (ageing) accurate. — [Tally Help: Company Features (F11)](https://help.tallysolutions.com/company-features-f11-tally/)
- Multi-currency: more than one currency can be created and vouchers recorded in them. — [Tally: Audit Trail / FAQ search result](https://tallysolutions.com/tally/audit-trail-in-tallyprime/) (note: from search summary of Tally currency FAQ; exact page not fetched)
- Feature history by release, which shows the compliance features Tally treats as table stakes: — [TallyPrime features release-wise](https://help.tallysolutions.com/tally-prime/welcome-to-tally-prime/tallyprime-features/)
  - e-Invoice with real-time or bulk IRN and QR generation (Rel 1.1); e-Way Bill generated during voucher entry, with bulk generation and tracking (Rel 2.0)
  - Reconciliation of GSTR-1, GSTR-2A and GSTR-2B, and multiple GST registrations in one company (Rel 3.0)
  - "Connected GST": direct upload and download of GSTR-1 and GSTR-3B (Rel 5.0); automated TDS under 194Q (Rel 5.0)
  - Connected Banking with bank reconciliation, vouchers created from bank statements, and real-time balances (Rel 6.0); HSN summary with B2B/B2C split (Rel 6.0); data split, i.e. splitting a company by financial year (Rel 6.0)
  - IMS with GSTR-2B recomputation (Rel 6.1); Edit Log for transactions and masters with user names (Rel 2.1 and 6.1); Edit Log Summary with version switching (Rel 6.1)
  - Release 7.0: PrimeBanking payments with limits and payment advice, direct ITC reduction in IMS, scheduled auto backup, JSON/Excel/XML import and export
  - TCS on realisation or accrual, and Form 27EQ (Rel 1.1.4)
- TallyPrime 7.0 adds "Bharat Connect for Business": a seller pushes invoices and payment information into the buyer's Tally, where they are auto-recorded and reconciled. — [Tally: Bharat Connect in TallyPrime 7.0](https://tallysolutions.com/tally/b2b-bharat-connect-tallyprime/)
- 2026 pricing: Silver ₹22,500 one-time; Gold ₹63,500; TSS renewal ₹4,500–13,500 per year. — [Turia Industry Report 2026](https://turia.in/articles/indian-accounting-software-industry-report-2026/)

**Zoho Books India (cloud; plan tiers show what Zoho considers core vs advanced)**
- Plans and prices (monthly / annual billing, per organisation per month, excluding taxes): Free ₹0 (1 user + 1 accountant); Standard ₹899/₹749 (3 users); Professional ₹1,799/₹1,499 (5 users); Premium ₹3,599/₹2,999 (10 users); Elite ₹5,999/₹4,999 (15 users); Ultimate ₹9,599/₹7,999 (25 users). — [Zoho Books India Pricing](https://www.zoho.com/in/books/pricing/)
- What each tier adds (each includes the tiers below): — [Zoho Books India Pricing](https://www.zoho.com/in/books/pricing/)
  - **Free:** invoices, quotes, bills, expenses, journals; bank reconciliation; sales and purchase orders; inventory tracking; GST reports and filing; 50+ reports; customer portal. Capped at 1,000 invoices per year.
  - **Standard:** e-invoicing; transaction period locking; Invoice Management System (IMS); progress invoicing; expanded banking.
  - **Professional:** multi-currency; custom user roles; sales and purchase approvals; projects and timesheets; price lists; workflows.
  - **Premium:** fixed asset management; budgets; cash-flow forecasting; payroll; vendor portal.
  - **Elite:** warehouses, batch and serial tracking, composite items (advanced inventory).
  - **Ultimate:** advanced analytics.
- Turia describes Zoho Books as free below ₹25 lakh turnover. The pricing page instead caps the Free plan by invoice count, so the two descriptions may refer to different points in time. — [Turia 2026](https://turia.in/articles/indian-accounting-software-industry-report-2026/) vs [Zoho pricing](https://www.zoho.com/in/books/pricing/)
- Transaction locking freezes transactions dated before a lock date: they cannot be added, modified or deleted. Locks can be set per module (Sales, Purchases, Banking, Accountant) with different dates, or as one date for everything. — [Zoho Books Help: Transaction Lock](https://zstatic.zohostatic.com/books/help/accountant/transaction-lock.md)
- An audit trail was released for all Indian users inside the Activity Reports module, in response to the MCA notification of 24 March 2021. (Source is a partner forum post, not official documentation.) — [Zoho Community: Audit Trail in Zoho Books](https://help.zoho.com/portal/fr/community/topic/use-of-audit-trail-in-zoho-books?page=1)

**Busy (IndiaMART-owned; traders and manufacturers)**
- Plans: Start (basic billing, inventory, accounting); Smart (advanced GST, inventory, e-invoicing, reporting); Power (multi-branch management); Power+ (more users, companies and compliance for large enterprises). Mobile app with 100+ reports; "BUSY on Cloud" provides remote access to the desktop software. The vendor claims 6,00,000+ businesses. — [Busy: Compare](https://busy.in/compare/)
- Turia lists Busy pricing at Blue about ₹3,600/yr, Saffron about ₹6,999/yr, Emerald about ₹9,000/yr, plus a free plan. IndiaMART acquired Busy for up to ₹500 crore. — [Turia 2026](https://turia.in/articles/indian-accounting-software-industry-report-2026/)
- Busy positions Marg as "mainly used in the pharma sector" and itself as cross-industry. — [Busy: Compare](https://busy.in/compare/)

**Vyapar (billing-first, mobile and desktop, micro and small businesses)**
- Claimed feature set: GST billing, POS, barcodes, quotations and estimates, delivery challans, 30+ invoice templates; GST reports, e-way bill generation, e-invoice generation; "complete accounting", inventory and godown management, low-stock alerts; multi-user with permissions; multiple firms in one app; payment reminders; WhatsApp marketing; online and offline modes on Android, Mac and Windows. — [Vyapar comparison page](https://vyaparapp.in/comparison-with-other-apps?brand=busy) (vendor marketing)
- Vyapar's page puts its own price at ₹3,999 + GST and lists Tally, Busy and Zoho at ₹22,500 + GST, and Marg at ₹12,600 + GST. These are competitor-published figures and conflict with other sources. — [Vyapar comparison page](https://vyaparapp.in/comparison-with-other-apps?brand=busy)
- Turia reports 1M+ users, of whom 1 lakh+ pay (unfootnoted). — [Turia 2026](https://turia.in/articles/indian-accounting-software-industry-report-2026/)

**myBillBook (FloBiz; billing-first, mobile)**
- 1M+ monthly active users. — [Turia 2026](https://turia.in/articles/indian-accounting-software-industry-report-2026/)
- Per Vyapar's comparison page, myBillBook charges extra for Tally export (₹3,000 + GST) and WhatsApp marketing (₹500/yr). This is a competitor claim. — [Vyapar comparison page](https://vyaparapp.in/comparison-with-other-apps?brand=busy)
- Comparison-search summaries say myBillBook pitches GST filing from the app and WhatsApp billing with UPI payment links. These are vendor pages and were not independently verified. — [myBillBook blog (Tally vs Marg)](https://mybillbook.in/blog/tally-prime-vs-marg-erp/)

**Marg ERP (pharma and FMCG distribution)**
- Vendor claims ">50% share in pharma/FMCG trade" and 850+ sales and support centres. Pricing starts at ₹5,550/yr through resellers. — [Turia 2026](https://turia.in/articles/indian-accounting-software-industry-report-2026/)

### Inferences
- **Core across all six products, so an Indian SME would call an app without these "incomplete":** voucher entry for sales, purchase, receipt, payment, journal, contra and credit/debit notes; party ledgers carrying GSTIN; GST auto-calculation; receivables and payables (bill-wise outstanding); bank reconciliation; day book, ledger and registers; trial balance, P&L and balance sheet; GST reports (GSTR-1, GSTR-3B, 2B reconciliation). Zoho puts bank reconciliation, journals and GST filing in its Free tier, which shows these are baseline.
- **Advanced or optional features,** which Tally switches off by default and Zoho puts in mid or upper tiers: cost centres and categories, budgets, interest calculation, multi-currency, custom roles and approvals, fixed assets, cash-flow forecasting, payroll, batch/serial/warehouse inventory.
- **Compliance automation has moved into the core:** e-invoice IRN, e-way bill, IMS and 2B reconciliation. Zoho puts e-invoicing, IMS and period locking in its first paid tier (Standard). Tally added direct GSTR upload/download, IMS and 2B recomputation in 2024-25 releases.
- Accounts.ai's existing sales vs purchase register comparison and GST summaries cover part of the GST layer. The missing core is the ledger and voucher engine, bill-wise outstanding, bank reconciliation and statutory financial statements.

### Gaps
- No official, fetched documentation was obtained for Busy, Marg or myBillBook feature lists. Their help docs or feature pages need direct checking for multi-currency, cost centres and budgets. The Busy compare page has no feature table.
- The Zoho pricing page does not say which tier includes reporting tags (Zoho's cost-centre equivalent), branches/multi-GSTIN (only a "Locations" add-on with one GSTIN is mentioned), e-way bill, TDS or recurring transactions.
- TallyPrime's standard voucher types (Contra, Payment, Receipt, Journal, Sales, Purchase, Credit Note, Debit Note, plus Memorandum, Reversing Journal and the order and inventory vouchers) are general domain knowledge and were not verified against a fetched Tally help page in this session.
- No independent, non-vendor feature-by-feature comparison of all six products was found.

---

## Q2. Which compliance features are legally required or expected in India as of 2026?

### Takeaway
An Indian SME accounting app in 2026 needs to support the following:
1. **GST data flows.** GSTR-1/1A is now the binding source of GSTR-3B liability: the auto-populated liability has been hard-locked since the July 2025 tax period. Inward ITC is driven by IMS actions feeding GSTR-2B.
2. **E-invoicing** for taxpayers whose aggregate turnover (AATO) exceeded ₹5 crore in any year from 2017-18 (rule effective 1 August 2023). Taxpayers with AATO of ₹10 crore or more must also report to the IRP within 30 days (from 1 April 2025).
3. **E-way bill** rules: ₹50,000 consignment threshold; generation limited to documents up to 180 days old and extensions capped at 360 days (from 1 January 2025); multi-factor authentication (MFA) mandatory for all taxpayers from 1 April 2025.
4. **TDS/TCS under the new Income-tax Act 2025** (in force 1 April 2026). Sections 194C/194J/194H/194I/194Q are now rows in a table under Section 393, with new payment codes and forms. TCS under 206C(1H) on sale of goods stopped applying from 1 April 2025.
5. **A non-disableable audit trail (edit log)** for every company under Rule 3(1) of the Companies (Accounts) Rules, applicable to financial years beginning on or after 1 April 2023.

### Cited Findings

**GST returns: GSTR-1, GSTR-1A, GSTR-3B hard-lock, IMS, GSTR-2B, 3-year time bar**
- **Phase 1 hard lock (in force):** since the July 2025 tax period (returns filed from August 2025), the auto-populated outward liability in GSTR-3B Tables 3.1 and 3.2 cannot be edited. Values come from GSTR-1, GSTR-1A and IFF, so errors must be fixed in GSTR-1A before GSTR-3B is filed. — [Taxscan (Jul 2026)](https://www.taxscan.in/top-stories/big-gst-change-from-july-2026-gstr-3b-itc-locking-explained-1448389); [A.S. Banka & Co (23 Jun 2026)](https://asbanka.com/2026/06/23/gstr-3b-hard-locking-gstr-1a-ims-itc/)
- **Phase 2 (ITC Table 4A locked to GSTR-2B), status uncertain:** commentary says Table 4A is "expected to be linked to GSTR-2B data, with no manual ITC entry for B2B supplies" from around July 2026. One source says that as of September 2026 GSTN had not issued an advisory notifying the Table 4A lock. — [Taxscan](https://www.taxscan.in/top-stories/big-gst-change-from-july-2026-gstr-3b-itc-locking-explained-1448389); [GSTRecoPro 2026 guide](https://gstrecopro.in/blogs/gstr-3b-hard-locking-2026-guide). One blog conflicts, claiming a hard block (ITC above 2B rejected) from the April 2026 return. — [TaxGarden](https://taxgarden.in/blog/gstr-3b-itc-hard-block-april-2026-action-plan)
- **IMS (Invoice Management System):** live on the GST portal from October 2024. Sources give 1 October 2024 or 14 October 2024 as the start date. Recipients can Accept, Reject or keep Pending each supplier invoice. Accepted invoices flow into GSTR-2B as eligible ITC; rejected ones are excluded and the supplier is notified; pending ones stay out of 2B and 3B, but only within the Section 16(4) time limits. No action means deemed acceptance. Any action after the 14th requires recomputing GSTR-2B. — [TaxGuru: IMS w.e.f. 01.10.2024](https://taxguru.in/goods-and-service-tax/gst-invoice-management-system-w-e-f-01-10-2024-simplified.html); [Masters India: IMS](https://www.mastersindia.co/blog/invoice-management-system-ims-gst/); [Tally: IMS cycle](https://tallysolutions.com/gst/ims-gst-cycle-how-it-works/)
- **3-year time bar on returns:** the Finance Act 2023 and Notification 28/2023-CT (effective 1 October 2023) bar filing GSTR-1, GSTR-3B, GSTR-4 through GSTR-9 and related returns more than three years after the due date. GSTN said on 7 June 2025 that the portal would enforce this from the July 2025 tax period, then moved it to the September 2025 period (advisory of 9 September 2025) and to the November 2025 period (advisory of 29 October 2025). Its illustration shows October 2022 GSTR-1/3B and FY 2020-21 GSTR-9/9C barred from 1 December 2025. — [GSTN Advisory No. 379 (MahaGST copy)](https://www.mahagst.gov.in/public/uploads/gstnadvisory/1768890686_379%20Advisory%20to%20file%20pending%20returns%20before%20expiry%20of%20three%20years.pdf); [Taxmann](https://www.taxmann.com/post/blog/gstn-advisory-on-filing-pending-gst-returns-before-three-year-expiry); [BDO India](https://www.bdo.in/en-gb/news/2024/gst-return-filing-time-limit-soon-no-filing-to-be-allowed-after-3-years-of-due-date)
- **GST rate structure ("GST 2.0"), effective 22 September 2025:** the main slabs fell from four to two, 5% and 18%, with the 12% and 28% slabs dropped. Most 28% items moved to 18% and most 12% items to 5%. A 40% rate applies to select luxury and "sin" goods (tobacco, sugary drinks, gambling, some luxury vehicles). Compensation cess continued for pan masala, gutka and tobacco until the government decided otherwise; one later source says it was withdrawn on 1 February 2026. — [EY Tax Alert (Sep 2025)](https://www.ey.com/content/dam/ey-unified-site/ey-com/en-in/alerts-hub/2025/09/gst-council-announces-major-rate-rationalization-and-trade-facilitation-measures.pdf); [Busy: GST 2.0 slabs](https://busy.in/gst/gst-2-0-transition-new-slab-rates.md); [Moneylife GST 2.0 FAQs](https://moneylife.in/article/gst-20-faqs/78175.html). Some sources conflict on whether certain goods remain at 28% plus cess.

**E-invoicing (IRN via IRP)**
- **Threshold:** e-invoicing is mandatory for B2B and B2G invoices (and credit/debit notes) of taxpayers whose aggregate turnover exceeded **₹5 crore in any preceding financial year from 2017-18**. Set by CBIC Notification 10/2023-CT dated 10 May 2023, **effective 1 August 2023** (previously ₹10 crore). — [EY alert (May 2023)](https://www.ey.com/en_in/technical/alerts-hub/2023/05/cbic-lowers-turnover-threshold-for-e-invoicing-to-inr5-crores-with-effect-from-1-august-2023); [Fonoa](https://www.fonoa.com/resources/blog/india-lowers-e-invoicing-threshold-to-inr-50-million)
- **30-day reporting rule:** from **1 April 2025**, taxpayers with **AATO of ₹10 crore or more** cannot report an invoice, credit note or debit note to the IRP more than 30 days after the document date. Example: an invoice dated 1 April 2025 cannot be reported after 30 April 2025. Announced by GSTN advisory of 5 November 2024. Before this, the rule applied only to AATO of ₹100 crore or more, from 1 November 2023 under the 13 September 2023 advisory. No time restriction applies below ₹10 crore AATO. — [Taxmann: GSTN update](https://www.taxmann.com/post/blog/time-limit-of-30-days-for-reporting-e-invoice-on-irp-portal-for-taxpayers-with-aato-of-10-crores-and-above-gstn-update/); [GSTN Advisory No. 293 (MahaGST copy)](https://www.mahagst.gov.in/public/uploads/gstnadvisory/1760531580_293%20Advisory%20Time%20Limit%20for%20Reporting%20e%20Invoice%20on%20the%20IRP%20Portal%20%20Lowering%20of%20Threshold%20to%20AATO%2010%20Crores%20and%20Above.pdf)
- A CA commentator argues the 30-day limit is an operational GSTN rule rather than a change to Section 31 of the CGST Act. This is one opinion. — [TaxGuru](https://taxguru.in/?p=957992)
- An industry report flags a further cut in the e-invoicing threshold below ₹5 crore as the "next demand shock" on the regulatory watch list. This is speculation, not a notified change. — [Turia 2026](https://turia.in/articles/indian-accounting-software-industry-report-2026/)

**E-way bill**
- **Threshold:** e-way bills are generally required for consignments above ₹50,000. Some states set their own intra-state limits; West Bengal and J&K, for example, follow ₹50,000. — [Busy: state-wise e-way bill thresholds](https://busy.in/gst/state-wise-threshold-limits-for-e-way-bills.md)
- **From 1 January 2025:** an e-way bill can only be generated for documents dated within 180 days, and extensions are capped at 360 days from the original generation date. — [GSTN Advisory No. 309 (MahaGST copy)](https://www.mahagst.gov.in/public/uploads/gstnadvisory/1760530021_309.Advisory%20on%20Updates%20to%20E-Way%20Bill%20and%20E-Invoice%20Systems.pdf); [Cashflo: what's new for 2025](https://www.cashflo.io/magazine/e-way-bill-e-invoice-systems-whats-new-for-2025)
- **Multi-factor authentication for e-way bill and e-invoice portals:** mandatory for AATO above ₹20 crore from 1 January 2025, above ₹5 crore from 1 February 2025, and for all taxpayers from 1 April 2025. — [Taxonation](https://taxonation.com/show-detail-news/2187318/multi-factor-authentication-required-for-e-way-bill-and-e-invoice-generation-for-all-gst-assesses-from-april-1-2025); [Maritime Gateway](https://www.maritimegateway.com/creation-of-e-way-bills-and-e-invoices-require-multi-factor-verification/)

**TDS / TCS (Income-tax Act 2025 in force from 1 April 2026)**
- The Income-tax Act 2025 replaced the 1961 Act from **1 April 2026**, with 536 sections, 23 chapters and 16 schedules. The 194-series TDS sections are consolidated into a table in **Section 393**. Salary TDS is in Section 392 and TCS in Section 394. — [Wikipedia: Income-tax Act, 2025](https://en.wikipedia.org/wiki/Income-tax_Act,_2025); [TaxGarden: old vs new TDS numbers](https://taxgarden.in/blog/income-tax-act-2025-section-393-tds-new-numbers-old-194c-194j-194q)
- The old 1961 section numbers apply to payments up to 31 March 2026, and FY 2025-26 returns and certificates keep them. From 1 April 2026 ("Tax Year 2026-27"), the new references and 4-digit payment codes apply. Form 16 becomes Form 130, Form 16A becomes Form 131, and Form 27D (TCS certificate) becomes Form 133. — [TaxGarden](https://taxgarden.in/blog/income-tax-act-2025-section-393-tds-new-numbers-old-194c-194j-194q)
- Rates and thresholds for the sections SMEs use most often. These are carried over "as revised by Finance Act 2025", so the same figures apply in FY 2025-26 and Tax Year 2026-27. — [TaxGarden](https://taxgarden.in/blog/income-tax-act-2025-section-393-tds-new-numbers-old-194c-194j-194q); [OneFinOps mapping](https://onefinops.com/blog/section-194-to-393-tds-mapping-guide-fy-2026-27)

  | Old (1961 Act) | New ref (2025 Act) | Payment code(s) | Rate | Threshold |
  |---|---|---|---|---|
  | 194C contractors | 393(1) Sl. 6(i) | 1023 (Ind/HUF), 1024 (others) | 1% Ind/HUF; 2% others | ₹30,000 single payment / ₹1,00,000 aggregate per year |
  | 194J professional / technical fees | 393(1) Sl. 6(iii) | 1027 (professional), 1026 (technical) | 10% / 2% | ₹50,000 |
  | 194H commission / brokerage | 393(1) Sl. 1(ii) | 1006 | 2% | ₹20,000 |
  | 194I rent | 393(1) Sl. 2(ii) | 1009 (land/building), 1008 (plant/machinery) | 10% / 2% | ₹50,000 per month or part of a month |
  | 194Q purchase of goods | 393(1) Sl. 8(ii) | 1031 | 0.1% | Purchases above ₹50 lakh from one seller, where the buyer's previous-year turnover exceeds ₹10 crore |
  | 194A interest (non-bank) | 393(1) Sl. 5(ii) | 1020 / 1021 | 10% | ₹50,000 (₹1,00,000 for senior citizens, per the page) |

- **Conflicts:** one source gives the 194I threshold as ₹6,00,000 per FY and another as ₹50,000 per month, which are the same amount annualised. An older FY 2025-26 chart still shows 194H at 5%; newer sources use 2%. — [TaxGarden](https://taxgarden.in/blog/income-tax-act-2025-section-393-tds-new-numbers-old-194c-194j-194q); [CalcGuru](https://calcguru.in/section-393-tds-fy-2026-27-transition-guide/); [Tax2win](https://tax2win.in/guide/tds-rate-chart)
- **206C(1H) TCS on sale of goods:** not applicable from 1 April 2025 under Finance Act 2025. From that date only 194Q TDS by the buyer applies to sale of goods. Sources differ on whether the sub-section was formally "omitted" or made inapplicable by a proviso. — [Income Tax India: TDS on purchase of goods](https://www.incometaxindia.gov.in/w/tds-on-purchase-of-goods); [TaxGuru](https://taxguru.in/?p=947512); [TDSMan: changes w.e.f. 1 April 2025](https://blog.tdsman.com/tag/section-206c1h/)
- Payment codes are new, and sources disagree on the starting code (1001 vs 1005). They advise verifying against incometax.gov.in. — [TaxGarden](https://taxgarden.in/blog/income-tax-act-2025-section-393-tds-new-numbers-old-194c-194j-194q)

**Audit trail / edit log: proviso to Rule 3(1), Companies (Accounts) Rules 2014**
- The proviso was inserted by G.S.R. 205(E) dated 24 March 2021. It was deferred by G.S.R. 235(E) (31 March 2022) and the requirement applies to **financial years commencing on or after 1 April 2023**. — [AMSS (Shardul Amarchand)](https://www.amsshardul.com/insight/audit-trails-under-the-companies-act-a-hazy-path-ahead/); [EIRC-ICAI material on Rule 11(g)](https://www.eirc-icai.org/uploads/background_materials/REPORTING%20UNDER%20RULE%2011(g)%20of%20the%20Companies%20(Audit%20&%20Auditors)%20Rules,%202014%20(1)%20(4)_1712134060.pdf)
- **What the software must do:** (1) record an audit trail of each and every transaction; (2) create an edit log of each change made in the books of account, with the date the change was made; (3) ensure the audit trail feature cannot be disabled. — [ClearTax News](https://news.cleartax.in/mandatory-to-use-accounting-software-with-audit-trail-mca/6016/amp); [Setindiabiz guide](https://www.setindiabiz.com/blog/audit-trail-compliance-accounting-software-mca-guidelines); [Tally: Audit Trail in TallyPrime](https://tallysolutions.com/tally/audit-trail-in-tallyprime/)
- **Applies to all companies under the Companies Act 2013**, including banks and NBFCs. — [TaxGuru: Rule 11(g) FAQs](https://taxguru.in/company-law/reporting-paragraphs-audit-report-faqs-audit-trail-rule-11g.html)
- **ICAI-style interpretations relevant to software design:** every change must be logged and kept, and keeping only the latest change does not comply. An error log is not enough. The audit trail must also be enabled "at the database level", even where database access is limited to one user. A backup alone does not ensure compliance. — [TaxGuru: Rule 11(g) FAQs](https://taxguru.in/company-law/reporting-paragraphs-audit-report-faqs-audit-trail-rule-11g.html)
- **Auditor reporting (Rule 11(g), Companies (Audit and Auditors) Rules):** the auditor must state whether the software had the feature, whether it operated throughout the year for all relevant transactions, whether it was tampered with, and whether it was preserved as required. Auditors cannot rely on management representations alone. — [TaxGuru: Rule 11(g) FAQs](https://taxguru.in/company-law/reporting-paragraphs-audit-report-faqs-audit-trail-rule-11g.html)
- **Retention and backup:** books must be kept for 8 financial years (Section 128(5)), and commentary says the audit trail should be kept as long. Rule 3(5) requires daily backups on servers physically in India. (Secondary source, paraphrased.) — [Setindiabiz](https://www.setindiabiz.com/blog/audit-trail-compliance-accounting-software-mca-guidelines)
- **Penalties under Section 128 (as stated by the secondary source):** company ₹25,000 to ₹5,00,000; directors/KMP ₹50,000 to ₹5,00,000. — [Setindiabiz](https://www.setindiabiz.com/blog/audit-trail-compliance-accounting-software-mca-guidelines)
- **Suggested log fields (secondary-source best practice):** transaction particulars; before and after values; user identity and role; creation and modification timestamps from server-synchronised time; deletions and reversals; login and access logs. — [Setindiabiz](https://www.setindiabiz.com/blog/audit-trail-compliance-accounting-software-mca-guidelines)
- **How vendors implemented it:** TallyPrime's Edit Log records the date, time and user of each change, tracks deleted vouchers and changes to ledgers, groups and stock items, and lets users compare versions. — [Tally: Audit Trail (Edit Log)](https://tallysolutions.com/tally/audit-trail-in-tallyprime/); [TallyPrime release-wise features](https://help.tallysolutions.com/tally-prime/welcome-to-tally-prime/tallyprime-features/)

### Inferences
- **The audit trail is a schema decision, not a feature to add later.** The double-entry core should use append-only voucher versions or an immutable change-log table: who, when, before and after, with soft deletes. No admin switch should turn it off, and it should cover master data (ledgers, groups) as well as vouchers. ICAI guidance expects logging at the database level, so SQLite triggers writing to a log table are a natural fit. Without this, any company client's auditor must qualify the Rule 11(g) report.
- **GSTR-1 accuracy now decides GSTR-3B liability** because of the hard lock. The app's existing register checks should become a "pre-filing GSTR-1 vs books" reconciliation, with a GSTR-1A amendment workflow.
- **ITC must be reconciled against GSTR-2B and IMS actions**, whether or not the Table 4A lock is notified. Purchase vouchers need an ITC status field (eligible, ineligible, pending-IMS, rejected, reversed).
- **Tax masters must be date-effective.** GST rates changed on 22 September 2025, TDS law changed on 1 April 2026, and 206C(1H) ended on 1 April 2025. Storing rates and sections with valid-from and valid-to dates, and both old and new TDS section references, avoids breaking FY 2025-26 data.
- **E-invoicing is mandatory only above ₹5 crore AATO.** Many micro and small clients will be below that, but anyone above needs IRN/QR on B2B invoices. Above ₹10 crore the 30-day rule makes an "IRN not generated, X days left" alert valuable.
- **Rule 3(5) daily backup on Indian servers** affects hosting: the SQLite file and backups for company clients should sit in an Indian region.

### Gaps
- No official GSTN advisory confirming or denying the GSTR-3B Table 4A (ITC) hard lock as of October 2026 was found. Check gst.gov.in/newsandupdates.
- No CBIC notification after 2023 revising the ₹5 crore e-invoice threshold was found. As of the latest sources it remains ₹5 crore, but there is no official 2026 confirmation.
- Whether the 3-year return time bar went live on the portal from the November 2025 tax period was not confirmed by a post-December 2025 source.
- The exact gazette text of the Rule 3(1) proviso, the ICAI Implementation Guide on Rule 11(g) (2024 revised edition), and the Rule 3(5) text were not fetched directly.
- Names and due dates of the TDS/TCS quarterly statements under the 2025 Act (successors to 24Q/26Q/27Q/27EQ) were not confirmed. Check CBDT notifications and incometax.gov.in.
- Whether LLPs or proprietorships have any equivalent audit-trail obligation was not established. The sources only cover companies.
- Exact HSN-level GST rates after 22 September 2025, including special rates for gold and diamonds, were not verified.

---

## Q3. What do Indian SME users rate as most important, and what are the common pain points?

### Takeaway
Hard survey data on which specific accounting features SMEs value is scarce. Available evidence points to the following priorities: fast GST-compliant billing; GST return preparation; receivables and payables tracking; inventory; low price or free tiers; mobile access; offline and local data; vernacular UI; and compatibility with the CA's tool, which is usually Tally. Pain points:
- Cost
- Steep learning curve and need for training (Tally, Busy)
- Setting up tools
- Slow multi-user performance
- Few integrations
- Lock-in, because the accountant knows Tally

### Cited Findings
- **Tally dominance (contested):** "reported at over 75% share". Trade press cites "over 80%", and a PCQuest reader survey put usage nearer 51%. — [Turia Industry Report 2026](https://turia.in/articles/indian-accounting-software-industry-report-2026/)
- **Software penetration:** among tech-savvy MSMEs, 29% use accounting software, 17% POS and 14% CRM. 6% still rely on manual methods. Barriers: 36% cite resistance to new technology and 18% cite high implementation costs. (PayNearby MSME Digital Index 2024) — [BW Businessworld](https://www.businessworld.in/article/about-36-msmes-struggle-with-tech-adoption-18-cite-high-costs-report-524353)
- **Setup difficulty:** a December 2025 study of 7,835 MSMEs found 36.8% find "navigating and setting up digital tools" somewhat or very challenging, and 35.6% struggle with "finding the right digital tools". — [India SME Forum META Report Card 2025](https://indiasmeforum.org/digishaastra/assets/docs/Final-META-Report-Card-2025.pdf)
- **Zoho survey (June 2024, 5,149 MSMEs, vendor-sponsored):** high software cost, budget constraints, lack of tech skills and integration hassles are the top hurdles. — [Zoho press release](https://prezohoweb.zoho.com/news/zoho-survey-reveals-that-high-cost-of-software-a-top-hurdle.html)
- **Manufacturing SMEs (2026, n=500):** 42% cite resistance from staff and management as the main ERP barrier, ahead of software cost at 31%. 75 respondents use only Tally or accounting software. — [BSquare ERP Adoption Report 2026](https://www.bsquare.in/images/BSquare_ERP_Adoption_Report_2026_FINAL_updated%20.pdf)
- **What SMEs value, from market analysis rather than a survey:** billing and invoicing, inventory, receivables and payables, GST return preparation, and increasingly mobile use; simple, fast GST billing; offline use and vernacular UI for Tier 2–4 markets; a "my data on my computer" preference; freemium tiers. Willingness to pay for micro-businesses is about ₹0–5,000 a year. — [Turia 2026](https://turia.in/articles/indian-accounting-software-industry-report-2026/)
- **Structural pain points:**
  - Switching costs, because businesses stay with Tally since their accountants know it.
  - Vertical fragmentation (pharma batch/expiry, jewellery, textiles).
  - Intuit exited QuickBooks India in 2023. Turia's explanation is that it could not compete on local price, GST depth, the CA channel and entrenched Tally/Zoho.

  — [Turia 2026](https://turia.in/articles/indian-accounting-software-industry-report-2026/)
- **2026 trends:**
  - AI-native tools offering OCR of invoices and bank statements, auto-reconciliation and GST-code prediction.
  - CAs shifting from data entry to advisory work.
  - Embedded accounting via ONDC, Account Aggregator and e-invoicing.

  — [Turia 2026](https://turia.in/articles/indian-accounting-software-industry-report-2026/)
- **TallyPrime user reviews:** 4.5/5 on G2 (about 280 reviews). Complaints include a steep learning curve, few third-party integrations, slowness with large datasets, and slow customer service. Praise covers ease of use once learned, GST handling and inventory. — [G2: TallyPrime](https://ai.g2.com/product/tallyprime). On Capterra AU, 4.4/5 (228 reviews); one reviewer says "if more than 2 users are there, it becomes slow", and another raises the risk of remote access. — [Capterra AU: Tally](https://www.capterra.com.au/software/127762/tally-erp-9). SaaSworthy's review summary: steep curve for first-time users, dated UI, limited help resources. — [SaaSworthy: Tally reviews](https://www.saasworthy.com/product/tally/reviews)
- **Vendor ratings (self-published):** Vyapar 4.7 and myBillBook 4.7 user rating, per Vyapar's comparison page. Vendor and competitor pages describe Vyapar and myBillBook as needing no accounting knowledge, and Tally and Busy as needing training. — [Vyapar comparison page](https://vyaparapp.in/comparison-with-other-apps?brand=busy)

### Inferences
- The most valuable "proper accounting" features for Accounts.ai are those that remove the CA's need to re-key data into Tally: a Tally-compatible chart of accounts, Tally XML/Excel export, and bill-wise outstanding that matches what CAs expect. Accountant lock-in is the main documented switching barrier.
- Ease of setup is a measured pain point (36.8% in the META study). The Excel-upload-to-books flow, with sensible default ledgers created automatically, addresses it directly.
- AI chat over the ledger fits the 2026 trend (OCR, auto-reconciliation, GST-code prediction). Auto bank reconciliation and HSN/GST-rate suggestion are the AI features competitors are adding.
- Low willingness to pay at the micro end (₹0–5,000/yr) means compliance-heavy features (e-invoice, TDS, audit trail) are the natural paid tier. This matches Zoho's tiering.

### Gaps
- No independent 2024–2026 survey ranking specific accounting features (for example bank reconciliation vs ageing vs budgets) for Indian SMEs was found.
- No Zoho Books, Busy, Vyapar or myBillBook review-aggregate data (complaint themes) was retrieved. Only Tally reviews were found.
- The Tally market-share figure (51% to 80%+) is contested and none of the cited figures come from an audited source.

---

## Q4. What default chart of accounts and ledgers do these products create for a new company?

### Takeaway
TallyPrime defines the mental model Indian accountants use. It provides 28 predefined groups (15 primary: 9 Balance Sheet and 6 P&L; 13 sub-groups) and only 2 predefined ledgers, Cash and Profit & Loss A/c. All GST, bank, capital, sales, purchase and round-off ledgers are created by the user under those groups: GST ledgers under Duties & Taxes, banks under Bank Accounts, and so on.

### Cited Findings
- **TallyPrime primary groups (15).** Balance Sheet (9): Capital Account, Loans (Liability), Current Assets, Current Liabilities, Fixed Assets, Investments, Misc. Expenses (ASSET), Suspense A/c, Branch/Divisions. P&L (6): Direct Expenses, Direct Incomes, Indirect Expenses, Indirect Incomes, Purchase Accounts, Sales Accounts. — [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)
- **TallyPrime sub-groups (13) with parent:** Bank Accounts (Current Assets); Bank OD A/c (Loans (Liability)); Cash-in-hand (Current Assets); Deposits (Asset) (Current Assets); Duties & Taxes (Current Liabilities); Loans & Advances (Asset) (Current Assets); Provisions (Current Liabilities); Reserves & Surplus (Capital Account); Secured Loans (Loans (Liability)); Stock-in-hand (Current Assets); Sundry Creditors (Current Liabilities); Sundry Debtors (Current Assets); Unsecured Loans (Loans (Liability)). — [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)
- **Predefined ledgers:**
  - Cash, under Cash-in-hand, with an opening balance entered as on the books-beginning date.
  - Profit and Loss A/c, under Primary. It cannot be deleted, but it can be renamed or altered. The previous year's result carries forward as its opening balance and shows under liabilities. It is used for journals that transfer profit to Capital or Reserves.

  — [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)
- **Duties & Taxes** holds all tax accounts (GST, VAT, CENVAT, excise and so on). It shows total liability, or an asset for advances paid, with a per-item breakup. — [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)
- **Stock-in-hand:** with accounts integrated with inventory, stock values come from inventory records and cannot be edited manually. When not integrated, opening and closing stock are entered manually. — [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)

### Inferences
- **Recommended default seed for Accounts.ai** (inferred from Tally's group structure; ledger names are the commonly used ones and are not a vendor's documented default list):
  - The 28 Tally groups, including the Primary / Balance Sheet / P&L flags and nature (asset, liability, income, expense).
  - Ledgers: Cash; Profit & Loss A/c; Capital A/c (Capital Account); one bank ledger (Bank Accounts); Sales and Purchase ledgers per GST rate, or a single one (Sales Accounts / Purchase Accounts).
  - GST ledgers under Duties & Taxes: Output CGST, Output SGST/UTGST, Output IGST, Input CGST, Input SGST, Input IGST, plus Cess if needed. Optionally RCM payable and ITC-reversal ledgers.
  - TDS Payable ledgers per section, under Duties & Taxes.
  - Round Off, under Indirect Expenses or Indirect Incomes.
  - Suspense A/c; Opening Stock / Closing Stock under Stock-in-hand.
- Using Tally's group names directly helps CAs recognise the books and makes Tally import and export simpler, which addresses the switching-cost pain point.

### Gaps
- Zoho Books India's default chart of accounts (account types and pre-created accounts such as "Output CGST" or "Input Tax Credits") was not retrieved. Zoho's help pages returned only question titles.
- Default ledgers in Vyapar, myBillBook, Busy and Marg were not found. Busy and Marg are believed to use Tally-like group trees, but this was not verified in this session.
- Tally's GST ledger configuration (tax type, GST rate on ledger, round-off method) is documented on a separate help page that was not fetched.

---

## Q5. How do these products handle financial years, opening balances, period locking, and multiple companies or branches?

### Takeaway
Indian products assume an April–March financial year, a "books beginning from" date with opening balances on ledgers, and year-end carry-forward of P&L into the P&L A/c ledger. Tally can split company data by year. Period locking is explicit in Zoho, through module-wise lock dates in the Standard plan and above. Tally emphasises its Edit Log rather than a hard lock. Multi-GSTIN in one company (Tally Rel 3.0), multi-branch (Busy "Power" plan) and multiple firms (Vyapar) are standard upper-tier capabilities.

### Cited Findings
- Tally's Cash ledger opening balance is entered "as on the books beginning day". The P&L ledger carries the previous year's profit or loss forward as its opening balance. — [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)
- TallyPrime Release 6.0 added "data split with a simplified single-company option" (splitting a company's data by period). — [TallyPrime release-wise features](https://help.tallysolutions.com/tally-prime/welcome-to-tally-prime/tallyprime-features/)
- TallyPrime supports multiple GST registrations in a single company (Release 3.0). It has a "Branch/Divisions" primary group for branch accounting. — [TallyPrime release-wise features](https://help.tallysolutions.com/tally-prime/welcome-to-tally-prime/tallyprime-features/); [Tally Help: Ledgers and Groups](https://help.tallysolutions.com/ledgers-and-groups-in-tallyprime/)
- Zoho Books transaction locking prevents adding, modifying or deleting transactions dated before the lock date. Locks can be set per module or as one date for all. Zoho's KB covers whether a lock can be disabled to edit past transactions, and why transactions can still be created on the lock date. — [Zoho Books Help: Transaction Lock](https://zstatic.zohostatic.com/books/help/accountant/transaction-lock.md); [Zoho Books Accountant KB](https://zstatic.zohostatic.com/in/books/kb/accountant)
- Zoho Books gates "transaction period locking" in Standard and above, "custom user roles" in Professional and above, and offers a "Locations" add-on with one GSTIN. Vyapar claims Zoho Books allows only one business per subscription, while Vyapar allows unlimited firms. — [Zoho Books India Pricing](https://www.zoho.com/in/books/pricing/); [Vyapar comparison page](https://vyaparapp.in/comparison-with-other-apps?brand=busy) (competitor claim)
- Busy positions multi-branch management in its "Power" plan. — [Busy: Compare](https://busy.in/compare/)
- Vyapar claims "multiple firms in one app" and "multi-user management with permissions". — [Vyapar comparison page](https://vyaparapp.in/comparison-with-other-apps?brand=busy)
- TallyPrime 7.0 added scheduled auto backup to TallyDrive or local storage. — [TallyPrime 7.0 search summary / release-wise features](https://help.tallysolutions.com/tally-prime/welcome-to-tally-prime/tallyprime-features/)

### Inferences
- **Must-have:** company master with FY start (default 1 April) and books-beginning date; opening balances for ledgers, including bill-wise opening for debtors and creditors, opening stock and opening GST credit balances; a validation that total Dr equals total Cr in opening balances, with any difference posted to an "Opening Difference" or Suspense account.
- **Must-have, given Rule 3(1):** a lock date (period lock) so that filed GST periods and audited years cannot be silently changed. Any unlock or edit should itself be written to the audit trail. Zoho's model is a good reference for SQLite: a per-module lock date checked in a trigger or service layer.
- **Year-end close:** carry the P&L result into the P&L A/c ledger (Tally model), or transfer it to Capital/Reserves via journal. Carry forward balance-sheet ledger balances and open bill-wise items. Do not require a hard "split" of the database.
- **Multi-company** (one login, many companies, with CA firms as power users) is should-have early, since CAs manage many clients. **Multi-GSTIN or branches within one PAN** is should-have for growing SMEs.

### Gaps
- Tally's official handling of period locking (whether TallyPrime has a native "lock period" beyond security controls and the Edit Log) was not confirmed. No source was found.
- Busy, Marg and myBillBook handling of FY change, carry-forward and opening balances was not retrieved.
- Zoho Books' detailed opening-balance workflow (opening balance adjustments account, migration date) was not fetched.

---

## Q6. Synthesis: what is the prioritised feature inventory and build order for Accounts.ai's double-entry core?

### Takeaway
"Complete" for an Indian SME in 2026 has three layers:
1. **Statutory-grade books:** vouchers, ledgers, bill-wise outstanding, bank reconciliation, the three financial statements, and a non-disableable audit trail with period locks.
2. **GST compliance loop:** GSTR-1/1A from books, 3B from 1A, 2B/IMS-driven ITC, e-invoice and e-way bill.
3. **Payments-side compliance:** TDS under the new Section 393 table.

The advanced layers come after these: cost centres, budgets, multi-currency, fixed assets, multi-branch, payroll and inventory depth. Vendor tiering supports this split. Zoho's Free tier has journals, bank reconciliation and GST filing. Its Standard tier adds e-invoice, IMS and period lock. Professional adds multi-currency and roles; Premium adds fixed assets, budgets and payroll. Tally switches off cost centres, bill-wise and interest by default.

### Cited Findings
- Zoho Books tier gating: Free = journals, bank rec, GST filing, 50+ reports; Standard = e-invoicing, period locking, IMS; Professional = multi-currency, custom roles, approvals; Premium = fixed assets, budgets, cash-flow forecasting, payroll; Elite = batch/serial/warehouse inventory. — [Zoho Books India Pricing](https://www.zoho.com/in/books/pricing/)
- Tally F11 optional features (cost centres, interest calculation, bill-wise) default to "No". — [Tally Help: Company Features (F11)](https://help.tallysolutions.com/company-features-f11-tally/)
- Audit trail is mandatory for all companies for FYs beginning on or after 1 April 2023, cannot be disabled, and auditors must report on it under Rule 11(g). — [TaxGuru: Rule 11(g) FAQs](https://taxguru.in/company-law/reporting-paragraphs-audit-report-faqs-audit-trail-rule-11g.html); [ClearTax News](https://news.cleartax.in/mandatory-to-use-accounting-software-with-audit-trail-mca/6016/amp)
- GSTR-3B liability has been locked to GSTR-1/1A since the July 2025 tax period. — [A.S. Banka & Co](https://asbanka.com/2026/06/23/gstr-3b-hard-locking-gstr-1a-ims-itc/)
- E-invoicing applies above ₹5 crore AATO (since 1 August 2023), with the 30-day IRP limit for AATO of ₹10 crore or more (since 1 April 2025). — [EY](https://www.ey.com/en_in/technical/alerts-hub/2023/05/cbic-lowers-turnover-threshold-for-e-invoicing-to-inr5-crores-with-effect-from-1-august-2023); [Taxmann](https://www.taxmann.com/post/blog/time-limit-of-30-days-for-reporting-e-invoice-on-irp-portal-for-taxpayers-with-aato-of-10-crores-and-above-gstn-update/)
- TDS moved to Section 393 of the Income-tax Act 2025 from 1 April 2026. — [TaxGarden](https://taxgarden.in/blog/income-tax-act-2025-section-393-tds-new-numbers-old-194c-194j-194q)
- Turia identifies AI OCR, auto-reconciliation and GST-code prediction as the 2026 differentiators, and accountant lock-in to Tally as the main switching barrier. — [Turia 2026](https://turia.in/articles/indian-accounting-software-industry-report-2026/)

### Inferences

**MUST-HAVE (Phase 1: the double-entry core; without these the app is not "proper accounting")**
1. **Company and FY setup:** company name, PAN, GSTIN(s) and state, FY start (1 April), books-beginning date, base currency INR, decimal and rounding rules.
2. **Chart of accounts:** Tally's 28-group hierarchy (15 primary, 13 sub) seeded by default; user-defined sub-groups; ledgers with type and nature, and GST/PAN/state on party ledgers.
3. **Default ledgers:** Cash, P&L A/c, Capital, Bank, Sales, Purchase, Output/Input CGST/SGST/IGST, Round Off, Suspense.
4. **Opening balances:** ledger-wise Dr/Cr, bill-wise opening for debtors and creditors, opening stock value; a balancing check with the difference posted to a suspense account.
5. **Voucher engine:** Sales, Purchase, Receipt, Payment, Contra, Journal, Credit Note and Debit Note, enforcing Dr = Cr. Sales and purchase vouchers auto-post GST from party state vs company state (CGST+SGST vs IGST) and post round off. Voucher numbering per series and FY, which GST requires to be unique per FY.
6. **Bill-wise outstanding:** new reference, against reference, advance, on account; receivables and payables ageing; party statements.
7. **Books and registers:** day book, cash book, bank book, ledger account, journal register, sales and purchase registers (link to the existing register comparison).
8. **Financial statements:** trial balance (grouped and ledger-wise), P&L, balance sheet with drill-down to vouchers; closing stock handling.
9. **Audit trail and edit log:** immutable, cannot be disabled, covering vouchers and masters, recording user, timestamp, before and after values, and soft-deleted records. Kept for 8 years. Viewable report with version compare (Tally's Edit Log is the reference UX).
10. **Period lock and year-end close:** lock date (global or per module); carry forward balances and open bills to the next FY; P&L into Capital/Reserves.
11. **Bank reconciliation:** import a bank statement from Excel/CSV (fits the existing import pipeline); match to vouchers; BRS report; create vouchers from unmatched statement lines.
12. **GST from books:** GSTR-1 (B2B, B2CL, B2CS, CDNR, HSN summary with B2B/B2C split, document summary) and GSTR-3B computed from vouchers; reconciliation of GSTR-2B against the purchase register, already partly built.
13. **Users and roles (basic):** owner, accountant, data-entry and view-only. Every action is attributed to a user, which the audit trail requires.
14. **Excel import and export of masters and vouchers,** plus Tally-compatible export (XML or Excel) so CAs can take data into Tally.

**SHOULD-HAVE (Phase 2: compliance depth and what growing SMEs expect)**
1. **TDS:** section master with date-effective entries (1961 Act numbers for FY 2025-26 and earlier, Section 393 table refs and payment codes from 1 April 2026); threshold tracking per party (194C single and aggregate, 194J ₹50k, 194H ₹20k, 194I ₹50k per month, 194Q ₹50 lakh); auto-deduction on purchase or payment; TDS payable ledgers; challan and quarterly-return data export. TCS on sale of goods is **not** needed after 1 April 2025 (206C(1H) ended), but other TCS heads may be.
2. **IMS workflow mirror:** accept, reject and pending status per supplier invoice; ITC status on purchase vouchers; GSTR-1A amendment tracking; a pre-3B check that books equal GSTR-1/1A.
3. **E-invoice** (IRN and QR through IRP/GSP API) for clients above ₹5 crore AATO, with a 30-day countdown for AATO of ₹10 crore or more. **E-way bill** generation for consignments above ₹50,000, respecting the 180-day document and 360-day extension limits.
4. **Date-effective GST rate and HSN master,** reflecting the 22 September 2025 slabs (5/18/40) and preserving earlier rates for older invoices.
5. **Multi-company** (CA firm view) and **multi-GSTIN or branches** under one company.
6. **Cash-flow statement, ratio analysis, interest on overdue bills, payment reminders** (WhatsApp/email).
7. **Credit and debit note linkage** to the original invoice; recurring and reversing journals; vouchers in draft or approval state.
8. **Daily automated backup** stored in India, for Rule 3(5) for company clients.
9. **Fixed asset register with depreciation** (Companies Act and Income-tax rates). Zoho treats this as Premium, so it can be late Phase 2.
10. **Basic inventory linked to sales and purchase** (item, HSN, unit, quantity, rate, stock valuation) if clients are traders. Billing-first competitors all include this.

**NICE-TO-HAVE (Phase 3: advanced or vertical)**
1. Cost centres and cost categories, job costing, budgets and variance, scenarios. These are optional in Tally and Premium in Zoho.
2. Multi-currency vouchers with forex gain/loss (exporters and importers). Professional tier in Zoho.
3. Advanced inventory (godowns, batch and expiry, serial numbers, BOM/manufacturing) and POS. Only needed for pharma, FMCG or manufacturing verticals (Marg, Busy territory).
4. Payroll (PF/ESI/PT, Form 130 under the new Act). Keep brief; often outsourced.
5. Connected banking or Account Aggregator feeds; UPI payment links on invoices; Bharat Connect-style B2B invoice exchange.
6. Direct GSTN filing (GSP integration for GSTR-1/3B upload). JSON export is an acceptable interim.
7. AI layer: OCR of bills and bank statements, automatic ledger and HSN/GST-rate suggestion, anomaly detection on the audit trail, natural-language queries over the ledger (the existing AI chat). This is the 2026 differentiator rather than a completeness item.
8. Vernacular UI and mobile app.

**Suggested build order (dependency-driven):**
1. Schema: company/FY, groups, ledgers, voucher header and lines, immutable audit log via SQLite triggers, lock dates.
2. Seed the default chart of accounts and GST ledgers; opening balances.
3. Voucher entry and Excel import of vouchers with GST auto-posting.
4. Books, registers, trial balance, P&L and balance sheet.
5. Bill-wise outstanding and ageing.
6. Bank reconciliation from imported statements.
7. GSTR-1 and GSTR-3B from books, plus 2B/IMS reconciliation (reusing existing modules).
8. Period lock and year-end carry-forward.
9. TDS (Section 393 and legacy).
10. Multi-company and multi-GSTIN.
11. E-invoice and e-way bill APIs.
12. Advanced features (cost centres, budgets, multi-currency, fixed assets, inventory depth).

### Gaps
- No primary-source ranking of feature importance by Indian SMEs exists in the material found. The must/should/nice split above is inferred from vendor tiering (Zoho), defaults (Tally F11), legal mandates and market analysis (Turia).
- Schedule III (Companies Act) balance-sheet format requirements for company clients were not researched in this session. They are likely needed for company-format financial statements.
- MSME Form 1 / Section 43B(h) payables tracking (payment to MSE suppliers within 45 days, with a deduction disallowed otherwise) appears in TallyPrime 7.0 release notes as "revised MSME Form 1 Annexure" but was not researched. It may be a should-have for payables ageing.
