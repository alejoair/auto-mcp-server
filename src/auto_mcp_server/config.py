from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator


class ToolConfig(BaseModel):
    name: str | None = None
    description: str | None = None
    file: str
    function: str

    # Resolved absolute path — set by ServerConfig validator
    _resolved_file: Path | None = None

    def resolved_path(self) -> Path:
        if self._resolved_file is None:
            return Path(self.file).resolve()
        return self._resolved_file


class ServerConfig(BaseModel):
    name: str
    version: str = "1.0.0"
    host: str = "127.0.0.1"
    port: int = 8000
    transport: Literal["http", "sse", "streamable-http"] = "http"
    tools: list[ToolConfig]

    # Directory of the config file — set externally before validation or via parse_file
    _config_dir: Path | None = None

    @model_validator(mode="after")
    def resolve_tool_paths(self) -> ServerConfig:
        base = self._config_dir or Path.cwd()
        for tool in self.tools:
            raw = Path(tool.file)
            tool._resolved_file = (base / raw).resolve() if not raw.is_absolute() else raw
        return self


def load_config(config_path: str | Path) -> ServerConfig:
    import json

    path = Path(config_path).resolve()
    with path.open() as f:
        data = json.load(f)

    config = ServerConfig.model_validate(data)
    config._config_dir = path.parent
    # Re-resolve paths now that _config_dir is set
    config.resolve_tool_paths()
    return config
