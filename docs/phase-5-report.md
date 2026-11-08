# Stage 5: English Streamlit workspace

Publication note: machine-specific paths and interpreter commands are generalized
for sharing. Original execution transcripts are retained locally; placeholders
such as `<project-root>` and `<temporary-source-copy>` need local substitution.
Recorded commands, outcomes and limitations retain their original meaning.

Date: 2026-10-31 (Asia/Singapore).
Workspace: `<project-root>`.

## Outcome and scope

Implemented and started an English local Streamlit interface over the selected
extractive-response workflow. It supports report-year selection, questions,
verbatim excerpts, source details, physical PDF page links, refusal explanations,
and response JSON download. The current local preview is at
`http://127.0.0.1:8501` and binds only to the loopback interface.

The four tabs are Ask the Annual Report, Financial KPIs, Year-over-Year, and
About & Evaluation. KPI and comparison tabs explain the missing verified inputs
without displaying example figures or charts. LLMs, verified KPI storage, YoY
calculations, the 40-question evaluation, and final owner acceptance remain
pending. No model API call, public deployment, Git commit, or push occurred.

## 1. Changed files and dependencies

| File | Change |
| --- | --- |
| `app.py` | Local Streamlit entry point |
| `src/financial_intelligence_copilot/ui.py` | Scope controls, question form, response/source cards, four tabs, per-session cache |
| `src/financial_intelligence_copilot/ui_state.py` | Inventory checks, actual-byte source fingerprint, safe page links, optional development record |
| `.streamlit/config.toml` | Loopback binding, usage-statistics opt-out, minimal toolbar, light theme, static serving disabled |
| `pyproject.toml` | Pin Streamlit 1.66.1 alongside the existing dependencies |
| `tests/test_ui.py` | Six AppTest workflows using neutral local PDF fixtures |
| `tests/test_ui_state.py` | Six source-state, missing-file, path, link, and optional-record checks |
| `assets/screenshots/local-workspace.jpg` | Browser-captured overview of the local workspace |
| `README.md`, `docs/development-plan.md` | Current status and reproducible launch/review instructions |

