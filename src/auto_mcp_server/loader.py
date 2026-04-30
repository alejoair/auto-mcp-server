from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path


def load_function(file_path: Path, function_name: str) -> Callable:
    module_name = f"_auto_mcp_{file_path.stem}_{abs(hash(str(file_path)))}"

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    if not hasattr(module, function_name):
        raise AttributeError(f"Function '{function_name}' not found in {file_path}")

    fn = getattr(module, function_name)
    if not callable(fn):
        raise TypeError(f"'{function_name}' in {file_path} is not callable")

    return fn
