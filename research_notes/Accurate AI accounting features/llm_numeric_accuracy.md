# Maximising numeric accuracy of LLM answers over tabular financial data (text-to-SQL / table QA)

Scope: evidence on how accurate LLMs are when answering numeric questions over tables and databases, which techniques measurably help, what OpenAI and Anthropic recommend, what production analytics copilots do, and what error rate remains. The context is Accounts.ai: one SQLite DB per Excel upload, an LLM calling a `run_sql` tool through the OpenAI Responses API (Claude as the alternative). Research date: 22 Oct 2026. Where a source is from before 2024 or is self-reported by a vendor, it is flagged.

---

## Q1. What do benchmarks show about LLM accuracy on numeric/financial table questions, and which error types dominate?

### Takeaway
Even the best text-to-SQL systems in 2026 score about 80–82% execution accuracy on BIRD, against 93% for humans. Frontier models answering single-shot over an unfamiliar analytics schema score only about 46–69%. Financial table-QA benchmarks (TableBench, FinQA) show models well below human level on numerical reasoning. Errors are dominated by schema/semantic mistakes (wrong column, join, filter or business definition), not syntax. Arithmetic slips are a separate, large error class when the model does maths "in its head". The benchmarks are noisy themselves: more than half of BIRD Mini-Dev examples have annotation errors.

### Cited Findings

