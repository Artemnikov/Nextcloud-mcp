import io
from urllib.parse import quote

import httpx
from pypdf import PdfReader, PdfWriter

from .auth import Config


def _safe(path: str) -> str:
    p = path.strip().lstrip("/")
    if any(seg == ".." for seg in p.split("/")):
        raise ValueError(f"Path traversal not allowed: {path!r}")
    return p


def _download(cfg: Config, path: str) -> bytes:
    url = f"{cfg.dav_url}/{quote(_safe(path))}"
    with httpx.Client(auth=cfg.auth, timeout=30.0) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.content


def _upload(cfg: Config, path: str, data: bytes) -> None:
    url = f"{cfg.dav_url}/{quote(_safe(path))}"
    with httpx.Client(auth=cfg.auth, timeout=30.0) as c:
        r = c.put(url, content=data)
        r.raise_for_status()


def register(mcp, cfg: Config) -> None:
    @mcp.tool()
    def nc_pdf_read_text(path: str) -> dict:
        """Extract text from each page of a PDF stored in Nextcloud.

        Returns {path, pages: list[str]} — one string per page. Pages from
        scanned/image-only PDFs come back empty (this is text extraction,
        not OCR).
        """
        reader = PdfReader(io.BytesIO(_download(cfg, path)))
        return {"path": path, "pages": [p.extract_text() or "" for p in reader.pages]}

    @mcp.tool()
    def nc_pdf_merge(paths: list[str], output_path: str) -> dict:
        """Merge multiple PDFs (in the given order) into one, upload to Nextcloud.

        paths: list of Nextcloud paths to PDFs.
        output_path: destination Nextcloud path for the merged PDF.
        """
        writer = PdfWriter()
        total = 0
        for p in paths:
            reader = PdfReader(io.BytesIO(_download(cfg, p)))
            for page in reader.pages:
                writer.add_page(page)
                total += 1
        buf = io.BytesIO()
        writer.write(buf)
        data = buf.getvalue()
        _upload(cfg, output_path, data)
        return {"output_path": output_path, "size": len(data), "pages": total}

    @mcp.tool()
    def nc_pdf_extract(path: str, pages: list[int], output_path: str) -> dict:
        """Extract specific 1-indexed pages from a PDF into a new PDF.

        pages: 1-indexed page numbers in the order they should appear in the
        output. To extract a range, expand it (e.g. [1,2,3,4]). Use this to
        split a PDF: call once per desired output, e.g. extract([1,2]) and
        extract([3,4]) into two files.
        """
        reader = PdfReader(io.BytesIO(_download(cfg, path)))
        n = len(reader.pages)
        writer = PdfWriter()
        for p in pages:
            if not 1 <= p <= n:
                raise ValueError(f"Page {p} out of range 1..{n}")
            writer.add_page(reader.pages[p - 1])
        buf = io.BytesIO()
        writer.write(buf)
        data = buf.getvalue()
        _upload(cfg, output_path, data)
        return {"output_path": output_path, "size": len(data), "pages": len(pages)}
