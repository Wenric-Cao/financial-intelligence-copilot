# Automatic official-report initialization on Streamlit Community Cloud

## Public visitor experience

Open the existing app and wait for **Official reports ready**. No PDF selection,
Chrome extension, API key or model service is required. The product owner chose
this behavior on 2026-11-08 after the session-only upload design failed to meet
the expectation that a public portfolio link should work for a new visitor.

A fresh checkout intentionally has no original reports, page text or index.
`app.py` now obtains the two exact registered AIA English FY2024/FY2025 reports
from official HTTPS sources and prepares temporary runtime data automatically.
Once ready, select a year and ask an English question. Original excerpts retain
physical PDF page numbers and official source links. Unconfirmed financial
lookups still abstain: loading source data does not approve a financial fact.

Refreshes and new tabs reuse the server's checked runtime. A server restart or
redeployment clears temporary files; the next visit automatically downloads and
rebuilds them. Cold starts depend on AIA availability and source validation and
can take longer than later requests. No latency guarantee is claimed.

## Source and storage controls

- Only two exact AIA URLs, filenames and SHA256 hashes are accepted. Their
  identities are pinned in both the manifest and automatic-loader code.
- Redirects are rejected. Each download is limited to 16 MiB, with a 30-second
  socket timeout and a checked 90-second body deadline. A blocking read can
  finish at the socket timeout before the deadline check runs.
- Both PDFs must pass complete-byte hash checks before parsing. Page parsing,
  index reconstruction and source validation must finish before adoption.
- A lock serializes preparation. The process retains one current cache entry;
  active sessions keep their adopted handles alive during a metadata revision.
- Runtime files live outside the Git checkout. The manifest's original
  acquisition history and all financial/evaluation review decisions remain
  unchanged; an actual download receipt records the new acquisition times.
- Cache access rechecks public metadata and workspace bytes. Changes fail
  closed or require reconstruction; no previous answer is released as fallback.
- Original reports, full extracted text, indexes and secrets are not committed
  to GitHub or offered through download/static-file routes. Source cards link
  to AIA's original PDFs. No report is sent to an LLM provider.
- Manual uploads remain isolated to their own session and never populate the
  shared automatic cache.

The official [AIA annual reports page](https://www.aia.com/en/media-centre/annual-reports)
identifies the sources. AIA's [terms of use](https://www.aia.com/en/terms-of-use)
remain applicable; fetching and hash checks do not grant a redistribution
license or establish a legal basis for every use. The app does not host a
downloadable copy of the reports or claim a license from AIA.

## Configuration and failure recovery

`app.py` reads the process environment variable `FIC_AUTO_LOAD_REPORTS`, default
`true`. `.env.example` is an example only; it is not loaded automatically.
To require local files or per-session uploads, set the process variable to
`false` before starting Streamlit:

```sh
FIC_AUTO_LOAD_REPORTS=false .venv/bin/python -m streamlit run app.py
```

Automatic loading runs only when all five expected runtime files are absent:
the two raw reports, two page snapshots and the retrieval index. A partial local
dataset is not silently replaced. Complete local data continues through normal
source validation. For a partial local workspace, follow the README rebuild
commands or deliberately use a clean source checkout.

If automatic loading fails, questions stay disabled. Open source diagnostics,
then select **Retry official report loading**. A failed attempt is retained for
the current browser session and metadata revision so unrelated widget changes
do not repeat network requests. If AIA serves different bytes, redirects, or an
unavailable source, review the source/version before changing any pin. Do not
bypass the hash check.

## Optional manual fallback

1. Expand **Load official AIA reports for this session**.
2. Obtain the full English FY2024 and FY2025 reports through the two official
   links. Use only reports you are authorized to process.
3. Select each PDF in its labeled fiscal-year field, then click **Load official
   reports**. Each must be no larger than 16 MiB and match its pinned SHA256.
4. The app prepares an isolated temporary workspace and validates it before use.
   **Clear loaded reports** removes only this manual workspace.

This fallback is session-only. A refresh, new tab or restart may require another
manual upload if automatic fetching remains unavailable. Selecting files in one
tab never makes another tab's manual workspace available. Uploading sends the
reports to the existing Streamlit server, not GitHub, and grants no approval.

For assisted browser uploads only, OpenAI's [Chrome extension instructions](https://learn.chatgpt.com/docs/chrome-extension#upload-files)
require **Allow access to file URLs**. That broader local permission is not
needed for automatic initialization or normal manual file selection. The app
does not change browser permissions.

## Actual verification records

The earlier [Stage 13 hosted check](phase-13-report.md#completed-hosted-follow-up)
loaded two real reports into one manual session (734 physical pages / 2,159
chunks), returned FY2025 page 64, and abstained on an unconfirmed VONB lookup.
That check did not prove refresh/new-visitor readiness; the distinction is why
automatic initialization was added. See the [Stage 14 record](phase-14-report.md)
for the new implementation's actual tests and hosted acceptance status.

Historical evaluation runs remain separate. No cloud initialization or upload
creates a new semantic evaluation, gold approval, financial confirmation or
human score.
