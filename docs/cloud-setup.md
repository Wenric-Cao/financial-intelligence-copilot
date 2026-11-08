# Session data loading on Streamlit Community Cloud

## Why a fresh cloud checkout cannot answer yet

Streamlit Community Cloud runs a checkout of the GitHub repository. The project
intentionally excludes original annual reports, page text, indexes, local stores
and secrets. A registered manifest row is source metadata; it does not provide
the report bytes. The missing-page error therefore requires a complete runtime
dataset, rather than committing one page JSON file.

See Streamlit's [file organization documentation](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization).

## Load the two registered official reports

1. Open the app and its **Load official reports** section.
2. Obtain the full English FY2024 and FY2025 reports using the displayed official
   links or the [AIA annual reports page](https://www.aia.com/en/media-centre/annual-reports).
   Use only documents you are authorized to process.
3. Choose the FY2024 PDF and FY2025 PDF in their separate upload fields. Each
   report has a 16 MiB limit. Only the two exact registered file versions are
   accepted: SHA256 must match `data/manifest.csv`. Renaming a file does not
   substitute a different report or version.
4. Click **Load official reports**. The server checks both hashes, parses physical
   PDF pages, builds and revalidates the evidence index, and prepares a separate
   reviewed-fact projection from the actual recorded decisions. Loading reports
   does not confirm any KPI or approve a comparison.
5. When loading succeeds, ask a selected-report question. Original excerpts have
   physical page references and official source links. Unconfirmed financial
   queries remain unavailable.
6. Use **Clear loaded reports** to discard this app session's loaded workspace.
   A later visit or server restart may require loading the reports again.

The current real review packet has zero confirmed facts and five pending annual
pairs. The prepared reviewed store is empty; no financial or evaluation approval
is inferred from upload, source checks or successful retrieval.

## Data handling and limits

This is a fixed two-report research workflow, not arbitrary PDF chat. Uploading
sends the selected PDFs to the Streamlit app server for processing. The app uses
an isolated temporary directory for that session, validates the full dataset
before adopting it, and leaves the source checkout unchanged. Reports and full
text are not committed to GitHub or exposed through an app download/static-file
route. Responses contain the relevant short evidence and official source link.
This is not a promise of durable storage or instantaneous deletion on a network
disconnect; explicit clearing removes the app-owned workspace, and normal
temporary-directory/session cleanup applies afterward. Hosting operators remain
part of the processing environment.

The app makes no automatic report-download request and calls no model API.
It does not send reports to an LLM provider. Separate sessions do not adopt one
another's working directories. Changed project source/review metadata invalidates
the previous session dataset and requires preparing it again.

AIA's [terms of use](https://www.aia.com/en/terms-of-use), section 7, restrict
public/commercial copying, republication and retrieval-system use except where
permitted. An official public download link is not evidence of a redistribution
license. This upload workflow does not grant rights or certify that a particular
use is permitted. Public full-report hosting or a preloaded public corpus needs
an appropriate rights basis; neither is enabled by this repair.

## Local use and troubleshooting

An already-prepared local workspace continues to work without uploads. To
rebuild local files manually, follow the README's parsing/indexing commands.
The cloud upload route uses the same parser and source checks.

- **Hash mismatch:** select the exact registered official version. If the source
  has changed, review its identity, manifest and dependent evidence; do not bypass
  the hash check or silently update it.
- **Only one report selected:** select the other fiscal year before loading.
- **Invalid/locked PDF or extraction failure:** preserve the original files and
  report the error. No synthetic replacement or fabricated page evidence is used.
- **Source/review configuration changed:** load again to create a current isolated
  workspace. Existing approvals are not transferred to different content.
- **Historical evaluation unavailable:** raw local runs are not part of the
  checkout/session. See `EVALUATION.md` for the recorded development observations;
  the cloud app must not invent a new run or human score.
