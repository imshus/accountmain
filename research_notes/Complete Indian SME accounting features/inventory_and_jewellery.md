# Inventory (Stock) Accounting for Indian SMEs, with Jewellery-Specific Handling (India, current to Oct 2026)

Research date: 22 Oct 2026. Convention used throughout: **[LAW]** = statute / notified standard / government order; **[RULING]** = advance ruling or tribunal order (binding only on that applicant or case); **[TRADE]** = trade practice or vendor convention, not law; **[INFERENCE]** = my own derivation from cited material. "Snippet-level" means the claim came from a search-result summary and the full page was not read. Pages read in full or from extracted text: BIS hallmarking-jewellers page, the ICAI EIRC AS 2 refresher deck (23 Apr 2026), the ELP/GJEPC GST presentation (2018), the Busy jewellery page, the Tally jewellery page, and the Patron Accounting AS 2 guide.

---

## Q1. Stock summary layout (Tally Prime / Busy / Marg); item groups, units of measure, godowns

### Takeaway
The Tally-style Stock Summary is a grouped item list (Stock Group > Stock Item, optionally by godown). For each row it shows Opening, Inwards, Outwards and Closing, each with Quantity, Rate and Value. Quantities always reconcile (Opening + In - Out = Closing). Values do not reconcile in Tally's default view, because Outwards is shown at **sales value** while Closing is shown at **cost**. A separate "Show Profit" view reconciles the value side using consumption at cost. Accounts.ai should show Outwards at cost (consumption) by default, with sales value and gross profit as optional columns.

