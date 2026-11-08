# AIA KPI candidate review guide

Prepared on 2026-10-31. All ten records are **unverified candidates**, with
`verified=false`, `review_status=pending_owner_review`, no reviewer signature,
and `comparability_status=needs_owner_review`. This guide records engineering
source checks, not product-owner financial approval.

## Candidate inventory

Values are reported annual levels, not currency-adjusted growth inputs. Both
periods run from 1 January to 31 December of the indicated year. Pages below
are **physical PDF pages**, starting at 1, rather than printed page labels.

| Metric code | FY2024 candidate | FY2025 candidate | Currency / unit | FY2024 PDF page | FY2025 PDF page |
| --- | ---: | ---: | --- | ---: | ---: |
| VONB | 4,712 | 5,516 | USD million | 30 | 27 |
| ANP | 8,606 | 9,484 | USD million | 30 | 27 |
| VONB_MARGIN | 54.5 | 58.5 | percent; no currency | 30 | 27 |
| OPAT | 6,605 | 7,136 | USD million | 36 | 35 |
| UFSG | 6,327 | 6,765 | USD million | 49 | 33 |

Candidate IDs follow `AIA-{year}-{metric_code}`, for example
`AIA-2025-OPAT`. A margin of `58.5` is stored in percent units; it is not stored
as a decimal fraction. Monetary values remain in millions without scaling.

