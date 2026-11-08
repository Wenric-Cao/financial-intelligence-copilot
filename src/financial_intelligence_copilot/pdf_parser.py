"""Extract PDF text without dropping or renumbering physical pages.

Company and fiscal year are caller-supplied labels, not facts verified by this
parser. Text is untrusted data: no instructions, links, or scripts are executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import pymupdf

LOGGER = logging.getLogger(__name__)
PageStatus = Literal["ok", "empty_text", "extraction_error"]


class PDFParseError(ValueError):
    """A document could not be opened as a usable, unlocked PDF."""


@dataclass(frozen=True)
class DocumentMetadata:
    """Labels checked against the official report by the person importing it."""

    doc_id: str
    issuer: str
    fiscal_year: int
    language: str = "en"

    def __post_init__(self) -> None:
        for name in ("doc_id", "issuer", "language"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if type(self.fiscal_year) is not int or not 1000 <= self.fiscal_year <= 9999:
            raise ValueError("fiscal_year must be a four-digit integer")


@dataclass(frozen=True)
class PDFPage:
    """A physical page; pdf_page is always one-based, including blank pages."""

    doc_id: str
    issuer: str
    fiscal_year: int
    language: str
    pdf_page: int
    text: str
    status: PageStatus
    error: str | None = None


@dataclass(frozen=True)
class ParsedPDF:
    """Page records and an identity hash of the local input file."""

    source_filename: str
    sha256: str
    page_count: int
    pages: tuple[PDFPage, ...]

    def to_dict(self) -> dict:
        """Return JSON-serializable records with an explicit schema version."""
        return {"schema_version": 1, **asdict(self)}


def parse_pdf(path: str | Path, metadata: DocumentMetadata) -> ParsedPDF:
    """Extract native text and retain metadata for every physical PDF page.

    Empty text is flagged for review: the page might be blank, image-only, or
    otherwise lack extractable text. This is not an OCR or financial-table parser.
    Document-level failures raise PDFParseError; page extraction failures become
    explicit records and warnings, preserving the original page sequence.
    """
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"PDF file does not exist or is not a file: {source}")

    with source.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()

    try:
        document = pymupdf.open(source)
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise PDFParseError(f"Cannot open PDF {source.name}: {exc}") from exc

    with document:
        if not document.is_pdf:
            raise PDFParseError(f"Input is not a PDF: {source.name}")
        if document.needs_pass:
            raise PDFParseError(f"Password-protected PDF is unsupported: {source.name}")
        if document.page_count == 0:
            raise PDFParseError(f"PDF has no pages: {source.name}")

        pages = []
        for index in range(document.page_count):
            pdf_page = index + 1
            error = None
            try:
                page = document.load_page(index)
                text = page.get_text("text", sort=True)
                status: PageStatus = "ok" if text.strip() else "empty_text"
                if status == "empty_text":
                    LOGGER.warning(
                        "%s | PDF page %s: no extractable text; blank or image-only "
                        "page possible; manual review required (OCR is disabled)",
                        metadata.doc_id,
                        pdf_page,
                    )
            except Exception as exc:
                # MuPDF exposes several exception types. Keep failures local to a
                # page and visible, so later physical page numbers stay correct.
                text = ""
                status = "extraction_error"
                error = f"{type(exc).__name__}: {exc}"
                LOGGER.warning(
                    "%s | PDF page %s: extraction failed: %s", metadata.doc_id, pdf_page, error
                )

            pages.append(
                PDFPage(
                    doc_id=metadata.doc_id,
                    issuer=metadata.issuer,
                    fiscal_year=metadata.fiscal_year,
                    language=metadata.language,
                    pdf_page=pdf_page,
                    text=text,
                    status=status,
                    error=error,
                )
            )

        return ParsedPDF(source.name, digest, document.page_count, tuple(pages))


def main(argv: list[str] | None = None) -> int:
    """Parse one local PDF and write JSON without overwriting an existing file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--fiscal-year", required=True, type=int)
    parser.add_argument("--language", default="en")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    try:
        if args.output.exists():
            raise ValueError(f"Output already exists; choose another path: {args.output}")
        metadata = DocumentMetadata(args.doc_id, args.issuer, args.fiscal_year, args.language)
        result = parse_pdf(args.pdf, metadata)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(result.to_dict(), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except (OSError, ValueError) as exc:
        LOGGER.error("%s", exc)
        return 2

    empty = sum(page.status == "empty_text" for page in result.pages)
    failed = sum(page.status == "extraction_error" for page in result.pages)
    print(
        f"Parsed {result.page_count} physical PDF pages; "
        f"{empty} empty-text pages; {failed} extraction errors."
    )
    print(f"SHA256: {result.sha256}\nOutput: {args.output}")
    return 1 if failed or all(page.status != "ok" for page in result.pages) else 0


if __name__ == "__main__":
    raise SystemExit(main())
