# FailureForge Slice 24 - CLI Adapter Load Validation

Slice 24 makes target adapter file loading fail closed at the CLI boundary.

## Purpose

`run-sandbox` and `replay` both accept `--adapter`. A missing, malformed, or
schema-invalid adapter should return the same controlled operator error shape
as other target-source validation failures instead of surfacing a traceback.

## Rules

- missing adapter files return exit code `2`
- malformed adapter JSON returns exit code `2`
- schema-invalid adapters return exit code `2`
- adapter load failures print a concise stderr message
- adapter load failures do not start sandbox execution
- the same adapter load boundary applies to `run-sandbox` and `replay`