**Text-to-SQL leaderboards (BIRD, Spider 2.0)**
- Huawei's DataGallery-Text2SQL ranked first on the BIRD public leaderboard as of 9 Sep 2026, with **82.39% execution accuracy (EX)** and an R-VES of 77.64. This is vendor-reported, and it is not stated whether the system is an ensemble. — [Technology Magazine](https://technologymagazine.com/news/huawei-datagallery-tops-benchmark-for-enterprise-text2sql-ai)
- Google's Gemini-SQL2 reportedly reached **80.04% EX** on the BIRD single-model track. The same aggregator lists human performance at **92.96%** on dev, and Claude Opus 4.6 at about 70.1% (unverified aggregator figures; no technical report for Gemini-SQL2 was released as of June 2026). — [AI Weekly](https://aiweekly.co/alerts/googles-gemini-sql2-tops-bird-text-to-sql-at-8004)
- CHASE-SQL (Google, ICLR 2025) reached **73.01% EX on BIRD dev and 73.0% on test**, and 70.33% on dev with open-source models only. — [ICLR 2025 proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/974ff7b5bf08dbf9400b5d599a39c77f-Abstract-Conference.html); [hyper.ai summary](https://hyper.ai/en/papers/2410.01943)
- MAC-SQL (older, Dec 2023) scored 59.39% / 59.59% EX on BIRD dev/test with GPT-4, which shows how much the field moved in 2024–2026. — [arXiv 2312.11242](https://arxiv.org/abs/2312.11242v2)
- Spider 2.0 (enterprise-scale BigQuery/Snowflake/dbt workflows) started very low in 2024: o1-preview at 17.03% and GPT-4o at 10.13% success (third-party aggregator). A later undated leaderboard snapshot shows entries in the 50s–90s, up to about 96.7%, but the variant and date are unclear. — [hyper.ai Spider 2.0](https://hyper.ai/ja/sota/tasks/text-to-sql/benchmark/text-to-sql-on-spider-2-0); [benchmarklist](https://benchmarklist.com/benchmarks/spider_2_0/) (conflicting and undated; treat with caution)

**Directly comparable "business analytics" setting (most relevant to Accounts.ai)**
- *Semantic Layers for Reliable LLM-Powered Data Analytics* (Rumiantsau & Fokeev, arXiv, 28 Apr 2026). Setup: Claude Opus 4.7, Claude Sonnet 4.6 and GPT-5.4 answered 100 natural-language questions over the Contoso Retail dataset (ClickHouse), single-shot. Results:
  - Schema only: **45.5%–50.5%** accuracy.
  - Schema plus a **4 KB hand-written markdown document** of measures, conventions and disambiguation rules: **67.7%–68.7%**, a gain of **+17 to +23 percentage points** (p < 0.01).
  - Within each condition, the three models were statistically indistinguishable. The document, not the choice of model, explained nearly all the variance. — [arXiv 2604.25149](https://arxiv.org/abs/2604.25149)

**Financial / table numerical QA**
- TableBench (2024; 2024-era models) results:
  - The best model, GPT-4-Turbo with textual CoT, scored **51.32% overall**, against **~86% for humans**.
  - On the Numerical Reasoning subset, GPT-4-Turbo scored 53.01 (TCoT) and 49.31 (PoT), against a human score of about 87.1.
  - Raw tables come partly from FinQA. — [arXiv 2408.09174](https://arxiv.org/html/2408.09174v2)
- TAT-LLM (2024): a fine-tuned 7B LLaMA-2 that uses an **external executor for calculations** outperformed GPT-4 on FinQA, TAT-QA and TAT-DQA. — [arXiv 2401.13223](https://arxiv.org/html/2401.13223v3)
- FinAgent-RAG (May 2026) reported 76.81% on FinQA, 78.46% on ConvFinQA and 74.96% on TAT-QA. **However, the paper was withdrawn in July 2026 for "significant methodological errors in the experimental design"**, so do not rely on its numbers, including a widely repeated claim that PoT removed 88% of arithmetic errors. — [arXiv 2605.05409](https://arxiv.org/abs/2605.05409)

**Error types**
- Shen et al. (2025) built a 29-type error taxonomy in 7 categories from 4,602 incorrect queries produced by in-context-learning text-to-SQL systems on Spider/BIRD. A secondary summary reports that **schema-related errors cause over 80% of execution failures**. I did not verify the 80% figure in the primary text. — [arXiv 2501.09310](https://arxiv.org/html/2501.09310v1)
- NL2SQL-BUGs (2025) is a benchmark of 2,018 expert-annotated semantic errors (9 main categories, 31 subcategories). SOTA LLMs reach only **~75.16% accuracy at detecting** whether SQL is semantically wrong, so LLM self-checking of SQL is far from reliable. — [arXiv 2503.11984](https://arxiv.org/pdf/2503.11984)
- SQL-of-Thought's correction taxonomy uses schema linking, join, filter, aggregation and subquery errors as its main categories. — [arXiv 2509.00581](https://arxiv.org/pdf/2509.00581)
- Snowflake says the main difficulty is that the model must infer "how tables relate and the hidden caveats", which is what its semantic model supplies. — [Snowflake engineering blog](https://snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes)
- FinQA error analyses:
  - FINDER (GPT-4 generating executed Python): of 100 errors, **9% retrieval, 7% ground-truth issues, and the remainder logical errors**, such as computing a signed difference when the question wanted absolute change. This is a search summary of the paper; I did not read the full text. — [arXiv 2510.13157](https://arxiv.org/pdf/2510.13157)
  - A 40-error review found arithmetic (3) and retrieval (3) errors tied as the most common. The sample is very small. — [arXiv 2310.14435](https://arxiv.org/pdf/2310.14435)
  - The original FinQA paper (2021, RoBERTa era, older) found 15% of errors came from the retriever. — [arXiv 2109.00122](https://arxiv.org/pdf/2109.00122)

**Benchmark noise**
- *Pervasive Annotation Errors Break Text-to-SQL Benchmarks and Leaderboards* (Jin, Choi, Zhu, Kang; Jan 2026; CIDR 2026). Findings:
  - Expert-verified annotation error rates: **52.8% on BIRD Mini-Dev** and **62.8% on Spider 2.0-Snow**.
  - Re-evaluating 16 BIRD agents on a corrected subset shifted relative performance by **−7% to +31%** and ranks by ±9.
  - Rank correlation with the full Dev set fell from 0.85 to 0.32. — [arXiv 2601.08778](https://arxiv.org/abs/2601.08778)
  - A summary of the CIDR version says CHESS moved from 62% to 81% (4th to 1st) after the corrections. The paper versions differ on some figures. — [CIDR 2026 page](https://vldb.org/cidrdb/2026/text-to-sql-benchmarks-are-broken-an-in-depth-analysis-of-annotation-errors.html)

### Inferences
- For Accounts.ai, the **semantic/business-meaning gap** is the dominant risk, not SQL syntax. Examples: what "outstanding", "revenue", "net" or "balance" mean; debit/credit sign conventions; which date column to use; whether to include GST. The 2026 semantic-layer study suggests this is worth roughly 20 points of accuracy, more than switching between frontier models.
- Published accuracy numbers are a noisy upper/lower bound. Benchmark errors cut both ways, so an app-specific evaluation set on real ledgers matters more than leaderboard rank.
- Arithmetic done in model text is a distinct, avoidable error class. Older PoT and TAT-LLM evidence, plus the TableBench PoT results, support always computing with SQL or code.

### Gaps
- I found no benchmark built specifically on small-business ledgers, invoices or bank statements in SQLite. All numbers are from generic BI datasets (BIRD, Contoso) or SEC-filing QA (FinQA/TAT-QA).
- No 2025–2026 FinQA/TAT-QA leaderboard figures for current frontier models (GPT-5.x/6, Claude 4.x/5.x) were found from a primary, non-withdrawn source.
- A schema-linking error rate of "29%–49% on Spider/BIRD" appeared in a search summary attributed to an LLM text-to-SQL survey, but I could not confirm which paper it came from.
- The hallucination-rate figures in the semantic-layer paper (arXiv 2604.25149) were not in the abstract, and the PDF was not machine-readable.

---

## Q2. Which techniques have evidence of improving accuracy, and how much?

### Takeaway
The strongest evidence, in rough order of impact for a small single-DB app, is:
1. Rich schema/semantic context, including descriptions, business rules, distinct values and relationships (+17–23 pp in a 2026 controlled study).
2. Delegating all arithmetic to executed code/SQL instead of the model (PoT about +12% average over CoT, older evidence).
3. Execution feedback and refinement loops (removing a refiner cost 4.6–9.3 pp in ablations).
4. Clarification and abstention for ambiguous questions (large relative gains in research systems).
5. Generating multiple SQL candidates and selecting by execution result. This gives a small overall gain (~1.5 pp) but a larger one on hard questions (~7.6 pp), and a trained selector beats plain voting.
6. Few-shot or "verified query" examples retrieved by similarity.

Grounding checks that every number in the answer came from a tool output are recommended by recent work and are mechanically cheap, but I found no benchmark quantifying their effect.

### Cited Findings

**1. Schema descriptions, business semantics, sample values (schema linking)**
- Adding a 4 KB markdown semantic document raised accuracy by 17–23 pp for Claude Opus 4.7, Sonnet 4.6 and GPT-5.4 (to 67.7–68.7%). — [arXiv 2604.25149](https://arxiv.org/abs/2604.25149)
- Snowflake reportedly measured the same LLM going from **57% to 78% on BIRD-SQL after adding a semantic model**. This is a third-party summary that I could not verify in Snowflake's primary source. — [Atlan](https://atlan.com/know/snowflake/cortex-analyst-vs-text-to-sql/)
- Cortex Analyst's semantic model holds descriptive names, **synonyms**, descriptions, instructions, and pre-defined metrics and filters, and limits the model to relevant columns. Its context-enrichment step uses semantic search to retrieve **relevant literal values**, so that "USA" maps to "United States of America". — [Snowflake engineering blog, Aug 2024](https://snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes)
- In vendor tests, showing **distinct values per column** worked better than raw inserted rows or a `SELECT * LIMIT 3` preview, and adding **foreign-key relationships** improved accuracy. The underlying paper is not named, so treat this as a vendor claim. — [Actian blog](https://www.actian.com/blog/ai-and-ml/prompting-llms-for-text-to-sql/)
- LangChain's SQL chain appends sample rows after each `CREATE TABLE` to make data formats clear. This is practice, with no measured effect. — [LangChain docs](https://lagnchain.readthedocs.io/en/stable/modules/chains/examples/sqlite.html)
- Databricks Genie guidance:
  - Add table/column descriptions and **synonyms matching business terms**.
  - **Hide unnecessary or duplicate columns**.
  - Define PK/FK relationships so joins are correct.
  - Start with a small set of instructions and expand them based on test failures. — [Databricks tune-quality docs](https://docs.databricks.com/aws/en/genie/tune-quality); [Databricks blog](https://databricks.com/blog/5-key-lessons-implementing-aibi-genie-self-service-marketing-insights)
- Uber QueryGPT:
  - Accuracy **declined as more tables and SQL samples were onboarded**.
  - Plain similarity search over schemas and SQL was not enough, so Uber added an intent classifier and curated "workspaces" to narrow the tables shown.
  - Tables with 200+ columns could consume 40–60K tokens.
  - The design took 20+ iterations. — [Uber blog](https://www.uber.com/blog/query-gpt)

**2. Delegating arithmetic to code/SQL (Program-of-Thought, calculators)**
- Program of Thoughts (Chen et al., Nov 2022, **older**): separating computation (executed Python) from reasoning gave an **average gain of about 12% over CoT** across math and financial datasets (FinQA, ConvFinQA, TATQA). PoT plus self-consistency reached near-SoTA on the financial datasets at the time. — [arXiv 2211.12588](https://arxiv.org/abs/2211.12588)
- TableBench (2024) found:
  - PoT "delivers commendable results in purely numerical computations" but falls short in textual reasoning.
  - Its PoT scores were capped because code was generated once with no correction. GPT-4-Turbo's **executable-code ratio was only 78.67%**.
  - So PoT needs an execution-error retry loop to pay off. — [arXiv 2408.09174](https://arxiv.org/html/2408.09174v2)
- TAT-LLM's external executor for calculations let a 7B model beat GPT-4 on FinQA/TAT-QA/TAT-DQA (2024). — [arXiv 2401.13223](https://arxiv.org/html/2401.13223v3)
- Caution: the FinAgent-RAG claim that PoT "eliminates 88% of arithmetic errors" comes from a paper **withdrawn for methodological errors**. — [arXiv 2605.05409](https://arxiv.org/abs/2605.05409)

**3. Execution-guided self-correction (feeding SQL errors and results back)**
- MAG-SQL (2024): removing its Sub-SQL Refiner dropped BIRD dev EX from **57.62 to 48.31 (−9.3 pp)** with GPT-3.5. — [arXiv 2408.07930](https://arxiv.org/pdf/2408.07930)
- MAC-SQL (Dec 2023, older): removing the Refiner reportedly cost **−4.63 pp** on BIRD dev, the largest single component. This comes from a secondary source and was not verified in the paper table. — [beancount.io research log](https://beancount.io/bean-labs/research-logs/2026/06/08/mac-sql-multi-agent-collaborative-text-to-sql); [MAC-SQL paper](https://arxiv.org/abs/2312.11242v2)
- Snowflake Cortex Analyst runs an **error-correction agent** that checks generated SQL with the SQL compiler and loops the LLM to fix syntax/semantic errors, including hallucinated entities or functions. — [Snowflake engineering blog](https://snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes)

**4. Multiple candidates, self-consistency, selection**
- OpenSearch-SQL (2025): 67.8 EX with single generation versus **69.3 with self-consistency and voting (~+1.5 pp)** on BIRD dev. The gain is concentrated on hard questions (**~+7.6 pp**), with little change on easy/medium ones. This is from a search summary of the paper's tables; the PDF was not machine-readable for me. — [arXiv 2502.14913](https://arxiv.org/pdf/2502.14913)
- CHASE-SQL generates diverse candidates (divide-and-conquer, query-plan CoT, instance-aware synthetic few-shot) and picks one with a **fine-tuned pairwise selection model**. The paper reports that this selector **outperforms consistency (majority) voting**. — [ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/974ff7b5bf08dbf9400b5d599a39c77f-Abstract-Conference.html)
- CSC-SQL (2025) argues plain majority voting can select a suboptimal output and adds a correction step. It reports 69.19% on BIRD dev with a 7B model. — [arXiv 2505.13271](https://arxiv.org/html/2505.13271v2)
- Query and Conquer (2025) groups candidates by **execution behaviour (result sets) rather than SQL text**. It reports roughly a 10% gain for Qwen2.5-Coder-7B; which benchmark this applies to was unclear from the summary. — [arXiv 2503.24364](https://arxiv.org/pdf/2503.24364)
- Snowflake runs **several SQL-generation agents on different LLMs in parallel**, then a synthesizer agent produces the final query. — [Snowflake engineering blog](https://snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes)

**5. Few-shot / verified example queries**
- Cortex Analyst retrieves **human-verified queries** from the semantic model by semantic similarity and injects them as context. — [Snowflake engineering blog](https://snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes)
- Databricks Genie "trusted assets" are parameterized example SQL queries and registered SQL functions. The "verified" label is shown only when the response matches a trusted asset exactly. — [Databricks tune-quality docs](https://docs.databricks.com/aws/en/genie/tune-quality)
- CHASE-SQL's "instance-aware synthetic few-shot" generator is one of its three candidate sources. — [ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/974ff7b5bf08dbf9400b5d599a39c77f-Abstract-Conference.html)
- OpenAI notes that examples in prompts **may hurt performance on reasoning models**, so few-shot should be evaluated rather than assumed helpful. — [OpenAI function-calling guide](https://developers.openai.com/api/docs/guides/function-calling)

**6. Clarifying questions and abstention on ambiguous or unanswerable queries**
- AmbiSQL (2025) does interactive ambiguity detection and question rewriting. It reports **87.2% precision** in detecting ambiguity and a **50% relative gain** in SQL exact-match when paired with text-to-SQL systems. — [arXiv 2508.15276](https://arxiv.org/html/2508.15276v1)
- PRACTIQ (NAACL 2025) is a conversational text-to-SQL dataset with 4 ambiguous and 4 unanswerable categories, each with a clarification turn. LLM baselines struggle with these. — [Amazon Science](https://amazon.science/publications/practiq-a-practical-conversational-text-to-sql-dataset-with-ambiguous-and-unanswerable-queries)
- Cortex Analyst's first agent classifies questions as ambiguous or non-data and **rejects them**, offering similar answerable questions instead of guessing. — [Snowflake engineering blog](https://snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes)
- The annotation-error study lists "ambiguous questions" as one of four root patterns of wrong gold labels, so even expert annotators disagree on ambiguous wording. — [CIDR 2026 page](https://vldb.org/cidrdb/2026/text-to-sql-benchmarks-are-broken-an-in-depth-analysis-of-annotation-errors.html)

**7. Grounding / number-verification checks**
- Proof-Carrying Numbers (PCN, 2025):
  - The model emits numbers as tokens bound to structured claims, and a verifier checks each against the source under a declared policy (exact, rounding, tolerance).
  - Verification sits in the **renderer**, not the model, and is **fail-closed**: unverified numbers are marked unverified.
  - The paper claims formal soundness properties. — [arXiv 2509.06902](https://arxiv.org/abs/2509.06902v1)
- A practitioner pattern: attach provenance (which tool result each figure came from) and mechanically compare the figure in the prose to that result. Saying 4.2% when the query returned 6.8% is a mechanically catchable faithfulness error. — [tianpan.co blog](https://tianpan.co/blog/2026/05/17/agent-narrated-a-number-it-should-have-computed)
- A practitioner reports that asking the generator to "be careful" did not help. Verifying each extracted claim against source data with a **separate** model did. This is anecdotal. — [DZone](https://dzone.com/articles/fact-check-llm-outputs)
- LLMs detect semantic SQL errors only about 75% of the time (NL2SQL-BUGs), so LLM-as-judge verification is a partial net, not a guarantee. — [arXiv 2503.11984](https://arxiv.org/pdf/2503.11984)

### Inferences
These are implementation patterns for Accounts.ai, derived from the findings above. Points marked "engineering judgement" are general knowledge, not researched here.

- **Auto-build a per-upload "data dictionary" prompt** (a mini semantic layer) and let the user edit it. It should contain:
  - each column's name, inferred type, plain-English meaning, units and currency;
  - the debit/credit sign convention;
  - for low-cardinality columns (party names, ledger heads, voucher types, GST rates), the distinct values, or the top N with counts;
  - min/max dates and amounts;
  - row counts;
  - 3–5 sample rows;
  - business rules such as "Outstanding = invoice amount − payments received" and "Revenue excludes GST".

  This is the single highest-evidence lever (+17–23 pp in arXiv 2604.25149).
- **Normalise at ingest so the LLM cannot get formats wrong** (engineering judgement):
  - Convert dates to ISO `YYYY-MM-DD`.
  - Strip currency symbols and thousands separators (including Indian lakh grouping).
  - Convert amounts to numbers. Store money as integer paise or as exact decimals, since floating-point REAL can produce 0.1+0.2-style drift in sums.
  - Split debit/credit or apply a consistent sign.
  - Record any rows that failed to parse, and surface them.
- **Never let the model do arithmetic in prose.** Every total, difference, percentage or average must come from SQL (`SUM`, `ROUND`) or from a `calculate` tool executed in Python with `decimal`. Instruct the model, and enforce it with the grounding check below.
- **Execution feedback loop:** return SQLite error text, "0 rows", and suspicious results (NULL sums, unexpectedly large row counts from a join fan-out) to the model with an explicit retry budget of 2–3. This mirrors the refiner components that were worth 4.6–9.3 pp.
- **Cheap self-consistency for money questions:**
  - Generate 2–3 SQL candidates, at different temperatures or from GPT plus Claude, or with a "write an independent cross-check query" instruction.
  - Execute them all and compare **result values**, not SQL text.
  - If they agree, answer with higher confidence. If they disagree, show the assumption difference or ask a clarifying question.
  - Evidence suggests the gain concentrates on hard questions, which is where accounting queries such as ageing, reconciliations and period comparisons sit.
- **Grounding gate before display (fail-closed):** require the final answer as structured output, for example `{answer_text, figures:[{value, query_id, row/col}], sql:[...], assumptions:[...], needs_clarification}`. Then programmatically check that every number in `answer_text` equals (after rounding rules) a value in a tool result, or a `calculate` output. If any number fails, block or regenerate the answer, or mark it "unverified".
- **Verified query library** for the 20–50 standard accounting questions (trial balance, totals by party, receivables ageing, GST payable, monthly sales, top customers, bank balance on date):
  - Implement these as deterministic, tested SQL templates or functions, and let the LLM select and parameterise them, as with Databricks trusted assets and Snowflake verified queries.
  - Label these answers "verified".
  - Free-form SQL is the fallback, labelled accordingly.
- **Clarify or abstain:** add a classification step, or an instruction plus a `needs_clarification` field, for ambiguous terms (which period, which entity, gross or net, include GST?) and for questions the data cannot answer (a column is missing). Say what is missing rather than guess.

### Gaps
- I found no study that isolates the effect of number-grounding checks on end-to-end accuracy or user-visible error rate. The evidence is a protocol paper (PCN) and practitioner posts.
- There are no per-technique ablations on financial or ledger data specifically. The magnitudes above come from BIRD or generic BI datasets.
- The OpenSearch-SQL and MAC-SQL ablation numbers were taken from search summaries or secondary sources, because the PDFs could not be parsed. Verify them before quoting them as exact.
- I did not find controlled 2025–2026 evidence comparing "distinct values" with "sample rows" in prompts, other than a vendor blog citing an unnamed paper.

---

## Q3. What do OpenAI and Anthropic docs recommend for reliable tool use, structured outputs and reasoning effort?

### Takeaway
Both vendors recommend **strict, schema-constrained tool calls**: OpenAI "recommend[s] always enabling strict mode", and Anthropic offers `strict: true` with grammar-constrained sampling. Both also recommend detailed tool descriptions and a small number of well-scoped tools. Strict mode guarantees the *shape* of arguments, not the *correctness* of the SQL or the numbers. OpenAI treats reasoning effort as a tunable knob to choose by evals, not the primary fix for quality. For reasoning models, reasoning items must be passed back across tool calls.

### Cited Findings

**OpenAI: function calling (Responses API)**
- "We recommend always enabling strict mode."
  - Requirements: `additionalProperties: false` on every object, and every property listed in `required`. Optional fields are expressed as a type union with `null`.
  - If `strict` is omitted, Responses tries to normalise the schema into strict mode and falls back to non-strict if it cannot. — [OpenAI function-calling guide](https://developers.openai.com/api/docs/guides/function-calling)
- Schema design guidance:
  - Use enums and object structure to make invalid states unrepresentable.
  - **Don't make the model fill arguments your code already knows.**
  - Combine functions that are always called in sequence.
  - Apply the "intern test".
  - Aim for **fewer than 20 functions**; fewer tools are associated with higher accuracy. — [OpenAI function-calling guide](https://developers.openai.com/api/docs/guides/function-calling)
- Use the system prompt to say when to use and when not to use each function. Include examples for recurring failures, but note that **examples may hurt performance on reasoning models**. — [OpenAI function-calling guide](https://developers.openai.com/api/docs/guides/function-calling)
- `parallel_tool_calls: false` ensures zero or one call per turn. — [OpenAI function-calling guide](https://developers.openai.com/api/docs/guides/function-calling)
- For reasoning models, reasoning items returned with tool calls **must be passed back** with the tool outputs. The simplest way is `previous_response_id` or replaying all output items. — [OpenAI function-calling guide](https://developers.openai.com/api/docs/guides/function-calling); [OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)

**OpenAI: reasoning effort**
- Values are `none`, `minimal`, `low`, `medium`, `high`, `xhigh` and `max`, and each model supports only a subset. Medium is the default on several current models.
  - `high`: for hard reasoning and complex debugging.
  - `xhigh`: only "when your evals show a clear benefit".
  - Effort is "a tuning knob, not the primary way to recover quality".
  - For agentic work, define what "done" means and how the model should verify its work.
  - Reserve at least 25,000 tokens for reasoning plus output, or responses may come back `incomplete` with no visible output. — [OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)
- In long or tool-heavy flows on GPT-5.5/5.4, set the message `phase` field (`commentary` vs `final_answer`), so that preambles are not mistaken for final answers. Function calling with the GPT-6 Astra and GPT-6.1 Sol models requires the Responses API. — [OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning)

**Anthropic (Claude)**
- "Provide extremely detailed descriptions. This is by far the most important factor in tool performance":
  - what the tool does, when to use it and when not to, parameter meanings, and caveats/limitations;
  - **at least 3–4 sentences per tool**.
- Use `input_examples` for format-sensitive inputs, consolidate related operations into fewer tools, and return only high-signal information in tool results. — [Anthropic: Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use)
- `strict: true` guarantees that tool `input` follows `input_schema` and that the tool `name` is valid, via grammar-constrained sampling. Without it, Claude may return `"2"` instead of `2` or omit required fields. — [Anthropic: Strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)
- Forced tool use (`tool_choice: any/tool`):
  - It **returns a 400 error on Claude Opus 5.5, Sonnet 5.5, Fable 5.1 and Mythos 5.1**. On those models, use `auto` with strict tool use, or use structured outputs for a fixed JSON response shape.
  - On models that accept it, forcing a tool **skips thinking**. To let the model think before calling, use `auto` plus a prompt instruction. — [Anthropic: Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use)

### Inferences
- Define `run_sql` with `strict: true` and a minimal schema, for example `{sql: string, purpose: string}`. Have the code inject the DB handle, row limits and timeouts rather than asking the model for them (OpenAI: "don't make the model fill arguments your code already knows").
- Return the final answer through structured outputs (a JSON schema) so the grounding gate can parse figures and SQL reliably.
- Strict mode removes malformed-call failures but does nothing for semantic correctness. The verification layer (Q2) is still required.
- For GPT-6 Luna, check its model page for supported effort levels. Start at `medium` and A/B test `high` on your evaluation set. Always pass reasoning items back across the multi-call `run_sql` loop, or quality can drop mid-chain.
- If you use Claude Opus/Sonnet 5.5, do not rely on forced tool choice. Use `auto` plus instructions that every numeric claim must come from `run_sql`, and enforce it in code.

### Gaps
- I found no OpenAI or Anthropic documentation with quantitative accuracy gains from strict mode or effort levels on data/SQL tasks.
- I found no model-specific guidance for "GPT-6 Luna". The reasoning guide named GPT-5.5, GPT-5.6, GPT-6 Astra and GPT-6.1 Sol.
- I did not fetch Anthropic's page on returning tool errors (`is_error`) or its "Writing tools for agents" engineering post. Both are likely relevant to the SQL retry loop.

---

## Q4. What practical guardrails do production text-to-SQL and analytics copilots use?

### Takeaway
Production systems converge on the same set of guardrails:
- a curated semantic layer (descriptions, synonyms, metric definitions, hidden columns, join keys);
- verified or trusted example queries;
- question classification that rejects ambiguous or non-data questions;
- multi-candidate generation with compiler-based error correction;
- benchmark suites that compare result sets to gold SQL;
- iterative tuning from user feedback.

Vendors' self-reported accuracy with these layers is around 90%. Accuracy drops sharply without them.

### Cited Findings
- **Snowflake Cortex Analyst (Aug 2024)** pipeline:
  1. A classification agent that sends ambiguous or non-SQL questions back with suggested answerable alternatives.
  2. A feature-extraction agent (time-series, period-over-period, ranking).
  3. Context enrichment with verified queries and literal-value retrieval.
  4. Parallel SQL generation on several LLMs, written against a simplified logical schema and then mapped to the physical schema.
  5. A compiler-backed error-correction loop.
  6. A synthesizer that produces the final query.

  Self-reported **>90% accuracy** on an internal real-world set, **~2x single-shot GPT-4o**, and about 14% higher than another market solution. — [Snowflake engineering blog](https://snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes); see also [Snowflake BI accuracy post](https://snowflake.com/en/engineering-blog/cortex-analyst-text-to-sql-accuracy-bi)
- One comparison site claims Cortex Analyst reaches 85–90% with a well-built YAML semantic layer and can fall to **19.2%** without it, and that building the layer takes 3–6 months. The sourcing is unclear, so treat this as low confidence. — [Querio](https://querio.ai/articles/best-text-to-sql-tools-ranked-real-accuracy)
- **Databricks Genie**:
  - Trusted assets: parameterized example SQL and UC functions, labelled "verified" only on an exact match.
  - Benchmarks: questions with gold SQL whose *results* are compared to Genie's response; questions without gold SQL are flagged for review.
  - Synonyms, descriptions, hidden columns and PK/FK definitions.
  - Knowledge store capped at 200 snippets.
  - Instructions should start small and expand iteratively. — [Databricks tune-quality docs](https://docs.databricks.com/aws/en/genie/tune-quality); [Databricks blog](https://databricks.com/blog/5-key-lessons-implementing-aibi-genie-self-service-marketing-insights)
- **Uber QueryGPT**:
  - Intent classification to pick relevant schemas.
  - Domain "workspaces" of curated tables and SQL samples to narrow context.
  - Large schemas trimmed because of the token cost.
  - 20+ iterations; accuracy fell as scope grew. — [Uber blog](https://www.uber.com/blog/query-gpt)
- **Annotation-error audit (Jan 2026)**: even expert gold SQL has pervasive errors, so a "verified" label needs genuine human review of the query logic. — [arXiv 2601.08778](https://arxiv.org/abs/2601.08778)

### Inferences
These are concrete guardrails sized for a single SQLite DB per upload:
1. **Read-only, sandboxed execution** (engineering judgement): open SQLite read-only (`mode=ro`), allow only `SELECT` or `WITH`, set a statement timeout and row cap, and return truncated-result warnings to the model.
2. **Ingest-time data-quality report** shown to the user and given to the model: rows parsed and rejected, duplicate detection, columns with mixed types, and totals per sheet. The model can then say "12 rows had unparseable amounts and were excluded" instead of silently giving a wrong total.
3. **Show your work**: always display the executed SQL (collapsible), the result table, the row count, and the assumptions made (period, filters, sign convention). Let users click through to the underlying rows.
4. **Confidence labels** derived from checks, not from model self-report:
   - "Verified" when a verified template was used.
   - "Cross-checked" when two independent queries agree.
   - "Unverified" when only one query was run or the grounding gate needed a retry.
   - "Needs clarification".
5. **Refuse when data is missing**: if the question needs a column or table that does not exist (for example "profit" with no expense data), say so explicitly.
6. **Reconciliation invariants for accounting** (domain inference): totals by group should sum to the overall total; for double-entry, debits should equal credits; opening balance + movements should equal closing balance. Run these automatically where applicable and flag violations.
7. **Evaluation harness** like Databricks benchmarks: 100–300 real questions over representative uploads, each with gold SQL. Compare result values, not SQL text. Run on every prompt, model or effort change, and track accuracy by question category.

### Gaps
- I found no public post-launch error rates from Snowflake, Databricks or Uber measured on real user traffic. Reported numbers are internal evaluations.
- I did not research Pinterest's text-to-SQL blog in this pass.

---

## Q5. How much does each technique help, and what residual error rate remains with best practices?

### Takeaway
Reported effect sizes:

| Technique | Reported effect | Basis |
|---|---|---|
| Semantic documentation | +17–23 pp | Strong, 2026 |
| Execution refiner / self-correction | +4.6–9.3 pp | Ablations, 2023–24 |
| Self-consistency voting | ~+1.5 pp overall, ~+7.6 pp on hard questions | 2025 |
| Trained selector | Beats voting | ICLR 2025 |
| Program-of-thought vs CoT | ~+12% average | 2022, older |
| Ambiguity handling | ~50% relative gain in exact match | Research system |

Even with best practices, the state of the art leaves roughly 10–30% of answers wrong on benchmarks: top BIRD systems are about 80–82% versus 93% for humans, and frontier models with a semantic doc score about 68% single-shot on BI questions. Vendors self-report about 90% on curated domains. **"100% accuracy" cannot be guaranteed** for free-form questions. What can be guaranteed engineering-wise is that every displayed number is traceable to an executed query over the user's data, and that the system flags or abstains when it is unsure.

### Cited Findings
- Semantic documentation: **+17 to +23 pp**, from about 46–51% to about 68–69%, across three frontier models; the model choice was not significant. — [arXiv 2604.25149](https://arxiv.org/abs/2604.25149)
- Semantic model, same LLM on BIRD: **57% to 78%** (third-party report of a Snowflake result; unverified). — [Atlan](https://atlan.com/know/snowflake/cortex-analyst-vs-text-to-sql/)
- Refiner/self-correction ablations: **−9.3 pp** without it (MAG-SQL, GPT-3.5), and **−4.63 pp** (MAC-SQL, secondary source). — [arXiv 2408.07930](https://arxiv.org/pdf/2408.07930); [beancount.io](https://beancount.io/bean-labs/research-logs/2026/06/08/mac-sql-multi-agent-collaborative-text-to-sql)
- Self-consistency voting: **~+1.5 pp** overall, **~+7.6 pp** on hard BIRD questions (OpenSearch-SQL). — [arXiv 2502.14913](https://arxiv.org/pdf/2502.14913)
- PoT vs CoT: **~+12% average** (2022). — [arXiv 2211.12588](https://arxiv.org/abs/2211.12588)
- Ambiguity detection and rewriting: **87.2% detection precision; 50% relative exact-match gain** (AmbiSQL). — [arXiv 2508.15276](https://arxiv.org/html/2508.15276v1)
- Multi-agent production pipeline vs single-shot GPT-4o: **~2x** (Snowflake, self-reported, 2024). — [Snowflake engineering blog](https://snowflake.com/engineering-blog/snowflake-cortex-analyst-behind-the-scenes)
- Residual error on public benchmarks:
  - Best BIRD EX **82.39%** (vendor-reported) vs human **92.96%**. — [Technology Magazine](https://technologymagazine.com/news/huawei-datagallery-tops-benchmark-for-enterprise-text2sql-ai); [AI Weekly](https://aiweekly.co/alerts/googles-gemini-sql2-tops-bird-text-to-sql-at-8004)
  - Frontier models with a semantic doc reach **~68%** single-shot on a 100-question BI set. — [arXiv 2604.25149](https://arxiv.org/abs/2604.25149)
  - 2024-era models reach **~51%** on TableBench vs ~86% for humans. — [arXiv 2408.09174](https://arxiv.org/html/2408.09174v2)
- LLM-based semantic error detection catches only **~75%** of buggy SQL, so verification layers leak. — [arXiv 2503.11984](https://arxiv.org/pdf/2503.11984)
- Benchmarks themselves carry **52.8–62.8%** annotation error rates in audited subsets, so "accuracy" figures have wide uncertainty in both directions. — [arXiv 2601.08778](https://arxiv.org/abs/2601.08778)
- Grounding and retrieval reduce but do not eliminate errors. Retrieval gaps and conflicting sources still need human judgement (vendor view). — [Bigdata.com blog](https://bigdata.com/blog/why-llms-hallucinate-in-financial-analysis-and-how-grounding-fixes-it)

### Inferences
- Gains do not simply add up, because they target overlapping errors. A realistic expectation for Accounts.ai with every layer in place is high accuracy on routine single-table aggregations, especially those served by verified templates, with residual risk on ambiguous or multi-step questions. The system should *detect* most of those cases (candidate disagreement, grounding failures, clarification triggers) rather than answer them silently and wrongly. This is extrapolation; there is no ledger-specific benchmark.
- Recommended framing for the client's "100% accuracy" requirement:
  - *Guaranteed by design:* no number appears that was not computed by SQL or code over their uploaded data; the SQL and rows are inspectable; arithmetic is exact (decimal or integer money).
  - *Not guaranteed:* that the model interpreted an ambiguous question the way the user meant, that the uploaded sheet is clean and complete, or that a free-form query's logic (join/filter) is right.
  - *Mitigations:* clarification prompts, verified templates for standard reports, cross-check queries, confidence labels, and an evaluation suite with a tracked accuracy number.
- The fastest wins for a small app, ordered by effort versus evidence:
  1. Data dictionary / semantic doc plus ingest normalisation.
  2. Strict tool schema plus a SQL error-retry loop.
  3. SQL-only arithmetic plus a number-grounding gate.
  4. Verified templates for the top accounting reports.
  5. A clarification/abstain path.
  6. A dual-candidate cross-check on money questions.
  7. An evaluation suite.

### Gaps
- No source measured the residual error after combining all of these techniques in one system on financial ledger data. Every figure is per technique, or for a vendor's whole pipeline on undisclosed data.
- No independent (non-vendor) measurement of Snowflake/Databricks accuracy on real customer traffic was found.
- The effect size of number-grounding gates on user-visible error is unmeasured in the literature I found.