The underlying sources are the official [FY2024 English annual report](https://www.aia.com/content/dam/group-wise/en/docs/investor-relations/2025/2024%20Annual%20Report%20%28Eng%29.pdf)
and [FY2025 English annual report](https://www.aia.com/content/dam/group-wise/en/docs/investor-relations/2025/AIA%202025%20annual%20report_EN.pdf).
The exact downloaded-byte hashes are in `../data/manifest.csv`. Local copies
remain in `data/raw/` and are excluded from version control.

## Review in the local interface

1. Open [the local workspace](http://127.0.0.1:8501) and select **Financial KPIs**.
2. Select a report year or explicitly choose **Both fiscal years** for review.
3. Select each candidate. Open its official PDF link and check the visible table
   layout. The interface shows exact native-text header context and row, which
   can contain sidebar noise or adjacent rows; these do not replace the PDF.
4. Expand **Definition, scope and tax references**. Check each relevant note.
5. Download **all candidates (CSV)** if helpful. This export preserves pending
   status and blank reviewer/date fields; it does not approve any record.
6. Return an explicit decision by candidate ID, with corrections or uncertainties.
   Confirm financial facts separately from whether a pair is comparable.

For each record, check:

- [ ] Correct company, annual period, fiscal-year column, and physical source page.
- [ ] Correct whole numeric cell, sign, currency, and unit.
- [ ] Group versus segment scope; shareholder versus total/NCI treatment.
- [ ] Metric definition, exclusions, accounting/tax assumptions, and source context.
- [ ] Correct distinction between annual reported levels and CER/AER commentary.
- [ ] Prior-year comparative and any restatement or basis change reviewed.

A useful review response is: `AIA-2025-OPAT: value/unit/period/scope confirmed;
comparability still pending tax-basis review`. This is a response format example,
not a recorded approval. No record is approved by silence or a generic request
to continue development.

## Definitions and comparability issues to resolve

| Metric | Required interpretation and review pages |
| --- | --- |
| VONB | Group **Total after non-controlling interests**, not Subtotal or a market row. Review Group adjustments and annual period in FY2024 PDF pp.335, 370 and FY2025 pp.326, 362. Review exchange-rate presentation in FY2024 p.347 / FY2025 p.338 and FY2025 tax assumptions on p.343. |
| ANP | Annualised new premiums, with its first-year/single-premium definition and exclusions; do not substitute PVNBP or a generic sales measure. Definitions: FY2024 p.359 / FY2025 p.351. Annual tables: FY2024 p.335 / FY2025 p.326. |
| VONB_MARGIN | Company-defined margin uses VONB **gross of NCI** and excludes pension business. It must not be recomputed from the displayed after-NCI VONB divided by ANP. Definitions: FY2024 pp.335, 370 / FY2025 pp.326, 362. FY2025 p.343 explains the exclusion of potential future GMT top-up tax from EV/VONB assumptions. |
| OPAT | Use **attributable to AIA shareholders, excluding NCI**. FY2024 p.203 distinguishes 6,605 from total OPAT 6,632; FY2025 p.191 distinguishes 7,136 from 7,171. FY2025 p.35 footnote confirms scope. FY2025 p.34 describes first-time notional GMT top-up tax and Bermuda corporate income tax. |
| UFSG | Group generation **net of tax, before new-business reinvestment and central costs**. Do not substitute operating free surplus generation, free-surplus balance, or a per-share measure. Definition: FY2024 p.48 / FY2025 p.33. Review FY2025 pp.48, 343 for notional operating GMT versus actual net-profit tax treatment. |

FY2025 OPAT includes a notional GMT top-up tax charge of USD169 million and a
Bermuda corporate income tax charge of USD33 million; UFSG includes the notional
GMT charge. These disclosures identify a basis issue for review. The project has
not adjusted either year's numbers or certified any pair as comparable.

The FY2025 report repeats the same five FY2024 headline values as the original
FY2024 candidates. This is a checked **value match for five cells**, not a blanket
finding that no restatements exist, definitions are unchanged, or all tax/currency
bases are comparable. Report commentary on CER growth and percentage-point
movements must not be presented as a calculation from unadjusted annual levels.
No percentage or percentage-point change is calculated in this stage.

## What the software checks

`data/kpi_candidates.json` stores the exact token, row, header context, original
page offsets, source URL, source hash, definition pages, periods, scope and review
status. Values are plain decimal strings in JSON and `Decimal` in Python.

The loader checks the actual raw-PDF hash against the manifest, freshly extracts
the cited page, verifies exact source spans and whole-token boundaries, and
compares the normalized token with the stored value. It rejects inconsistent
units, duplicate metric-years, invalid page/period metadata, and attempted
verification signatures in the candidate dataset. Missing values never become
zero. It also checks the five FY2025 prior-year comparative tokens independently.

These checks do not establish that a column, definition, or financial basis was
interpreted correctly. Product-owner review remains necessary. The tested
comparison backend and interface now have separate fact and pair-review gates.
The UI shows recorded confirmations/readiness and only charts a calculated pair;
actual approvals remain pending. Stage 11 adds a separate persisted reviewed
store exporter/validator; the actual all-pending packet produces zero records.
The interface has no approval control and extractive Q&A directs financial
requests to the financial tabs. The UI continues to use current source-checked
reviews rather than trusting a stored `verified` flag.

## Record review decisions separately

`data/kpi_reviews.json` contains ten pending fact reviews and five pending pair
reviews. No approvals or reviewer signatures have been filled. Each decision
binds to the SHA256 of the complete original candidate record, including the
value, period, source location, definition references and caveats. A change to
any bound field invalidates the old decision, even if the candidate ID stays the
same. The candidate dataset itself stays unverified and is not edited to simulate
a reviewed store.

| Review | Decisions | Required confirmation checks |
| --- | --- | --- |
| One candidate fact | `pending`, `confirmed`, `rejected` | Value, unit/currency, period, scope, definition and source |
| One annual pair | `pending`, `comparable`, `not_comparable` | Definition, unit/currency, period, scope, exchange-rate basis, tax basis and restatement |

Pending records have null reviewer/date/check fields. A recorded decision needs
the actual reviewer, a timezone-aware ISO 8601 timestamp and explanatory notes.
`confirmed` and `comparable` additionally require every named check to be true.
Fact confirmation alone does not authorize a comparison. A generic request to
continue development leaves all decisions pending.

The engineering collaborator can record explicit decisions returned by the
product owner, preserving their qualifications and unresolved issues. These are
local audit records: content hashes detect stale decisions but do not authenticate
who typed a reviewer name. The operator remains responsible for recording only
actual decisions.

To audit the current packet against actual local sources:

```bash
.venv/bin/python scripts/check_comparison_readiness.py \
  --output data/processed/comparison-readiness.rerun.json
```

Choose a new output filename for each run. The command rechecks the raw PDFs and
candidate spans, validates the packet, and emits reasons for blocked pairs.
Current actual result: **0 confirmed facts and 0/5 pairs calculated**. Every
computed-change field is null. No real AIA comparison has been calculated.

When changed candidates need a fresh pending packet, preserve the existing audit
record and create a separate template with:

```bash
.venv/bin/python scripts/check_comparison_readiness.py \
  --init-review data/kpi_reviews.next.json
```

This prepares only pending decisions; it does not transfer or invent approvals.
The loader reads `data/kpi_reviews.json`, so a new template must be reviewed and
deliberately adopted before it can replace that audit record. No command here
overwrites an existing file.

After both gates pass, the backend checks identical issuer, metric, units,
currency, scope and basis, with consecutive full January–December periods and
independent source documents. For a positive prior amount it computes absolute
change and percentage change. A percent-unit metric produces percentage-point
change rather than percentage growth. Zero or negative prior values require
review and return no calculated change. A local Decimal context preserves exact
finite differences and uses at least 34 significant digits for repeating ratios;
presentation rounding remains separate.

## Export an explicit confirmed-fact projection

Stage 11 provides a separate local reviewed store without modifying candidates
or recording new decisions:

```bash
.venv/bin/python scripts/build_verified_store.py \
  --output data/processed/verified-kpis.rerun.json
.venv/bin/python scripts/build_verified_store.py \
  --check data/processed/verified-kpis.rerun.json
```

Use a new output filename. The current actual packet yields **0/10 reviewed
facts**, with an empty `records` list. Rechecks bind the current candidate,
review, manifest and PDF bytes; an old export fails after review revocation or
source changes. `--check` does not alter files. Consumers must revalidate through
the loader rather than trust a saved flag. Only explicit confirmed facts appear
with their recorded reviewer, timestamp, notes and source context. Content hashes
do not authenticate the reviewer, and fact confirmation leaves comparability
pending. Numerical Q&A is not connected to this store yet.
