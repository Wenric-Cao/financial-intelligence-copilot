# Stage 10: guarded financial UI and recorded evaluation integration

Publication note: machine-specific paths and interpreter commands are generalized
for sharing. Original execution transcripts are retained locally; placeholders
such as `<project-root>` and `<temporary-source-copy>` need local substitution.
Recorded commands, outcomes and limitations retain their original meaning.

Date: 2026-11-08 (Asia/Singapore).
Workspace: `<project-root>`.

## Outcome

Connected the existing source-bound financial reviews and comparison backend to
the English interface. Year-over-Year now shows readiness for each annual pair,
human-readable blocking reasons and separate source links. A calculated pair can
display amount/percentage changes or percentage-point changes and a Plotly chart.
Financial KPIs separately projects recorded fact confirmations without rewriting
the candidate records.

About & Evaluation now validates the actual historical forty-case Stage 8 run
and shows its original date, counts/denominators, missing human judgments and
older code/configuration status. It does not rerun or regrade that evaluation.

Actual AIA state remains **10 pending facts, 5 pending pairs, 0 calculations and
0 charts**. No owner decision, candidate verified flag, gold answer or human score
was changed. Approved chart paths were tested only with explicitly neutral
temporary fixtures. A separate persisted verified-KPI CSV/database remains absent.

## 1. Modified files

| File | Change |
| --- | --- |
| `src/financial_intelligence_copilot/ui.py` | Read-only fact projection, comparison readiness/source cards, gated metrics/charts/export, recorded evaluation display and error states |
| `src/financial_intelligence_copilot/ui_state.py` | Include review packet, evaluation suite/record and config bytes/presence in UI revisions |
| `src/financial_intelligence_copilot/ui_charts.py` | Plot two guarded annual levels with exact labels, source metadata and correct percent units |
| `src/financial_intelligence_copilot/evaluation_records.py` | Validate frozen run/case/response bindings, aggregate consistency and data dependencies; flag historical code/configuration |
| `src/financial_intelligence_copilot/answer.py` | Financial/refusal messages direct users to the integrated tabs without falsely denying recorded confirmations |
| `pyproject.toml` | Pin Plotly 7.1.0 alongside the existing dependencies |
| `tests/test_ui.py` | Ten additional neutral AppTest workflows for approved/pending charts, review withdrawal, stale results and historical record handling |
| `tests/test_ui_state.py` | Four new edit/add/remove revision checks |
| `tests/test_ui_charts.py` | 53 neutral chart consistency/precision/source-label checks |
| `tests/test_evaluation_records.py` | 37 historical record/digest/summary/dependency checks |
| `assets/screenshots/comparison-readiness.jpg`, `assets/screenshots/evaluation-record.jpg` | Actual browser captures of the pending financial view and historical evaluation |
| `README.md`, `PRD.md`, `ARCHITECTURE.md`, review/demo/development guides | Current UI boundaries, reproduction and pending acceptance |

The raw PDFs, page snapshots, retrieval index, candidate values and real review
packet were preserved. No model provider or paid API was configured or called.
No deployment, Git commit or push occurred.

## 2. Financial review and comparison behavior

The UI calls `load_review_state` and `comparison_results` together. Loading checks
actual source PDFs and exact candidate spans, raw candidate digests and review
schema. Fact confirmation alone cannot authorize a comparison. Only the
backend's `status=calculated` result enters the metric/chart branch; unresolved,
rejected, incompatible and nonpositive-prior cases display reasons without
computed values or charts.

Readiness explicitly concerns both FY2024 and FY2025, independently of the
sidebar's single-report question scope. Each selected pair shows both original
annual periods and physical PDF source links. Approved views also show scope,
basis, reviewer/time/notes and recorded decisions. Decimal calculation results
remain exact in JSON; percentage growth is rounded to two decimals for display.
Percent-unit metrics show percentage-point differences. Changes in reported
levels are not labeled as CER growth.

The chart helper validates complete source/period/token metadata, known
currency/units, finite Decimal levels, a positive prior base and distinct
consecutive source documents. It plots reported levels, not recomputed growth.
Floats are used only for chart geometry; exact Decimal strings remain visible
in labels and hover. A percent level of 30 is plotted/labeled as 30%, not 3,000%.
Review/source authorization remains the guarded caller's responsibility.

Fact confirmations are an in-memory read-only projection of the source and
review records. Candidate JSON remains unverified/pending by design; no UI
approval control writes review decisions or creates a verified store.

### Revision and revocation checks

The UI fingerprint now includes optional `data/kpi_reviews.json`,
`data/evaluation_cases.json`, the fixed historical run file and `pyproject.toml`,
in addition to the existing source inventory. Additions, same-size edits and
removals change the revision. Workspace/year/recheck events clear review and
comparison state along with prior responses. Validation errors clear prior
results rather than falling back to the last chart.

Independent review found a narrow cached-state gap in the KPI pane during a
rerun. A fresh fingerprint check now runs on every review-state return, including
cache hits; the comparison pane also checks before display. A dedicated neutral
race test confirms that stale confirmed inputs and charts are hidden. Checks
run on rerun/query/recheck, not continuously on an idle page.

## 3. Historical evaluation display

