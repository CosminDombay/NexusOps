import re
from dataclasses import dataclass
from typing import Any


VARIABLE_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


class VariableResolutionError(Exception):
    """Raised when a command contains unresolved required variables."""


@dataclass(frozen=True)
class VariableDefinition:
    name: str
    description: str = ""
    default_value: str | None = None
    required: bool = False
    sensitive: bool = False


class VariableResolutionService:
    """Small placeholder resolver for operational templates."""

    def resolve_text(
        self,
        value: str,
        *,
        definitions: list[dict[str, Any]] | None = None,
        variables: dict[str, str] | None = None,
    ) -> str:
        definition_map = {
            str(item.get("name")): item
            for item in definitions or []
            if item.get("name")
        }
        provided = variables or {}
        missing: list[str] = []

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name in provided and provided[name] != "":
                return str(provided[name])
            definition = definition_map.get(name, {})
            default_value = definition.get("default_value")
            if default_value not in (None, ""):
                return str(default_value)
            if definition.get("required", False) or name not in definition_map:
                missing.append(name)
            return ""

        resolved = VARIABLE_PATTERN.sub(replace, value)
        if missing:
            unique = ", ".join(sorted(set(missing)))
            raise VariableResolutionError(f"Missing required template variable(s): {unique}")
        return resolved

    def unresolved_names(self, value: str) -> list[str]:
        return sorted(set(VARIABLE_PATTERN.findall(value)))
