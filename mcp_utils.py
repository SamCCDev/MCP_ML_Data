"""
================================================================================
UTILIDADES DEL CLIENTE MCP — COMPATIBILIDAD CON SDKs DE LLMs
================================================================================

Este módulo concentra la lógica auxiliar que el notebook necesita para hablar
con los SDKs de Google Gemini y OpenRouter. Mantenerla aquí (y no a la vista
en el notebook) deja el flujo principal de la demo limpio y centrado en el
protocolo MCP.

Contenidos:
- `limpiar_schema_para_gemini`: poda recursiva del JSON Schema de las
  herramientas MCP para dejar solo los campos que el `Schema` de Gemini acepta,
  y convierte los `type` a las claves Enum (mayúsculas) que exige el protobuf.
- `es_error_cuota`: heurística para detectar errores de rate limit / cuota
  agotada (HTTP 429 o `RESOURCE_EXHAUSTED`) en excepciones de Gemini o de
  cualquier SDK compatible con OpenAI.
"""

# Campos que el SDK de Gemini acepta oficialmente dentro de su clase Schema.
CAMPOS_SOPORTADOS_GEMINI = {
    "type", "format", "description", "nullable",
    "enum", "properties", "required", "items",
}

# Mapeo de los tipos JSON Schema (minúsculas) a las claves del Enum Protobuf
# que el SDK de Google espera literalmente en mayúsculas.
MAPEO_TIPOS_GEMINI = {
    "object":  "OBJECT",
    "string":  "STRING",
    "integer": "INTEGER",
    "number":  "NUMBER",
    "boolean": "BOOLEAN",
    "array":   "ARRAY",
}


def limpiar_schema_para_gemini(schema: dict) -> dict:
    """Devuelve una copia del JSON Schema con solo los campos soportados por
    Gemini y con los `type` mapeados a las claves Enum del protobuf."""
    if not isinstance(schema, dict):
        return schema

    nuevo_schema = {}
    for k, v in schema.items():
        if k not in CAMPOS_SOPORTADOS_GEMINI:
            continue
        if k == "type" and isinstance(v, str):
            nuevo_schema[k] = MAPEO_TIPOS_GEMINI.get(v.lower(), v)
        elif k == "properties" and isinstance(v, dict):
            nuevo_schema[k] = {pk: limpiar_schema_para_gemini(pv) for pk, pv in v.items()}
        elif k == "items" and isinstance(v, dict):
            nuevo_schema[k] = limpiar_schema_para_gemini(v)
        else:
            nuevo_schema[k] = v
    return nuevo_schema


def es_error_cuota(exc: BaseException) -> bool:
    """Detecta si una excepción corresponde a un rate limit o cuota agotada
    (HTTP 429 / RESOURCE_EXHAUSTED) en cualquier SDK de LLM usado por el
    notebook. Se usa para disparar el auto-fallback Gemini → OpenRouter."""
    if exc is None:
        return False

    codigo = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if codigo == 429:
        return True

    mensaje = str(exc).lower()
    marcadores = (
        "429",
        "rate limit",
        "rate_limit",
        "quota",
        "resource_exhausted",
        "resource exhausted",
        "too many requests",
    )
    return any(m in mensaje for m in marcadores)
