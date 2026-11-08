# Stage 9: English portfolio documentation and isolated-source rehearsal

Publication note: machine-specific paths and interpreter commands are generalized
for sharing. Original execution transcripts are retained locally; placeholders
such as `<project-root>` and `<temporary-source-copy>` need local substitution.
Recorded commands, outcomes and limitations retain their original meaning.

Date: 2026-10-31 (Asia/Singapore).
Workspace: `<project-root>`.

## Outcome

Completed the English product requirements, implemented architecture, scripted
prototype demonstration and a single owner acceptance worksheet. Updated README
navigation and first-run ordering. These materials describe the actual local
extractive prototype and its unresolved product gates, rather than declaring the
full MVP complete.

An isolated source copy without official reports, processed artifacts, secrets,
Git metadata or a virtual environment passed all 342 tests with the existing
project interpreter/dependencies. This is a source-independence check, not a new
machine or fresh dependency-installation result. Missing-report readiness failed
with a clear source-file error and produced no output.

No runtime code, tests, dependency declaration, financial candidate, review
decision or evaluation score changed. No video was recorded. The existing local
preview and earlier actual screenshots remain available. No public release,
deployment, paid API, Git commit or push occurred.

## 1. Modified files and documentation checks

| File | Change |
| --- | --- |
| `PRD.md` | Users/jobs, selected local mode, F1-F5 requirements, priorities, acceptance criteria and current status |
| `ARCHITECTURE.md` | Current Mermaid flow, implemented modules/data/provenance, UI/CLI boundaries, trust limits and pending capabilities |
| `docs/demo-script.md` | Approximately two-minute spoken script, operator cues, setup, recorded fallbacks and interview disclosure |
| `docs/acceptance-checklist.md` | One review entry point for five factual cases, ten candidate facts, five pairs and forty evaluation proposals/responses |
| `README.md` | Delivery links, source-intake order, installation before audit commands, two actual historical screenshots and reproduction instructions |
| `docs/development-plan.md`, this report | Updated milestone status and actual stage evidence |

Independent documentation cross-reviews checked claims against the code, raw
evaluation/readiness records and original requirements. They confirmed that the
UI currently renders candidates and historical Stage 4 About counts; Stage 7
comparison and Stage 8 evaluation results are CLI/file workflows. The UI does
not yet consume their records or show a real comparison chart.

One scope inconsistency was corrected: generative answering is a separately
configured/product-decided extension under the selected local mode, rather than
an implied current acceptance requirement. Architecture wording also distinguishes
complete numeric tokens from integers, and explains the two actual offset spaces:
trimmed parser page text for retrieval versus fresh untrimmed sorted native text
for candidate/evaluation evidence. Those offsets must not be interchanged.

The demonstration keeps all KPI values pending. Its third scenario explains the
blocked comparison and recorded evaluation evidence; it does not substitute a
toy chart or claim a successful verified-number/comparison demonstration. Timing
bands are speaking cues, not measured recording durations. Existing screenshots
are identified as recorded Stage 5/6 captures.

Checked ten documents and 41 local Markdown file/image targets: all resolved,
and fenced blocks were balanced. The check is
local; official external URLs were not re-fetched or given a new verification
date. Validation details are recorded in `data/processed/phase-9-doc-checks.json`.

## 2. Current environment checks

Actual command:

```bash
.venv/bin/python -m pip check
```

Result: `No broken requirements found`. Pip also reported its existing
non-writable cache warning; no cache permissions were changed.

The interpreter is Python 3.13.9. Installed project/development packages remain
PyMuPDF 1.26.7, Streamlit 1.66.1, pytest 8.4.2 and Ruff 0.14.2. A version probe
found no runtime metadata for setuptools. The declared build requirement is
`setuptools==80.9.0`, normally provided by pip's isolated build process; this
stage did not attempt a fresh build or dependency installation. No application
runtime dependency failure was found by `pip check` or the test rehearsal.

## 3. Isolated source copy

Created `<temporary-source-copy>` with a Python copy operation
over the actual output of:

```bash
git ls-files --cached --others --exclude-standard -z
```

The initial copy contained 69 Git-eligible files. The copy operation checked
that source paths stay inside the project. It excluded ignored report PDFs,
processed data, `.env`, `.venv` and `.git`. In both `data/raw/` and
`data/processed/`, only `.gitkeep` was present before the checks. The later final
documentation is synchronized into that owned temporary copy without changing
its tested Python source. The ignored record
`data/processed/phase-9-rehearsal.json` captures the copy, environment and results.

Verified that the imported module actually comes from the temporary source tree,
not the original editable checkout:

```bash
PYTHONPATH='<temporary-source-copy>/src' \
  '<project-root>/.venv/bin/python' \
  -c 'import pathlib, financial_intelligence_copilot as p; path=pathlib.Path(p.__file__).resolve(); assert path.is_relative_to(pathlib.Path.cwd()); print("Imported source copy:", path)'
```

Working directory: `<temporary-source-copy>`.
Actual import: the temporary copy's `src/financial_intelligence_copilot/__init__.py`.

## 4. Commands and actual rehearsal results

From the temporary source directory, using the already installed dependencies:

```bash
PYTHONPATH='<temporary-source-copy>/src' \
  '<project-root>/.venv/bin/python' -m pytest -q \
  > '<project-root>/data/processed/phase-9-rehearsal-pytest.log' 2>&1

PYTHONPATH='<temporary-source-copy>/src' \
  '<project-root>/.venv/bin/python' -m ruff check .

PYTHONPATH='<temporary-source-copy>/src' \
  '<project-root>/.venv/bin/python' -m ruff format --check .
```

Actual results:

```text
342 passed, 5 warnings in 2.52s
All checks passed!
33 files already formatted
```

The warnings are the known PyMuPDF/SWIG import deprecations. No new tests were
added for these reversible documentation edits. Running the existing suite in
the source copy checks that neutral fixtures and CLI tests do not silently
depend on the developer's official PDFs or processed cache.

Then ran the documented readiness command without local reports:

```bash
PYTHONPATH='<temporary-source-copy>/src' \
  '<project-root>/.venv/bin/python' \
  scripts/check_comparison_readiness.py \
  --output data/processed/no-report.readiness.json
```

Actual result: exit status **2**, naming the missing registered FY2024 PDF.
`data/processed/no-report.readiness.json` was not created. This is the expected
missing-source behavior, not a successful real-data calculation or a fabricated
source fallback.

## 5. Reproduction and acceptance limits

This rehearsal reuses an installed dependency environment. It does not prove a
fresh Python install, package-registry access, offline package building, every
supported Python version, public hosting or successful acquisition of sources
on another machine. README now gives the ordered path: install/test, obtain and
register reports, parse, build the index, open the local workspace, then run the
candidate/comparison/evaluation commands.

The Stage 8 development results are unchanged: 40 completed cases, 40/40 current
engineering expectations, 12/12 literal source spans and 21/28 proposed top-five
page hits after the documented repairs. Gold and human-scoring counts remain
zero; no semantic accuracy claim follows from those observations or 342 passing
software tests. Full financial and product acceptance remains pending.

Next use the [acceptance worksheet](acceptance-checklist.md) to record actual
source/answer, KPI fact, pair comparability and evaluation decisions. Only then
can approved inputs enter a reviewed store, real charts and semantic scores.
Final recorded demonstration and publication decisions also remain open.
