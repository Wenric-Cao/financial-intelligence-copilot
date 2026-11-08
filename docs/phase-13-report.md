# Cloud repair: isolated session report loading

Executed on 2026-11-08 (Asia/Singapore) after the product owner supplied the
existing Streamlit app URL and its missing-page screenshot.

## Cause and implemented repair

The hosted checkout has source metadata, but correctly lacks ignored raw PDFs,
page snapshots and retrieval index. The prior interface consequently disabled
queries with a missing `data/processed/AIA-2024-EN.pages.json` error. Committing
full report data would violate the repository's publication scope.

The repair introduces an explicit, per-session loading workflow for exactly the
registered AIA FY2024/FY2025 English report versions. Both whole-file SHA256
values must match before parsing. The backend uses staged, private temporary
storage, prepares all page/index files, revalidates the retriever and existing
review decisions, and atomically adopts the complete directory. It never writes
raw data or caches into the source checkout. No automatic download or model API
is involved.

The UI uploads the selected files to the application server for processing,
holds the temporary workspace for that app session, and offers explicit clear.
Clearing or metadata invalidation removes only the session-owned workspace and
rotates upload controls; other sessions and local source data remain separate.
Missing runtime data now has actionable report selectors and official links,
with the original diagnostic preserved in an expander. Each upload is limited
to 16 MiB. Normal prepared local workspaces keep working without uploading.

This is a fixed-report workflow, not arbitrary PDF chat or a preloaded public
corpus. AIA source terms restrict public/commercial reuse; public accessibility
does not establish permission. Users must have an appropriate basis to process
their selected reports. See [cloud setup](cloud-setup.md) for source references,
data handling and limitations. Full reports/text are not offered for download,
committed to GitHub or sent to a model provider. An idle disconnect does not
establish instantaneous deletion, and temporary storage is not durable.

## Files

| Files | Change |
| --- | --- |
| `session_data.py` | Exact report/size/hash checks, metadata snapshots, staged parser/index validation, isolated publication and cleanup |
| `ui.py` | Session upload/adoption/reset controls, missing-data guidance and metadata invalidation |
| `tests/test_session_data.py` | 28 neutral-PDF backend cases, including provenance, paths, failure cleanup, races and isolation |
| `tests/test_ui.py` | Six new end-to-end neutral upload/session cases through the real preparation pipeline |
| `.streamlit/config.toml` | 16 MiB upload limit; static file serving remains disabled |
| `README.md`, `ARCHITECTURE.md`, `PRD.md`, `docs/cloud-setup.md` | Correct hosted setup, current checks and explicit storage/review boundaries |
| `docs/phase-13-report.md` | This repair record |

## Actual automated checks

```bash
.venv/bin/python -m pytest -q tests/test_session_data.py tests/test_ui.py tests/test_ui_state.py
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pip check
git diff --check
```

Focused suite: **77 passed**, 5 existing PyMuPDF/SWIG deprecation warnings,
4.03 s. Full suite: **609 passed**, the same 5 warnings, **9.97 s**.
Ruff check passed and all **48 Python files** were formatted. Pip found no broken
requirements; it disabled its unavailable cache. Diff whitespace checks passed.
Tests use explicitly labeled neutral documents, never invented company results.

Checks cover missing/wrong/extra/oversized uploads, pinned hashes and physical
pages, complete query readiness, stale metadata, existing-destination protection,
concurrent destination preparation, independent sessions, cleanup and secret/raw
history exclusion. UI checks preserve an old valid session on failed replacement,
clear old answers after metadata changes and reset upload selections on clear.

## Actual source rehearsal

The real local report bytes were supplied to the same backend in a new temporary
directory outside the project. This did not copy existing page/index caches.
The workspace fingerprint, source-rebuilding retriever and both answer modes
were then exercised. Actual result:

| Check | Result |
| --- | --- |
| Registered reports loaded | 2 |
| Physical page records | 734 |
| Evidence chunks | 2,159 |
| Risk Appetite/RMF excerpt | Source-span-checked FY2025 physical PDF page 64 |
| Confirmed financial facts | 0 |
| VONB lookup | `fact_review_pending`, no financial value |
| Historical raw evaluation copied | No |
| Source/review/manifest/evaluation-case bytes | Unchanged |

FY2025 physical page 3 still has no native text; the known warning remains
visible and page numbering is retained. Temporary rehearsal files were cleaned.
The local evidence is recorded under ignored `data/processed/phase-13-real-rehearsal.json`.
This is source/engineering verification, not financial acceptance or semantic
accuracy. All actual KPI and pair approvals and human evaluation ratings remain
pending.

## Publication and hosted verification

This tested repair is published to the existing repository under the owner's
standing instruction. It updates the owner's existing hosted app rather than
creating a new account or hosting service. After that deployment updates, verify
the two upload controls, load the registered reports, submit a factual query and
inspect the returned physical page link. Live observations and screenshots are
retained locally under ignored processed outputs; they must not be invented or
inferred from unit tests. Each new visitor/session must load its own authorized
report copies; the app does not distribute a shared complete corpus.
