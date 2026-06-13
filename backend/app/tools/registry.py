from __future__ import annotations
import functools
import inspect
import json
from typing import Any, Callable, TypeVar
from pydantic import BaseModel
from app.core.logging import logger

F = TypeVar("F", bound=Callable)

_registry: dict[str, dict[str, Any]] = {}
_dept_tools: dict[str, list[str]] = {
    "data_extraction": [],
    "quant_analysis": [],
    "qual_analysis": [],
    "visualization": [],
    "report_assembly": [],
}


def tool(departments: list[str] | None = None):
    """Decorator to register a function as an agent tool."""
    def decorator(fn: F) -> F:
        name = fn.__name__
        sig = inspect.signature(fn)
        doc = fn.__doc__ or ""

        # Build JSON schema for params
        params_schema: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
        for param_name, param in sig.parameters.items():
            if param_name in ("db", "self"):
                continue
            annotation = param.annotation
            type_map = {str: "string", int: "integer", float: "number", bool: "boolean", list: "array", dict: "object"}
            json_type = type_map.get(annotation, "string")
            params_schema["properties"][param_name] = {"type": json_type}
            if param.default is inspect.Parameter.empty:
                params_schema["required"].append(param_name)

        _registry[name] = {
            "name": name,
            "description": doc.strip(),
            "function": fn,
            "parameters_schema": params_schema,
            "departments": departments or list(_dept_tools.keys()),
        }

        for dept in (departments or []):
            if dept in _dept_tools:
                _dept_tools[dept].append(name)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        return wrapper  # type: ignore
    return decorator


class ToolRegistry:
    def get_tool(self, name: str) -> dict[str, Any] | None:
        return _registry.get(name)

    def get_tools_for_dept(self, department: str) -> list[dict[str, Any]]:
        names = _dept_tools.get(department, [])
        return [_registry[n] for n in names if n in _registry]

    def call(self, name: str, **kwargs) -> Any:
        tool_def = _registry.get(name)
        if not tool_def:
            raise ValueError(f"Tool not found: {name}")
        fn = tool_def["function"]
        try:
            result = fn(**kwargs)
            logger.info("tool_called", tool=name, success=True)
            return result
        except Exception as e:
            logger.error("tool_error", tool=name, error=str(e))
            raise

    def to_openai_functions(self, department: str) -> list[dict[str, Any]]:
        """Format tools as OpenAI function calling spec."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters_schema"],
                },
            }
            for t in self.get_tools_for_dept(department)
        ]


tool_registry = ToolRegistry()
