# Stage 1 execution record

Publication note: machine-specific paths and interpreter commands are generalized
for sharing. Original execution transcripts are retained locally; placeholders
such as `<project-root>` and `<temporary-source-copy>` need local substitution.
Recorded commands, outcomes and limitations retain their original meaning.

Date: 2026-10-24 (Asia/Singapore).
Workspace: `<project-root>`.

## 1. Requirements and environment inspection

Read `Financial_Intelligence_Copilot_Project_Plan.md` and
`Codex_First_Task_Prompt.md`. No applicable `AGENTS.md` was found in the workspace
or the checked ancestor directories. The two existing Markdown files were left
unchanged.

Commands actually run included:

```bash
pwd
rg --files --hidden -g '!.git' -g '!node_modules' -g '!**/.venv/**' -g '!**/venv/**' -g '!**/__pycache__/**'
python3 --version
python3 -m pip --version
python3 --version
git rev-parse --show-toplevel
```

Import availability was inspected with `importlib.util.find_spec`.

- Default `python3`: Python 3.14.4, without PyMuPDF, pytest, or Ruff.
- Available Anaconda interpreter: Python 3.13.9, with pytest/Ruff but no PyMuPDF.
- The initial directory inherited a Git repository rooted at
  `<user-home>`. No changes were made to that parent repository.
- Initial project contents were the two Markdown requirement/task documents;
  no official PDFs were present.

Files added for planning: `docs/development-plan.md`.
Tests at this step: not applicable; this was read-only inspection.

## 2. Project skeleton and isolated setup

Files added:

- `.gitignore`, `.env.example`, `pyproject.toml`, `README.md`.
- `data/manifest.csv` (header only), `data/raw/.gitkeep`,
  `data/processed/.gitkeep`.
- `src/financial_intelligence_copilot/__init__.py`.
- `assets/screenshots/.gitkeep`, `tests/fixtures/README.md`.

Commands actually run:

```bash
python3 -m venv .venv
git -c init.defaultBranch=main init .
PIP_NO_CACHE_DIR=1 PIP_RETRIES=0 PIP_TIMEOUT=15 .venv/bin/python -m pip install --disable-pip-version-check -e '.[dev]'
.venv/bin/python --version
.venv/bin/python -m pip check
git rev-parse --show-toplevel
git status --short
git check-ignore -v --non-matching .env .env.local .env.example data/raw/report.pdf data/processed/report.pages.json data/raw/.gitkeep data/processed/.gitkeep .venv/bin/python
```

Environment issues and resolution:

- The initial sandboxed editable install could not reach the package index during
  build dependency resolution. Retrying the install with approved network access
  succeeded. No global Python packages were changed.
- The initial sandboxed Git initialization could not create `.git`. The approved
  retry succeeded, creating an independent repository inside this workspace.
- No commits, remotes, pushes, deployment, or paid API calls were made.

Actual installed versions:

| Component | Version |
| --- | --- |
| Python | 3.13.9 |
| PyMuPDF | 1.26.7 |
| pytest | 8.4.2 |
| Ruff | 0.14.2 |
| pytest dependency: iniconfig | 2.3.1 |
| pytest dependency: packaging | 26.3 |
| pytest dependency: pluggy | 1.7.0 |
| pytest dependency: Pygments | 2.21.0 |

Direct dependencies and the build backend are pinned in `pyproject.toml`.
Transitive versions above record this run; they are not a full dependency lock.

Results: package installed successfully; `pip check` reported
`No broken requirements found`. The independent Git root is now the workspace.
The ignore rules exclude local secrets, PDFs, extracted full text, and `.venv`,
while allowing `.env.example` and directory placeholders.

A final inline Python check used `subprocess.run(['git', 'check-ignore', '-q',
'--', path])` to assert expected ignore status for nine paths and `csv.reader`
to inspect the manifest. Actual output:

```text
Git ignore verification: 9 paths match expectations.
Source manifest: 11 header fields, 0 data rows.
Real annual reports: 0 local PDFs; real ingestion remains pending.
```

## 3. PDF page parser and tests

Files added:

- `src/financial_intelligence_copilot/pdf_parser.py`.
- `tests/test_pdf_pages.py`.

Features: physical pages start at 1; every page retains document ID, issuer,
fiscal year, language, and native text; empty/error pages retain their positions;
warnings identify their document/page; local source hashes accompany JSON output.
Issuer/year/language are caller-supplied labels and require source review.

Commands actually run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/fic-parse-pdf --help
```

Actual results:

```text
pytest: 15 passed, 5 warnings in 1.30s
ruff check: All checks passed!
ruff format --check: 3 files already formatted
fic-parse-pdf --help: usage displayed successfully; exit status 0
```

The five pytest warnings are import-time PyMuPDF/SWIG deprecation warnings about
`SwigPyPacked`, `SwigPyObject`, and `swigvarlink` lacking `__module__`. An additional
`swigvarlink` warning was printed at interpreter shutdown. These were not hidden
or counted as test failures.

Test coverage includes both year labels, physical versus printed numbering, a
blank middle page, metadata propagation, the actual input hash, image-only pages,
an injected extraction failure, document instructions retained as plain text,
missing/corrupt/non-PDF/encrypted input, invalid metadata, JSON export, output
overwrite protection, and an all-empty-document review exit status.

All PDF fixtures are neutral generated test documents in pytest temporary
directories. They contain no financial figures and are not official reports.
The plain-text instruction test is a parser check, not a claim that a future RAG
system resists prompt injection.

## 4. Official report acquisition instructions

File updated during creation: `README.md`, with manual download, placement,
source-manifest, hashing, parsing, and physical-page review instructions.

A read-only check followed links from
[AIA's official annual report page](https://www.aia.com/en/media-centre/annual-reports)
to the [2024 English report](https://www.aia.com/content/dam/group-wise/en/docs/investor-relations/2025/2024%20Annual%20Report%20%28Eng%29.pdf)
and [2025 English report](https://www.aia.com/content/dam/group-wise/en/docs/investor-relations/2025/AIA%202025%20annual%20report_EN.pdf).
The 2024 link also uses a `2025` URL directory; this does not establish its fiscal
year. No official PDF was saved locally by this workflow.

Local report parsing commands in the README are instructions for the next step;
they have **not** been run against real AIA reports. Download timestamps, hashes,
real-report page checks, financial values, and model evaluation results remain
unpopulated. No source-manifest row claims that a report was downloaded.

## 5. Next acceptance gate

The product owner downloads and checks both complete English reports, places them
in `data/raw/`, and records actual source details. Then run the documented parser
commands, inspect warnings, and compare physical pages against the PDFs. Review
real extraction quality before adding chunking, year-filtered retrieval, or Q&A.

Stage 1 parser tests and tooling checks are complete. Real-report ingestion,
KPI verification, and RAG evaluation remain pending.
