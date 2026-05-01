import base64
from urllib.parse import quote
from xml.etree import ElementTree as ET

import httpx

from .auth import Config

DAV_NS = "{DAV:}"


def _safe(path: str) -> str:
    """Strip leading slashes and reject path traversal."""
    p = path.strip().lstrip("/")
    if any(seg in ("", "..") for seg in p.split("/") if seg or p):
        # Allow empty (root) but reject any '..' segments anywhere
        for seg in p.split("/"):
            if seg == "..":
                raise ValueError(f"Path traversal not allowed: {path!r}")
    return p


def _url(cfg: Config, path: str) -> str:
    p = _safe(path)
    return f"{cfg.dav_url}/{quote(p)}" if p else cfg.dav_url + "/"


def _client(cfg: Config) -> httpx.Client:
    return httpx.Client(auth=cfg.auth, timeout=30.0, follow_redirects=True)


def _propfind_xml(content: str, base_href: str) -> list[dict]:
    """Parse a PROPFIND multistatus response into entries."""
    root = ET.fromstring(content)
    entries: list[dict] = []
    for resp in root.findall(f"{DAV_NS}response"):
        href = resp.findtext(f"{DAV_NS}href") or ""
        # Skip the entry that represents the listed dir itself
        if href.rstrip("/") == base_href.rstrip("/"):
            continue
        propstat = resp.find(f"{DAV_NS}propstat")
        if propstat is None:
            continue
        prop = propstat.find(f"{DAV_NS}prop")
        if prop is None:
            continue
        is_dir = prop.find(f"{DAV_NS}resourcetype/{DAV_NS}collection") is not None
        size = prop.findtext(f"{DAV_NS}getcontentlength")
        modified = prop.findtext(f"{DAV_NS}getlastmodified")
        # Derive name + path from href: strip the dav prefix
        from urllib.parse import unquote
        decoded = unquote(href)
        # path relative to user root: drop everything up to /files/<user>/
        marker = "/files/"
        idx = decoded.find(marker)
        rel = decoded
        if idx != -1:
            tail = decoded[idx + len(marker):]
            slash = tail.find("/")
            rel = tail[slash + 1:] if slash != -1 else ""
        rel = rel.rstrip("/")
        name = rel.rsplit("/", 1)[-1] if rel else ""
        entries.append({
            "name": name,
            "path": rel,
            "is_dir": is_dir,
            "size": int(size) if size else None,
            "modified": modified,
        })
    return entries


def register(mcp, cfg: Config) -> None:
    @mcp.tool()
    def nc_list(path: str = "") -> list[dict]:
        """List files and folders in a Nextcloud directory.

        path: directory path relative to the user's root (e.g. "" for root, "cv" for /cv).
        Returns a list of {name, path, is_dir, size, modified}.
        """
        url = _url(cfg, path)
        body = (
            '<?xml version="1.0"?>'
            '<d:propfind xmlns:d="DAV:">'
            "<d:prop>"
            "<d:resourcetype/><d:getcontentlength/><d:getlastmodified/>"
            "</d:prop>"
            "</d:propfind>"
        )
        with _client(cfg) as c:
            r = c.request("PROPFIND", url, headers={"Depth": "1", "Content-Type": "application/xml"}, content=body)
            r.raise_for_status()
            from urllib.parse import urlparse
            base_href = urlparse(url).path
            return _propfind_xml(r.text, base_href)

    @mcp.tool()
    def nc_read(path: str) -> dict:
        """Read a file from Nextcloud. Returns {text} for UTF-8 text or {base64} for binary."""
        with _client(cfg) as c:
            r = c.get(_url(cfg, path))
            r.raise_for_status()
            data = r.content
        try:
            return {"path": path, "text": data.decode("utf-8")}
        except UnicodeDecodeError:
            return {"path": path, "base64": base64.b64encode(data).decode("ascii")}

    @mcp.tool()
    def nc_write(path: str, content: str) -> dict:
        """Write UTF-8 text content to a file (creates or overwrites)."""
        data = content.encode("utf-8")
        with _client(cfg) as c:
            r = c.put(_url(cfg, path), content=data)
            r.raise_for_status()
        return {"path": path, "size": len(data)}

    @mcp.tool()
    def nc_write_binary(path: str, content_b64: str) -> dict:
        """Write base64-encoded binary content to a file."""
        data = base64.b64decode(content_b64)
        with _client(cfg) as c:
            r = c.put(_url(cfg, path), content=data)
            r.raise_for_status()
        return {"path": path, "size": len(data)}

    @mcp.tool()
    def nc_delete(path: str) -> dict:
        """Delete a file or folder."""
        with _client(cfg) as c:
            r = c.delete(_url(cfg, path))
            r.raise_for_status()
        return {"deleted": path}

    @mcp.tool()
    def nc_mkdir(path: str) -> dict:
        """Create a folder (MKCOL). Parent must exist."""
        with _client(cfg) as c:
            r = c.request("MKCOL", _url(cfg, path))
            r.raise_for_status()
        return {"created": path}

    @mcp.tool()
    def nc_move(src: str, dst: str) -> dict:
        """Move/rename a file or folder."""
        with _client(cfg) as c:
            r = c.request("MOVE", _url(cfg, src), headers={"Destination": _url(cfg, dst), "Overwrite": "T"})
            r.raise_for_status()
        return {"src": src, "dst": dst}