The [official Streamlit package](https://pypi.org/project/streamlit/) and
[AppTest documentation](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest)
were checked before implementation. The installed version is pinned rather than
left floating. Installation used the existing Python 3.13.9 virtual environment:

```bash
PIP_NO_CACHE_DIR=1 PIP_RETRIES=0 PIP_TIMEOUT=20 .venv/bin/python -m pip install --disable-pip-version-check -e '.[dev]'
.venv/bin/python -m pip check
```

Actual result: Streamlit 1.66.1 installed successfully; `pip check` reported
`No broken requirements found`. Its transitive UI dependencies were installed in
the project venv; no global Python installation was modified.

## 2. User experience and source consistency

The company is fixed to AIA for this MVP. The fiscal-year control selects FY2024
or FY2025 and is passed directly to the existing source-filtered answer engine.
Examples include a factual question, a missing subject, and an unverified KPI.
The interface visibly identifies the mode as local extractive, including partial
evidence and research-use notices. It does not describe responses as generated
summaries or verified financial answers.

Quotes are displayed as literal code text with wrapping, not HTML or executable
content. Citation details preserve evidence IDs, source SHA256, and original page
character ranges. Links point to the registered source URL with `#page=N`; the
number is the physical PDF page, not an inferred printed-page number. The helper
checks HTTPS/no credentials and page-number type; official-source identity still
depends on the previously reviewed manifest, not that URL syntax check alone.

Only response JSON can be downloaded from the app. It does not offer local PDF
downloads, embed local reports, or enable a static report directory. Original
PDFs and extracted full text remain ignored local data.

### Cache invalidation

Every Streamlit rerun hashes actual bytes of the manifest, policy, retrieval
index, both raw PDFs, and page snapshots. A change invalidates the session's
response and engine. Fiscal-year or workspace changes also clear the old result.
The hash check detects same-size edits even when timestamps are preserved.

Before the first response, `load_retriever` performs the full existing source,
snapshot, and index verification. Fingerprints are checked again after loading
and after answering. A changed/missing/invalid source never produces a response
from the previous cache. A Recheck local sources action forces revalidation.

The cached engine is per session, not a globally shared mutable object. Initial
queries and first queries after a year switch may take several seconds; later
same-scope queries reuse the validated snapshot when bytes are unchanged. An idle
browser page does not continuously watch every file: checks run on rerun/query/
recheck. No continuous live-source guarantee is claimed.

## 3. Automated checks actually run

```bash
.venv/bin/python -m pytest tests/test_ui.py -q
.venv/bin/python -m pytest tests/test_ui_state.py -q
.venv/bin/python -m pytest -q > data/processed/phase-5-pytest.log 2>&1
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

Actual final results:

```text
118 passed, 5 warnings in 1.24s
All checks passed!
20 files already formatted
```

The five warnings remain the known PyMuPDF/SWIG import deprecations. The initial
UI-only run passed all six AppTest cases. The additional workspace-state run
passed all six cases.

The AppTest fixtures create two tiny documents explicitly labeled as neutral test
fixtures with no real company or financial claims. AIA document IDs and years
are routing labels required by the fixed-company UI. Tests parse and index those
fixtures locally and exercise the real extractive backend. No official PDFs or
network access are needed to run this test suite in a new checkout.

Coverage includes default controls and tab states, exact source rendering and
physical pages, year switching with old-result removal, missing-data failure,
snapshot-tampering rejection, literal source markup, same-timestamp byte changes,
workspace path escape prevention, safe page anchors, and absent/invalid run data.

## 4. Local server and live browser verification

Actual launch command:

```bash
.venv/bin/python -m streamlit run app.py \
  --server.address 127.0.0.1 --server.port 8501 \
  --server.headless true --browser.gatherUsageStats false
```

The first sandboxed attempt could not bind a local port. The approved loopback
retry started successfully; the server was restarted after final preview
configuration changes. The running address is `127.0.0.1:8501`, not a public host.
The optional Watchdog performance suggestion was not required for functionality.

A real in-app browser then exercised the existing official local reports:

| Browser action | Observed outcome |
| --- | --- |
| Open English workspace | Four tabs, fixed AIA company, FY2025 selection, local-mode notice |
| Ask FY2025 risk-governance question | Original excerpt labeled FY2025 / PDF page 64 with the correct official page anchor |
| Change to FY2024 | FY2025 response removed before the next submission |
| Ask what AIA Vitality is | Original text from FY2024 / PDF page 359, without changing source year |
| Ask about the absent test subject | No-evidence explanation; no leftover quotes |
| Ask for VONB in USD million | Verified-KPI unavailability explanation, rather than an unreviewed number |
| Inspect KPI and YoY tabs | Explicit unavailable states with no figures or charts |
| Inspect About & Evaluation | Recorded Stage 4 checks distinguished from answer accuracy and the unrun formal evaluation |

These observations are recorded in the ignored
`data/processed/phase-5-browser-checks.json`. They are manual browser verification
of software behavior, not owner acceptance, answer correctness, or a new model
evaluation. The browser overview screenshot is a real capture, not a mockup.

## 5. Evaluation and financial-data boundaries

About & Evaluation reads the optional recorded Stage 4 development JSON. If the
record is missing or invalid, it displays no invented scores. Its counts are
explicitly historical development checks; the UI test count is not relabeled as
answer accuracy. Existing partial-coverage and lexical-relevance limitations
remain in force. The source manifest still records owner review as pending.

The app does not automatically mark any number as verified. Financial KPIs and
comparisons need their own reviewed data workflow. The interface is suitable for
inspecting factual evidence now; it does not complete the full planned MVP.

## Next acceptance work

The owner can review at least five factual cases in the local interface. Next,
prepare 3-5 common KPI candidates with actual values, currency/units, periods,
scope, basis, and independent source pages for review. Only approved candidates
should enter the verified KPI store or Python comparison pipeline. Generative
model integration and the full 40-question evaluation remain later work.
