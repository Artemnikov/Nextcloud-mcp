import os
import shutil
import subprocess
import tempfile
from importlib import resources
from pathlib import Path

import httpx

from .auth import Config

TYPST_BIN = os.environ.get("TYPST_BIN", "typst")
COMPILE_TIMEOUT = 60


def _template_source() -> str:
    return resources.files("nextcloud_mcp.templates").joinpath("cv.typ").read_text(encoding="utf-8")


def _typst_string(s: str) -> str:
    """Quote a string for safe interpolation into typst source."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _typst_array_of_pairs(rows: list) -> str:
    """((a, b), (c, d)) — typst tuple-of-tuples literal."""
    parts = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ValueError(f"contacts row must be [left, right], got {row!r}")
        parts.append(f"({_typst_string(row[0])}, {_typst_string(row[1])})")
    return "(" + ", ".join(parts) + (",)" if len(parts) == 1 else ")")


def _typst_dict(d: dict) -> str:
    if not d:
        return "(:)"
    parts = [f"{_typst_string(k)}: {_typst_string(v)}" for k, v in d.items()]
    return "(" + ", ".join(parts) + ")"


def _compile_to_pdf(main_typ: str, extra_files: dict[str, str] | None = None) -> tuple[bytes, str]:
    """Write source(s) to a tempdir, run typst, return (pdf_bytes, stderr)."""
    extra_files = extra_files or {}
    with tempfile.TemporaryDirectory(prefix="nc-typst-") as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "main.typ").write_text(main_typ, encoding="utf-8")
        for name, content in extra_files.items():
            (tmp_path / name).write_text(content, encoding="utf-8")
        out_pdf = tmp_path / "out.pdf"
        proc = subprocess.run(
            [TYPST_BIN, "compile", "main.typ", str(out_pdf)],
            cwd=tmp,
            capture_output=True,
            text=True,
            timeout=COMPILE_TIMEOUT,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"typst compile failed:\n{proc.stderr}")
        return out_pdf.read_bytes(), proc.stderr


def _upload_pdf(cfg: Config, dest_path: str, data: bytes) -> None:
    from urllib.parse import quote

    p = dest_path.strip().lstrip("/")
    if any(seg == ".." for seg in p.split("/")):
        raise ValueError(f"Path traversal not allowed: {dest_path!r}")
    url = f"{cfg.dav_url}/{quote(p)}"
    with httpx.Client(auth=cfg.auth, timeout=30.0) as c:
        r = c.put(url, content=data)
        r.raise_for_status()


def register(mcp, cfg: Config) -> None:
    @mcp.tool()
    def nc_cv_template_source() -> str:
        """Return the bundled CV typst template source.

        The template exposes `cv(...)` (header table + contact table + sections)
        and `role(company, title, period)` helpers. Read this to see exactly
        what params and helpers are available before composing a CV body.
        """
        return _template_source()

    @mcp.tool()
    def nc_cv_render(
        name: str,
        title: str,
        contacts: list,
        body: str,
        output_path: str,
        right_to_left: bool = False,
        links: dict | None = None,
    ) -> dict:
        """Render a CV via the bundled typst template, upload the PDF to Nextcloud.

        Args:
          name: full name shown in the header (left cell).
          title: subtitle next to the name (right cell).
          contacts: list of [left, right] string pairs, one per contact row.
          body: typst body content. Use '== Section', '- bullet', '*bold*',
                and '#role[Company][Title][Period]' helpers.
          output_path: destination path in Nextcloud (e.g. 'cv/cv-en.pdf').
          right_to_left: set true for Hebrew/Arabic. Switches direction + font order.
          links: optional dict mapping displayed text -> URL (auto-linkifies in CV).

        Returns {pdf_path, size, warnings}.
        """
        links = links or {}
        rtl_flag = "true" if right_to_left else "false"
        wrapper = (
            '#import "cv.typ": cv, role\n'
            "#show: cv.with(\n"
            f"  name: {_typst_string(name)},\n"
            f"  title: {_typst_string(title)},\n"
            f"  contacts: {_typst_array_of_pairs(contacts)},\n"
            f"  links: {_typst_dict(links)},\n"
            f"  right-to-left: {rtl_flag},\n"
            ")\n\n"
            f"{body}\n"
        )
        pdf_bytes, stderr = _compile_to_pdf(wrapper, {"cv.typ": _template_source()})
        _upload_pdf(cfg, output_path, pdf_bytes)
        return {"pdf_path": output_path, "size": len(pdf_bytes), "warnings": stderr or None}

    @mcp.tool()
    def nc_typst_compile(
        source: str,
        output_path: str,
        extra_files: dict | None = None,
    ) -> dict:
        """Compile arbitrary typst source and upload the resulting PDF to Nextcloud.

        Escape hatch for layouts beyond the bundled CV template.

        Args:
          source: full typst source for the entry file (will be saved as 'main.typ').
          output_path: destination path in Nextcloud.
          extra_files: optional dict of {filename: content} written next to main.typ
                       (use for #import targets, e.g. {"cv.typ": "<source>"}).
        """
        extras = extra_files or {}
        if "main.typ" in extras:
            raise ValueError("'main.typ' is reserved; place entry source in 'source' arg.")
        pdf_bytes, stderr = _compile_to_pdf(source, extras)
        _upload_pdf(cfg, output_path, pdf_bytes)
        return {"pdf_path": output_path, "size": len(pdf_bytes), "warnings": stderr or None}
