from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.tools.function_tool import FunctionTool

from .config import ServerConfig
from .loader import load_function


def build_server(config: ServerConfig) -> FastMCP:
    mcp = FastMCP(name=config.name, version=config.version)

    for tool_cfg in config.tools:
        fn = load_function(tool_cfg.resolved_path(), tool_cfg.function)

        if tool_cfg.name or tool_cfg.description:
            tool = FunctionTool.from_function(
                fn,
                name=tool_cfg.name or None,
                description=tool_cfg.description or None,
            )
            mcp.add_tool(tool)
        else:
            mcp.add_tool(fn)

    return mcp


def run_server(config: ServerConfig) -> None:
    mcp = build_server(config)
    mcp.run(transport=config.transport, host=config.host, port=config.port)
