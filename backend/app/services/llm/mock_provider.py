import re
import json
from typing import Dict, Any, Optional
from backend.app.services.llm.base import BaseLLMProvider
from backend.app.services.llm.document_analyzer import (
    analyze_requirements_heuristics,
    generate_srs_heuristics,
    generate_architecture_heuristics,
    generate_schema_heuristics,
    generate_api_heuristics,
    generate_skeleton_heuristics,
    generate_test_cases_heuristics,
    handle_rag_query_heuristics,
)

class MockProvider(BaseLLMProvider):
    """
    Document-driven mock provider. Generates rich, domain-tailored software
    engineering artifacts dynamically from ANY uploaded requirement document.
    """

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None) -> str:
        prompt_lower = prompt.lower()
        if "project context:" in prompt_lower or "user question:" in prompt_lower or "rag" in prompt_lower or "question" in prompt_lower:
            return handle_rag_query_heuristics(prompt)
        return "Req-to-Code Mock Provider: Structured response generated successfully."

    def generate_json(self, prompt: str, system_prompt: Optional[str] = None, schema: Optional[Dict[str, Any]] = None,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None) -> Dict[str, Any]:
        instruction_lower = prompt[:500].lower()
        prompt_lower = prompt.lower()

        # 1. Requirement / Domain Model Extraction (specific match)
        if (
            "build a complete, validated domain model" in instruction_lower
            or "domain model in json" in instruction_lower
            or "extract structured software engineering" in instruction_lower
            or "extract requirements" in instruction_lower
            or "categories to extract" in prompt_lower
        ):
            return analyze_requirements_heuristics(prompt)

        # 2. Backend Skeleton (Check before architecture since architecture may be mentioned)
        if (
            "starter project skeleton" in instruction_lower
            or "fastapi starter project skeleton" in instruction_lower
            or "boilerplate code for main.py" in prompt_lower
            or "backend skeleton" in instruction_lower
        ):
            return generate_skeleton_heuristics(prompt)

        # 3. Test Cases
        if (
            "requirements-driven test suite" in instruction_lower
            or "test suite" in instruction_lower
            or "test cases linked to requirement" in prompt_lower
            or "testcase" in instruction_lower
        ):
            return generate_test_cases_heuristics(prompt)

        # 4. API Documentation
        if (
            "restful openapi" in instruction_lower
            or "openapi documentation" in instruction_lower
            or "api documentation" in instruction_lower
            or "endpoints, http methods" in prompt_lower
        ):
            return generate_api_heuristics(prompt)

        # 5. Database Schema
        if (
            "normalized relational database schema" in instruction_lower
            or "database schema" in instruction_lower
            or "mermaid er diagram" in prompt_lower
            or "sql ddl" in instruction_lower
        ):
            return generate_schema_heuristics(prompt)

        # 6. SRS Generation
        if (
            "ieee 830" in instruction_lower
            or "software requirements specification" in instruction_lower
            or "srs" in instruction_lower
        ):
            return generate_srs_heuristics(prompt)

        # 7. Architecture Design
        if (
            "system architecture" in instruction_lower
            or "optimal system architecture" in instruction_lower
            or "architecture and layered design" in instruction_lower
            or "layered design" in instruction_lower
            or "architecture" in instruction_lower
        ):
            return generate_architecture_heuristics(prompt)

        # Fallback keyword matching over full prompt
        if "skeleton" in prompt_lower:
            return generate_skeleton_heuristics(prompt)
        if "testcase" in prompt_lower or "test case" in prompt_lower:
            return generate_test_cases_heuristics(prompt)
        if "endpoint" in prompt_lower or "api" in prompt_lower:
            return generate_api_heuristics(prompt)
        if "schema" in prompt_lower or "table" in prompt_lower:
            return generate_schema_heuristics(prompt)
        if "srs" in prompt_lower:
            return generate_srs_heuristics(prompt)
        if "architecture" in prompt_lower:
            return generate_architecture_heuristics(prompt)

        # Default fallback JSON derived dynamically
        return analyze_requirements_heuristics(prompt)
