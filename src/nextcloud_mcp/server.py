from mcp.server.fastmcp import FastMCP

from .auth import Config

mcp = FastMCP("nextcloud-mcp")


def init(cfg: Config) -> None:
    from . import files, cv

    files.register(mcp, cfg)
    cv.register(mcp, cfg)
