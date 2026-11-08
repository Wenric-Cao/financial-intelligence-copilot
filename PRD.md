# Product requirements: Financial Intelligence Copilot

Status: local research prototype; product-owner acceptance pending.
Updated on 2026-11-08. Product owner: the project owner. Engineering support:
AI engineering collaborator.

## Users, problem and jobs

The primary users are junior financial research analysts and business analysts.
Secondary users are financial technology product teams, AI solutions consultants
and corporate strategy researchers. They need to locate annual-report facts,
check financial definitions and compare consistent annual measures while keeping
the underlying evidence available for review.

The product supports three jobs:

1. Find a fact in the selected official annual report and inspect its original
   wording and physical PDF page.
2. Review a reported financial value together with its currency, unit, annual
   period, consolidation scope and definition before accepting it as an input.
3. Compare approved annual inputs only after their financial bases have been
   reviewed, with separate evidence for each input.

These user needs come from the project requirements. No user study, measured
time saving, business adoption or customer outcome is claimed.

## Product scope and selected mode

The MVP uses AIA Group Limited's official English FY2024 and FY2025 annual
reports. The company is fixed to AIA; users select a report year. Project
artifacts and the interface are English by default, preserving original source
wording where needed.

The product owner selected **local original-text excerpt responses**. The current
experience returns verbatim evidence or an explicit abstention. It does not
generate summaries. Model integration would require a separate product decision,
provider configuration and approval of any external API cost; no model API is
configured or called in the current mode.

The MVP includes report ingestion, scoped evidence retrieval, source inspection,
reviewed KPIs, guarded Python comparisons, comparison charts, actual evaluation
records and a reproducible English portfolio demonstration. Financial review and
evaluation acceptance remain necessary to complete that scope.

Excluded from the MVP are investment recommendations, forecasts, trading,
securities accounts, live prices, cross-company rankings, arbitrary PDF uploads,
complex OCR, universal table extraction, model training and large-scale crawling.
Original reports are obtained locally from official sources; the application
does not redistribute them. Paid APIs, public deployment and Git push require
explicit authorization.

## Requirements and acceptance criteria

| ID / priority | Required user outcome and acceptance criteria | Current status |
| --- | --- | --- |
| F1 - report questions / P0 | A user selects FY2024 or FY2025 and receives original excerpts from that report, with company, year, physical `PDF page N`, source link and context. Evidence shortage and unsupported workflows produce an explanation. A request to invent or omit citations does not bypass evidence rules. The owner accepts at least five factual cases, checking relevance and completeness as well as literal wording. | Local extractive workflow implemented. Owner acceptance pending; some multipart answers remain partial. |
| F2 - financial KPIs / P0 | Display 3-5 common metrics for both years only as verified after explicit fact review. Each input retains value, currency, unit, period, scope, basis and source. Candidate values remain visibly unverified until that decision. | Five metrics / ten candidates and their review interface are implemented. All ten remain unverified; zero facts are confirmed and the reviewed store is pending. |
| F3 - annual comparison / P0 | Each pair requires confirmed facts and a separate comparability decision. Compare matching company, definition, currency, unit, annual period, scope and basis. Python calculates amount changes and ordinary growth only for a positive prior base; percentage metrics use percentage-point changes. Zero/negative prior bases, incompatible inputs and unresolved tax, currency or restatement issues require review. Charts label years, units and independent input sources. | Guarded Decimal backend, source-bound readiness UI and conditional Plotly charts implemented and tested with neutral quantities, including review revocation. Zero real AIA pairs calculated; actual facts/pairs remain pending. |
| F4 - traceability / P0 | Every released quote and financial input has inspectable original evidence. Invalid or changed source data prevents reuse of an old result or approval. Financial confirmation, comparability and semantic answer quality are explicit review decisions. Show the research-use notice. | Source checks, pending-review controls and stale-result handling implemented. These controls do not establish semantic or financial correctness; owner review remains pending. |
| F5 - local experience / P1 | Provide English Ask the Annual Report, Financial KPIs, Year-over-Year and About & Evaluation tabs, clear empty/refusal/error states, and local setup instructions. A user following the README can obtain authorized reports, rebuild local data and inspect three scenarios: fact evidence, a verified number and a comparable annual change. | Four tabs and local preview implemented. Financial tabs consume recorded reviews and gated results; actual verified-number/comparison scenarios await inputs. About now validates the historical forty-case run and labels its date, denominators and missing human scores. Final demonstration and owner acceptance remain pending. |

The notice is: **Research demonstration only - not investment advice.** A source
page confirms where text was found; it does not by itself confirm that an answer
is complete or that a financial definition was interpreted correctly.

## Human review and decision rights

The product owner confirms requirements, source suitability, financial facts,
comparability, evaluation gold answers and final acceptance. The engineering
collaborator implements the workflow, preserves evidence and reports observed
results. A request to continue development is not financial or gold approval.

| Decision | Required review | Effect |
| --- | --- | --- |
| KPI fact confirmation | Numeric cell and sign, currency/unit, period, scope, definition and source; explicit candidate ID, reviewer, time and notes | Can authorize a reviewed input. Candidate source records remain distinct from the reviewed store. |
| Pair comparability | Both confirmed inputs plus definitions, periods, scope, exchange-rate basis, tax basis and restatement treatment | Can authorize a structurally valid comparison. Matching headline values alone is insufficient. |
| Gold answer approval | Proposed answer or answerability label and supporting source context, including valid alternative pages | Establishes an evaluation reference for that case; does not score the application's answer. |
| Response scoring | A frozen response judged against an approved reference and agreed rubric | Produces human semantic judgments with explicit denominators. Source-span checks cannot supply these ratings. |

Reviews bind to the content they assess; edited inputs or responses require
fresh decisions. Content hashes do not authenticate human identity. No actual
reviewer name, review time or approval is inferred automatically.

Use the [KPI review guide](docs/kpi-review-guide.md) and
[evaluation review guide](docs/evaluation-review-guide.md) for concrete review
materials and decision formats.

## Current evidence and quality acceptance

The implementation has **446 passing automated tests**. The repaired 40-case
development run recorded **40/40 engineering behavior matches**, **12/12 literal
released-source spans**, and **21/28 proposed evidence-page hits within five
results**. There are **0 approved gold answers and 0 human-scored cases**; all
semantic correctness metrics remain unavailable. These observations are software
and source checks, not product acceptance or answer accuracy. The same exposed
development suite was rerun after observed guard repairs; it is not held out.
See [EVALUATION.md](EVALUATION.md) for the original run, denominators and failures.

Final quality acceptance requires at least 40 owner-reviewed questions covering
facts, numbers, table/basis interpretation, comparisons and boundaries, plus
actual raw runs and human judgments. The original plan's suggested targets are
80% answer correctness, 90% citation correctness, 100% reviewed KPI calculation
correctness and 80% correct abstention. They remain planning targets until the
owner agrees the rubric and actual results are recorded. New independent
acceptance cases are needed for a future held-out claim.

## Remaining delivery gates

1. Accept factual evidence cases and review the ten KPI candidates and five
   annual pairs, resolving NCI definitions, reported versus CER presentation,
   FY2025 tax changes and any restatement questions.
2. Populate reviewed inputs from explicit decisions and exercise the integrated
   guarded comparisons/charts on actual data for all three required scenarios.
3. Approve evaluation references, score frozen responses and publish honest
   results with known omissions and failures.
4. Complete reproducibility and English demonstration materials, then obtain
   final owner acceptance. Public release is a separate authorization decision.

Source acquisition, implementation milestones and actual stage records are in
the [development plan](docs/development-plan.md) and [README](README.md).