The optional fixed record is
`data/processed/phase-8-evaluation.after-fix.json`. Missing records display an
unavailable state. Invalid records produce an error and no previous counts.
The reader checks run/suite/case/response digests, exact case membership, frozen
proposal bindings and consistency of aggregate counts with raw rows.

Whitelisted suite/manifest/policy/index/raw-page/source dependencies must match
current file bytes. Missing, changed or unsafe data paths fail validation. Code
and project-configuration differences instead mark the record historical, so a
legitimate older run remains inspectable with an explicit warning. Summary
observations are read from that frozen run; no semantic judgment is inferred.

The visible recorded values remain:

```text
Recorded date: 2026-10-31 09:28 UTC
Cases completed: 40/40
Current-mode engineering behavior matches: 40/40
Literal source spans: 12/12
Proposed evidence-page hits within five results: 21/28
Approved gold answers: 0
Human-scored cases: 0
```

No excerpt or eligible-page set displays N/A rather than a pass. Human answer,
numerical, citation-relevance and abstention correctness remain unavailable. The
new UI and dependency changes correctly mark the code/configuration as newer
than the record. The Stage 8 files and their metrics were not overwritten.

## 4. Dependencies and commands actually run

The implementation checked the [official Plotly package](https://pypi.org/project/plotly/)
and [Streamlit Plotly-chart API](https://docs.streamlit.io/develop/api-reference/charts/st.plotly_chart).
The installed Streamlit 1.66.1 signature was also inspected locally before use.
Plotly 7.1.0 is pinned and runs locally; no cloud graphing account or API is used.

The initial default-index install could not resolve the package. The approved
official-PyPI retry installed it in the project venv, followed by refreshing the
editable project metadata from the updated dependency manifest:

```bash
.venv/bin/python -m pip install --disable-pip-version-check --no-cache-dir \
  --retries 0 --timeout 20 --index-url https://pypi.org/simple plotly==7.1.0
.venv/bin/python -m pip install --disable-pip-version-check --no-cache-dir \
  --retries 0 --timeout 20 --index-url https://pypi.org/simple -e '.[dev]'
.venv/bin/python -m pip check
```

Actual results: Plotly 7.1.0 installed, editable project rebuilt/reinstalled, and
`No broken requirements found`. Pip check still emitted its existing
non-writable-cache warning; cache permissions were not changed. Other pinned
runtime/development packages remained satisfied; the isolated build used the
declared build backend.

Focused tests and final checks:

```bash
.venv/bin/python -m pytest tests/test_ui_charts.py -q
.venv/bin/python -m pytest tests/test_evaluation_records.py -q
.venv/bin/python -m pytest tests/test_ui.py -q
.venv/bin/python -m pytest -q > data/processed/phase-10-pytest.log 2>&1
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

Actual final full-suite results:

```text
446 passed, 5 warnings in 7.70s
All checks passed!
37 files already formatted
```

The five warnings remain the known PyMuPDF/SWIG import deprecations. Focused
chart, record-reader and UI runs passed 53, 37 and 18 tests respectively. The
104 additions cover chart values/labels/units, stale dependency and summary
handling, review revision changes and UI approval withdrawal. These are software
checks, not financial acceptance or semantic accuracy.

Temporary neutral PDFs explicitly label their counts as test-only. The approved
fixture path shows 10 to 12, change 2 and 20.00%; the percent fixture shows 30%
to 33% and 3 pp. Test reviewer signatures refer only to those fixtures. No real
AIA candidate was approved to exercise a chart. Tests verify original candidate
bytes and false verified flags remain unchanged.

## 5. Actual-source UI and browser checks

Ran AppTest on the actual `app.py` and current local data. Result: zero
exceptions; five pending pairs; zero calculated values/charts. The evaluation
table showed the recorded 40/40, 12/12 and 21/28 counts. This is saved in ignored
`data/processed/phase-10-real-ui-smoke.json`.

Restarted the existing loopback-only preview with:

```bash
.venv/bin/python -m streamlit run app.py \
  --server.address 127.0.0.1 --server.port 8501 \
  --server.headless true --browser.gatherUsageStats false
```

The real browser at `http://127.0.0.1:8501` showed:

| Action | Observed outcome |
| --- | --- |
| Open Year-over-Year | Five readiness rows, confirmed facts 0/10, calculated pairs 0/5 and no growth chart |
| Select OPAT | Pending fact/comparability reasons, separate FY2024 physical page 36 and FY2025 physical page 35 links |
| Open About & Evaluation | Original recorded date, 40/40 cases, 12/12 spans, 21/28 proposed page hits |
| Inspect score/provenance notices | Zero approved gold/human-scored cases and an earlier code/configuration warning |

The two new screenshots are real captures. Browser observations are recorded in
ignored `data/processed/phase-10-browser-checks.json`. No browser approval was
entered and no live AIA chart was fabricated. Review revocation and approved
chart branches were checked with neutral AppTests, not claimed as real-data
financial acceptance.

## Next acceptance work

Use the existing owner worksheet and guides to confirm specific factual cases,
financial inputs and comparability decisions. Recorded decisions can then
activate the guarded UI path. A persisted reviewed store/export, actual approved
data demonstration and formal human evaluation still require those decisions.
The UI inspection and 446 software checks do not supply them automatically.
