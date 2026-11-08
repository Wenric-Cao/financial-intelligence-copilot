# Stage 14: public-link automatic official-report initialization

## Problem and product decision

Stage 13 successfully validated two real PDF uploads in one browser session.
The product owner's next tab still had no data because the temporary workspace
was owned by that WebSocket session. The earlier one-session success did not
prove that the public link was ready for a new visitor. Streamlit documents
this boundary in its [Session State reference](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state).

On 2026-11-08 the product owner selected automatic cloud initialization, so
visitors can ask questions without uploading reports. This changes the runtime
data lifecycle, not financial review or evaluation acceptance.

## Changed files and behavior

- `cloud_data.py` and `test_cloud_data.py`: exact official URL/hash/filename
  allowlist, bounded HTTPS transport, rejected redirects, complete staged
  preparation, actual download receipt and a locked process-owned runtime cache.
- `ui.py`, `app.py` and `test_ui.py`: automatic startup only for a completely
  empty runtime inventory, shared official data for fresh sessions, explicit
  retry, and isolated manual upload fallback. Partial local data is not hidden.
- `.env.example`, README, PRD, architecture and cloud setup: document automatic
  reconstruction after restart, the fallback's session boundary and actual
  acceptance limits. The process environment can disable automatic loading.

Original PDFs, page text, indexes, raw response JSON and local receipts remain
ignored. No API key, paid service, model call, new hosting target, browser
permission change or financial approval is introduced.

## Actual software and source checks

Commands run from the project root:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pip check
git diff --check
```

The implementation checkpoint passed **657 tests**, with five existing
PyMuPDF/SWIG deprecation warnings. Ruff lint/format, dependency consistency and
diff whitespace checks passed. The new backend's 43 transport/cache tests use
explicit neutral PDFs and fake transport responses; they do not fabricate AIA
financial results. The UI tests use real neutral PDF parsing/indexing with only
the network/cache boundary replaced.

The regression checks cover new independent sessions, both report years,
physical-page evidence, failure/retry without a widget-triggered request loop,
partial-local-data rejection, manual-upload isolation, pending financial facts,
concurrent cache reuse, source changes, oversized/incomplete/redirected
downloads, temporary cleanup and retained workspace ownership.

An actual-network local rehearsal completed at
**2026-11-08T10:46:54.479778+00:00**:

| Observation | Actual result |
| --- | --- |
| Official downloads | Exactly two; pinned hashes matched |
| Next cache access | Reused the same prepared root without another download |
| Prepared inventory | 2 reports, 734 physical pages, 2,159 chunks |
| Reviewed facts | 0 |
| FY2025 risk-governance query | `extractive_evidence`, first physical PDF page 64 |
| VONB lookup | `abstained`, `fact_review_pending`, no financial value |
| Manifest/candidates/reviews/evaluation cases | Byte hashes unchanged |

The original known FY2025 physical page 3 has no native extractable text. It
retains its physical page and empty-page status; OCR is still disabled. No
invented text replaces it. The ignored local rehearsal receipt is
`data/processed/phase-14-real-bootstrap.json`.

## Hosted acceptance

Pending at the implementation checkpoint: publish the validated change to the
existing repository, then verify automatic loading with no PDF selections,
physical-page/hash evidence, a refresh, a separate new tab and pending financial
lookup on the existing Streamlit deployment. A local/network rehearsal or the
earlier manual-upload success does not satisfy these hosted checks.

## Remaining project gates

No gold answers, financial confirmations, pair-comparability decisions or human
scores were added. All ten real fact reviews and five comparisons remain
pending, with zero calculated pairs. The historical forty-case run is not
rerun or relabeled as this change's semantic accuracy. Automatic source loading
is an engineering repair, not completion of the financial MVP.
