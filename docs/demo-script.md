# Two-minute portfolio demonstration

Updated for the Stage 10 interface on 2026-11-08; evaluation observations retain
their recorded Stage 8 date. The current
application is a local **verbatim-excerpt research prototype**. Verified financial
answers, approved comparisons/charts and owner-scored evaluation remain
target-MVP work. Generative answering requires a separate product/configuration
decision under the selected local mode. This script does not claim completion
of those pending capabilities.

## Spoken script

Approximately two minutes at a measured interview pace. The timing bands are
cues, not measured recording times. Complete setup before speaking.

<!-- SPOKEN SCRIPT START -->

**0:00-0:18 - Problem and current product**

> Financial research requires finding the right disclosure and checking its
> context. I built Financial Intelligence Copilot around AIA's official 2024
> and 2025 annual reports. The current prototype returns original excerpts with
> physical PDF pages. It is a research demonstration, not investment advice.

**0:18-0:45 - Inspect a sourced excerpt**

> With FY2025 selected, I ask who sets risk appetite and approves the risk
> management framework. This excerpt identifies the Board on PDF page 64.
> I can open the source and inspect the passage. Exact source matching establishes
> where the words came from; relevance and completeness still require review.

**0:45-1:05 - Review a candidate KPI**

> The KPI tab separates candidate values from verified facts. This OPAT candidate
> shows its unit, annual period, shareholder scope and source page. It remains
> pending owner review. Tax-basis notes are visible, and exporting the review
> sheet does not approve the number.

**1:05-1:20 - Show the comparison boundary**

> The comparison tab remains blocked. The recorded readiness audit has zero
> confirmed facts and zero of five pairs calculated. Financial verification and
> comparability need separate decisions before a real chart is appropriate.

**1:20-1:45 - Explain actual evaluation evidence**

> Forty development cases completed. Proposed evidence-page hits were 21 of 28
> within five pages, leaving seven misses. There are zero approved gold answers
> and zero human-scored cases, so semantic accuracy is unavailable. The recorded
> 446 passing software tests are engineering checks, not answer accuracy.

**1:45-2:00 - Trade-offs and ownership**

> I chose local lexical retrieval and source inspection for auditability.
> Table layouts and partial answers remain limitations. I led requirements,
> analysis and acceptance planning, using Codex to assist implementation and
> tests. Financial approval remains the product owner's responsibility.

<!-- SPOKEN SCRIPT END -->

## Preflight: prepare the actual local workspace

1. Follow the [README setup and source-intake instructions](../README.md).
   Use the installed `.venv`, or install the pinned project dependencies in a new
   environment. This mode requires no API key or model service.
2. Confirm these actual local inputs exist; a new checkout does not include the
   raw reports, full extracted pages, index or recorded run files:

   ```text
   data/manifest.csv
   data/raw/AIA_2024_Annual_Report_EN.pdf
   data/raw/AIA_2025_Annual_Report_EN.pdf
   data/processed/AIA-2024-EN.pages.json
   data/processed/AIA-2025-EN.pages.json
   data/retrieval_policy.json
   data/processed/retrieval-index.json
   data/kpi_candidates.json
   data/kpi_reviews.json
   ```

   Obtain genuine reports and run the documented parser/index builder when
   necessary. Do not use fixture PDFs, replace source hashes just to pass a
   check, or invent missing records for a demonstration.
