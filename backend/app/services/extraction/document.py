"""Turn a PDF into positioned words: embedded text layer first, Tesseract OCR for image-only pages.

Coordinates are PDF points with the origin at the top-left of the page, for both paths, so the field parser
does not care where a word came from. OCR words carry Tesseract's own per-word confidence (0-1);
text-layer words have confidence 1.0 because the characters are exact.
"""
import io
import shutil
import statistics
import time
from dataclasses import dataclass, field

import pymupdf
from PIL import Image

from app.core.config import get_settings


class DocumentUnreadable(Exception):
    """The file cannot be opened/rendered as a PDF. Not retryable: retrying the same bytes will not help."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class OCRUnavailable(Exception):
    """OCR engine missing or crashed. Retryable once the engine is available."""


@dataclass
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    conf: float
    page: int

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def h(self) -> float:
        return self.y1 - self.y0


@dataclass
class Segment:
    """Run of words on one line separated from neighbours by a column-sized gap."""
    words: list[Word]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def x0(self) -> float:
        return self.words[0].x0

    @property
    def x1(self) -> float:
        return self.words[-1].x1

    @property
    def y0(self) -> float:
        return min(w.y0 for w in self.words)

    @property
    def y1(self) -> float:
        return max(w.y1 for w in self.words)

    @property
    def conf(self) -> float:
        return min(w.conf for w in self.words)

    @property
    def height(self) -> float:
        return max(w.h for w in self.words)

    def bbox(self) -> list[float]:
        return [round(self.x0, 1), round(self.y0, 1), round(self.x1, 1), round(self.y1, 1)]


@dataclass
class Line:
    page: int
    words: list[Word]
    segments: list[Segment] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "   ".join(s.text for s in self.segments)

    @property
    def yc(self) -> float:
        return statistics.fmean(w.yc for w in self.words)

    @property
    def y0(self) -> float:
        return min(w.y0 for w in self.words)


@dataclass
class Page:
    number: int  # 1-based
    width: float
    height: float
    method: str  # "text" | "ocr"
    words: list[Word]
    lines: list[Line]
    mean_conf: float | None = None
    duration_ms: int = 0


@dataclass
class DocumentText:
    pages: list[Page]
    page_count: int

    @property
    def methods(self) -> set[str]:
        return {p.method for p in self.pages}

    def all_lines(self) -> list[Line]:
        return [ln for p in self.pages for ln in p.lines]

    def full_text(self) -> str:
        return "\n".join(ln.text for ln in self.all_lines())

    def to_json(self) -> dict:
        return {"page_count": self.page_count, "pages": [
            {"page": p.number, "method": p.method, "mean_confidence": p.mean_conf, "width": p.width,
             "height": p.height, "duration_ms": p.duration_ms, "word_count": len(p.words),
             "lines": [ln.text for ln in p.lines]} for p in self.pages]}


def build_lines(words: list[Word], page: int) -> list[Line]:
    if not words:
        return []
    ordered = sorted(words, key=lambda w: (w.yc, w.x0))
    lines: list[list[Word]] = []
    for w in ordered:
        if lines:
            cur = lines[-1]
            cur_y = statistics.fmean(x.yc for x in cur)
            cur_h = statistics.median(x.h for x in cur)
            if abs(w.yc - cur_y) <= max(2.0, 0.45 * min(cur_h, w.h)):
                cur.append(w)
                continue
        lines.append([w])
    result = []
    for lw in lines:
        lw.sort(key=lambda w: w.x0)
        med_h = statistics.median(w.h for w in lw)
        gap_threshold = max(5.0, 0.62 * med_h)
        segments: list[Segment] = []
        current: list[Word] = [lw[0]]
        for prev, w in zip(lw, lw[1:], strict=False):
            if w.x0 - prev.x1 > gap_threshold:
                segments.append(Segment(current))
                current = [w]
            else:
                current.append(w)
        segments.append(Segment(current))
        result.append(Line(page=page, words=lw, segments=segments))
    return result


def _text_words(page: pymupdf.Page, number: int) -> list[Word]:
    words = []
    for x0, y0, x1, y1, text, *_ in page.get_text("words", sort=True):
        text = text.strip()
        if text:
            words.append(Word(text, x0, y0, x1, y1, 1.0, number))
    return words


def _ocr_words(page: pymupdf.Page, number: int, dpi: int) -> tuple[list[Word], float | None]:
    import pytesseract

    settings = get_settings()
    cmd = settings.tesseract_cmd or shutil.which("tesseract")
    if not cmd:
        raise OCRUnavailable("Tesseract OCR is not installed; scanned pages cannot be read.")
    pytesseract.pytesseract.tesseract_cmd = cmd
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    try:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config="--psm 3",
                                         timeout=60)
    except (pytesseract.TesseractError, RuntimeError, OSError) as exc:
        raise OCRUnavailable(f"OCR engine failed: {exc}") from exc
    scale = 72.0 / dpi
    words, confs = [], []
    for i, text in enumerate(data["text"]):
        text = (text or "").strip()
        conf = float(data["conf"][i])
        if not text or conf < 0:
            continue
        x, y, w, h = (data[k][i] * scale for k in ("left", "top", "width", "height"))
        words.append(Word(text, x, y, x + w, y + h, round(conf / 100.0, 3), number))
        confs.append(conf / 100.0)
    return words, (round(statistics.fmean(confs), 3) if confs else None)


def load_document(path: str) -> DocumentText:
    settings = get_settings()
    try:
        doc = pymupdf.open(path, filetype="pdf")
    except Exception as exc:  # MuPDF raises several error types for damaged files
        raise DocumentUnreadable("PDF_UNREADABLE", f"The file could not be parsed as a PDF ({exc}).") from exc
    with doc:
        if doc.needs_pass:
            raise DocumentUnreadable("PDF_ENCRYPTED", "The PDF is password-protected and cannot be read.")
        if doc.page_count == 0:
            raise DocumentUnreadable("PDF_EMPTY", "The PDF contains no pages.")
        if doc.page_count > settings.max_pages:
            raise DocumentUnreadable("PDF_TOO_MANY_PAGES",
                                     f"The PDF has {doc.page_count} pages; the limit is {settings.max_pages}.")
        pages = []
        for index, page in enumerate(doc):
            number = index + 1
            started = time.perf_counter()
            try:
                words = _text_words(page, number)
            except Exception as exc:
                raise DocumentUnreadable("PDF_PAGE_UNREADABLE", f"Page {number} could not be read ({exc}).") \
                    from exc
            visible = sum(len(w.text) for w in words)
            method, mean_conf = "text", None
            if visible < settings.ocr_min_chars_per_page:
                words, mean_conf = _ocr_words(page, number, settings.ocr_dpi)
                method = "ocr"
            pages.append(Page(number, page.rect.width, page.rect.height, method, words, build_lines(words, number),
                              mean_conf, int((time.perf_counter() - started) * 1000)))
        return DocumentText(pages=pages, page_count=len(pages))


def validate_pdf(path: str) -> dict:
    """Open-and-inspect check used by the FILE_VALIDATION stage."""
    try:
        doc = pymupdf.open(path, filetype="pdf")
    except Exception as exc:
        raise DocumentUnreadable("PDF_UNREADABLE", f"The file could not be parsed as a PDF ({exc}).") from exc
    with doc:
        if doc.needs_pass:
            raise DocumentUnreadable("PDF_ENCRYPTED", "The PDF is password-protected and cannot be read.")
        if doc.page_count == 0:
            raise DocumentUnreadable("PDF_EMPTY", "The PDF contains no pages.")
        if doc.page_count > get_settings().max_pages:
            raise DocumentUnreadable("PDF_TOO_MANY_PAGES", f"The PDF has {doc.page_count} pages.")
        try:
            doc[0].get_text("words")
        except Exception as exc:
            raise DocumentUnreadable("PDF_PAGE_UNREADABLE", f"The first page could not be read ({exc}).") from exc
        meta = doc.metadata or {}
        return {"page_count": doc.page_count, "pdf_version": meta.get("format"),
                "producer": (meta.get("producer") or "")[:80], "is_repaired": bool(doc.is_repaired)}
