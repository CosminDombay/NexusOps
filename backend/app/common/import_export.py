from __future__ import annotations

import json
from typing import Any, Literal

import yaml

ExportFormat = Literal["json", "yaml"]


class ImportExportError(ValueError):
    """Raised when an import/export document cannot be parsed."""


def parse_document(content: str, document_format: ExportFormat) -> dict[str, Any]:
    try:
        if document_format == "json":
            parsed = json.loads(content)
        else:
            parsed = yaml.safe_load(content)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ImportExportError(f"Invalid {document_format.upper()} import document") from exc

    if not isinstance(parsed, dict):
        raise ImportExportError("Import document must be an object")
    return parsed


def render_document(payload: dict[str, Any], document_format: ExportFormat) -> str:
    if document_format == "json":
        return json.dumps(payload, indent=2, sort_keys=False) + "\n"
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
