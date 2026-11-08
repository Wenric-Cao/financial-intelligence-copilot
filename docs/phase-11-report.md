# Stage 11: source-bound reviewed-fact persistence

Executed on 2026-11-08 (Asia/Singapore). This increment implements persistence
for explicit KPI fact decisions. It does not record any real approval, perform
a real financial comparison, or produce semantic evaluation scores.

## Delivered behavior

- `verified_store.py` builds a separate JSON projection containing only facts
  already confirmed in the source-bound review packet. It preserves plain
  decimal strings, source context, financial caveats and actual review metadata.
- Candidate records remain unverified and unchanged. A fact confirmation does
  not approve pair comparability. The current UI/comparison path continues to
  validate live reviews; numerical Q&A is not connected to the new store.
- Export/check operations revalidate actual local PDFs and fingerprint complete
  candidate, review, manifest and registered source bytes. Missing, revoked,
  modified or stale inputs prevent reuse of the saved projection.
- Canonical JSON comparison preserves type distinctions, including booleans,
  integers and floats. Saved-store duplicate keys, non-finite values and payload
  tampering are rejected. The loader also checks for observed store-file changes
  during validation.
- Exports never overwrite an existing file. Output paths cannot alias canonical
  KPI input files or write inside `data/raw`, including an absent review file,
  symlink or `..` alias. Review identified this absent-input edge case before
  publication; five targeted regressions were added.
- Fingerprints detect observed content changes, not authenticated human identity
  or a filesystem lock. Callers must use the validator against current inputs,
  rather than trust a saved `verified` field or reuse an old in-memory snapshot.

## Changed files

| Files | Purpose |
| --- | --- |
| `src/financial_intelligence_copilot/verified_store.py` | Build, exclusively write and revalidate reviewed-fact projections |
| `scripts/build_verified_store.py` | Mutually exclusive `--output` / `--check`, English results and errors |
| `tests/conftest.py`, `tests/test_verified_store.py`, `tests/test_verified_store_cli.py` | Labeled neutral PDFs, fact-only export, revocation/tamper/race/path protection and subprocess integration |
| `README.md`, `PRD.md`, `ARCHITECTURE.md` | Current implementation, usage and persistence boundaries |
| `docs/kpi-review-guide.md`, `docs/development-plan.md`, `docs/acceptance-checklist.md`, `docs/publication-notes.md` | Review workflow, actual status and source-publication scope |
| `AGENTS.md` | Owner's standing instruction to publish completed, validated increments to the existing repository |
| `docs/phase-11-report.md` | This execution record |

## Actual commands and results

Commands below ran from the project root with the existing isolated dependency
environment. No dependency was added and no model/API was used.

```bash
.venv/bin/python -m pytest -q tests/test_verified_store.py tests/test_verified_store_cli.py
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pip check
git diff --check
```

Final new-feature tests: **44 passed**, 5 existing PyMuPDF/SWIG deprecation
warnings. Final full suite: **490 passed**, the same 5 warnings, **8.84 s**.
An earlier full run passed 485 tests before adding the five output-path
regressions. Ruff check passed, all 42 Python files were formatted, dependency
checks found no broken requirements, and the diff whitespace check passed.
Pip reported that its cache was unavailable and disabled it; the consistency
check still completed successfully. These tests establish software behavior,
not financial correctness, reviewer identity or semantic answer accuracy.

Actual local-source commands:

```bash
.venv/bin/python scripts/build_verified_store.py \
  --output data/processed/phase-11-verified-kpis.json
.venv/bin/python scripts/build_verified_store.py \
  --check data/processed/phase-11-verified-kpis.json
.venv/bin/python scripts/check_comparison_readiness.py \
  --output data/processed/phase-11-comparison-readiness.json
```

| Observation | Actual result |
| --- | --- |
| Local source candidates checked | 10 |
| Explicit fact confirmations | 0 |
| Reviewed store records | 0; `records=[]` |
| Candidate decisions pending / rejected | 10 / 0 |
| Pair decisions pending | 5 |
| Real annual pairs calculated | 0/5; all change fields null |
| Store export and recheck | Exit 0; `Exported 0/10` / `Validated 0/10` |
| Repeated export to original filename | Exit 2; original store bytes preserved |
| Modified copy with `verified_count=0.0` | Exit 2; strict type-sensitive validation rejected it |

The last two boundary checks used subprocesses and an ignored copy of the empty
store, never altered source/review records. Before/after SHA256 values for
`data/kpi_candidates.json`, `data/kpi_reviews.json` and `data/manifest.csv`
were identical. The genuine export also revalidated after the final path fix.

Local evidence files remain Git-ignored:

```text
data/processed/phase-11-inputs.before.json
data/processed/phase-11-verified-kpis.json
data/processed/phase-11-comparison-readiness.json
data/processed/phase-11-tampered-store.json
data/processed/phase-11-integrity-checks.json
```

## Acceptance and next work

The separate store mechanism is implemented; there is still no populated real
verified KPI dataset. The owner must review actual fact cells and definitions,
and separately resolve financial comparability, before promotion or calculation.
The [KPI guide](kpi-review-guide.md) contains the candidate IDs, physical pages
and NCI, exchange-rate and tax issues. Generic development or publication
instructions do not confirm those decisions.

Factual-answer acceptance and all forty gold/human evaluation judgments also
remain pending. Historical Stage 8 engineering observations retain their
original date and null semantic metrics. Further implementation may connect
source-checked reviewed facts to numerical answers after actual review, while
preserving the independent comparison gates.

This completed increment is prepared for the owner's authorized GitHub update.
Only code, tests and English documentation belong in that commit. Raw annual
reports, full text, local stores, caches, API secrets and internal planning
documents remain excluded. No public application deployment is performed.
