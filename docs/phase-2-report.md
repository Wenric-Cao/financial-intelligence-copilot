# Stage 2: real annual-report ingestion

Publication note: machine-specific paths and interpreter commands are generalized
for sharing. Original execution transcripts are retained locally; placeholders
such as `<project-root>` and `<temporary-source-copy>` need local substitution.
Recorded commands, outcomes and limitations retain their original meaning.

Date: 2026-10-25 (Asia/Singapore).
Workspace: `<project-root>`.

## Outcome and acceptance boundary

The two official AIA English annual reports are present locally and were parsed
with the existing Stage 1 CLI. All 734 physical-page records passed source-hash,
record-count, document metadata, and one-based page-sequence checks. An independent
engineering check also compared every record with fresh native PDF extraction.
Poppler independently confirmed both document page counts.

Engineering ingestion checks are complete. Product-owner source review remains
pending. No financial KPI value, calculation, generated answer, citation quality
score, or RAG evaluation result has been verified or produced in this stage.

## 1. Official acquisition and provenance

The [official AIA annual reports page](https://www.aia.com/en/media-centre/annual-reports)
was rechecked and its two English report links were followed. Only those two
identified PDFs were downloaded; no site crawl was performed. The local workflow
used Python `urllib.request.urlopen` with the exact official URLs, checked for a
PDF header and an official HTTPS destination, refused to overwrite existing
reports, and recorded the timestamp and SHA256 after each completed download.

| Document | Official source | Download completed (SGT) | Bytes |
| --- | --- | --- | ---: |
| AIA-2024-EN | [FY2024 PDF](https://www.aia.com/content/dam/group-wise/en/docs/investor-relations/2025/2024%20Annual%20Report%20%28Eng%29.pdf) | 2026-10-25T19:31:45+08:00 | 8,255,975 |
| AIA-2025-EN | [FY2025 PDF](https://www.aia.com/content/dam/group-wise/en/docs/investor-relations/2025/AIA%202025%20annual%20report_EN.pdf) | 2026-10-25T19:31:46+08:00 | 3,330,220 |

Actual local hashes:

```text
AIA-2024-EN
0e888a5752d71ac8c841c234212cd3fc0cca9f16991db1f36a774f13b97890e3

AIA-2025-EN
18537f928c3bb4879c35566252f2f8420c6a3a237016af4706b081a77d126977
```

`data/manifest.csv` now has two actual rows with official URLs, download times,
hashes, filenames, and source-review notes. Period ends were populated after
checking the year-ended headings on the relevant income statement pages.
These are engineering source checks, not product-owner KPI verification.

## 2. Parser commands and actual output

Commands actually run from the project root:

```bash
.venv/bin/fic-parse-pdf data/raw/AIA_2024_Annual_Report_EN.pdf \
  --doc-id AIA-2024-EN --issuer 'AIA Group Limited' --fiscal-year 2024 \
  --output data/processed/AIA-2024-EN.pages.json \
  2> data/processed/AIA-2024-EN.parse.log

.venv/bin/fic-parse-pdf data/raw/AIA_2025_Annual_Report_EN.pdf \
  --doc-id AIA-2025-EN --issuer 'AIA Group Limited' --fiscal-year 2025 \
  --output data/processed/AIA-2025-EN.pages.json \
  2> data/processed/AIA-2025-EN.parse.log
```

| Report | Physical pages | `ok` | `empty_text` | `extraction_error` | CLI exit |
| --- | ---: | ---: | ---: | ---: | ---: |
| FY2024 | 371 | 371 | 0 | 0 | 0 |
| FY2025 | 363 | 362 | 1 | 0 | 0 |

The FY2025 parser log names PDF page 3 as lacking native text. This record was
retained, and subsequent pages were not renumbered. The `ok` status indicates
non-empty extraction only, not financial correctness or perfect reading order.

## 3. Engineering visual spot checks

Poppler `pdfinfo` confirmed 371 and 363 pages respectively, with neither PDF
encrypted. `pdftoppm` rendered the selected physical pages with this command
pattern, using each page number in turn:

```bash
pdftoppm -f 166 -l 166 -scale-to 1400 -singlefile -png \
  data/raw/AIA_2024_Annual_Report_EN.pdf \
  /tmp/fic-aia-phase-2-review/AIA-2024-EN.pdf-page-166
```

The rendered pages were inspected alongside the extracted text:

| Document | Physical PDF page | Inspection finding |
| --- | ---: | --- |
| FY2024 | 1 | AIA cover, correct report year and stock-code identity |
| FY2024 | 14 | Chairman statement; printed page 012 |
| FY2024 | 166 | Consolidated income statement; printed page 164; correct year-ended heading |
| FY2025 | 1 | AIA cover, correct report year and stock-code identity |
| FY2025 | 3 | Promotional artwork with no native extractable text; not a missing page |
| FY2025 | 4 | Contents page; visible dotted leaders explain much of its extraction noise |
| FY2025 | 8 | Chairman statement; printed page 006 |
| FY2025 | 154 | Consolidated income statement; printed page 152; correct year-ended heading |

Physical and printed numbers differ. Future citations must continue to say
`PDF page N`; no global printed-page offset is inferred from these samples.
The statements were checked for identity, period, and page mapping. Their
financial values were not entered into a verified KPI store.

Rendered full-page review images are temporary local artifacts, not portfolio
screenshots or redistributed report assets. The official Chinese company name
is preserved as source content in these otherwise English reports.

## 4. Known extraction limits

FY2025 has native-text replacement characters on these physical pages:

| PDF page | U+FFFD count |
| ---: | ---: |
| 4 | 3,501 |
| 22 | 427 |
| 76 | 542 |
| 146 | 573 |

These pages contain contents navigation and dotted leaders; page 146 also has
concatenated text from adjacent columns. The raw output was preserved rather
than silently rewritten. No replacement characters were found in FY2024 text.
Other multicolumn pages can still have imperfect reading order without emitting
replacement characters.

Before retrieval, use a separate reviewed search-text representation to remove
leader noise or exclude navigation pages. Preserve original page text for source
inspection and ensure cleaned chunks still map to the correct physical page.
FY2025 page 3 needs no OCR for the present research use case because it is a
promotional page; retain its empty-text record in the page inventory.

## 5. Actual checks and local artifacts

The structural audit used inline Python (`csv`, `hashlib`, `json`, and per-record
assertions) and saved `data/processed/ingestion-check.json`. It verified:

- Exactly the two expected source records, with local bytes matching each hash.
- JSON hash, page count, and complete one-based sequence for each document.
- Matching issuer, fiscal year, language, and document ID on every page.
- Explicit empty/error page lists and replacement-character counts.

Additional commands actually run:

```bash
.venv/bin/python -m pytest -q > data/processed/phase-2-pytest.log 2>&1
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
shasum -a 256 data/raw/AIA_2024_Annual_Report_EN.pdf data/raw/AIA_2025_Annual_Report_EN.pdf
git check-ignore -v data/raw/AIA_2024_Annual_Report_EN.pdf data/raw/AIA_2025_Annual_Report_EN.pdf data/processed/AIA-2024-EN.pages.json data/processed/AIA-2025-EN.pages.json data/processed/ingestion-check.json
```

Actual results:

```text
pytest: 15 passed, 5 warnings in 0.09s
ruff check: All checks passed!
ruff format --check: 3 files already formatted
```

The existing PyMuPDF/SWIG deprecation warnings remain visible, including the
shutdown warning. Unit tests still use neutral generated fixtures; the real-data
structural audit above is a separate check, not an expanded RAG evaluation.
The macOS hash command matched both recorded digests, and Git confirmed that both
PDFs, both page JSON files, and the audit JSON are ignored.

Local ignored artifacts now include both PDFs, two page JSON files, two parser
logs, the structural audit JSON, and the pytest log. Public-facing project files
changed in this stage are `data/manifest.csv`, `README.md`,
`docs/development-plan.md`, and this report. Parser source and dependencies did
not change. No paid model calls, deployment, Git commits, or pushes occurred.

## Next development gate

Build page-bounded chunks and a local retrieval baseline with strict document and
fiscal-year filters. Handle the observed navigation noise before indexing. Keep
stable evidence IDs, raw excerpts, physical page numbers, and official source
links. Prepare at least five factual retrieval cases for product-owner review
before adding an approved LLM answering layer.
