"""Gemini LLM provider — NO silent fallback to mock.  Raises on failure."""

import json
import logging
from typing import Any, Dict, Optional

from backend.app.core.config import settings
from backend.app.services.llm.base import BaseLLMProvider, LLMProviderError, LLMTokenLimitError, with_retries
from backend.app.services.llm.factory import robust_json_parse

logger = logging.getLogger(__name__)


def pydantic_to_gemini_schema(schema_input: Any) -> Any:
    """Convert a Pydantic model class or JSON schema dict into a google.generativeai.protos.Schema.
    Strips unsupported protobuf fields like 'default', 'title', etc., and resolves $defs references.
    """
    if schema_input is None:
        return None
    try:
        from google.generativeai.protos import Schema, Type
    except ImportError:
        return schema_input

    if isinstance(schema_input, Schema):
        return schema_input

    type_map = {
        "string": Type.STRING,
        "number": Type.NUMBER,
        "integer": Type.INTEGER,
        "boolean": Type.BOOLEAN,
        "array": Type.ARRAY,
        "object": Type.OBJECT,
    }

    def convert_node(node: Dict[str, Any]) -> Schema:
        node_type = node.get("type")
        kwargs: Dict[str, Any] = {}

        # Resolve unions or optional fields (anyOf / oneOf with null)
        if not node_type and ("anyOf" in node or "oneOf" in node):
            sub_nodes = [n for n in (node.get("anyOf") or node.get("oneOf", [])) if n.get("type") != "null"]
            if sub_nodes:
                return convert_node(sub_nodes[0])
            node_type = "string"

        if node_type in type_map:
            kwargs["type_"] = type_map[node_type]
        elif isinstance(node_type, list):
            actual = [t for t in node_type if t != "null"]
            t_str = actual[0] if actual else "string"
            kwargs["type_"] = type_map.get(t_str, Type.STRING)
        else:
            kwargs["type_"] = Type.OBJECT

        if "description" in node and node["description"]:
            kwargs["description"] = str(node["description"])
        if "enum" in node and node["enum"]:
            kwargs["enum"] = [str(e) for e in node["enum"]]
        if "required" in node and node["required"]:
            kwargs["required"] = list(node["required"])
        if "items" in node and isinstance(node["items"], dict):
            kwargs["items"] = convert_node(node["items"])
        if "properties" in node and isinstance(node["properties"], dict):
            kwargs["properties"] = {k: convert_node(v) for k, v in node["properties"].items()}

        return Schema(**kwargs)

    raw_schema: Dict[str, Any] = {}
    if hasattr(schema_input, "model_json_schema"):
        raw_schema = schema_input.model_json_schema()
    elif isinstance(schema_input, dict):
        raw_schema = schema_input
    else:
        return schema_input

    defs = raw_schema.get("$defs", {})

    def resolve_refs(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref_key = node["$ref"].split("/")[-1]
                if ref_key in defs:
                    return resolve_refs(defs[ref_key].copy())
            return {k: resolve_refs(v) for k, v in node.items()}
        elif isinstance(node, list):
            return [resolve_refs(item) for item in node]
        return node

    resolved = resolve_refs(raw_schema)
    return convert_node(resolved)


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.LLM_API_KEY or settings.GEMINI_API_KEY
        self.model = model or settings.LLM_MODEL or settings.GEMINI_MODEL or "gemini-3.5-flash-lite"
        if not self.api_key:
            raise LLMProviderError(
                "Gemini API key not configured. Set LLM_API_KEY or GEMINI_API_KEY in backend/.env "
                "or switch LLM_PROVIDER to 'mock'."
            )

    @with_retries
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None) -> str:
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        model_instance = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
        )
        gen_config = genai.GenerationConfig(
            temperature=temperature if temperature is not None else settings.LLM_TEMPERATURE,
            max_output_tokens=max_tokens or settings.LLM_MAX_TOKENS,
        )
        response = model_instance.generate_content(prompt, generation_config=gen_config)
        return response.text

    @with_retries
    def generate_json(self, prompt: str, system_prompt: Optional[str] = None,
                      schema: Optional[Any] = None,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None) -> Dict[str, Any]:
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        model_instance = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
        )
        config_kwargs = {
            "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
            "max_output_tokens": max_tokens or settings.LLM_MAX_TOKENS,
            "response_mime_type": "application/json",
        }
        if schema:
            try:
                gemini_schema = pydantic_to_gemini_schema(schema)
                config_kwargs["response_schema"] = gemini_schema
            except Exception as e:
                logger.warning(
                    f"Could not convert schema to Gemini Protobuf Schema: {e}. "
                    "Structured schema enforcement disabled for this request."
                )
        gen_config = genai.GenerationConfig(**config_kwargs)

        full_prompt = (
            prompt
            + "\n\nCRITICAL: Respond ONLY with a valid JSON object. "
            "No Markdown code block delimiters."
        )
        response = model_instance.generate_content(full_prompt, generation_config=gen_config)

        # Inspect finish reason and token usage metadata
        if response.candidates:
            candidate = response.candidates[0]
            finish_reason = getattr(candidate, "finish_reason", None)
            finish_name = getattr(finish_reason, "name", str(finish_reason))
            usage = getattr(response, "usage_metadata", None)
            token_count = getattr(usage, "candidates_token_count", None) if usage else None

            if finish_reason == 2 or finish_name == "MAX_TOKENS":
                logger.error(
                    f"Gemini response truncated: finish_reason={finish_name}, tokens={token_count or settings.LLM_MAX_TOKENS}"
                )
                raise LLMTokenLimitError(
                    f"Gemini generation reached maximum output token limit ({token_count or settings.LLM_MAX_TOKENS} tokens) "
                    "and was truncated."
                )

        return robust_json_parse(response.text)