### Cited Findings
- TallyPrime Stock Summary: in the item-wise view (F5) you press F12 (Configure) and enable "Show opening balances", "Show goods inwards" and "Show goods outwards" to get the Opening / Inwards / Outwards / Closing columns. Snippet-level — [Tally Help: Stock Summary](https://help.tallysolutions.com/stock-summary/); [Tally Help: Stock Summary FAQ](https://help.tallysolutions.com/tally-prime/inventory-reports/stock-summary-faq-tally/)
- In Tally, the report reconciles on quantity only: Opening qty + Inward qty - Outward qty = Closing qty. The outward value shows **sale values**, while closing value is **cost** under each item's costing method. For a value reconciliation, the "Show Profit" (F7) view shows opening, inward, outward, closing and **consumption value at cost**. Snippet-level — [Tally Help: Stock Summary FAQ](https://help.tallysolutions.com/tally-prime/inventory-reports/stock-summary-faq-tally/)
- Tally shows a negative value for a sold item when inward values are not maintained. Its fix is the item behaviour option "Treat all sales as new manufacture". Snippet-level — [Tally Help: Stock Summary FAQ](https://help.tallysolutions.com/stock-summary-faq-tally/)
- If stock items use different units (kg, pcs, nos, ltr, ...), Tally does not show a quantity under Grand Total. Snippet-level — [Tally Help: Stock Summary FAQ](https://help.tallysolutions.com/stock-summary-faq-tally/)
- Godown pitfall from Tally's FAQ: closing value doubled when a sale was booked against a different godown from the purchase. Tally advises using the same godown on both entries. Snippet-level — [Tally Help: Stock Summary FAQ](https://help.tallysolutions.com/tally-prime/inventory-reports/stock-summary-faq-tally/)
- TallyPrime costing methods are Average Cost (the default), FIFO, LIFO, Standard Cost, Last Purchase Cost and Zero Cost. The method can be set per stock item and is chosen at the start of the financial year. Stock Summary, Balance Sheet and P&L let you change the "Basis of Values" to see the effect of another method. The default market valuation method is Average Price. Snippet-level; the full Tally help page returned HTTP 500 — [Tally Help: Stock valuation methods](https://help.tallysolutions.com/tally-prime/inventory/stock-valuation-methods-tallyprime/)
- Busy (jewellery edition) advertises "Multi-Location Inventory (Shop, Godown)", gross/net weight details, purity tracking (22K/18K/14K) and "monitor stock valuation" — [Busy: Jewellery accounting software](https://busy.in/accounting-software/jewellery-shop/)

### Inferences
- **[INFERENCE] Recommended Accounts.ai stock summary layout** (generic SME):
  `Group / Item | Opening (Qty, Rate, Value) | Inwards (Qty, Value) | Outwards (Qty, Value at cost) | Closing (Qty, Rate, Value)`
  Optional columns: Outward sales value and gross profit, as in Tally's F7 view. Drill down: Group > Item > Item ledger (voucher-wise running balance) > Voucher. Filters: period, godown, item group, valuation method, "include zero/negative stock".
- **[INFERENCE] Jewellery layout.** Stock must be multi-measure. Every movement should carry Pcs, Gross Wt (g, 3 decimals), Net Wt (g), Fine Wt (g), Diamond Wt (ct, 2-3 decimals), Stone Wt (ct or g), and Value. The jewellery stock summary should therefore show Opening / In / Out / Closing for **pcs, gross wt, net wt, fine wt, diamond ct and value**. Grand totals should be shown only for like units (Tally suppresses grand-total quantity when units differ, per the FAQ above). The most important metal-control total is fine gold summed across all karats.
- **[INFERENCE] Masters needed:** Stock Groups (hierarchical, e.g. Gold Jewellery > Rings > 18K Diamond Rings), Stock Categories (an orthogonal classification), Units of Measure (simple units: pcs, g, ct, mg; compound/alternate units such as 1 ct = 0.2 g), and Godowns/Locations (shop, safe/vault, karigar-at-site, "with party on approval"). Godown must be mandatory on every stock line, so per-godown balances always add up to the company total.
- **[INFERENCE]** Tally offers LIFO as a costing option, but LIFO is not permitted under AS 2 / Ind AS 2 (see Q2). Accounts.ai should not offer LIFO for statutory closing stock, or should allow it only for internal/MIS views with a warning.

### Gaps
- Exact Busy and Marg stock-summary column layouts were not verified from vendor help pages (not reached within budget). Busy's jewellery page confirms only godown/multi-location and weight fields.
- How exactly Tally's "Average Cost" is computed (periodic over the reporting period vs moving after each receipt) could not be confirmed, because help.tallysolutions.com returned HTTP 500 for the valuation-methods page.

---

## Q2. Valuation methods allowed in India (AS 2 / Ind AS 2 / ICDS II), how FIFO and weighted average work, and how closing stock flows to the trading account and balance sheet

### Takeaway
**[LAW]** Inventories are carried at the **lower of cost and net realisable value (NRV)**, tested item by item. Permitted cost formulas are **FIFO** and **weighted average**. **Specific identification** is required for items that are not ordinarily interchangeable, such as unique tagged jewellery pieces. **LIFO is not permitted.** Cost includes purchase, conversion and other costs to bring stock to its present location and condition. Cost excludes recoverable taxes such as GST ITC (for accounts; income tax differs), abnormal wastage, storage, unrelated admin overheads and selling costs. For income tax, ICDS II and Section 145A apply, and they require tax-inclusive valuation.

### Cited Findings
- **[LAW] Measurement rule:** AS 2 para 5: "Inventories should be valued at the lower of cost and net realisable value", applied item by item in most cases rather than in aggregate. NRV = estimated selling price minus estimated costs of completion minus estimated costs to make the sale. Worked example: cost 5,00,000; expected sale price 5,50,000; selling commission 10% (55,000); NRV 4,95,000; so write down by 5,000 — [ICAI EIRC Refresher Course on AS 2, 23 Apr 2026](https://www.eirc-icai.org/uploads/background_materials/AS%202_1777005077.pdf)
- **[LAW] Cost of purchase** (AS 2 para 7) includes purchase price, duties and taxes *other than those subsequently recoverable from taxing authorities*, freight inwards and other directly attributable costs, less trade discounts, rebates and duty drawbacks. **Excluded:** available GST credit, abnormal wastage of materials/labour, storage costs (unless needed in production before a further stage), administrative overheads that do not help bring inventory to its present location and condition, selling and distribution costs, and borrowing costs (except as AS 16 permits) — [ICAI EIRC AS 2 deck](https://www.eirc-icai.org/uploads/background_materials/AS%202_1777005077.pdf); [Patron Accounting AS 2 guide](https://www.patronaccounting.com/accounting-standards/as-2-valuation-of-inventories)
- **[LAW] Cost formulas** (AS 2 paras 14-17): use FIFO or weighted average for ordinarily interchangeable items. Use specific identification for items that are not ordinarily interchangeable. The ICAI deck lists **"high-value jewellery"** as a specific-identification example. The chosen formula must be applied consistently — [ICAI EIRC AS 2 deck](https://www.eirc-icai.org/uploads/background_materials/AS%202_1777005077.pdf)
- **[LAW] LIFO:** "LIFO is NOT permitted under AS 2. Only FIFO, Weighted Average or Specific Identification may be used." — [ICAI EIRC AS 2 deck](https://www.eirc-icai.org/uploads/background_materials/AS%202_1777005077.pdf). An ITAT order involving a jeweller records that AS 2 prescribes FIFO or weighted average and does not permit LIFO, and that a company is bound by the standard — [ITAT, Roopshree Jewellers P Ltd (ITA 442 & 882/2015)](https://itat.gov.in/public/files/upload/1523960339-I.T.A.442&882-2015-Roopshree%20Jewellers%20P%20Ltd.pdf) (snippet-level)
- **[LAW] Weighted average** is based on the cost of similar items at the start of the period plus those bought or produced during it. The average may be calculated **periodically or as each additional shipment is received**, which permits both periodic and moving average. Snippet-level — [TaxManagementIndia extract of AS 2](https://taxmanagementindia.com/web/tmi_blog_details.asp?id=187913). IAS 2 / Ind AS 2 likewise permit FIFO or weighted average — [ICAEW IAS 2 summary](https://icaew.com/technical/corporate-reporting/ifrs/ifrs-accounting-standards-tracker/ias-2-inventories)
- **[LAW] Techniques:** standard cost and the retail method may be used for convenience only if the results approximate actual cost (AS 2 para 18) — [ICAI EIRC AS 2 deck](https://www.eirc-icai.org/uploads/background_materials/AS%202_1777005077.pdf)
- **[LAW] NRV specifics:** grouping is allowed only for similar items where separating them is impractical. Raw materials are **not** written down if the finished goods they go into are expected to sell at or above cost, even if replacement cost has fallen. With a firm sales contract, NRV uses the contract price. Indicators of NRV below cost include damage, fashion obsolescence, falling selling prices and slow-moving stock (ageing). Write-downs go to P&L. Reversals are allowed up to original cost — [ICAI EIRC AS 2 deck](https://www.eirc-icai.org/uploads/background_materials/AS%202_1777005077.pdf); [Patron Accounting](https://www.patronaccounting.com/accounting-standards/as-2-valuation-of-inventories)
- **[LAW] Disclosure:** the accounting policy including the cost formula; total carrying amount classified (raw materials, WIP, finished goods, stores and spares, loose tools, etc.); carrying amount at NRV; write-downs and reversals; inventories pledged as security — [Patron Accounting](https://www.patronaccounting.com/accounting-standards/as-2-valuation-of-inventories) (Patron's paragraph numbering looks unreliable; use for content only)
- **[LAW] Scope:** AS 2 applies to non-Ind AS entities. Ind AS companies apply Ind AS 2. Cost formulas, NRV and the LIFO prohibition are essentially the same in both — [Patron Accounting](https://www.patronaccounting.com/accounting-standards/as-2-valuation-of-inventories)
- **[LAW] Income tax:** Section 145A requires purchases, sales and inventory to include taxes, duties and cess actually paid or incurred. ICDS II para 5 includes all duties and taxes in purchase cost *irrespective of credit availability*. Ind AS 2 para 11 (and AS 2 para 7) include only non-recoverable taxes — [Lakshmikumaran & Sridharan article](https://cn.lakshmisri.com/insights/articles/inventory-valuation-caught-in-the-web-of-icds-indas-and-settled-jurisprudence). ICDS II also requires lower of cost or NRV — [TaxHeal ICDS II AY 2026-27](https://www.taxheal.com/?p=128532); [CBDT ICDS document](https://wmstatic-prd.incometaxindia.gov.in/documents/20117/42998/Income-Computation-and-Disclosure-Standards-ICDS_2026-03-19_04-32-57_099952_en.pdf/26ca3241-ac28-5b8e-7d32-31e9b15a4898)
- **[RULING]** ITAT has held that the GST-inclusive or exclusive method is tax-neutral if applied consistently across opening stock, purchases, sales and closing stock. Additions made only to closing stock are rejected — [ITAT, Infinite Water Solutions Pvt Ltd](https://itat.gov.in/public/files/upload/1705568514-3235%20Infinite%20Water%20Solutions%20Pvt%20Ltd..pdf); [ITAT Cochin, Marine Business Associates](https://itat.gov.in/public/files/upload/1727959764-558%20Marine%20Business%20Associates.pdf) (snippet-level)

### Inferences
**Worked example (all arithmetic checked).** Item: fine gold in grams. Rates are illustrative, not market prices.

| Date | Txn | Qty (g) | Rate (Rs/g) | Amount (Rs) |
|---|---|---|---|---|
| 1 Apr | Opening | 100 | 10,000 | 10,00,000 |
| 5 Apr | Purchase P1 | 200 | 10,500 | 21,00,000 |
| 10 Apr | Sale/issue S1 | 150 | | |
| 20 Apr | Purchase P2 | 100 | 11,000 | 11,00,000 |
| 25 Apr | Sale/issue S2 | 180 | | |
| | **Closing** | **70** | | Goods available = 400 g / Rs 42,00,000 |

- **FIFO:** S1 = 100 g x 10,000 + 50 g x 10,500 = 15,25,000. S2 = 150 g x 10,500 + 30 g x 11,000 = 19,05,000. COGS = 34,30,000. Closing = 70 g x 11,000 = **7,70,000**. Check: 42,00,000 - 34,30,000 = 7,70,000.
- **Periodic weighted average** (one rate for the whole period, including opening): 42,00,000 / 400 g = 10,500/g. Closing = 70 x 10,500 = **7,35,000**. COGS = 330 x 10,500 = 34,65,000.
- **Moving weighted average** (re-average after each receipt): after P1, 300 g / 31,00,000 = 10,333.33/g. S1 = 150 x 10,333.33 = 15,50,000, leaving 150 g / 15,50,000. After P2, 250 g / 26,50,000 = 10,600/g. S2 = 180 x 10,600 = 19,08,000. Closing = 70 g x 10,600 = **7,42,000**. COGS = 34,58,000.
- **NRV test:** if year-end NRV = 10,200/g, closing becomes 70 x 10,200 = 7,14,000 under every method. The write-downs are 56,000 (FIFO), 21,000 (periodic WA) and 28,000 (moving WA). If NRV is 11,500/g, no write-down applies. **[INFERENCE]** Gold that is raw material for jewellery expected to sell at or above cost should not be written down (AS 2 rule cited above).
- **[INFERENCE] Engine design:** keep FIFO cost layers (receipt-date queue per item per godown) **and** a running moving-average per item. Compute periodic average on demand at report time. Store the method per item (default moving or periodic WA), locked once a year has transactions; changing it is an accounting-policy change that needs disclosure. Backdated vouchers require re-costing all later outward entries (FIFO layers and moving average are path-dependent).
- **[INFERENCE] Jewellery method selection:** (a) **Tagged finished pieces** (each diamond piece with a tag/barcode) are not interchangeable, so use **specific identification**: the cost of each tag = metal cost + diamond cost (by stone lot) + stone + labour. (b) **Metal pool** (bullion, fine gold, karat-wise gold, scrap) is interchangeable, so use FIFO or weighted average **per fine gram**. (c) **Loose diamonds** of the same lot/sieve/quality are interchangeable within the lot, so use weighted average per carat per lot. Certified solitaires use specific identification.
- **[INFERENCE] Common non-compliant trade practice:** valuing closing gold at the year-end market rate (mark-to-market) when that rate is above cost is not AS 2 compliant. AS 2 permits cost or NRV, whichever is lower, and never market above cost.
- **[INFERENCE, standard bookkeeping; not separately sourced here] Flow to final accounts:**
  - *Periodic system:* Trading A/c Dr side has Opening Stock + Purchases (net of returns) + Direct expenses (wages, karigar labour, freight inward). Cr side has Sales (net) + Closing Stock. The balance is Gross Profit, carried to P&L. The closing-stock entry is "Closing Stock A/c Dr / To Trading A/c". Closing stock then appears under **Current Assets: Inventories** in the Balance Sheet and becomes next year's opening stock.
  - *Perpetual (software) system:* COGS = Opening + Purchases - Closing, or posted per sale at cost. The software should compute closing stock value from the stock ledger and post or derive it automatically. It should also let an auditor override closing value (e.g. NRV write-down) via a journal "Inventory write-down (P&L) Dr / Inventory Cr".
  - *Companies:* classify inventories (raw materials, WIP, finished goods, stock-in-trade, stores and spares, loose tools) and disclose the mode of valuation (Schedule III; text not retrieved in this research).
- **[INFERENCE] GST-inclusive toggle:** books follow AS 2 (exclude recoverable GST). Offer a tax-audit report that restates opening, purchases, sales and closing GST-inclusive for Section 145A / ICDS II, applied consistently across all four, per the ITAT reasoning.

### Gaps
- The primary ICAI AS 2 PDF (kb.icai.org) could not be fetched (TLS certificate error). Quotations are from the ICAI EIRC regional refresher deck (23 Apr 2026) and secondary sources. The "periodically or as each shipment is received" wording is from a TMI extract (snippet-level), not the ICAI PDF.
- AS 2 reversal-of-write-down treatment: the ICAI deck and Patron describe reversals up to cost (this wording follows Ind AS 2 para 33). AS 2's explicit text on reversals was not verified.
- Ind AS 2's commodity broker-trader exception (fair value less costs to sell) was not researched. It is unlikely to apply to a jewellery manufacturer or wholesaler.
- Schedule III inventory classification text was not retrieved.

---

## Q3. Jewellery-specific accounting: weights (gross/net/fine), tunch, wastage, karat conversions, metal accounts, labour, diamonds by carat, "Wt/Rs" settlement, karigar/job work

### Takeaway
Jewellery businesses run **two parallel ledgers for every party and every stock item**: a rupee ledger and a **metal (fine-gram) ledger**. Stock and party balances are reconciled in fine grams (Net Wt x Tunch/100), not only in rupees. Diamonds are valued per carat, labour per gram or per piece, and wastage is either built into tunch or charged separately. "Rate cut" turns a metal balance into rupees. This architecture is mostly **[TRADE]** practice, implemented by jewellery ERPs, rather than law. The legal anchors are AS 2 (abnormal wastage expensed, normal wastage part of cost), GST job-work rules (Section 143 / ITC-04) and DGFT export wastage norms.

### Cited Findings
- **Fine weight** = gross (or net metal) weight x purity. Example: a 10 g ring at 14 ct has about 5.83 g fine gold — [The Gold Bullion Co: What is fine weight](https://thegoldbullion.co.uk/what-is-fine-weight) (snippet-level; the example uses the theoretical 14/24 purity, while India's 14K hallmark grade is 585)
- **Karat grades.** **[LAW]** Jewellery sold in mandatory districts must be hallmarked in the grades of IS 1417, and may be hallmarked at the next lower grade — [BIS: Hallmarking - Jewellers](https://www.bis.gov.in/hallmarking-jewellers/?lang=en). 14K, 18K and 22K were the original mandatory grades — [Vikaspedia: Hallmarking of gold jewellery](https://en.vikaspedia.in/viewcontent/social-welfare/social-awareness/consumer-education/hallmarking-of-gold-jewellery-consumer-education-1/hallmarking-of-gold-jewellery). 20K, 23K and 24K were added later — [Indian Jeweller](https://www.indianjeweller.in/Indian-Jewellery-News/13080/index.html). **9K (minimum fineness 375)** was made subject to mandatory hallmarking from July 2025 — [Business Standard, 21 Jul 2025](https://www.business-standard.com/india-news/9-carat-gold-gets-bis-hallmarking-approval-affordable-jewellery-125072100728_1.html); [Greater Kashmir](https://m.greaterkashmir.com/article/bis-makes-hallmarking-of-9-karat-gold-mandatory/415593) (sources differ on June vs July 2025)
- **Wastage (retail framing):** wastage % = (initial weight - final weight) / initial weight x 100. Retail wastage is commonly quoted at 5-7% of gold weight, higher for intricate designs — [Bajaj Finserv: gold wastage calculation](https://bajajfinserv.in/gold-wastage-percentage-calculation) (snippet-level)
- **[LAW] DGFT export wastage norms:** handmade gold/platinum jewellery 2.25%; machine-made gold/platinum 0.45% — [BusinessWorld](https://businessworld.in/article/govt-revises-wastage-norms-for-gold-silver-platinum-jewellery-exports-537896) (snippet-level). ELP describes DGFT jewellery wastage norms as "ranging from 0.20% to 5%" — [ELP for GJEPC, GST presentation (2018)](https://gjepc.org/presentation/Gold%20jewellery%20summit-%20Nishant%20Shah.pdf)
- **[LAW] Job-work process loss:** Section 143(5) lets waste and scrap from job work be supplied by a registered job worker on payment of tax, or by the principal if the job worker is unregistered. It does **not** cover irrecoverable process or manufacturing loss. Unreconciled loss risks a GST demand on the principal: inputs not returned within 1 year are deemed supplied on the day they were sent. ITC-04 disclosure and internal records help justify process loss. Authorities may treat claimed loss as suppressed turnover — [ELP for GJEPC](https://gjepc.org/presentation/Gold%20jewellery%20summit-%20Nishant%20Shah.pdf)
- **[LAW] Job-work documentation:** job work = treatment or process on goods belonging to *another registered person* (Section 2(68)). Goods move under a delivery challan with Rule 55 details. The challan is endorsed by the job worker on return or onward movement, and a fresh challan is needed for piecemeal returns. The principal files ITC-04 (Section 143 read with Rule 45(3)) — [ELP for GJEPC](https://gjepc.org/presentation/Gold%20jewellery%20summit-%20Nishant%20Shah.pdf)
- **[LAW] AS 2:** abnormal wastage is excluded from inventory cost and expensed. Conversion cost (direct labour + production overheads at normal capacity) is included — [ICAI EIRC AS 2 deck](https://www.eirc-icai.org/uploads/background_materials/AS%202_1777005077.pdf)
- **[TRADE] Karigar metal tracking in software:** "Manage gold issued to karigars, track returns, wastage, and balance gold" — [Online Munim (Techjockey listing)](https://techjockey.com/detail/online-munim-jewellery) (snippet-level). An ERPNext jewellery app issues raw metal to artisans, receives finished pieces, and tracks wastage and making charges per job — [Ecosire ERPNext Jewellery & Bullion](https://ecosire.com/fr/apps/erpnext/erpnext-jewellery-bullion) (snippet-level)
- **[TRADE] Metal ledgers / rate cut:** a Tally jewellery add-on module tracks metal inventory, performs **rate cuts**, handles **metal loans**, and reports outstanding balances — [Scribd: Tally "Jewels Module" document](https://www.scribd.com/document/617847472/Jewels-Module) (user-uploaded document, snippet-level)
- **[TRADE] Daily rate card:** an ERPNext jewellery suite keeps dated per-karat gold rates and computes line metal value = net weight x current karat rate — [Ecosire ERPNext Jewellery Management](https://ecosire.com/es/apps/erpnext/erpnext-jewellery-management) (snippet-level)
- **[TRADE] Making charges:** Busy supports making charges as fixed or %, separate stone charges, "Deduction (Melting Loss)" and "Loss & Wastage Tracking" — [Busy jewellery page](https://busy.in/accounting-software/jewellery-shop/). Retail making charge is either a % of gold value or a flat fee per gram — [Bajaj Finserv](https://bajajfinserv.in/gold-wastage-percentage-calculation) (snippet-level)

### Inferences
- **[INFERENCE, using IS 1417 grade designations] Purity table for the master:**

  | Karat | Hallmark fineness (ppt) | Fine factor | Theoretical K/24 |
  |---|---|---|---|
  | 24K | 999 / 995 | 0.999 / 0.995 | 1.0000 |
  | 23K | 958 | 0.958 | 0.9583 |
  | 22K | 916 | 0.916 | 0.9167 |
  | 20K | 833 | 0.833 | 0.8333 |
  | 18K | 750 | 0.750 | 0.7500 |
  | 14K | 585 | 0.585 | 0.5833 |
  | 9K | 375 | 0.375 | 0.3750 |

  Only 9K = 375 is explicitly sourced above. The other fineness values are the standard IS 1417 designations; the IS 1417 table itself was not retrieved. Design rule: use the **stated tunch on the voucher** for fine computation and use the karat only as a label and default. Fine = weight x tunch/100. Converting fine to karat weight: wt_K = fine / (fineness/1000); e.g. 10.000 g fine = 10.917 g of 22K (10/0.916).
- **[TRADE / INFERENCE] Tunch vs purity:** in wholesale, tunch is often quoted **above** the hallmark purity (e.g. 18K billed at tunch 76-78 instead of 75). The excess is effectively wastage or labour charged in metal. No authoritative source was found for this. The user's own register (Fine = Net.Wt x Tunch/100) is consistent with it, so the software must store **purity (karat)** and **tunch** as separate fields per line.
- **[INFERENCE] Weight relationships, using the user's columns:** Net.Wt = Gr.Wt - Dia.Wt(ct) x 0.2 - Stn.Wt (in g, or ct x 0.2). The metric carat = 0.2 g (standard definition, not separately sourced here). **Validate against the user's actual register**: check whether Net.Wt = Gr.Wt - Dia.Wt/5 - Stn.Wt holds on sample rows, and whether Stn.Wt is in carats or grams.
- **[INFERENCE] Worked line (illustrative rates).** An 18K diamond ring has Gr.Wt 5.200 g, Dia.Wt 0.50 ct (= 0.100 g) and Stn.Wt 0.150 g, so Net.Wt = 4.950 g. Tunch 76.00 gives **Fine = 4.950 x 0.76 = 3.762 g**. Dia.Val = 0.50 ct x Rs 60,000/ct = 30,000. Stn.Val = 1,500. Lbr.Val = Rs 800/g x 4.950 = 3,960.
  - **Rs-settled:** metal value = 3.762 g x Rs 12,000/g fine = 45,144. Taxable value = 45,144 + 30,000 + 1,500 + 3,960 = **80,604**. GST 3% = 2,418.12. Invoice total = 83,022.12.
  - **Wt-settled:** the party's **fine ledger is debited 3.762 g** and the **rupee ledger is debited 35,460** (diamond + stone + labour) plus GST. See Q5 for why GST should still be computed on the full 80,604 including metal value at the day's rate, not on 35,460 alone.
- **[INFERENCE] Party metal account ("fine balance") rules:**
  - Every party (customer, supplier, karigar) has Rs and Fine (g) balances, optionally per metal (gold, silver, platinum).
  - Sale (Wt) debits the party's fine. Receipt of fine gold, bullion or old gold credits the party's fine at **received weight x tested tunch**.
  - **Rate cut / rate fix** converts X g of fine balance into rupees at an agreed rate. The fine ledger is credited X g and the rupee ledger debited X x rate, or the reverse for payables. This is a separate voucher type that captures the agreed rate.
  - Reports: party-wise fine outstanding, ageing of fine balances, and a metal-position report (stock fine + receivable fine - payable fine). A negative position equals unhedged exposure to the gold price.
  - Year-end valuation of fine receivables/payables in rupees is an accounting-policy question; see Gaps.
- **[INFERENCE] Karigar / job-work account worked example:**
  - Issue 100.000 g bar @ 99.50 tunch = **99.500 g fine**, recorded in godown "Karigar-X" (stock stays the principal's).
  - Receipt: jewellery net 127.500 g @ 18K tunch 75.00 = 95.625 g fine. Scrap returned 2.000 g @ 92.00 = 1.840 g fine. Agreed wastage allowance 1.5% of net = 1.9125 g fine.
  - Karigar fine balance = 99.500 - 95.625 - 1.840 - 1.9125 = **0.1225 g fine due from karigar**.
  - Labour = 127.500 g x Rs 400 = Rs 51,000 payable (GST per Q5).
  - Within agreed norms, wastage allowance goes into the cost of the finished goods (normal loss). Excess loss is abnormal and expensed (AS 2), and is a GST-risk item (Section 143 / ITC-04).
- **[INFERENCE] Diamond stock:** keep diamond stock by **lot/parcel** (shape, sieve/size, colour, clarity) in carats, plus pieces, at weighted average Rs/ct per lot. Certified solitaires are individual items (certificate no.). When diamonds are set, issue carats from the lot to the job card, and the tag's diamond cost = carats x lot average.

### Gaps
- No authoritative source (law or industry-body guide) was found describing the B2B **"Wt" settlement mechanics** (wholesaler sells, retailer returns fine gold and pays labour/diamond value in cash), "tunch above purity" conventions, or standard wastage percentages for wholesale manufacturing. This is described from trade knowledge and the user's own register and should be validated with the client.
- How to value party fine balances in rupees at the balance-sheet date was not found in any ICAI guidance. Candidate policies are historical rate, year-end rate, or treating them as a financial asset/liability.
- Gold metal loans (bank gold loans / Gold Monetisation Scheme) and their accounting were not researched.

---

## Q4. Hallmarking and HUID (BIS), scope as of 2026

### Takeaway
**[LAW]** Under the Hallmarking of Gold Jewellery and Gold Artefacts Order, 2020 (as amended up to the Third Amendment of Aug 2026), gold jewellery and artefacts sold in notified districts must carry a BIS hallmark. The hallmark has three marks: the BIS logo, purity in carat and fineness, and a **6-character alphanumeric HUID**. Only HUID-based hallmarks have been valid for sale since 1 Apr 2023. Coverage expanded to **380 districts (2 Mar 2026)** and then **385 districts (Second Amendment, 28 Apr 2026)**, and was revised again on 3/6 Aug 2026 (count not confirmed). Key exemptions: articles under 2 g, jewellers with turnover up to Rs 40 lakh, kundan/polki/jadau, and export. The order covers gold only.

### Cited Findings
- **[LAW] Order and amendments:** the base order is dated 15.01.2020. The BIS page lists amendments of 9 Oct 2020, 1 Jun 2021, 23 Jun 2021, 4 Apr 2022, 3 Mar 2023, 31 Mar 2023, 6 Sep 2023, 5 Nov 2024, 31 Jul 2025, 2 Mar 2026, 28 Apr 2026 and **3 Aug 2026** — [BIS: Hallmarking - Jewellers](https://www.bis.gov.in/hallmarking-jewellers/?lang=en)
- **[LAW] District phases:** 256 districts (Jun 2021), 288 (Apr 2022), 343 (Sep 2023), 361 (Nov 2024) and 373 (Jul 2025) — [IIFL rollout timeline](https://www.iifl.com/blogs/gold-loan/mandatory-hallmarking-india-2021-2026-rollout-timeline). The 6th phase added 7 districts (e.g. Rupnagar, Banda, Beed, Gomati, Katihar, Beawar, Neemuch), effective 2 Mar 2026, for a total of **380** — [News On Air, 12 Mar 2026](https://www.newsonair.gov.in/govt-adds-7-more-districts-in-6th-phase-of-mandatory-gold-hallmarking); [BIS 6th-phase district list (PDF)](https://www.bis.gov.in/wp-content/uploads/2026/03/List-of-additional-07-districts-covered-under-the-mandatory-hallmarking-in-the-sixth-phase.pdf). The Second Amendment, S.O. 2117(E) dated 28 Apr 2026, substituted a consolidated annexure of **385 districts** — [ComplianceCalendar](https://www.compliancecalendar.in/learn/mandatory-gold-hallmarking-order-2026-revised-consolidated-coverage-across-385-districts) (single secondary source; the BIS PDF filename also references 385 districts)
- **[LAW] Third Amendment Order, 2026,** S.O. 4345(E): issued 3 Aug 2026 and gazetted / in force 6 Aug 2026 (sources differ on the date). It substitutes a new annexure (district list) without changing the hallmarking process, purity standards or registration — [TeamLease RegTech](https://teamleaseregtech.com/updates/article/58507/hallmarking-of-gold-jewellery-and-gold-artefacts-third-amendment-order-2026/); [Corpseed](https://www.corpseed.com/law-update/hallmarking-gold-jewellery-gold-artefacts-third-amendment-order-2026); [Simpliance](https://simpliance.in/India/EHS/govt_notification/central/notification-of-the-hallmarking-of-gold-jewellery-and-gold-artefacts-third-amendment-order-2026-15153)
- **[LAW] Hallmark components:** BIS Standard Mark, purity in carat and fineness, and a six-digit HUID. The jeweller's own mark is optional. Customers verify via the BIS CARE app — [BIS: Hallmarking - Jewellers](https://www.bis.gov.in/hallmarking-jewellers/?lang=en). The HUID is a 6-character alphanumeric code and has been mandatory for gold sales from 1 Apr 2023 — [ClearTax News](https://news.cleartax.in/gold-with-huid-tag-to-be-sold-now-from-apr-1-23/9032/amp)
- **[LAW] Exemptions (BIS FAQ 9):** articles for export meeting the foreign buyer's specification; articles under 2 g (FAQ 12: detachable parts under 2 g are also exempt); consignments from abroad to a recognised AHC; medical, dental, veterinary, scientific or industrial articles; gold thread; articles not substantially complete and intended for further manufacture; bullion (bar, plate, sheet, foil, rod, wire, strip, tube, coin); export and re-import, and international exhibitions; government-approved domestic B2B exhibitions; **Kundan, Polki and Jadau**; **jewellers with annual turnover up to Rs 40 lakh**; gold watches and fountain pens — [BIS: Hallmarking - Jewellers](https://www.bis.gov.in/hallmarking-jewellers/?lang=en)
- **[LAW] Jeweller obligations:**
  - Registration is online (manakonline.in / NSWS), instant, free and valid for life. It is required for any manufacturer, wholesaler, distributor or retailer selling hallmarked gold or silver. Job-work artisans not selling in the chain may be exempt with supporting documents.
  - Hallmarking is required **once in the chain, at the first point of sale**.
  - The **invoice must show** each article's description, net precious-metal weight, carat and fineness, and hallmarking charges, and state that the consumer can get purity verified at a BIS-recognised AHC.
  - **HUID on the invoice is voluntary**, and maintaining HUID records is not mandatory.
  - Old hallmarked jewellery without HUID must be re-hallmarked with HUID before sale (2023 amendments).
  - The registered jeweller is liable for purity shortfalls (compensation) and must cooperate with BIS surveillance sampling.
  - The order "is applicable for gold jewellery and artefacts only".
  - Source: [BIS: Hallmarking - Jewellers](https://www.bis.gov.in/hallmarking-jewellers/?lang=en)
- **[LAW]** White gold and gold alloys conforming to IS 1417 are covered — [BIS: Hallmarking - Jewellers](https://www.bis.gov.in/hallmarking-jewellers/?lang=en)

### Inferences
- **[INFERENCE]** The user's diamond-studded 14K/18K gold jewellery is **not** within the kundan/polki/jadau exemption. If sold (at the first point of sale) in or into a mandatory district by a jeweller with turnover above Rs 40 lakh, each piece of 2 g or more needs a HUID hallmark on the gold.
- **[INFERENCE] Software requirements:**
  - A **HUID field per tagged piece** (6-char alphanumeric, unique, validated), plus AHC name, hallmarking date and hallmarking charge.
  - The invoice must print net metal weight, karat and fineness per article, hallmarking charges, and the AHC-verification statement (mandatory). HUID on the invoice is optional but recommended.
  - Block sale of non-HUID gold pieces of 2 g or more unless an exemption reason is selected (export, under 2 g, kundan/polki, below turnover threshold, sent for further manufacture).
  - A district master flag ("mandatory hallmarking district") from the BIS annexure, updatable as amendments arrive.
- **[INFERENCE]** For a B2B wholesaler, "first point of sale" suggests the wholesaler/manufacturer's sale of finished jewellery is where hallmarking must already be done. However, the exemption for articles "not substantially complete... intended for further manufacture" may cover semi-finished B2B supplies. Confirm with the client's actual flow.

### Gaps
- The district count after the Third Amendment (Aug 2026), and the districts it added or removed, were not found.
- The 385-district figure rests on one secondary source plus a BIS PDF filename.
- The status of silver hallmarking (voluntary HUID-based silver hallmarking reportedly from 1 Sep 2025) was not verified. BIS says the mandatory order is gold-only.
- No source was found on how hallmarking applies specifically to B2B wholesale-to-retailer transfers beyond the "once in the chain at first point of sale" FAQ.

---

## Q5. GST on jewellery: rates, job work/making charges, and valuation of metal-settled ("Wt") and exchange transactions

### Takeaway
**[LAW]** Gold, silver, platinum and diamond jewellery (HSN 7113) is taxed at **3%** on the full transaction value: metal + diamonds + stones + making. This was unchanged by the 22 Sep 2025 GST rate rationalisation. Cut and polished diamonds are **1.5%** (raised from 0.25% w.e.f. 18 Jul 2022). Rough diamonds are **0.25%**. Job work **on diamonds is 1.5%** (from 1 Oct 2019). Job work on other Chapter 71 goods (e.g. gold jewellery) for a **registered** principal is **5%**. The same making service for an **unregistered** customer is not "job work" and is taxable at **18%** (per AAR/ELP). Where consideration is partly gold (exchange or metal settlement), the taxable value is the **market value of the jewellery supplied** (Section 15 + Rule 27), not just the cash part. The user's "5% on making charges" is right only for job work for registered principals. A jeweller selling its own jewellery cannot split off making charges at 5%; the whole value is at 3%.

### Cited Findings
- **[LAW] Jewellery 3%:** gold, silver, platinum and diamond jewellery "continue to attract 3% GST on the transaction value". The GST 2.0 changes took effect 22 Sep 2025 — [Tally Solutions: Jewellery HSN code & GST rate guide](https://tallysolutions.com/gst/jewellery-hsn-code-gst-rate-classification-invoicing-guide-for-businesses/) (snippet-level). Diamonds set into gold, platinum etc. and sold as ornaments are diamond jewellery at 3% under HSN 7113 — [Razorpay: GST on diamonds](https://razorpay.com/learn/gst-on-diamond/) (snippet-level)
- **[LAW] Cut and polished diamonds:** reduced from 3% to 0.25% w.e.f. 25 Jan 2018 — [Business Standard, Jan 2018](https://www.business-standard.com/article/companies/around-94-of-polished-diamond-to-benefit-from-lower-gst-rate-of-0-25-118011900616_1.html) (snippet-level). Raised to **1.5%** w.e.f. 18 Jul 2022 after the 47th GST Council meeting (28-29 Jun 2022) to resolve ITC accumulation — [GJEPC Solitaire: "Increase in GST on cut & polished diamonds to 1.5%"](https://gjepc.org/solitaire/?p=16021) (headline only); [Razorpay](https://razorpay.com/learn/gst-on-diamond/). Rough diamonds are 0.25% — [Razorpay](https://razorpay.com/learn/gst-on-diamond/). **Conflict:** one secondary source claims polished diamond **imports** remain at 0.25% (unverified).
- **[LAW] Job work on diamonds 1.5%:** the 37th GST Council (20 Sep 2019, Goa) cut "job work services in relation to diamonds" from 5% to 1.5% — [StudyCafe: 37th GST Council recommendations](https://studycafe.in/37th-gst-council-meeting-held-on-20th-sep-2019-recommendations-83599.html); [Business Standard, 21 Sep 2019](https://www.business-standard.com/article/economy-policy/gst-rate-cut-in-diamond-job-work-to-free-up-rs-1-500-cr-working-capital-119092100384_1.html) (snippet-level)
- **[RULING] Chapter 71 job work 5% (registered principal):** job work on Chapter 71 products ("cut and polished diamonds; precious and semi-precious stones; or plain and studded jewellery of gold and other precious metals") is 5% under Sr. No. 26(i)(c) of Notification 11/2017-CT(Rate) when the principal is registered. Services to unregistered persons are outside "job work" and attract 18% under Sr. No. 26(iv) — [Gujarat AAR No. 89/2020, 17 Sep 2020](https://gstcouncil.gov.in/sites/default/files/AAR/guj_aar_89_2020_17.09.2020_enpte.pdf); [Kerala AAR, CGR Gold Trading](https://busy.in/caselaw/cgr-gold-trading-authority-for-advance-ruling-kerala) (snippet-level)
- **[LAW / professional opinion] Customer-supplied material:**
  - Where jewellery is made from a customer's own gold for an unregistered customer, raise an invoice for making charges at **18%** ("will not qualify as job work as the customer is not a registered person"), plus a 3% invoice for any goods supplied, and document receipt and return of the customer's goods.
  - Where jewellery is made from the jeweller's own material, invoice "the entire product value applying GST @3%".
  - Source: [ELP for GJEPC (2018)](https://gjepc.org/presentation/Gold%20jewellery%20summit-%20Nishant%20Shah.pdf)
- **[CONFLICT, TRADE BLOGS]** Several secondary sources state that making charges shown separately are "generally taxed at 5%" — [Tally Solutions GST guide](https://tallysolutions.com/gst/jewellery-hsn-code-gst-rate-classification-invoicing-guide-for-businesses/); [BankBazaar](https://bankbazaar.com/gold-rate/gst-on-gold.html). Another says separately billed making charges "may fall under Heading 9988 and attract 1.5%" — [GetSwipe](https://getswipe.in/blog/article/gst-on-diamond-jewellery-rates-compliance). Both are snippet-level and conflict with the ELP/AAR view above.
- **[LAW] Old gold bought from consumers:** per the CBEC press release of 13 Jul 2017, an individual selling old gold jewellery is not acting in the course or furtherance of business, so it is not a supply — [ELP for GJEPC](https://gjepc.org/presentation/Gold%20jewellery%20summit-%20Nishant%20Shah.pdf)
- **[LAW / professional opinion] Exchange valuation:** "exchange" is a supply under Section 7 (cited as Section 3 in the presentation). Since price is not the sole consideration, under **Section 15 read with Rule 27** the taxable value is the market value of the new jewellery or of goods of like kind and quality. GST is typically charged on the market value of goods sold in exchange for old product — [ELP for GJEPC](https://gjepc.org/presentation/Gold%20jewellery%20summit-%20Nishant%20Shah.pdf). A Taxguru article also treats old jewellery as non-monetary consideration under Section 15 and charges 3% on the value of new jewellery — [Taxguru](https://taxguru.in/?p=1075067) (snippet-level)
- **[RULING, CONFLICTING] Margin scheme (Rule 32(5)) for second-hand jewellery:**
  - Karnataka AAR: value = selling price - purchase price for second-hand goods sold without processing and without ITC — [Taxmann](https://www.taxmann.com/post/blog/gst-leviable-only-on-difference-between-selling-and-purchase-price-of-second-hand-jewellery-aar-karnataka)
  - West Bengal AAR (Kundan Kumar Prasad): allowed after minor processing that does not change the jewellery's nature; supply at 3% — [GST Council AAR PDF](https://gstcouncil.gov.in/sites/default/files/AAR/kundan_kumar_prasad_advance_ruling.pdf)
  - Kerala AAR (Best Money Gold Jewellery Ltd, 2023): denied, reasoning that gold does not depreciate — [Busy caselaw page](https://busy.in/caselaw/best-money-gold-jewellery-limited-authority-for-advance-ruling-tamilnadu) (the URL says Tamil Nadu, the summary says Kerala; unresolved)
- **[LAW] Sale on approval:** goods taken for supply on approval may move under a delivery challan with an e-way bill where applicable, and the invoice is issued on delivery or approval (CBEC Circular 10/10/2017-GST, 18 Oct 2017). Carrying goods to another state and supplying there = inter-state supply (IGST). Section 31(7) governs invoice timing for approval/sale-or-return goods — [ELP for GJEPC](https://gjepc.org/presentation/Gold%20jewellery%20summit-%20Nishant%20Shah.pdf)
- **[LAW]** Dealers in precious metals and stones are covered by PMLA reporting and KYC requirements — [ELP for GJEPC](https://gjepc.org/presentation/Gold%20jewellery%20summit-%20Nishant%20Shah.pdf)

### Inferences
- **[INFERENCE] Valuing "Wt"-settled B2B sales:** when a wholesaler sells jewellery and the buyer settles the metal portion by delivering fine gold, the consideration is partly non-monetary. By the same Section 15 / Rule 27 logic applied to exchanges, **GST at 3% is due on the full value of the jewellery**: fine wt x the prevailing gold rate on the date of supply, plus diamond, stone and labour value. It is not due only on the rupee part (labour + diamonds).
  - In the Q3 example that means 3% on Rs 80,604, not on Rs 35,460.
  - The buyer's delivery of fine gold back is a separate supply of gold by a registered buyer (3%, with ITC to the wholesaler), i.e. a barter of two supplies.
  - The software should therefore (a) require a **metal rate on every Wt invoice** (from a daily rate master) to compute taxable value, and (b) print fine weight, rate used and taxable value. No CBIC circular or AAR specific to B2B fine-gold settlement was found, so the client's CA should confirm.
- **[INFERENCE] Tax-code matrix for Accounts.ai:**

  | Supply | HSN/SAC | GST rate |
  |---|---|---|
  | Jewellery (gold/silver/platinum/diamond-studded) | 7113 | 3% |
  | Gold bars/coins | 7108 | 3% |
  | Cut & polished diamonds | 7102 | 1.5% |
  | Rough diamonds | 7102 | 0.25% |
  | Job work on diamonds | 9988 | 1.5% |
  | Job work on other Ch. 71 goods for a registered principal | 9988 | 5% |
  | Making on customer gold for an unregistered person / repairs | 9988 / other | 18% (verify) |

  Make the rate a function of (HSN/SAC, customer registration status, job-work flag), not a single item rate.
- **[INFERENCE]** Karigar labour bills: a registered karigar doing job work for the registered jeweller charges 5% (1.5% for diamond work). The jeweller claims ITC. The karigar's GSTIN status must be captured.

### Gaps
- The current consolidated text of Notification 11/2017-CT(Rate) entry 26 after the 56th GST Council (Sep 2025) rationalisation was not verified. The 5% / 1.5% / 18% job-work mapping is from pre-2025 AARs and the 2019 Council decision, plus secondary claims that Chapter 71 rates were unchanged in GST 2.0.
- **E-way bill for jewellery:** a vendor guide says an e-way bill is needed for inter-state movement — [CodingClave 2026 guide](https://codingclave.com/guides/best-jewelry-shop-software-india-2026). From prior knowledge (not verified here), the Annexure to Rule 138(14) exempts Chapter 71 jewellery and precious stones. Unresolved; verify.
- PMLA cash-transaction thresholds for jewellers and income-tax cash/PAN limits (Section 269ST, Rule 114B) were not researched.
- GST treatment of lab-grown diamonds was not researched.

---

## Q6. What a jewellery business needs from accounting software (Indian jewellery ERPs, Tally add-ons)

### Takeaway
Indian jewellery software consistently offers:
- weight- and purity-based inventory (gross/net/fine, karat/tunch)
- tag, barcode or QR per piece with HUID entry
- making charges (fixed, % or per gram) and separate stone/diamond charges
- wastage and melting-loss tracking
- karigar issue/receive with metal-balance tracking
- old-gold purchase/exchange
- daily metal rate master
- multi-location stock
- GST-compliant billing

**Party-wise fine-gold ledgers with "rate cut" and metal loans** appear mainly in specialist add-ons (e.g. Tally jewellery modules) rather than in mainstream SME packages. That is a differentiation opportunity for Accounts.ai.

### Cited Findings
- **TallyPrime (jewellery page):** "Track inventory by weight or purity", track gold/silver/stone purity, "Track variation in metal losses", "Perform karigar accounting", hallmark entry, "Barcodes and tagging for all jewellery SKUs", POS with GST invoices, multi-branch, stock ageing and sales by design/category/metal. It does not mention carat or compound units, HUID, old gold exchange or making charges — [Tally: Jewellery accounting software](https://tallysolutions.com/accounting-software/jewellery/)
- **Busy (jewellery page):** purity 22K/18K/14K; gross/net weight; diamonds by purity, weight and karats; making charges (fixed/%); separate stone charges; loss and wastage tracking; melting-loss deduction; job work (in-house and out-house); old gold purchase entry and exchange; barcode/QR printing and billing; **HUID / hallmark number entry**; multi-location (shop, godown); GST for gold, diamonds and making charges. No metal/fine balance account is listed — [Busy: Jewellery accounting software](https://busy.in/accounting-software/jewellery-shop/)
- **Tally add-on "Jewels Module":** metal inventory, **rate cuts**, **metal loans**, sales/purchase entries, outstanding-balance reports — [Scribd document](https://www.scribd.com/document/617847472/Jewels-Module) (snippet-level, user-uploaded)
- **ERPNext jewellery apps:** issue raw metal to artisans, receive finished pieces, track wastage and making per job — [Ecosire ERPNext Jewellery & Bullion](https://ecosire.com/fr/apps/erpnext/erpnext-jewellery-bullion). Dated per-karat gold rate records, line value = net wt x karat rate, optional rate-feed scheduler — [Ecosire ERPNext Jewellery Management](https://ecosire.com/es/apps/erpnext/erpnext-jewellery-management) (snippet-level)
- **Online Munim:** karigar module for gold issued, returns, wastage and balance gold, with job-work history; full accounting (ledger, trial balance, P&L, GST, TDS) — [Techjockey listing](https://techjockey.com/detail/online-munim-jewellery) (snippet-level)
- **Joolet:** barcode/QR inventory, metal weight tracking, fine-weight profit calculation, loss control for in-house and job-work processes — [GoodFirms: Joolet](https://www.goodfirms.co/company/joolet) (snippet-level)
- **Vendor-written 2026 buyer's guide** (treat with caution): generic tools such as Tally or basic billing "often don't handle karigar issue workflows properly". Indian jewellery compliance covers BIS HUID, split GST on metal vs making vs stones, e-invoice above Rs 5 cr, and e-way bill; Busy/Marg-based offerings add barcode/RFID tags, karigar workflows and girvi (gold loan) modules — [CodingClave](https://codingclave.com/guides/best-jewelry-shop-software-india-2026) (snippet-level)
- **[LAW] BIS invoice content** (net metal weight, carat/fineness, hallmarking charges) is mandatory for hallmarked jewellery sales — [BIS: Hallmarking - Jewellers](https://www.bis.gov.in/hallmarking-jewellers/?lang=en)

### Inferences
**[INFERENCE] Implementation-ready feature list for Accounts.ai (jewellery mode), in priority order for the B2B diamond-jewellery client:**

1. **Item / tag master:**
   - Design/style no., category, metal and karat, default tunch.
   - Per-tag fields: tag/barcode no. (unique), HUID, Gr.Wt, Dia.Wt (ct) with lot links, Stn.Wt, Net.Wt (auto-computed with an override flag), cost breakup.
   - Tags are specific-identification inventory.
2. **Voucher line schema matching the client's register:** Item, Purity, Tunch, Gr.Wt, Dia.Wt, Stn.Wt, Net.Wt, Fine (= Net x Tunch/100, 3 decimals), Dia.Val, Stn.Val, Lbr.Val (basis: per g net / per g gross / per piece / %), Total, and **Settlement = Wt | Rs**.
   - Rs: Total includes Fine x rate.
   - Wt: Total excludes metal; fine posts to the party's metal ledger.
   - GST is computed on full value in both modes (see Q5).
3. **Dual ledgers:** Rs + fine grams per party and per metal. Voucher types: Metal Receipt/Issue (with tested tunch), **Rate Cut** (metal to Rs at an agreed rate), Metal Loan in/out, and Approval Out/In (delivery challan, Section 31(7)).
4. **Daily rate master** per metal/purity (999 and 995 fine, 916, 750, 585, 375; silver 999), used for Rs valuation, GST value on Wt invoices and NRV checks.
5. **Karigar / job work:**
   - Issue/receive by job card, karigar godown, wastage allowance %, labour rate, karigar fine balance.
   - Challans (Rule 55) and an ITC-04 report.
   - Loss beyond norm flagged as abnormal.
6. **Diamond lots:** carats + pieces per lot, weighted average Rs/ct, issue to job cards, certified-stone register.
7. **Stock reports:**
   - Multi-measure stock summary (pcs / gross / net / fine / ct / value) by group, godown and karat.
   - Tag-wise stock and ageing.
   - **Metal position** (stock fine + receivable fine - payable fine).
   - Melting/wastage register.
   - Physical stock verification by barcode scan with variance.
8. **Valuation:** tags at specific cost; metal pool at FIFO or WA per fine gram; lots at WA per ct; lower of cost or NRV check against the rate master; closing-stock posting to P&L and Balance Sheet.
9. **Compliance:** BIS invoice fields and AHC statement; HUID uniqueness check; old-gold purchase voucher (non-supply from consumers) and exchange invoice valued at the market value of new jewellery; HSN-wise GST rates per the Q5 matrix.

### Gaps
- Feature documentation for **Logic ERP** and **Jewel Soft** specifically could not be retrieved, so their support for party fine ledgers, rate cut and karigar metal accounts is unverified.
- No vendor documentation found describes "Wt/Rs" settlement columns by that name. The client's register appears to follow a regional (likely Mumbai/Gujarat/Rajasthan wholesale) convention that should be confirmed directly with the client.
- Marg's jewellery features were not reviewed.
