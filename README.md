# nextcloud-mcp

MCP server for Nextcloud. Exposes WebDAV file CRUD plus a typst-based CV
render tool to Claude Code (or any MCP-aware client).

## Install

Requires:
- Python ≥ 3.10
- [`uv`](https://docs.astral.sh/uv/)
- [`typst`](https://github.com/typst/typst) on `PATH` (override with `TYPST_BIN`)

Clone, then resolve deps:

```sh
git clone https://github.com/Artemnikov/Nextcloud-mcp.git
cd Nextcloud-mcp
uv sync
```

## Configure

Create an app password in Nextcloud:
**Personal settings → Security → Devices & sessions → Create new app password**.

Set env vars:

```sh
export NEXTCLOUD_URL=http://your-host:port
export NEXTCLOUD_USER=your-user
export NEXTCLOUD_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx-xxxx
```

## Wire into Claude Code

Add to `~/.claude.json` under `mcpServers`:

```json
"nextcloud": {
  "type": "stdio",
  "command": "/path/to/uv",
  "args": ["run", "--project", "/path/to/Nextcloud-mcp", "nextcloud-mcp"],
  "env": {
    "NEXTCLOUD_URL": "http://your-host:port",
    "NEXTCLOUD_USER": "your-user",
    "NEXTCLOUD_APP_PASSWORD": "xxxx-xxxx-xxxx-xxxx-xxxx"
  }
}
```

## Tools

### Files (WebDAV)

| Tool | Args | Returns |
|---|---|---|
| `nc_list` | `path=""` | `[{name, path, is_dir, size, modified}, ...]` |
| `nc_read` | `path` | `{path, text}` or `{path, base64}` |
| `nc_write` | `path, content` | `{path, size}` |
| `nc_write_binary` | `path, content_b64` | `{path, size}` |
| `nc_delete` | `path` | `{deleted}` |
| `nc_mkdir` | `path` | `{created}` |
| `nc_move` | `src, dst` | `{src, dst}` |

All paths are relative to the user's Nextcloud root. `..` segments are rejected.

### CV / typst

| Tool | Purpose |
|---|---|
| `nc_cv_template_source` | Read the bundled `cv.typ` template (header table + contact table + section helpers). |
| `nc_cv_render` | High-level: takes `name`, `title`, `contacts`, `links`, `body`, `right_to_left`, compiles via the bundled template, uploads PDF to `output_path`. |
| `nc_typst_compile` | Compile arbitrary typst `source` (+ optional `extra_files` for imports), upload PDF. |

## Layout

```
src/nextcloud_mcp/
  __init__.py     # main()
  server.py       # FastMCP("nextcloud-mcp"); init() wires modules
  auth.py         # reads env vars, returns Config + httpx.BasicAuth
  files.py        # WebDAV tools
  cv.py           # typst render tools
  templates/
    cv.typ        # bundled CV template (2-col header, 2x2 contact, accent headings)
```
