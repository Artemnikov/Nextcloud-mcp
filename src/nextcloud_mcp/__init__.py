def main() -> None:
    from .auth import get_config
    from .server import mcp, init

    cfg = get_config()
    init(cfg)
    mcp.run(transport="stdio")