3. Start the preview from the project root, or reuse an existing preview at the
   same address:

   ```bash
   .venv/bin/python -m streamlit run app.py \
     --server.address 127.0.0.1 --server.port 8501 \
     --server.headless true --browser.gatherUsageStats false
   ```

   Open [the local workspace](http://127.0.0.1:8501). This is a local preview,
   not a public deployment. Stop a manually started preview with Ctrl+C.
4. Select **FY2025** and click **Recheck local sources**. Allow source verification
   to finish before the timed demonstration. If verification fails, use the
   failure and fallback procedure below; do not describe unverified output as
   a successful live result.
5. Open **About & Evaluation**. It now reads the validated historical Stage 8
   record and labels its date, denominators and unavailable human scores. Keep
   [EVALUATION.md](../EVALUATION.md) available for failure details. The display
   is not a fresh evaluation run or a semantic accuracy result.
6. If present, prepare these existing local artifacts in separate panes:

   ```text
   data/processed/phase-7-comparison-readiness.final.json
   data/processed/phase-8-evaluation.after-fix.json
   data/processed/phase-8-human-review.after-fix.json
   ```

   Identify them as **recorded runs**. A new readiness/evaluation run must use
   fresh output filenames and retain its own results, including failures.
   The commands are in the [KPI review guide](kpi-review-guide.md) and
   [evaluation record](../EVALUATION.md).
7. Rehearse the three interactions below. Check the current UI output rather
   than assuming the historical result will recur. The 446-test count is the
   recorded Stage 10 checkpoint; any new software-check claim needs its actual
   command output and date.

## Operator cue sheet

| Time | Action | Evidence to point at | Accuracy of the claim |
| --- | --- | --- | --- |
| 0:00 | Show the title and fixed company/year controls. | Local extractive mode and research-only notice. | The current workflow uses official reports and original excerpts; it does not call an LLM. |
| 0:18 | In **Ask the Annual Report**, choose FY2025, paste the question below and click **Find evidence**. | The actual response, physical PDF page and official source link. | The recorded `fact-08` response is on PDF p.64. Say the scripted result only if the live result actually shows it. |
| 0:45 | Open **Financial KPIs**; keep **Selected fiscal year** and choose `OPAT · FY2025` under **Review candidate**. | **Pending owner review**, USD million, annual period, shareholder scope, table row and PDF p.35 link. | This is candidate `AIA-2025-OPAT`, not a verified financial answer. Open **Definition, scope and tax references** if time allows. |
| 1:05 | Open **Year-over-Year** and choose a metric. | Readiness table, pending reasons, zero confirmed facts, zero of five pairs calculated, both annual source links. | Only confirmed comparable pairs can reach Plotly; current actual AIA inputs remain pending. |
| 1:20 | Open **About & Evaluation**; optionally show [EVALUATION.md](../EVALUATION.md) alongside it. | Historical Stage 8 date, after-fix counts, proposed page hits and unavailable human scores. | Forty engineering expectations matched; this is not 40/40 answer accuracy. The same exposed suite was rerun after a repair. |
| 1:45 | Return to source limitations or the project README. | Documented remaining work and ownership. | Close with trade-offs and the AI-assisted implementation disclosure. |

Copyable FY2025 question, also recorded as `fact-08`:

```text
Which body sets AIA's Risk Appetite and approves its Risk Management Framework according to the 2025 annual report?
```

The recorded response identifies the Board and links to physical **PDF page 64**.
Do not substitute printed page labels. The OPAT example links to physical **PDF
page 35**; it distinguishes shareholder-attributable OPAT from the total including
non-controlling interests. The related tax discussion is on FY2025 PDF p.34.

## Failures and honest fallbacks

- **Missing files or source-validation failure:** show the error and explain that
  the workflow fails closed. Do not edit the source manifest or approve a KPI to
  bypass it. Use the [recorded Stage 6 UI observations](phase-6-report.md) and
  [recorded Stage 8 run](phase-8-report.md), saying, "This is a recorded result;
  the live workspace is currently unavailable."
- **Live refusal, different page or partial excerpt:** describe what is actually
  on screen. The source may contain the fact while the current selector returns
  incomplete evidence. If useful, open recorded `fact-08` in
  `phase-8-evaluation.after-fix.json` and explicitly distinguish it from the live
  result. Do not overlay an expected result or claim the issue was fixed.
- **Official PDF link unavailable:** if the registered local PDF is available,
  open it privately in a PDF reader and navigate to physical page 64 or 35.
  Otherwise use the documented recorded observation. The app links to original
  sources; it does not host or redistribute a PDF copy.
- **Recorded local artifacts missing in a new checkout:** use the checked-in
  [evaluation report](../EVALUATION.md) as a historical record, or reproduce a
  run through the documented process before presenting it. Do not create a
  replacement artifact with expected scores.
- **Comparison is still blocked:** this is the expected current product state.
  Show pending reviews and explain the remaining decision; do not substitute
  arbitrary AIA values into a toy chart or silently call a candidate verified.

No new video or media asset is needed for this demonstration. Existing screenshots
are historical UI illustrations, not proof that the current session succeeded.

## Interview follow-up points

- **Why this architecture?** A small, inspectable local pipeline preserves source
  IDs and physical page offsets. BM25 can miss table/basis passages and semantic
  paraphrases; the recorded proposed-page result is 21/28 at five, not a claim of
  reliable document understanding.
- **What does validation prove?** Literal quote/token identity and software
  constraints are tested. Financial definitions, column meaning, completeness,
  relevance and comparability require separate human judgments. A matching
  prior-year cell does not approve the pair.
- **What was learned from evaluation?** Four initial intent-boundary mismatches
  were retained, repaired and rerun on the same development cases. Seven proposed
  page misses and partial factual responses remain documented. There is no
  held-out or human-scored accuracy result.
- **What is next?** Owner review of factual cases and KPI facts, separate pair
  comparability decisions, reviewed-store integration, guarded real comparisons
  and charts, and semantic evaluation. Generative answering remains a separate
  configuration and acceptance decision.
- **How was AI used?** "I led requirements, analysis, technical trade-offs and
  acceptance planning. Codex assisted coding, tests, documentation and review.
  Source-span checks and automated tests do not replace product-owner approval."
  Do not describe pending source or KPI review as already completed human
  validation, and do not invent users, recruiter feedback or measured time saved.

Review references: [KPI review guide](kpi-review-guide.md),
[evaluation review guide](evaluation-review-guide.md),
[actual evaluation evidence](../EVALUATION.md), and
[setup and reproduction instructions](../README.md).
