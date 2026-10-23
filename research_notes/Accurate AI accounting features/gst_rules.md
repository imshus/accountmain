# Indian GST Rules for Computing GST Summaries from Sales/Purchase Registers (current to Oct 2026)

Scope: India only. Research date 22 Oct 2026. Sources are official where I could reach them: the GST Council press release for the 56th meeting, CBIC statute pages, and GSTN advisories hosted on state GST sites. Where I could not, they are practitioner or vendor guides (ClearTax, Tally, Zoho, TaxGuru, Taxmann, IRIS, Busy). Points I took from my knowledge of the statute rather than from a page fetched this session are labelled "[statute knowledge, not fetched]" and should be checked before they are hard-coded.

---

## 1. Intra-state vs inter-state supply: CGST+SGST/UTGST vs IGST, place of supply, GSTIN state codes

### Takeaway
The tax type depends on comparing two things: the **location of the supplier** and the **place of supply (POS)**. If both are in the same State/UT, the supply is intra-state: CGST + SGST, or CGST + UTGST in a UT, each at half the rate. If they differ, the supply is inter-state: IGST at the full rate. Supplies to or by an SEZ are always inter-state. In a register, the supplier's state is the first two digits of its own GSTIN. The POS is a separate field: it often equals the buyer's GSTIN state code, but not always.

