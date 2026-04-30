from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from pathlib import Path

from .config import ServerConfig
from .loader import load_function


@dataclass
class ValidationResult:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.ok = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def validate_config(config: ServerConfig) -> ValidationResult:
    result = ValidationResult()

    if not config.tools:
        result.add_error("No tools defined in config.")
        return result

    for i, tool in enumerate(config.tools):
        label = f"Tool[{i}] '{tool.name or tool.function}'"
        file_path: Path = tool.resolved_path()

        # 1. File exists
        if not file_path.exists():
            result.add_error(f"{label}: file not found: {file_path}")
            continue

        if not file_path.is_file():
            result.add_error(f"{label}: path is not a file: {file_path}")
            continue

        if file_path.suffix != ".py":
            result.add_error(f"{label}: file must be a .py file, got: {file_path.suffix}")
            continue

        # 2. File imports without errors
        try:
            fn = load_function(file_path, tool.function)
        except SyntaxError as e:
            result.add_error(f"{label}: syntax error in {file_path}: {e}")
            continue
        except ImportError as e:
            result.add_error(f"{label}: import error in {file_path}: {e}")
            continue
        except AttributeError as e:
            result.add_error(f"{label}: {e}")
            continue
        except TypeError as e:
            result.add_error(f"{label}: {e}")
            continue
        except Exception as e:
            result.add_error(f"{label}: unexpected error loading {file_path}: {type(e).__name__}: {e}")
            continue

        # 3. Type hints present (warning only)
        hints = {}
        try:
            hints = fn.__annotations__ if hasattr(fn, "__annotations__") else {}
        except Exception:
            pass

        sig = inspect.signature(fn)
        params_without_hints = [
            p for p in sig.parameters
            if p not in hints and p != "self"
        ]
        if params_without_hints:
            result.add_warning(
                f"{label}: parameters without type hints: {params_without_hints}. "
                "FastMCP may not generate a correct schema."
            )

    return result