### Cited Findings
- **Section 7 IGST Act (inter-state):** a supply of services is inter-state when the supplier's location and the place of supply are in different States/UTs, "subject to the provisions of section 12". Supplies to or by an SEZ developer or SEZ unit are treated as inter-state. — [CBIC, IGST Act s.7](https://taxinformation.cbic.gov.in/content/html/tax_repository/gst/acts/2017_IGST_Act/active/chapteriv/section7_v1.00.html) (read via search snippet; direct fetch failed on a certificate error); [Lakshmikumaran & Sridharan](https://lakshmisri.com/insights/articles/intra-state-supplies-inter-state-supplies-under-gst-law)
- **Section 8 IGST Act (intra-state):** a supply is intra-state when supplier location and place of supply are in the same State/UT. The proviso to s.8(2) excludes supplies to or by an SEZ developer/unit from intra-state. — [KnowYourGST, IGST s.8](https://www.knowyourgst.com/gstlaw/igst-act/8-intra-state-supply-182/)
- **Section 12 IGST Act** (POS of services where supplier and recipient are both in India) overrides the s.7/s.8 classification for services. In a 2022 case, the Telangana High Court remanded a matter where the department had recorded the *unregistered* recipient's location as POS, citing s.12(9). This is a single remand ruling, not settled law. — [LiveLaw](https://livelaw.in/amp/news-updates/telangana-high-court-section-12-of-the-igst-act-assessee-igst-203550)
- **Intra-state split:** CGST and SGST each take half the rate. For example, 5% becomes CGST 2.5% + SGST 2.5%. Turning off the same-state option makes the sale inter-state (IGST). — [ClearTax GST calculator](https://cleartax.in/s/gst-calculator)
- **2025 change to place of supply for intermediary services:** the 56th Council recommended omitting s.13(8)(b) IGST Act. After the amendment, POS for intermediary services (cross-border) becomes the recipient's location under the default s.13(2), so these services can qualify as exports. — [GST Council press release, 56th meeting, Annexure V item 6](https://gstcouncil.gov.in/sites/default/files/2025-09/press_release_press_information_bureau.pdf)

**State/UT code list** (first two digits of GSTIN; also the code used for POS). Source: [Zoho Books India: valid state codes](https://www.zoho.com/in/books/kb/gst/valid-state-codes-list.html), cross-checked against [myBillBook 2026 list](https://mybillbook.in/blog/state-gst-codes/) and [Masters India](https://www.mastersindia.co/gst/list-of-state-code-under-gst/).

| Code | State/UT | Alpha | Code | State/UT | Alpha |
|---|---|---|---|---|---|
| 01 | Jammu & Kashmir | JK | 20 | Jharkhand | JH |
| 02 | Himachal Pradesh | HP | 21 | Odisha | OD |
| 03 | Punjab | PB | 22 | Chhattisgarh | CG |
| 04 | Chandigarh (UT) | CH | 23 | Madhya Pradesh | MP |
| 05 | Uttarakhand | UK | 24 | Gujarat | GJ |
| 06 | Haryana | HR | 26 | Dadra & Nagar Haveli and Daman & Diu (UT, merged) | DN |
| 07 | Delhi | DL | 27 | Maharashtra | MH |
| 08 | Rajasthan | RJ | 29 | Karnataka | KA |
| 09 | Uttar Pradesh | UP | 30 | Goa | GA |
| 10 | Bihar | BR | 31 | Lakshadweep (UT) | LD |
| 11 | Sikkim | SK | 32 | Kerala | KL |
| 12 | Arunachal Pradesh | AR | 33 | Tamil Nadu | TN |
| 13 | Nagaland | NL | 34 | Puducherry | PY |
| 14 | Manipur | MN | 35 | Andaman & Nicobar Islands (UT) | AN |
| 15 | Mizoram | MZ | 36 | Telangana | TS |
| 16 | Tripura | TR | 37 | Andhra Pradesh | AD |
| 17 | Meghalaya | ML | 38 | Ladakh (UT) | LA |
| 18 | Assam | AS | 97 | Other Territory | OT |
| 19 | West Bengal | WB | | | |

- **Codes 25 and 28:** 25 was the old Daman & Diu code, which merged into 26 after Jan 2020. 28 was the pre-bifurcation Andhra Pradesh code. Neither is in the current registration master as an active state code. — [myBillBook](https://mybillbook.in/blog/state-gst-codes/); older lists still show 25 = Daman & Diu ([Sage](https://www.sagesoftware.co.in/blogs/what-is-gst-state-code-list/))

### Inferences
- **Classification rule for software:** `supplier_state = own_GSTIN[:2]`, `pos = POS column (normalised to 2-digit code)`.
  - `pos == supplier_state` and not SEZ/export: expect CGST = SGST = rate/2 × taxable, and IGST = 0.
  - Otherwise: expect IGST = rate × taxable, and CGST = SGST = 0.
  - Exports and SEZ supplies are always IGST, or zero-rated under LUT.
- **Purchase register:** use the *supplier's* GSTIN state code vs POS (usually your own state).
- **The buyer's GSTIN state code is only a proxy for POS.** It fails for bill-to/ship-to goods, services relating to immovable property, hotel stays, events and similar cases. Software should treat `buyer_GSTIN[:2] != POS` as a *warning*, not an error.
- **[statute knowledge, not fetched]** POS for goods involving movement is where movement terminates for delivery (IGST s.10(1)(a)). Under bill-to-ship-to, it is the principal place of business of the person on whose order goods are delivered (s.10(1)(b)).
- **[statute knowledge, not fetched]** The general rule for services (s.12(2)):
  - registered recipient: the recipient's location;
  - unregistered recipient: the recipient's address on record if available, otherwise the supplier's location.
- **[statute knowledge, not fetched]** Imports of goods and services are inter-state (IGST s.7(2), 7(4)).
- **[statute knowledge, not fetched] UTGST vs SGST:** UTGST replaces SGST only in UTs *without* a legislature: Andaman & Nicobar (35), Lakshadweep (31), DNH & DD (26), Ladakh (38) and Chandigarh (04). Delhi (07), Puducherry (34) and J&K (01) use SGST. A register can store both in one "SGST/UTGST" column.
- **Normalise POS input.** It may arrive as a name ("Maharashtra"), an alpha code ("MH"), a 2-digit code ("27"), or "27-Maharashtra". Map all four forms to the 2-digit code. Accept "TG" as well as "TS" for Telangana, and both "AP" and "AD" for Andhra Pradesh, because different vendors use different alpha codes.

### Gaps
- I could not fetch the official GSTN state-code master. I also could not confirm the special codes 96 (foreign country / other country, used for exports in e-invoice) and 99 (Centre jurisdiction) from a source in this session.
- The full current text of IGST s.10 and s.12 was not fetched. The POS rules above are from statute knowledge.
- I did not confirm whether the s.13(8)(b) omission has been notified and its effective date; it needs a Finance Act/notification check.

---

## 2. GST rate slabs as of 2026 (GST 2.0), cess, tax computation, back-calculation and rounding

### Takeaway
From **22 September 2025**, the 56th GST Council collapsed the 5/12/18/28% structure into a **5% "merit" rate, an 18% "standard" rate and a 40% "de-merit" rate**, plus nil/exempt and the legacy special rates (3% gold/silver/jewellery, 0.25% rough diamonds, 1.5% cut/polished diamonds). Tobacco and pan masala stayed on the old 28% + compensation cess regime until **1 February 2026**. On that date the compensation cess ended and those goods moved to 40% (bidi to 18%), with a new Health and National Security Cess on pan masala and additional central excise on tobacco, both levied *outside* GST. Tax = taxable value × rate/100. To back out tax from an inclusive amount, use taxable = inclusive × 100/(100 + rate). Tax payable is rounded to the nearest rupee under Section 170, but invoices and returns carry amounts to 2 decimals.

### Cited Findings
**GST 2.0 structure (56th GST Council, meeting 3 Sept 2025)**
- The Council rationalised the "4-tiered tax rate structure" into a 2-rate structure: "a Standard Rate of 18% and a Merit Rate of 5%; a special de-merit rate of 40% for a select few goods and services". — [GST Council press release (PIB), 56th meeting](https://gstcouncil.gov.in/sites/default/files/2025-09/press_release_press_information_bureau.pdf); [EY Tax Alert, Sept 2025](https://www.ey.com/content/dam/ey-unified-site/ey-com/en-in/alerts-hub/2025/09/gst-council-announces-major-rate-rationalization-and-trade-facilitation-measures.pdf)
- **Effective dates in the same press release:**
  - (a) Rate changes on services apply from 22 Sept 2025.
  - (b) Rate changes on all goods apply from 22 Sept 2025, *except* pan masala, gutkha, cigarettes, chewing tobacco (zarda), unmanufactured tobacco and bidi.
  - (c) Those tobacco goods "will continue at the existing rates of GST and compensation cess where applicable, till loan and interest payment obligations under the compensation cess account are completely discharged".
  - (d) The Finance Minister would decide the actual transition date for them.
  - Source: [GST Council press release](https://gstcouncil.gov.in/sites/default/files/2025-09/press_release_press_information_bureau.pdf)
- **Examples of moves to 5%:** hair oil, soap, shampoo, toothpaste, bicycles, kitchenware; most packaged foods (namkeen, sauces, pasta, chocolates, coffee, butter, ghee); tractors and agricultural machinery; handicrafts; man-made fibre (18%→5%) and yarn (12%→5%); fertiliser inputs (sulphuric acid, nitric acid, ammonia 18%→5%); renewable energy devices; hotel accommodation ≤ Rs 7,500 per unit per day (12%→5%); beauty and wellness services (gyms, salons, yoga) "18% with ITC" → "5% without ITC". — [GST Council press release](https://gstcouncil.gov.in/sites/default/files/2025-09/press_release_press_information_bureau.pdf)
- **Moves to 18%:** ACs, all TVs, dishwashers, small cars, motorcycles ≤350cc, buses, trucks, ambulances, three-wheelers, cement (28%→18%). All auto parts were set at a uniform 18%. — [GST Council press release](https://gstcouncil.gov.in/sites/default/files/2025-09/press_release_press_information_bureau.pdf)
- **Moves to nil:** UHT milk, pre-packaged paneer/chena, Indian breads (5%→nil); 33 lifesaving drugs (12%→nil) and 3 cancer/rare-disease drugs (5%→nil). Other drugs went 12%→5%. Individual life and health insurance policies are exempt. — [GST Council press release](https://gstcouncil.gov.in/sites/default/files/2025-09/press_release_press_information_bureau.pdf)
- **Moves to 40%** (from Annexure II/IV of the release):
  - motor cars other than the small cars listed at 18%;
  - motorcycles >350cc;
  - aircraft for personal use and yachts;
  - revolvers/pistols and smoking pipes;
  - aerated/sweetened/flavoured waters (2202 10), caffeinated beverages, carbonated fruit drinks, pan masala (28%→40%);
  - "other non-alcoholic beverages" 2202 91 00 / 2202 99 (18%→40%);
  - tobacco products 2401/2402/2403/2404 (28%→40%);
  - services: admission to casinos, race clubs and events like IPL; race-club bookmaker licensing; leasing of goods that attract 40%; specified actionable claims (betting, casinos, gambling, horse racing, lottery, online money gaming), all "28% with ITC → 40% with ITC".
  - Bidi went 28%→18%.
  - Source: [GST Council press release](https://gstcouncil.gov.in/sites/default/files/2025-09/press_release_press_information_bureau.pdf)
- GST on pan masala, gutkha, cigarettes, unmanufactured tobacco and zarda is levied on **Retail Sale Price** instead of transaction value. — [GST Council press release](https://gstcouncil.gov.in/sites/default/files/2025-09/press_release_press_information_bureau.pdf)

**Tobacco and compensation cess transition (1 Feb 2026)**
- The government fixed **1 February 2026** as the implementation date. The GST compensation cess on tobacco and pan masala "will cease to be applicable from February 1". Pan masala now bears a Health and National Security Cess, and tobacco products bear an additional central excise duty. Parliament passed the enabling bills in Dec 2025, and the rules/dates were notified on 31 Dec 2025. — [Deccan Herald](https://www.deccanherald.com/amp/story/india%2Fadditional-excise-duty-on-tobacco-health-cess-on-pan-masala-to-be-effective-february-1-3848089); [Outlook Business](https://www.outlookbusiness.com/news/additional-excise-duty-on-tobacco-health-cess-on-pan-masala-to-be-effective-feb-1)
- From 1 Feb 2026, pan masala, cigarettes, tobacco and similar products attract 40% GST, while biris are taxed at 18%. — [Deccan Herald](https://www.deccanherald.com/amp/story/india%2Fadditional-excise-duty-on-tobacco-health-cess-on-pan-masala-to-be-effective-february-1-3848089); [Swarajya](https://swarajyamag.com/amp/story/economy/higher-taxes-on-tobacco-and-pan-masala-from-1-february-2026-as-centre-brings-new-excise-duty-and-health-cess-regime)

**Special rates that remain**
- Gold, silver and platinum: 3% on metal value plus 5% on making charges (job work). This is described as unchanged post-GST 2.0. — [Busy GST rates](https://busy.in/gst-rates.md). Jewellery: 3% on the full invoice value. — [Tally (2026)](https://tallysolutions.com/gst/gst-on-silver-diamond-precious-stones-tax-guide-for-jewellery-retailers/)
- Rough diamonds (HSN 7102): 0.25%. Cut and polished diamonds: 1.5% (since July 2022). — [Swipe](https://getswipe.in/blog/article/gst-on-diamond-jewellery-rates-compliance); [Tally](https://tallysolutions.com/gst/gst-on-silver-diamond-precious-stones-tax-guide-for-jewellery-retailers/)

**Computation formulas**
- Forward: GST Amount = (Value of supply × GST rate)/100, and Price = Value + GST. Back-calculation from an inclusive price: GST Amount = Value − [Value × {100/(100 + GST rate)}]. Example: 100,000 at 18% gives GST 18,000 and an invoice of 118,000. — [ClearTax GST calculator](https://cleartax.in/s/gst-calculator)

**Rounding**
- Section 170 CGST Act: tax, interest, penalty, fine and other sums (including refunds) are rounded off to the nearest rupee. 50 paise or more rounds up; less than 50 paise is ignored. — [Busy](https://busy.in/gst/rounding-off-rules-in-gst-invoices/); [Tally](https://tallysolutions.com/gst/gst-rounding-off-tax-rules)
- Section 170 does not require every invoice line or intermediate calculation to be converted to whole rupees. The GST portal accepts invoice value, taxable value and tax up to two decimals. The e-invoice schema has a separate invoice-level round-off field (`RndOffAmt`). — [Gimbooks](https://www.gimbooks.com/blog/gst-invoice-round-off-differences/) (vendor interpretation, not an official clarification)
- Practitioners disagree on whether to round tax per invoice or on the month's aggregate liability. Masters India argues that per-invoice rounding is correct. — [Masters India](https://www.mastersindia.co/blog/rounding-off-tax-under-gst/)

### Inferences
- **Use an effective-dated rate table.** A register spanning FY 2025-26 legitimately contains 12% and 28% rates (and compensation cess) on invoices dated **before 22 Sept 2025**, and 28% + cess on tobacco until **31 Jan 2026**. Valid rate sets by invoice date:
  - before 22 Sept 2025: {0, 0.1, 0.25, 1.5, 3, 5, 6, 12, 18, 28};
  - from 22 Sept 2025: {0, 0.1, 0.25, 1.5, 3, 5, 18, 40}, with 28% + cess still allowed only for tobacco HSNs until 31 Jan 2026.
  - [The 0.1% (merchant export) and 6% (some job-work/brick schemes) entries are statute knowledge, not fetched. Treat them as "allowed but rare".]
- **Credit/debit notes against pre-22-Sept-2025 invoices should carry the original invoice's rate.** [Inference from time-of-supply principles; verify against s.14 CGST Act.]
- **Compensation cess on non-tobacco goods** (cars, aerated drinks and so on) appears to have ended from 22 Sept 2025, because those goods moved to 40% and the release keeps cess only for the tobacco group. [Inference; I did not fetch the Compensation Cess rate notification.] Flag any cess on non-tobacco items dated on or after 22 Sept 2025, and any compensation cess at all on or after 1 Feb 2026.
- **The new pan masala cess and tobacco excise are not GST.** They do not appear in GSTR-1/3B GST columns and should not be summed into GST totals.
- **Back-calc in pandas:**
  ```python
  taxable = (incl * 100 / (100 + rate)).round(2)
  tax = incl - taxable
  # intra-state split
  cgst = (tax / 2).round(2)
  sgst = tax - cgst
  ```
  Assigning the residual paisa to SGST keeps the totals exact.
- **Recommended tolerance for validation:** compute `expected = round(taxable * rate / 100, 2)` per line. Accept |actual − expected| ≤ Rs 1 per invoice, since lines may be rounded individually and an invoice-level round-off may be posted separately. Use a tighter bound (≤ Rs 0.05) per line. Report return-level totals to 2 decimals, and round only the final payable per tax head to whole rupees (s.170).

### Gaps
- I could not open the CBIC rate notifications themselves (Notification 9/2025-CT(Rate) and related) to confirm the full HSN-wise schedules. Item-level rates above come from the Council release, which says it "alone" does not have force of law.
- I could not confirm from an official source whether the compensation cess on non-tobacco goods was formally exempted from 22 Sept 2025.
- The exact rates of the new Health & National Security Cess and the tobacco excise were not verified from notifications. Secondary sources mention, for example, unmanufactured tobacco excise going from 64% to 70%.
- I found no official e-invoice/GSTR-1 numeric tolerance for tax ≠ rate × value.
- I found no evidence of further rate-slab changes between Feb 2026 and Oct 2026. Absence of evidence is not confirmation.

---

## 3. GSTR-1 and GSTR-3B structure; net GST payable; order of ITC utilisation

### Takeaway
GSTR-1 reports outward supplies invoice-wise (B2B, B2C Large, exports, credit/debit notes) and summary-wise (B2C small rate-wise, nil/exempt, advances, HSN summary split into B2B/B2C tabs, documents issued). GSTR-3B is the summary return that pays the tax:
- **3.1:** outward supplies and RCM inward supplies;
- **3.2:** inter-state supplies to unregistered persons, composition dealers and UIN holders;
- **4:** ITC available, reversed, net and ineligible;
- **5:** exempt inward supplies;
- **6.1:** payment.

Since the **July 2025 tax period**, auto-populated liability in 3B (from GSTR-1/1A/IFF) is **non-editable**. Net payable = output tax − ITC set off in the Rule 88A order. IGST credit is used first: against IGST, then against CGST/SGST in any order or proportion. CGST credit can never pay SGST and vice versa. RCM tax is paid in cash only.

### Cited Findings
**GSTR-1 tables**
- **Tables 1–3:** GSTIN, legal name, ARN/date.
- **4A:** B2B non-RCM supplies invoice-wise (including e-commerce supplies attracting TCS). **4B:** B2B supplies on which the recipient pays tax under reverse charge.
- **5:** inter-state B2C invoices above the B2C-Large threshold, invoice-wise.
- **6:** zero-rated supplies and deemed exports (exports, SEZ, EOU), with shipping bill details.
- **7:** B2C "others", rate-wise (7A intra-state, 7B inter-state with POS).
- **8:** nil-rated, exempt and non-GST supplies, split by inter/intra-state and registered/unregistered.
- **9:** amendments to 4/5/6 and credit/debit notes (9A amendments to B2B/B2CL/exports; 9B credit/debit notes for registered and unregistered recipients; 9C amendments of credit/debit notes).
- **10:** amendments to Table 7.
- **11:** advances received or adjusted.
- **12:** HSN-wise summary, now split into B2B and B2C tabs with HSN chosen from a dropdown and value/tax validations.
- **13:** documents issued.
- **14/14A:** supplies through e-commerce operators (TCS u/s 52 or tax u/s 9(5)), by operator GSTIN.
- **15/15A:** supplies on which the ECO pays tax u/s 9(5).
- Source: [ClearTax: details in GSTR-1](https://cleartax.in/s/details-mentioned-return-gstr-1)
- **B2C Large threshold:** reduced from Rs 2.5 lakh to **Rs 1 lakh** by Notification 12/2024-Central Tax dated 10 July 2024, effective 1 Aug 2024. It applies to inter-state B2C invoices in Tables 5, 9 and 10 (and 7B). A GSTN advisory of 3 Sept 2024 told taxpayers to keep using Rs 2.5 lakh until the portal was updated. — [Cashflo](https://www.cashflo.io/magazine/gst-alert-reduced-b2c-invoice-reporting-threshold-in-gstr-1); [Taxscan](https://taxscan.in/gst-council-recommends-lowering-b2c-inter-state-invoice-reporting-in-gstr-1-threshold-to-rs-1-lakh/412286); [Tally help](https://help.tallysolutions.com/tally-prime/gstr-1/b2c-large-invoices-5a-5b/). The ClearTax page is internally inconsistent: it says "reduced... to Rs.1 lakh" but still describes Rs 2.5 lakh in places. — [ClearTax](https://cleartax.in/s/details-mentioned-return-gstr-1)
- **HSN digits:** under Notification 78/2020 (15 Oct 2020), Table 12 needs a minimum 4 or 6 HSN digits depending on preceding-year aggregate turnover. — [ClearTax](https://cleartax.in/s/details-mentioned-return-gstr-1). Taxpayers with turnover above Rs 5 crore must report at least 6 digits (maximum 8) for both B2B and B2C. — [West Bengal CT functionality note](https://comtax.wb.gov.in/GST/Functionality_Taxpayer/functionality_Return_20220525_2.pdf)
- **GSTN clarification, 11 June 2025:** a taxpayer with only B2C supplies must still put one entry in Table 12A (B2B tab), with any HSN/UQC and other fields set to 0. — [ClearTax](https://cleartax.in/s/details-mentioned-return-gstr-1)

**GSTR-3B tables**
- **3.1:**
  - (a) outward taxable supplies (other than zero-rated, nil-rated and exempted);
  - (b) outward taxable supplies (zero-rated);
  - (c) other outward supplies (nil-rated, exempted);
  - (d) inward supplies liable to reverse charge;
  - (e) non-GST outward supplies.
- **3.2:** inter-state supplies to unregistered persons, composition taxable persons and UIN holders.
- **4:** (A) ITC available (import of goods, import of services, inward supplies liable to RCM, inward supplies from ISD, all other ITC); (B) ITC reversed; (C) net ITC = A − B; (D) ineligible ITC.
- **5:** values of exempt, nil-rated and non-GST inward supplies, including purchases from composition dealers.
- **6:** payment of tax, through ITC, TDS/TCS credit and cash (including interest and late fee).
- Source: [Zoho: sections of GSTR-3B](https://www.zoho.com/en-in/erp/kb/filing-and-compliance/sections-gstr-3b.html)
- **Table 3.1.1** was inserted for supplies notified u/s 9(5) (supplies through e-commerce operators). — [TaxGuru Table 4 guide](https://taxguru.in/goods-and-service-tax/gstr-3b-table-4-itc-expert-guide.html)
- **Revised Table 4 format** (Notification 14/2022-CT; applies from the Aug 2022 return period):
  - **4(A):** auto-populated from GSTR-2B, including ineligible ITC; **4(A)(5):** reclaims of earlier 4(B)(2) reversals.
  - **4(B)(1):** permanent reversals (Rules 38, 42, 43 and s.17(5)).
  - **4(B)(2):** temporary reversals (Rule 37, s.16(2)(b)/(c), credit notes, inadvertent errors).
  - **4(C):** net ITC = 4(A) − 4(B), credited to the electronic credit ledger.
  - **4(D)(1):** break-up of reclaims; **4(D)(2):** ITC not available by law (s.16(4) time-bar, POS rules such as CGST/SGST on an out-of-state hotel).
  - Source: [ClearTax: Table 4 of GSTR-3B](https://cleartax.in/s/table-4-of-gstr-3b); [TaxGuru](https://taxguru.in/goods-and-service-tax/gstr-3b-table-4-itc-expert-guide.html)
- **Hard-locking:**
  - GSTN advisory of 7 June 2025: auto-populated outward liability in GSTR-3B becomes **non-editable from the July 2025 tax period** (filed Aug 2025). Corrections must go through **GSTR-1A** for the same period before filing 3B. — [GSTN advisory (Maharashtra GST copy)](https://www.mahagst.gov.in/public/uploads/gstnadvisory/1760596521_352%20Advisory%20regarding%20non-editable%20of%20auto-populated%20liability%20in%20GSTR-3B.pdf); [PTI via The Week](https://www.theweek.in/wire-updates/business/2025/06/07/dcm15-biz-gst-return-edit.html)
  - GSTR-1A can be filed only once per period. — [ELP Law](https://elplaw.in/leadership/advisory-issued-by-goods-service-tax-network/)
  - The locking was first proposed for Jan 2025 and deferred. — [Lakshmikumaran & Sridharan](https://lakshmisri.com/insights/articles/hard-locking-gstr-3b-a-new-compliance-milestone-and-its-pitfalls)
  - **Conflict:** [SCC Online](https://www.scconline.com/blog/?p=351217) reports that Table 3.2 was kept editable (16 May 2025 advisory), while [Taxmann](https://www.taxmann.com/post/blog/gstr-3b-table-3-2-to-be-auto-populated-and-non-editable) reports a 19 July 2025 advisory making 3.2 non-editable from July 2025. Unresolved.

**ITC utilisation order**
- **Rule 88A (inserted 2019):** IGST ITC must be used first for IGST. Any balance may then be used for CGST and SGST/UTGST "in any order and in any proportion" (Circular 98/17/2019 dated 23 Apr 2019). CGST and SGST/UTGST ITC can be used only after IGST ITC is exhausted. CGST credit pays CGST and then IGST. SGST/UTGST credit pays SGST/UTGST and then IGST. CGST credit can never pay SGST/UTGST, and vice versa. — [TaxAdda](https://taxadda.com/order-of-utilisation-of-input-tax-credit-under-gst/); [Taxmann on CBIC clarification](https://www.taxmann.com/post/blog/clarifications-on-rule-88a-order-of-utilization-of-input-tax-credit-issued-by-cbic/); [TaxGuru Rule 88A](https://taxguru.in/goods-and-service-tax/rule-88a-cgst-rules.html)
- **Effective date:** sources give 29.03.2019 / 1 Apr 2019 / a 4 Apr 2019 notification date. — same sources (minor disagreement)
- **RCM is cash-only:** "output tax" (s.2(82)) excludes tax payable on reverse charge, and s.49(4) lets the electronic credit ledger pay only output tax. RCM liability is therefore paid from the electronic cash ledger (Rule 87). ITC on it is then available if otherwise eligible. — [TaxHeal](https://taxheal.com/pay-output-tax-cash-reverse-charge-gst-gst-itc-cant-claimed.html); [ClearTax CGST Rules Ch. 9](https://cleartax.in/s/cgst-rules-chapter-9-payment-of-tax); [WIRC-ICAI material](https://old.wirc-icai.org/images/material/Reverse-Charge-under-GST-DG.pdf)

### Inferences
- **GSTR-1 bucketing** of a sales register:
  - Buyer GSTIN present (valid) → **B2B** (4A, or 4B if RCM).
  - No GSTIN, inter-state (POS ≠ supplier state) and invoice value > Rs 1,00,000 → **B2CL** (Table 5). Use > Rs 2,50,000 only if the portal still enforces the older limit.
  - Other no-GSTIN supplies → **B2CS**, aggregated by POS × rate (Table 7).
  - Export/SEZ flag → **Table 6**.
  - Nil/exempt/non-GST → **Table 8**.
  - Credit/debit notes → **Table 9B**, split by registered/unregistered.
  - HSN × UQC × rate aggregate, separately for B2B and B2C → **Table 12**.
  - Document serial ranges and cancelled counts → **Table 13**.
- **GSTR-3B 3.1 from the same data:**
  - (a) = taxable value and tax of all non-zero-rated taxable outward supplies, net of credit/debit notes;
  - (b) = exports/SEZ;
  - (c) = nil + exempt;
  - (d) = purchase-register RCM lines (tax computed by the recipient);
  - (e) = non-GST.
  - **3.2** = the B2C inter-state portion, plus inter-state supplies to composition dealers and UIN holders, by POS.
- **Net payable algorithm per head, following Rule 88A:**
  1. Apply IGST credit to IGST liability.
  2. Spread the balance across CGST and SGST in any proportion. Software should pick the split that minimises cash, e.g. fill whichever head has less own credit.
  3. Apply CGST credit to remaining CGST, then to remaining IGST.
  4. Apply SGST credit to remaining SGST, then to remaining IGST.
  5. Cess credit pays only cess.
  6. Whatever remains is cash, plus all RCM tax (3.1(d)), which is always cash.
  7. Round the final cash per head to the nearest rupee (s.170).
- **[statute knowledge, not fetched]** The s.49(5)(c)/(d) proviso adds one more constraint: SGST/UTGST credit can pay IGST only once CGST credit available for IGST is exhausted. Code it so CGST credit is applied to residual IGST before SGST credit.
- **Worked example** (illustrative, my numbers): liability IGST 500, CGST 300, SGST 300; credit IGST 1,000, CGST 300, SGST 300.
  1. IGST credit pays IGST 500. The remaining 500 is split, e.g. CGST 250 and SGST 250.
  2. CGST credit pays the remaining CGST 50; SGST credit pays the remaining SGST 50.
  3. Cash = 0. Carried forward: CGST 250 and SGST 250. This split leaves the most usable balance; an alternative 300/200 split leaves CGST 300 and SGST 200.
- Because liability is now hard-locked to GSTR-1/1A, a dashboard's "3B liability" must equal the GSTR-1 view of the same period. Any edit to sales data after GSTR-1 is filed should be routed as a GSTR-1A or next-period amendment, not as a silent 3B change.

### Gaps
- I did not verify whether the GST portal now enforces the Rs 1 lakh B2CL threshold, since the latest advisory found was Sept 2024.
- I did not find the official dates for the HSN Table 12 B2B/B2C split and mandatory dropdown (commonly cited as phased in during 2025) from a GSTN advisory in this session.
- The final status of Table 3.2 locking is unresolved (sources conflict).
- I did not fetch the official GSTR-3B form notification text. Row labels come from Zoho and ClearTax summaries.
- I did not fetch the statutory text of s.49(5) and its proviso.

---

## 4. Input tax credit basics: eligibility, blocked credits (s.17(5)), GSTR-2B matching

### Takeaway
ITC is claimable only if all of the following hold:
- the buyer holds a tax invoice;
- the invoice appears in the buyer's **GSTR-2B** (s.16(2)(aa)), which is generated after accept/reject/pending actions in the **Invoice Management System (IMS)**;
- the goods or services are received;
- the supplier has paid the tax;
- the claim is made within the **s.16(4)** time limit: 30 November after the end of the FY, or the annual return date if earlier;
- the item is not blocked by **s.17(5)**.

ITC must be reversed if the supplier is not paid within 180 days (Rule 37) and proportionately for exempt or non-business use (Rules 42/43).

### Cited Findings
- **IMS actions:** a recipient can **accept**, **reject** or keep **pending** each inward record in IMS. Accepted records flow to GSTR-2B Table 4. Rejected records are excluded from GSTR-2B and ITC. Pending records stay out of GSTR-2B/3B until acted on. Records with no action are deemed accepted. A wrongly rejected record can be accepted again before GSTR-3B is filed. — [IRIS GST guidance note on IMS](https://irisgst.com/guidance-note-on-invoice-management-system-ims/); [GSTN additional FAQ on IMS, 17 Oct 2024](https://gstgyaan.com/pdf/additional-faq-on-ims-17-10-2024.pdf); [AI Accountant](https://www.aiaccountant.com/blog/gstr-2b-means-itc-rules)
- **Section 16(2)(aa):** an invoice must appear in GSTR-2B before ITC can be availed. **Section 16(4):** ITC cannot be claimed after 30 November following the end of the FY or the annual-return filing date, whichever is earlier. Pending IMS records cannot be carried beyond this. — [AI Accountant](https://www.aiaccountant.com/blog/gstr-2b-means-itc-rules); [IRIS](https://irisgst.com/?p=50388)
- One blog claims IMS became **mandatory for every regular GSTR-3B filer from 1 April 2026**. This is single-source and unverified. — [LegalRaasta](https://www.legalraasta.com/blog/?p=36605)
- **Reversal classes in 3B:**
  - Rule 37 (non-payment to supplier within 180 days) and s.16(2)(b)/(c) are *temporary* reversals (4(B)(2)), reclaimable via 4(A)(5).
  - Rules 38/42/43 and s.17(5) are *permanent* reversals (4(B)(1)).
  - Source: [ClearTax](https://cleartax.in/s/table-4-of-gstr-3b)
- **Section 17(5) blocked credits:**
  - motor vehicles for passengers with seating ≤13 (including driver), except when used for further supply of vehicles, passenger transport or driver training; vehicles seating >13 and goods carriages are generally eligible;
  - vessels and aircraft;
  - food and beverages, outdoor catering, beauty treatment, health services, cosmetic/plastic surgery;
  - renting of motor vehicles, life and health insurance, except where used for an outward supply of the same category or obligatory for an employer under law;
  - membership of clubs, health and fitness centres; travel benefits to employees;
  - works contract for construction of immovable property, except plant and machinery or as input for further works contract;
  - goods/services for construction of immovable property on own account;
  - composition tax;
  - goods/services for personal consumption;
  - goods lost, stolen, destroyed, written off, or disposed of as gifts or free samples;
  - **CSR** expenditure (added from 1 Oct 2023);
  - tax paid on demands involving fraud, detention or confiscation.
  - Source: [TaxGuru on blocked ITC](https://taxguru.in/goods-and-service-tax/input-tax-credit-claimed-itc-blocked-transactions-reg.html); [CG GST, Section 17 PDF](https://cggst.com/wp-content/uploads/2023/06/Section-17-1.pdf); [Busy](https://busy.in/gst/what-is-blocked-credit-in-gst-a-guide-to-section-175/); [Razorpay](https://razorpay.com/learn/section-17-5-cgst-act/)
- s.17(5)(d) now reads "**plant and machinery**" (not "plant or machinery") **retrospectively from 1 July 2017**. This amendment was made by Finance Act 2025, after the Supreme Court's Safari Retreats ruling. — [Busy](https://busy.in/gst/what-is-blocked-credit-in-gst-a-guide-to-section-175/) (sources differ on framing; verify the Act text)
- **Post-sale discounts:** the 56th Council recommended amending s.15(3)/s.34 so that post-sale discounts reduce value only through a GST credit note. The recipient must then reverse the matching ITC. Discounts given through financial/commercial credit notes need no ITC reversal (clarification to be issued). — [GST Council press release, Annexure V item 7](https://gstcouncil.gov.in/sites/default/files/2025-09/press_release_press_information_bureau.pdf)

### Inferences
- **Purchase-register ITC pipeline:**
  1. Classify each line as eligible, blocked under s.17(5) (via expense-ledger/HSN mapping: motor car, food, club, staff welfare, construction, etc.), or common-use (Rule 42/43 apportionment).
  2. Match it against GSTR-2B. Use the key (supplier GSTIN, normalised invoice number, invoice date, taxable value, tax), with fuzzy matching on invoice number (strip "/", "-", leading zeros, FY prefixes) and a ±Rs 1 tolerance on amounts.
  3. Bucket the result as: matched; in books not in 2B (defer; it cannot be claimed yet); in 2B not in books (missing purchase entry); amount/date/GSTIN mismatch.
- **Sanity checks:**
  - ITC claimed in a period should be ≤ 2B eligible ITC plus RCM paid in cash.
  - Flag invoices older than the s.16(4) cut-off.
  - Flag unpaid supplier invoices older than 180 days (needs a creditor ageing ledger) for Rule 37 reversal.
- Wrong-state ITC (CGST/SGST charged by an out-of-state hotel, for example) belongs in 4(D)(2) as not available. An "SGST input where supplier state ≠ own state" check catches it.

### Gaps
- I did not fetch the official CGST Act s.16/s.17 text. The clause-by-clause list above comes from secondary summaries.
- I could not officially confirm that IMS is mandatory from 1 April 2026.
- I did not verify current ITC-specific GSTR-2B changes in 2026, such as any move to make 2B/IMS figures non-editable in 3B Table 4.
- I did not research Rule 42/43 apportionment formulas in detail.

---

## 5. GSTIN format validation (15 characters, state code, PAN, checksum)

### Takeaway
A regular GSTIN has 15 characters:
- 2-digit state code;
- 10-character PAN (5 letters, 4 digits, 1 letter);
- 1 entity code (1–9, then A–Z, counting registrations under the same PAN in that state);
- "Z" by default;
- 1 check character computed with a mod-36 algorithm over the first 14 characters.

I tested the algorithm in this session against the sample GSTIN that appears in the sources (27AAPFU0939F1ZV → check char "V"). It reproduces the check character.

### Cited Findings
- **Positions 1–2:** state code. **3–12:** PAN. **13:** entity/registration number. **14:** "Z" by default (some sources say reserved). **15:** check code. — [AI Accountant: GSTIN format](https://www.aiaccountant.com/blog/gstin-format); [Tally: GSTIN format](https://awsdevint.tallysolutions.com/gst/gstin-gst-number-registration-format-search-status/); [Petpooja GSTIN tool](https://blog.petpooja.com/free-tools/gstin-verification-free/)
- The 15th character is a checksum, described as "mod-36". Sample: 27AAPFU0939F1ZV, where V is the checksum. — [Commmerce GSTIN validator](https://commmerce.com/tools/gstin-validator.md); [AI Accountant](https://www.aiaccountant.com/blog/gstin-format)
- **Algorithm** (as commonly implemented; no official GSTN specification was found). I executed it in this session, and it returned "V" for `27AAPFU0939F1Z`, matching the published sample:
  ```python
  CS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
  def gstin_check_char(first14: str) -> str:
      total = 0
      for i, ch in enumerate(first14.upper()):
          factor = 1 if i % 2 == 0 else 2      # weights 1,2,1,2,... from the left
          prod = CS.index(ch) * factor
          total += prod // 36 + prod % 36      # add "digits" in base 36
      return CS[(36 - total % 36) % 36]
  ```
  Validation: `len(g) == 15`, a regex match, `g[:2]` in the valid state-code set, and `gstin_check_char(g[:14]) == g[14]`. — algorithm description from the sources above; execution test is my own.

### Inferences
- Regex for regular taxpayers: `^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$`.
- **PAN 4th character** gives entity type (P individual, C company, F firm, H HUF, A AOP, T trust, B BOI, L local authority, J artificial juridical person, G government). [statute/PAN-structure knowledge, not fetched.] This is useful for a soft "entity type" sanity check.
- **Other registration types use different patterns**, so a strict regex should fall back to a checksum-only test with a "special registration" label rather than hard-failing. Examples: TDS/TCS registrations, UIN holders (embassies/UN), non-resident OIDAR (state code 99, e.g. "9917…"), and NRTP. [knowledge, not fetched.]
- **Cross-field checks:**
  - own GSTIN state code must equal the branch's state;
  - a supplier GSTIN in a purchase register must not equal own GSTIN;
  - the same PAN with a different state code means a related-branch transaction (taxable inter-state stock transfer).
- **Vectorisation:** the checksum loops over 14 characters, so for large registers apply it on the *unique* GSTINs (`df['gstin'].drop_duplicates()`) and map back.

### Gaps
- I found no official GSTN or CBIC document publishing the checksum algorithm. It is reverse-engineered and industry-standard, and it is validated here only against one published sample.
- I did not source the patterns for UIN, TDS, TCS, OIDAR and NRTP GSTINs.
- Live GSTIN status (active, cancelled, suspended) needs a GSP/GST public API. Out of scope here.

---

## 6. Common data errors in registers and how software flags them

### Takeaway
Most register errors fall into five groups:
- tax that does not equal rate × taxable value, including the case where the "taxable" column actually holds an inclusive amount;
- the wrong tax type for the place of supply: IGST together with CGST/SGST, IGST on an intra-state sale, or CGST/SGST on an inter-state one;
- unequal CGST and SGST;
- invalid or stale rates for the invoice date (12%/28% after 22 Sept 2025, or cess after the cut-offs);
- invalid GSTINs or state codes.

Each can be detected deterministically with vectorised pandas rules derived from Sections 1, 2 and 5. Except where cited, the rules below are my design inferences from the rules in Sections 1–5.

### Cited Findings
- An intra-state supply carries CGST + SGST at half the rate each, and an inter-state supply carries IGST at the full rate. An invoice therefore cannot correctly carry both IGST and CGST/SGST for the same supply. — [CBIC IGST s.7](https://taxinformation.cbic.gov.in/content/html/tax_repository/gst/acts/2017_IGST_Act/active/chapteriv/section7_v1.00.html); [KnowYourGST s.8](https://www.knowyourgst.com/gstlaw/igst-act/8-intra-state-supply-182/); [ClearTax calculator](https://cleartax.in/s/gst-calculator)
- SEZ supplies are inter-state even when the SEZ is in the supplier's own state, so IGST applies. — [CBIC IGST s.7](https://taxinformation.cbic.gov.in/content/html/tax_repository/gst/acts/2017_IGST_Act/active/chapteriv/section7_v1.00.html); [KnowYourGST s.8](https://www.knowyourgst.com/gstlaw/igst-act/8-intra-state-supply-182/)
- The portal accepts amounts to 2 decimals, and invoice-level round-off is a separate field. — [Gimbooks](https://www.gimbooks.com/blog/gst-invoice-round-off-differences/)
- GSTR-1 Table 12 now carries value and tax validations, and HSN is selected from a dropdown. Mismatches between the HSN summary and invoice totals are therefore a filing-time issue. — [ClearTax GSTR-1](https://cleartax.in/s/details-mentioned-return-gstr-1)
- Because 3B liability is locked to GSTR-1/1A from the July 2025 period, errors in the sales register flow straight into the payable amount unless they are fixed before GSTR-1/1A is filed. — [GSTN advisory](https://www.mahagst.gov.in/public/uploads/gstnadvisory/1760596521_352%20Advisory%20regarding%20non-editable%20of%20auto-populated%20liability%20in%20GSTR-3B.pdf)

### Inferences
Suggested validation rules (error = blocks the summary, warn = surfaced for review). Define `tax = cgst + sgst + igst`, `is_intra = (pos == own_state)`, and `tol = max(1.0, 0.0005 * taxable)`.

| # | Rule | Severity |
|---|---|---|
| 1 | `igst > 0 & (cgst > 0 \| sgst > 0)` on the same line or invoice | Error |
| 2 | `abs(cgst - sgst) > 0.05` (intra-state halves must match) | Error |
| 3 | `is_intra & igst > 0 & ~sez_or_export` | Error (or warn if a POS override exists, e.g. a hotel or event in another state) |
| 4 | `~is_intra & (cgst + sgst) > 0` | Error |
| 5 | `abs(tax - taxable*rate/100) > tol` | Error |
| 6 | `abs(tax - taxable*rate/(100+rate)) <= tol`, i.e. the "taxable" column is really tax-inclusive | Warn and suggest auto-fix |
| 7 | `rate` not in the valid set for `invoice_date` (Section 2 table; 12/28 after 22 Sept 2025 except tobacco HSNs until 31 Jan 2026) | Error |
| 8 | Rate implied by the tax (`tax/taxable*100`) is not a valid slab, while the `rate` column is blank | Infer the rate, then warn |
| 9 | Cess > 0 on non-tobacco HSN on/after 22 Sept 2025, or any compensation cess on/after 1 Feb 2026 | Warn |
| 10 | GSTIN fails regex, state-code set or checksum | Error |
| 11 | `buyer_gstin[:2] != pos` | Warn (legitimate for bill-to-ship-to and some services) |
| 12 | `own_gstin[:2] != branch_state`, or supplier GSTIN == own GSTIN | Error |
| 13 | POS invalid or missing, or code 25/28 used after its retirement | Error |
| 14 | B2B row (GSTIN present) with RCM flag where the supplier also charged tax | Warn |
| 15 | B2C inter-state invoice > Rs 1 lakh without POS (B2CL) | Error |
| 16 | Duplicate (GSTIN, invoice no., FY), or invoice no. > 16 chars / invalid characters [Rule 46 limit, statute knowledge, not fetched] | Error |
| 17 | Invoice date outside the selected return period; future-dated invoices | Warn |
| 18 | Credit note with positive sign (or vice versa), or credit note larger than the original invoice | Warn |
| 19 | Sum of line tax ≠ invoice-level tax beyond Rs 1 (round-off misposted) | Warn |
| 20 | Rate 0 but tax > 0, or exempt/nil row with tax | Error |
| 21 | Purchase: CGST/SGST from a supplier whose GSTIN state ≠ own state (ITC unavailable, 4(D)(2)) | Warn |
| 22 | Purchase line mapped to a blocked category (s.17(5)) but ITC claimed | Warn |
| 23 | Purchase not in GSTR-2B, or 2B record not in books | Warn (reconciliation) |
| 24 | HSN missing, or fewer than 4/6 digits for the turnover band | Warn |

- **Pandas pattern:** compute every rule as a boolean column (`df['e_both_taxes'] = ...`). Build `df['issues']` by joining the names of rules that are True. Then summarise counts by rule and by party. This keeps checks fast (vectorised) and explainable.
- **Auto-repair suggestions** (always shown to the user, never applied silently):
  - back-calculate the taxable value when rule 6 fires;
  - swap IGST into CGST/SGST halves when rule 3 fires and the POS is confirmed;
  - infer the rate from the tax ratio when the rate is blank.

### Gaps
- I found no official CBIC/GSTN list of register validation rules or e-invoice tolerance thresholds. The thresholds above (Rs 1 per invoice, 0.05% of value, Rs 0.05 for CGST/SGST equality) are design choices, not statutory.
- I did not fetch the Rule 46 invoice-number constraint (16 characters, unique per FY, permitted characters "-" and "/").

---

## 7. Reverse charge mechanism (RCM) and its effect on the summary

### Takeaway
Under RCM the **recipient**, not the supplier, pays the tax on notified goods/services (s.9(3)) and on certain supplies from unregistered persons (s.9(4)). The effect on the summary:
- **Supplier's GSTR-1:** shows the supply in Table 4B, with no tax collected.
- **Recipient's GSTR-3B:** declares the liability in Table 3.1(d) and pays it **in cash only**.
- **Recipient's ITC:** reclaimed, if eligible, in Table 4(A)(3) in the same return.

The net effect for a fully eligible recipient is zero, but the cash outflow is real and cannot be offset by the existing credit balance.

### Cited Findings
- Table 3.1(d) of GSTR-3B is "Inward supplies (liable to reverse charge)". It holds purchases where the recipient pays tax under RCM, including purchases from unregistered suppliers for which the recipient raises a self-invoice. — [Zoho GSTR-3B sections](https://www.zoho.com/en-in/erp/kb/filing-and-compliance/sections-gstr-3b.html); [Masters India docs](https://docs.mastersindia.co/masters-india-gst-software/introduction/gst-return/gstr-3b)
- ITC on RCM supplies is reported separately in Table 4(A) as "inward supplies liable to reverse charge (other than 1 & 2 above)", meaning other than imports of goods and services. — [Zoho](https://www.zoho.com/en-in/erp/kb/filing-and-compliance/sections-gstr-3b.html); [West Bengal GSTR-3B form](https://comtax.wb.gov.in/GST/GST_Forms/GSTR%203B.pdf)
- **RCM tax must be paid through the electronic cash ledger.** "Output tax" (s.2(82)) excludes RCM tax, s.49(4) restricts the credit ledger to output tax, and Rule 87 requires reverse charge amounts to be paid by debiting the cash ledger. After payment, ITC is available if otherwise eligible. — [TaxHeal](https://taxheal.com/pay-output-tax-cash-reverse-charge-gst-gst-itc-cant-claimed.html); [ClearTax CGST Rules Ch. 9](https://cleartax.in/s/cgst-rules-chapter-9-payment-of-tax); [WIRC-ICAI](https://old.wirc-icai.org/images/material/Reverse-Charge-under-GST-DG.pdf)
- On the supplier side, GSTR-1 Table 4B captures B2B supplies on which the recipient pays tax under RCM. — [ClearTax GSTR-1](https://cleartax.in/s/details-mentioned-return-gstr-1)
- One CGST advisory notes that certain inward supplies must be "declared in Table 3.1(d) of FORM GSTR-3B for payment of tax and that credit will not be available on the same". This appears to relate to a specific 2B-reconciliation context (supplier-reported RCM entries), not RCM generally. — reported via search on [West Bengal GSTR-3B material](https://comtax.wb.gov.in/GST/GST_Forms/GSTR%203B.pdf) (context unclear; treat with caution)

### Inferences
- **Purchase register:**
  - Lines flagged RCM, or matching a list of RCM services, should have **supplier tax = 0**.
  - The app computes tax itself (rate × taxable; IGST or CGST/SGST by POS) and posts it to 3.1(d) liability and to 4(A)(3) ITC, less any s.17(5) blocking.
  - It adds the RCM amount to the **cash** requirement regardless of the ITC balance.
- **Sales register:** RCM-flagged B2B lines go to GSTR-1 Table 4B. Their tax is excluded from the supplier's 3.1(a) liability.
- **Common RCM categories** to pre-map: GTA freight (where opted), legal services from advocates, sponsorship, director services, security services from non-body-corporate suppliers, renting of commercial property by an unregistered landlord to a registered tenant, and imports of services (reported as import ITC in 4(A)(2)). [knowledge, not fetched; the official RCM notification list (Notification 13/2017-CT(Rate) as amended) should be pulled to build the master.]
- **RCM rates follow the slab of the underlying service.** For example, GTA is 5% (RCM) or 18%/12% forward-charge options [not verified post-GST 2.0], so the RCM list must also be effective-dated.

### Gaps
- I did not fetch the current s.9(3)/9(4) RCM notification lists or any 2025–26 additions or removals. My recollection of an Oct 2024 RCM on commercial rent from unregistered landlords, and of GTA rate options after GST 2.0, is unverified.
- I did not verify the GSTN "RCM Liability/ITC Statement" (introduced 2024 to track RCM paid vs ITC claimed) or its 2026 status.
- I did not research the self-invoice requirement (Rule 47A, 30-day timeline) in this session.
