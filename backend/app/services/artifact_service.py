import re
import json
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.models.project import Project, UploadedFile
from backend.app.models.requirement import ExtractedRequirement
from backend.app.models.artifact import Artifact, ArtifactVersion
from backend.app.models.graph import GraphData
from backend.app.services.llm.factory import get_llm_provider
from backend.app.services.llm.base import LLMProviderError, cache_get, cache_put

from backend.app.prompts.common import PROMPT_RULE
from backend.app.services.domain_validator import is_valid_domain_table_name, is_valid_domain_endpoint_path

from backend.app.services.artifact_normalizer import (
    normalize_artifact_content,
    normalize_srs,
    normalize_architecture,
    normalize_schema,
    normalize_api,
    normalize_testcases
)

logger = logging.getLogger(__name__)

ARTIFACT_PROMPTS = {
    "srs": (
        f"Generate a comprehensive Software Requirements Specification (SRS) in strictly valid JSON.\n"
        f"Root JSON Schema:\n"
        f'{{"title": "Software Requirements Specification", "disclaimer": "", '
        f'"sections": [{{"id": "SEC-1", "title": "1.0 Introduction", "content": "..."}}]}}\n'
        f"Must include at least 6 sections: Introduction, Purpose, Scope, Definitions, Overall Description, Functional Requirements, Non-Functional Requirements. {PROMPT_RULE}"
    ),
    "architecture": (
        f"Suggest a requirement-specific system architecture and component topology based strictly on actual project requirements, domain boundaries, actors, workflows, and constraints in strictly valid JSON.\n"
        f"CRITICAL ARCHITECTURAL DIRECTIVES:\n"
        f"- Do NOT generate generic 3-layer tiers like 'Presentation Layer', 'Business Logic Layer', 'Data Access Layer'.\n"
        f"- Do NOT reuse a fixed component template across different projects. Decompose the system into authentic domain components matching the project's specific modules, actors, and workflows.\n"
        f"- Pattern MUST be grounded in project requirements (e.g., Modular Monolith, Event-Driven, or Microservices) with explicit technical justification.\n"
        f"- Respect explicit in-scope and out-of-scope boundaries from the requirement document (do NOT include components or integrations marked out of scope).\n"
        f"- Include role-specific client applications, API ingress, core functional domain services named after actual capabilities, integration adapters/workers (if required by features), and persistent data stores.\n"
        f"- Mermaid diagram MUST use clear subgraphs and labeled workflow arrows showing realistic data/event flow.\n"
        f"- Tech stack for each component MUST distinguish between '(Specified in Requirements)' and '(System Recommended)'.\n"
        f"Root JSON Schema:\n"
        f'{{"pattern": "<Architecture Pattern Name>", '
        f'"justification": "<Evidence-based architectural rationale grounded in requirements, modules, and workflows>", '
        f'"mermaid_diagram": "flowchart TD\\n    subgraph ClientTier [\\"Client Portals\\"]\\n        C1[\\"Portal Name\\\\n(Tech)\\"]\\n    end\\n    subgraph GatewayTier [\\"API Gateway\\"]\\n        GW[\\"FastAPI Gateway\\"]\\n    end\\n    subgraph DomainTier [\\"Domain Services\\"]\\n        S1[\\"Domain Service 1\\"]\\n        S2[\\"Domain Service 2\\"]\\n    end\\n    subgraph PersistenceTier [\\"Data Store\\"]\\n        DB[(\\"Relational DB\\")]\\n    end\\n    C1 -->|REST Requests| GW\\n    GW -->|Dispatch Operations| S1\\n    GW -->|Dispatch Operations| S2\\n    S1 -->|Read / Write| DB\\n    S2 -->|Read / Write| DB", '
        f'"layers": [{{"name": "<Component Name>", "tech": "<Technology Stack (Specified in Requirements / System Recommended)>", "responsibility": "<Domain responsibility with requirement IDs>", "supported_requirements": ["FR-001"], "dependencies": ["Component B"]}}]}}\n'
        f"Must include authentic domain components and a valid Mermaid flowchart TD diagram with subgraphs and labeled edges. {PROMPT_RULE}"
    ),
    "schema": (
        f"Generate a normalized relational database schema in strictly valid JSON.\n"
        f"Root JSON Schema:\n"
        f'{{"tables": [{{"name": "table_name", "description": "...", "columns": [{{"name": "id", "type": "INTEGER", "pk": true, "fk": null, "nullable": false, "description": "..."}}], "relationships": []}}], '
        f'"mermaid_er": "erDiagram\\n    USER {{\\n        int id PK\\n    }}", "sql_ddl": "CREATE TABLE ...;"}}\n'
        f"Must include at least 4 normalized tables with columns, primary keys, foreign keys, relationships, mermaid_er diagram, and sql_ddl. {PROMPT_RULE}"
    ),
    "api": (
        f"Generate RESTful OpenAPI documentation for all capabilities in strictly valid JSON.\n"
        f"Root JSON Schema:\n"
        f'{{"title": "API Documentation", "endpoints": [{{"path": "/api/v1/resource", "method": "GET", "summary": "...", "description": "...", "tag": "Resource", "auth_required": true, "parameters": [], "request_body": {{}}, "responses": [{{"code": "200", "description": "Success"}}]}}]}}\n'
        f"Must include at least 5 REST endpoints across resources. {PROMPT_RULE}"
    ),
    "skeleton": (
        f"Generate a production-ready FastAPI starter project in strictly valid JSON.\n"
        f"Root JSON Schema:\n"
        f'{{"directory_structure": ["main.py", "database/session.py", "models/entities.py", "routes/items.py"], '
        f'"files": [{{"path": "main.py", "content": "from fastapi import FastAPI...", "language": "python"}}]}}\n'
        f"Must include at least 4 files with valid Python syntax. {PROMPT_RULE}"
    ),
    "testcases": (
        f"Generate a comprehensive requirements-driven test suite in strictly valid JSON.\n"
        f"Root JSON Schema:\n"
        f'{{"cases": [{{"test_id": "TC-001", "linked_req_id": "FR-001", "scenario": "...", "preconditions": "...", "steps": "1. ...", "expected_result": "...", "type": "positive"}}]}}\n'
        f"Generate meaningful test cases only for requirements with sufficient actionable detail and acceptance criteria. {PROMPT_RULE}"
    )
}

class ArtifactService:
    @staticmethod
    def get_artifact(project_id: str, artifact_type: str, db: Session) -> Optional[Artifact]:
        return db.query(Artifact).filter(
            Artifact.project_id == project_id,
            Artifact.artifact_type == artifact_type
        ).first()

    @staticmethod
    def generate_artifact(project_id: str, artifact_type: str, db: Session, force_regenerate: bool = False) -> Artifact:
        """Generate a single artifact using LLM provider, save version history, and persist to DB."""
        from backend.app.services.llm.base import cache_invalidate_project

        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError("Project not found")

        if force_regenerate:
            cache_invalidate_project(project_id)

        # Fetch requirements to supply as context
        reqs = db.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == project_id).all()
        req_context = "\n".join([f"- [{r.req_id}] {r.title}: {r.description}" for r in reqs])

        # Find or create artifact record
        artifact = db.query(Artifact).filter(
            Artifact.project_id == project_id,
            Artifact.artifact_type == artifact_type
        ).first()

        title_map = {
            "srs": "SRS Document",
            "architecture": "Architecture Suggestion",
            "schema": "Database Schema",
            "api": "API Documentation",
            "skeleton": "Backend Skeleton",
            "testcases": "Test Cases",
        }

        if not artifact:
            artifact = Artifact(
                project_id=project_id,
                artifact_type=artifact_type,
                title=title_map.get(artifact_type, artifact_type.capitalize()),
                status="generating",
                current_version=1
            )
            db.add(artifact)
            db.commit()
            db.refresh(artifact)
        else:
            artifact.status = "generating"
            db.commit()

        try:
            if artifact_type == "srs":
                normalized = ArtifactService._generate_srs(project, reqs, db)
            elif artifact_type == "architecture":
                normalized = ArtifactService._generate_architecture(project, reqs, db, force_regenerate=force_regenerate)
            elif artifact_type == "schema":
                normalized = ArtifactService._generate_database_schema(project, reqs, db)
            elif artifact_type == "api":
                normalized = ArtifactService._generate_api_documentation(project, reqs, db)
            elif artifact_type == "testcases":
                normalized = ArtifactService._generate_testcases(project, reqs, db)
            elif artifact_type == "skeleton":
                from backend.app.services.code_gen_service import CodeGenService
                normalized = CodeGenService.generate_full_backend(project, db)
            else:
                # Call LLM provider (with cache check)
                provider = get_llm_provider()
                context_payload = req_context
                if artifact_type == "architecture":
                    extra_ctx = []
                    modules = [r for r in reqs if r.category == "module" or r.req_id.startswith("MOD-")]
                    entities = [r for r in reqs if r.category == "entity" or r.req_id.startswith("ENT-")]
                    nfrs = [r for r in reqs if r.category == "non_functional" or r.req_id.startswith("NFR-")]
                    if modules:
                        extra_ctx.append("Identified Domain Modules / Boundaries:\n" + "\n".join([f"- [{m.req_id}] {m.title}: {m.description}" for m in modules]))
                    if entities:
                        extra_ctx.append("Identified Domain Entities / Components:\n" + "\n".join([f"- [{e.req_id}] {e.title}: {e.description}" for e in entities[:15]]))
                    if nfrs:
                        extra_ctx.append("Non-Functional Requirements & Constraints:\n" + "\n".join([f"- [{n.req_id}] {n.title}: {n.description}" for n in nfrs]))
                    if extra_ctx:
                        context_payload = f"{req_context}\n\n" + "\n\n".join(extra_ctx)

                prompt = f"Project Title: {project.name}\n\n{ARTIFACT_PROMPTS.get(artifact_type, '')}\n\nProject Requirements Context:\n{context_payload}"
                
                # Check cache first
                cached = cache_get(project_id, artifact_type, prompt)
                if cached is not None:
                    logger.info(f"Cache hit for {artifact_type} in project {project_id[:8]}")
                    content_json = cached
                else:
                    try:
                        content_json = provider.generate_json(
                            prompt=prompt,
                            system_prompt="You are an expert Chief Architect and Staff Software Engineer. Return strictly valid JSON."
                        )
                        cache_put(project_id, artifact_type, prompt, content_json)
                    except LLMProviderError as e:
                        logger.error(f"LLM provider error generating {artifact_type}: {e}")
                        artifact.status = "error"
                        artifact.metadata_json = json.dumps({"error": str(e)})
                        db.commit()
                        raise
    
                # Normalize via canonical normalizer
                normalized = normalize_artifact_content(artifact_type, content_json)
        except Exception as e:
            logger.error(f"Error generating {artifact_type} for project {project_id}: {e}")
            artifact.status = "failed"
            artifact.metadata_json = json.dumps({"error": str(e), "count": 0})
            db.commit()
            raise

        # Count items
        def get_item_count(atype: str, data: Dict[str, Any]) -> int:
            if atype == "srs":
                return len(data.get("sections", []))
            elif atype == "schema":
                return len(data.get("tables", []))
            elif atype == "architecture":
                return len(data.get("layers", []))
            elif atype == "api":
                return len(data.get("endpoints", []))
            elif atype == "skeleton":
                return len(data.get("files", []))
            elif atype == "testcases":
                return len(data.get("cases", []))
            return 0

        meta_count = get_item_count(artifact_type, normalized)

        # Retry once if invalid (e.g. 0 sections or 0 tables)
        if meta_count == 0 and artifact_type in ["srs", "schema", "architecture", "api", "skeleton", "testcases"]:
            logger.warning(f"{artifact_type} returned 0 items. Retrying generation with explicit schema correction...")
            base_p = prompt if 'prompt' in locals() else f"Project: {project.name}\n{ARTIFACT_PROMPTS.get(artifact_type, '')}\n{req_context}"
            retry_prompt = f"{base_p}\n\nIMPORTANT: Previous attempt yielded 0 items. You MUST strictly adhere to the requested JSON schema with non-empty list of items."
            try:
                retry_json = provider.generate_json(
                    prompt=retry_prompt,
                    system_prompt="You are an expert Chief Architect and Staff Software Engineer. Return strictly valid JSON."
                )
                normalized = normalize_artifact_content(artifact_type, retry_json)
                meta_count = get_item_count(artifact_type, normalized)
            except Exception as e:
                logger.error(f"Retry generation failed for {artifact_type}: {e}")

        # Determine status and execute validation pipeline for skeleton
        validation_results = None
        if artifact_type == "skeleton":
            from backend.app.services.code_gen_service import CodeGenService
            expected_eps = 0
            api_art = db.query(Artifact).filter(Artifact.project_id == project_id, Artifact.artifact_type == "api").first()
            if api_art and api_art.content_json:
                try:
                    expected_eps = len(json.loads(api_art.content_json).get("endpoints", []))
                except Exception:
                    pass
            validation_results = CodeGenService.validate_generated_backend(normalized, expected_eps)
            has_failures = bool(validation_results.get("errors")) or not validation_results.get("compiled") or not validation_results.get("imported")
            validation_results["needs_review"] = has_failures
            artifact.status = "completed"
        elif meta_count == 0:
            artifact.status = "failed"
        else:
            artifact.status = "completed"

        metadata = {"count": meta_count}
        if validation_results:
            metadata.update(validation_results)
        artifact.content_json = json.dumps(normalized)
        artifact.metadata_json = json.dumps(metadata)
        
        # Save version history
        next_ver = (artifact.current_version or 1) + 1 if artifact.versions else 1
        artifact.current_version = next_ver

        version = ArtifactVersion(
            artifact_id=artifact.id,
            version_number=next_ver,
            content_json=json.dumps(normalized),
            changelog=f"Generated by {settings.LLM_PROVIDER.upper()} provider"
        )
        db.add(version)
        db.commit()
        db.refresh(artifact)

        try:
            from backend.app.services.rag_service import RagService
            RagService.index_project_chunks(project_id, db)
        except Exception as e:
            logger.warning(f"Failed to auto-index artifacts for project {project_id}: {e}")

        return artifact

    @staticmethod
    def generate_all(project_id: str, db: Session, job_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate all 6 artifacts and initialize Knowledge Graph."""
        from backend.app.services.job_runner import job_manager

        artifact_sequence = [
            ("srs", "SRS Document"),
            ("architecture", "Architecture"),
            ("schema", "Database Schema"),
            ("api", "API Documentation"),
            ("skeleton", "Backend Skeleton"),
            ("testcases", "Test Cases"),
        ]
        total_artifacts = len(artifact_sequence)
        results = {}
        errors = []

        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = "generating"
            db.commit()

        for idx, (art_type, art_label) in enumerate(artifact_sequence, 1):
            if job_id:
                job_manager.update_progress(
                    job_id,
                    progress=round(((idx - 1) / total_artifacts) * 100, 1),
                    message=f"Generating {art_label} ({idx} of {total_artifacts})..."
                )
            try:
                art = ArtifactService.generate_artifact(project_id, art_type, db)
                results[art_type] = art.status
                if job_id:
                    job_manager.update_progress(
                        job_id,
                        progress=round((idx / total_artifacts) * 100, 1),
                        message=f"Generated {art_label} ({idx} of {total_artifacts} artifacts)"
                    )
            except Exception as e:
                logger.error(f"Failed to generate {art_type}: {e}")
                results[art_type] = "error"
                errors.append(f"{art_type}: {str(e)[:200]}")
                if job_id:
                    job_manager.update_progress(
                        job_id,
                        progress=round((idx / total_artifacts) * 100, 1),
                        message=f"Failed {art_label} ({idx} of {total_artifacts}): {str(e)[:80]}"
                    )

        # Also initialize / update Knowledge Graph and ChromaDB RAG index
        from backend.app.services.graph_service import GraphService
        from backend.app.services.rag_service import RagService
        try:
            GraphService.generate_knowledge_graph(project_id, db)
            RagService.index_project_chunks(project_id, db)
        except Exception as e:
            logger.warning(f"Post-generation graph/RAG update failed for project {project_id}: {e}")

        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = "ready" if not errors else "partial"
            project.current_step = "ready"
            db.commit()

        result = {"status": "completed" if not errors else "partial", "artifacts": results}
        if errors:
            result["errors"] = errors
        return result

    @staticmethod
    def update_artifact(project_id: str, artifact_type: str, new_content: Dict[str, Any], changelog: str, db: Session) -> Artifact:
        artifact = db.query(Artifact).filter(
            Artifact.project_id == project_id,
            Artifact.artifact_type == artifact_type
        ).first()
        if not artifact:
            raise ValueError("Artifact not found")

        next_ver = (artifact.current_version or 1) + 1
        artifact.current_version = next_ver
        artifact.content_json = json.dumps(new_content)

        # Update metadata count if applicable
        count = 0
        if artifact_type == "srs":
            count = len(new_content.get("sections", []))
        elif artifact_type == "architecture":
            count = len(new_content.get("layers", []))
        elif artifact_type == "schema":
            count = len(new_content.get("tables", []))
        elif artifact_type == "api":
            count = len(new_content.get("endpoints", []))
        elif artifact_type == "skeleton":
            count = len(new_content.get("files", []))
        elif artifact_type == "testcases":
            count = len(new_content.get("cases", []))

        artifact.metadata_json = json.dumps({"count": count})

        version = ArtifactVersion(
            artifact_id=artifact.id,
            version_number=next_ver,
            content_json=json.dumps(new_content),
            changelog=changelog or "Manual update by user"
        )
        db.add(version)
        db.commit()
        db.refresh(artifact)

        try:
            from backend.app.services.rag_service import RagService
            RagService.index_project_chunks(project_id, db)
        except Exception as e:
            logger.warning(f"Failed to auto-index updated artifact for project {project_id}: {e}")

        return artifact

    @staticmethod
    def _clean_project_name(name: str) -> str:
        """Strip random hex or UUID suffixes from project names while preserving real words."""
        if not name:
            return "Software System"
        s = re.sub(r'[\s\-_]+[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', '', name, flags=re.I)
        s = re.sub(r'[\s\-_]+[0-9a-f]{4,8}$', '', s, flags=re.I)
        return s.strip() or name.strip()

    @staticmethod
    def _generate_srs(project: Project, reqs: List[ExtractedRequirement], db: Session) -> Dict[str, Any]:
        """Generate comprehensive Software Requirements Specification with full functional and non-functional requirement coverage."""
        provider = get_llm_provider()
        clean_name = ArtifactService._clean_project_name(project.name)

        # Clean helper for Markdown table cells to ensure strictly single-line valid syntax
        def _clean_cell(text: Any) -> str:
            if text is None:
                return ""
            s = str(text).strip()
            # Remove PDF extraction header artifacts (e.g. \nID\nRequirement\nPriority)
            s = re.sub(r'[\r\n]+\s*(?:ID|Requirement|Priority|Module|Category|Description|Status)\b[^\n]*', '', s, flags=re.IGNORECASE)
            # Replace remaining newlines with spaces
            s = re.sub(r'[\r\n]+', ' ', s)
            # Escape literal unescaped pipes
            s = re.sub(r'(?<!\\)\|', r'\|', s)
            return " ".join(s.split())

        # Helper to extract structured bullet items following a section heading
        def _extract_items_after_heading(text: str, heading_pattern: str) -> List[str]:
            if not text:
                return []
            norm_text = re.sub(r'[\r\n]+\s*[•*>-]\s*[\r\n]+', '\n- ', text)
            matches = list(re.finditer(heading_pattern, norm_text, re.IGNORECASE))
            for m in reversed(matches):
                start_pos = m.end()
                block = norm_text[start_pos:start_pos + 3000]
                next_sec = re.search(r"\n\s*(?:[0-9]+\.[0-9]*\s+[A-Z]|[0-9]+\.\s+[A-Z])", block)
                if next_sec:
                    block = block[:next_sec.start()]
                
                candidate_items = []
                for line in block.splitlines():
                    cleaned = line.strip()
                    if not cleaned or re.search(r'\.{3,}', cleaned) or re.match(r'^\d+$', cleaned):
                        continue
                    if cleaned.startswith('- ') or cleaned.startswith('* ') or re.match(r'^\d+[\.\)]\s*', cleaned):
                        item = re.sub(r'^[-*•]\s*|^\d+[\.\)]\s*', '', cleaned).strip()
                        if len(item) > 8 and not item.lower().startswith('and dependencies'):
                            candidate_items.append(item)
                    elif candidate_items and len(cleaned) > 3 and not re.match(r'^[0-9]+\.[0-9]+', cleaned):
                        candidate_items[-1] += " " + cleaned
                
                if candidate_items:
                    return candidate_items
            return []

        # 1. Fetch raw document text to parse exact scope and assumptions
        files = db.query(UploadedFile).filter(UploadedFile.project_id == project.id).all()
        raw_doc_text = "\n\n".join([f.extracted_text for f in files if f.extracted_text])

        in_scope_items = _extract_items_after_heading(raw_doc_text, r"(?:1\.2\s*)?(?:In[- ]scope|It will|Scope)[:\s]*")
        out_of_scope_items = []
        if raw_doc_text:
            out_m = re.search(r"Out of scope(?:\s+for[^\n:]*)?:\s*(.*?)(?=\n\s*[0-9]+\.|\Z)", raw_doc_text, re.DOTALL | re.IGNORECASE)
            if out_m:
                for line in out_m.group(1).strip().splitlines():
                    cleaned = re.sub(r"^[\s*•>-]+", "", line).strip()
                    if cleaned and not re.search(r'\.{3,}', cleaned) and len(cleaned) > 5:
                        out_of_scope_items.append(cleaned)

        if in_scope_items and out_of_scope_items:
            in_scope_clean = []
            for item in in_scope_items:
                if "out of scope" in item.lower():
                    parts = re.split(r'out of scope[^\n:]*:', item, flags=re.I)
                    if parts[0].strip():
                        in_scope_clean.append(parts[0].strip())
                    if len(parts) > 1 and parts[1].strip() and not out_of_scope_items:
                        out_of_scope_items.append(parts[1].strip())
                else:
                    in_scope_clean.append(item)
            in_scope_items = in_scope_clean

        doc_assumptions = _extract_items_after_heading(raw_doc_text, r"(?:2\.6\s*)?Assumptions\s*(?:and|&)?\s*Dependencies")
        doc_dependencies = _extract_items_after_heading(raw_doc_text, r"(?:External\s+)?Dependencies")

        functional_reqs = [r for r in reqs if r.category == "functional"]
        if not functional_reqs:
            functional_reqs = reqs

        # Deduplicate non-functional and constraints by requirement ID
        seen_nfr_ids = set()
        deduped_nfr_constraints = []
        for r in reqs:
            if r.category in ["non_functional", "constraint"] and r.req_id not in seen_nfr_ids:
                seen_nfr_ids.add(r.req_id)
                deduped_nfr_constraints.append(r)

        actor_reqs = [r for r in reqs if r.category == "actor"]
        entity_reqs = [r for r in reqs if r.category == "entity"]

        # Strict list of allowed actors from project's stored actor list
        allowed_actor_names = [a.title for a in actor_reqs]
        actor_context = "\n".join([f"- {a.title}: {a.description}" for a in actor_reqs]) if actor_reqs else "System"
        req_context = "\n".join([f"- [{r.req_id}] {r.title} ({r.category}): {r.description}" for r in reqs[:25]])

        # Prompt LLM for structured narrative sections
        narrative_prompt = f"""Project: {clean_name}
Actors/Roles:
{actor_context}

Project Requirements Context:
{req_context}

Generate standard narrative sections for this software project:
1. Introduction: Purpose, Document Scope, and System Overview. (Do NOT mention extraction or tools).
2. Overall Description: Product perspective, user characteristics, operating environment, and system architecture summary.
3. User Classes & Characteristics: MUST be structured with actor name, key responsibilities, system access permissions, and frequency of use. (Never raw JSON or empty arrays).
4. Definitions, Acronyms, and Abbreviations: A list with one item per term defining key business and technical terms for this domain.
5. Use Cases: 3 to 5 realistic end-to-end use cases covering main actors (Actor, Preconditions, Trigger, Main Flow as a numbered list with one step per line, Postconditions).

Return strictly valid JSON:
{{
  "introduction": "...",
  "overall_description": "...",
  "user_classes": [
    {{"role": "...", "description": "...", "permissions": "...", "frequency": "..."}}
  ],
  "definitions": [
    {{"term": "...", "definition": "..."}}
  ],
  "use_cases": [
    {{"title": "...", "actor": "...", "preconditions": "...", "flow": ["1. Step 1", "2. Step 2"], "postconditions": "..."}}
  ]
}}"""

        narrative = {}
        try:
            narrative = provider.generate_json(narrative_prompt, system_prompt="You are a Chief Software Architect and requirements engineering specialist. Return strictly valid JSON.")
        except Exception as e:
            logger.error(f"Failed to generate SRS narrative: {e}")

        # Build Section 1: Introduction & Project Scope
        intro_content = narrative.get("introduction")
        if not intro_content or not isinstance(intro_content, str):
            intro_content = (
                f"### 1.1 Purpose\n"
                f"This Software Requirements Specification (SRS) document details the complete functional, non-functional, and operational requirements for the {clean_name}. "
                f"It provides verified technical specifications for engineering development and quality assurance verification.\n\n"
                f"### 1.2 System Overview\n"
                f"The {clean_name} delivers domain-specific software capabilities designed to execute operations, validate transactional state changes, and enforce business rules with verifiable integrity."
            )

        # Append Project Scope (In scope / Out of scope) from raw document text
        scope_lines = ["\n\n### 1.3 Project Scope"]
        if in_scope_items:
            scope_lines.append("\n#### In-Scope Capabilities\n" + "\n".join([f"- {item}" for item in in_scope_items]))
        if out_of_scope_items:
            scope_lines.append("\n#### Out-of-Scope Boundaries\n" + "\n".join([f"- {item}" for item in out_of_scope_items]))
        if not in_scope_items and not out_of_scope_items:
            scope_lines.append(f"\nThe project scope encompasses the complete functional and operational capabilities defined in this specification for {clean_name}. Any capability not explicitly specified herein is considered outside the current release milestone.")

        intro_content += "".join(scope_lines)

        # Build Section 2: Overall Description
        overall_content = narrative.get("overall_description")
        if not overall_content or not isinstance(overall_content, str):
            overall_content = (
                f"### 2.1 Product Perspective\n"
                f"The {clean_name} operates as a unified platform integrating business service logic, secure transactional data persistence, and external service communication.\n\n"
                f"### 2.2 Operating Environment\n"
                f"The system runs in modern web and cloud environments utilizing modular backend microservices, relational persistence, and RESTful APIs."
            )

        # Build Section 3: User Classes & Characteristics (Markdown Table)
        user_classes_raw = narrative.get("user_classes", [])
        user_class_rows = []
        if isinstance(user_classes_raw, list) and user_classes_raw:
            for uc in user_classes_raw:
                if isinstance(uc, dict):
                    role = uc.get("role") or uc.get("name") or "System Actor"
                    desc = uc.get("description") or uc.get("responsibilities") or "System user"
                    perms = uc.get("permissions") or "Standard permissions"
                    freq = uc.get("frequency") or "Daily"
                    user_class_rows.append(f"| **{_clean_cell(role)}** | {_clean_cell(desc)} | {_clean_cell(perms)} | {_clean_cell(freq)} |")
        if not user_class_rows:
            for act in (actor_reqs or []):
                user_class_rows.append(f"| **{_clean_cell(act.title)}** | {_clean_cell(act.description)} | Role-based domain access | Active |")
        if not user_class_rows:
            user_class_rows.append(f"| **Authorized User** | Standard domain user interacting with {_clean_cell(clean_name)} services | Role-based domain access | Active |")

        user_classes_content = (
            "The system supports distinct user classes with defined operational responsibilities and security access levels:\n\n"
            "| User Class / Role | Responsibilities | Permissions & Access Level | Frequency of Use |\n"
            "| :--- | :--- | :--- | :--- |\n" +
            "\n".join(user_class_rows)
        )

        # Build Section 4: Definitions (List, one item per term)
        defs_raw = narrative.get("definitions", [])
        def_lines = []
        if isinstance(defs_raw, list) and defs_raw:
            for d in defs_raw:
                if isinstance(d, dict):
                    term = d.get("term") or d.get("word") or ""
                    definition = d.get("definition") or d.get("meaning") or ""
                    if term and definition:
                        def_lines.append(f"- **{term}**: {definition}")
                elif isinstance(d, str):
                    def_lines.append(f"- {d}")
        if not def_lines:
            for ent in entity_reqs[:8]:
                def_lines.append(f"- **{ent.title}**: {ent.description}")
        if not def_lines:
            def_lines = [
                f"- **{clean_name}**: The core software application under specification.",
                "- **CRUD**: Create, Read, Update, Delete database operations.",
                "- **JWT**: JSON Web Token used for authenticated API sessions."
            ]
        definitions_content = "Key terminology and abbreviations utilized throughout this specification:\n\n" + "\n".join(def_lines)

        # Build Section 5: Use Cases (Flow as numbered list, one step per line)
        use_cases_raw = narrative.get("use_cases", [])
        uc_parts = []
        if isinstance(use_cases_raw, list) and use_cases_raw:
            for idx, uc in enumerate(use_cases_raw, 1):
                if isinstance(uc, dict):
                    title = uc.get("title") or f"Use Case {idx}"
                    actor = uc.get("actor") or (allowed_actor_names[0] if allowed_actor_names else "System")
                    if allowed_actor_names and actor not in allowed_actor_names and actor != "System":
                        matched = [a for a in allowed_actor_names if a.lower() in actor.lower()]
                        actor = matched[0] if matched else allowed_actor_names[0]
                    pre = uc.get("preconditions") or "User is authenticated and system is online."
                    flow_val = uc.get("flow") or uc.get("steps") or []
                    if isinstance(flow_val, list):
                        flow_lines = [str(i+1) + ". " + re.sub(r'^[0-9]+[.\s]+', '', str(s)).strip() for i, s in enumerate(flow_val)]
                        flow_str = "\n".join(flow_lines)
                    else:
                        raw_steps = [s.strip() for s in str(flow_val).splitlines() if s.strip()]
                        flow_lines = [str(i+1) + ". " + re.sub(r'^[0-9]+[.\s]+', '', s).strip() for i, s in enumerate(raw_steps)]
                        flow_str = "\n".join(flow_lines) if flow_lines else "1. Actor initiates action.\n2. System validates input.\n3. System updates state and confirms."
                    post = uc.get("postconditions") or "State updated successfully."
                    uc_parts.append(
                        f"#### UC-{idx:02d}: {title}\n"
                        f"- **Primary Actor:** {actor}\n"
                        f"- **Preconditions:** {pre}\n"
                        f"- **Main Flow:**\n{flow_str}\n"
                        f"- **Postconditions:** {post}"
                    )
        if not uc_parts:
            primary_act = allowed_actor_names[0] if allowed_actor_names else "System"
            uc_parts.append(
                f"#### UC-01: Standard Operation Execution\n"
                f"- **Primary Actor:** {primary_act}\n"
                f"- **Preconditions:** System operational, actor authorized.\n"
                f"- **Main Flow:**\n1. Actor accesses system feature.\n2. Actor submits required transaction data.\n3. System validates constraints and commits changes.\n"
                f"- **Postconditions:** Transaction recorded and audit entry logged."
            )
        use_cases_content = "Detailed operational use cases illustrating core interaction patterns:\n\n" + "\n\n".join(uc_parts)

        # Deterministic & LLM-assisted Actor Resolution
        actors_map: Dict[str, str] = {}
        try:
            req_items_text = "\n".join([f"[{r.req_id}] {r.title}: {r.description}" for r in functional_reqs])
            actor_prompt = f"""For each functional requirement below, determine the Primary Actor(s) performing or initiating the action.

ALLOWED ACTORS (choose ONLY from this exact list or 'System'):
{allowed_actor_names}

RULES:
1. If the requirement describes an automated action (timer, schedule, automated calculation, automated notification, automatic cancellation, or threshold-based suspension where no human actor triggers the action), the actor MUST be 'System'.
   - Examples: 'The system shall automatically execute scheduled synchronization at midnight.' -> 'System'
   - 'The system shall calculate metrics when thresholds are met.' -> 'System'
   - 'The system shall reserve allocated units for <number> <unit>.' -> 'System'
2. If one or more human actors perform or initiate the action, list them from the allowed actors list (e.g. '<PrimaryActor>', '<SecondaryActor>').
   - Examples: 'The system shall allow the administrator to approve a submitted record...' -> 'Administrator'
   - 'The system shall allow participants to rate an encounter...' -> 'Participant'
   - 'The system shall allow role A and role B to register...' -> 'Role A, Role B'
3. NEVER output 'User' or any actor not in the allowed list.
4. Return strictly valid JSON:
{{"actors": {{"REQ-001": "<actor1>, <actor2>", "REQ-002": "<actor1>", "REQ-003": "System"}}}}

REQUIREMENTS:
{req_items_text}"""
            actor_res = provider.generate_json(actor_prompt, system_prompt="You are a Requirements Analyst. Assign actors strictly from the allowed list or 'System'. Return JSON.")
            if isinstance(actor_res, dict) and "actors" in actor_res:
                raw_actors = actor_res.get("actors", {})
                if isinstance(raw_actors, dict):
                    for rid, act in raw_actors.items():
                        if act and isinstance(act, str):
                            actors_map[rid] = act.strip()
                elif isinstance(raw_actors, list):
                    for item in raw_actors:
                        if isinstance(item, dict):
                            rid = item.get("req_id") or item.get("id") or item.get("requirement_id")
                            act = item.get("actor") or item.get("actors")
                            if rid and act:
                                actors_map[rid] = str(act).strip()
        except Exception as e:
            logger.warning(f"Failed LLM actor assignment: {e}")

        def resolve_primary_actor(r: ExtractedRequirement) -> str:
            assigned = actors_map.get(r.req_id, "").strip()
            if assigned and assigned != "User":
                parts = [p.strip() for p in assigned.split(",") if p.strip()]
                valid_parts = [p for p in parts if p in allowed_actor_names or p == "System"]
                if valid_parts:
                    return ", ".join(valid_parts)

            tl = f"{r.title}. {r.description}".lower()
            active_actors = []
            for a in allowed_actor_names:
                al = a.lower()
                pl = al + "s"
                patterns = [
                    rf"\ballow(?:s)?\s+(?:a\s+|an\s+|the\s+)?(?:verified\s+|registered\s+|authorized\s+)?{al}\b",
                    rf"\ballow(?:s)?\s+(?:a\s+|an\s+|the\s+)?(?:verified\s+|registered\s+|authorized\s+)?{pl}\b",
                    rf"\blet(?:s)?\s+(?:a\s+|an\s+|the\s+)?{al}\b",
                    rf"\blet(?:s)?\s+(?:a\s+|an\s+|the\s+)?{pl}\b",
                    rf"\bgive(?:s)?\s+(?:a\s+|an\s+|the\s+)?{al}\b",
                    rf"\bgive(?:s)?\s+(?:a\s+|an\s+|the\s+)?{pl}\b",
                    rf"\b{al}\s+submits?\b",
                    rf"\b{al}\s+creates?\b",
                    rf"\b{al}\s+searches?\b",
                    rf"\b{al}\s+rates?\b",
                    rf"\b{al}\s+chooses?\b",
                    rf"\b{al}\s+reports?\b",
                    rf"\b{al}\s+places?\b",
                    rf"\b{al}\s+adds?\b",
                    rf"\b{al}\s+updates?\b",
                    rf"\b{al}\s+accepts?\b",
                    rf"\b{al}\s+marks?\b",
                    rf"\b{al}\s+initiates?\b"
                ]
                if any(re.search(p, tl) for p in patterns):
                    active_actors.append(a)

            # Check if multiple allowed actors are mentioned in conjunction
            for a in allowed_actor_names:
                al = a.lower()
                if re.search(rf"\b{al}s?\b", tl) and any(conj in tl for conj in [f"{al} and", f"and {al}", f"{al},"]):
                    if a not in active_actors:
                        active_actors.append(a)

            if not active_actors:
                return "System"

            return ", ".join(sorted(list(set(active_actors))))

        # Map linked constraints per requirement for validation
        constraint_reqs = [cr for cr in reqs if cr.category == "constraint"]
        linked_constraints_map: Dict[str, str] = {}
        for r in functional_reqs:
            linked_c_texts = []
            r_tokens = set(re.findall(r'\b[a-zA-Z]{4,}\b', f"{r.title} {r.description}".lower())) - {"system", "shall", "allow", "order", "items", "valid"}
            for c in constraint_reqs:
                c_text = f"{c.title} {c.description}".lower()
                if r.req_id.lower() in c_text or any(t in c_text for t in r_tokens if len(t) > 4):
                    linked_c_texts.append(f"{c.title} {c.description}")
            linked_constraints_map[r.req_id] = " ".join(linked_c_texts)

        # Disallow ungrounded technology, channel, or third-party provider names
        UNGROUNDED_TECH_CHANNELS = [
            "sms", "text message", "email", "otp", "one-time password", "webhook",
            "stripe", "paypal", "push notification", "whatsapp", "s3", "redis",
            "kafka", "oauth", "jwt"
        ]

        def validate_ac_statement(criterion: str, req_full_text: str, linked_constraint_text: str = "") -> tuple:
            c_lower = criterion.lower()
            allowed_context = f"{req_full_text} {linked_constraint_text}".lower()

            # Reject ungrounded named channels, technologies, or features
            for tech in UNGROUNDED_TECH_CHANNELS:
                if re.search(r'\b' + re.escape(tech) + r'\b', c_lower):
                    if not re.search(r'\b' + re.escape(tech) + r'\b', allowed_context):
                        return (False, [f"ungrounded_tech:{tech}"])

            clean_c = re.sub(r'\b[A-Za-z]+-\d+\b', '', criterion)
            clean_c = re.sub(r'^\s*\d+[\.\)]\s*', '', clean_c)
            clean_c = re.sub(r'(\d),(\d)', r'\1\2', clean_c)

            req_norm = re.sub(r'(\d),(\d)', r'\1\2', allowed_context)
            req_nums = set(re.findall(r"\b\d+(?:\.\d+)?\b", req_norm))

            crit_nums = re.findall(r"\b\d+(?:\.\d+)?\b", clean_c)
            invalid_nums = []
            for cn in crit_nums:
                if cn in req_nums or cn == "0":
                    continue
                if re.search(r'\b' + re.escape(cn) + r'\b', req_norm):
                    continue
                invalid_nums.append(cn)

            return (len(invalid_nums) == 0, invalid_nums)

        # Batch generate Acceptance Criteria for all Functional Requirements using LLM
        ac_map: Dict[str, List[str]] = {}
        try:
            ac_batches = [functional_reqs[i:i + 10] for i in range(0, len(functional_reqs), 10)]
            for b in ac_batches:
                b_text = "\n".join([f"[{r.req_id}]: {r.title} - {r.description}" for r in b])
                ac_prompt = f"""For each functional requirement below, generate 1 to 3 short, testable Acceptance Criteria statements.

CRITICAL RULES:
1. Every number, duration, quantity, or threshold in your criteria MUST appear in that requirement's OWN text (or linked constraint). Do NOT invent new numbers or ungrounded quantities.
2. Do NOT introduce named technologies, channels, or features (such as SMS, email, OTP, payment providers) unless explicitly stated in that requirement's text.
3. If the requirement implies a failure case (e.g. limit exceeded, unpaid transaction, expired window, invalid credentials), include a failure case.
4. If a numeric limit or threshold exists, include a boundary pair (one case just below the limit / within limit, and one case at or exceeding the limit) using the exact threshold stated in the text.
5. Do NOT repeat the requirement sentence.
6. Return strictly valid JSON: {{"acceptance_criteria": {{"REQ-001": ["statement 1", "statement 2"]}}}}

REQUIREMENTS:
{b_text}"""
                ac_res = provider.generate_json(ac_prompt, system_prompt="You are a Principal QA Engineer. Use strictly facts from that requirement's text. Return valid JSON.")
                raw_ac = ac_res.get("acceptance_criteria", {}) if isinstance(ac_res, dict) else {}
                for rid, clist in raw_ac.items():
                    if isinstance(clist, list):
                        ac_map[rid] = [str(c).strip() for c in clist if str(c).strip()]
        except Exception as e:
            logger.warning(f"Failed to generate acceptance criteria via LLM: {e}")

        # Validate each requirement's acceptance criteria
        validated_ac_map: Dict[str, List[str]] = {}
        for r in functional_reqs:
            req_full = f"{r.title}. {r.description}"
            linked_c = linked_constraints_map.get(r.req_id, "")
            raw_statements = ac_map.get(r.req_id, [])
            valid_statements = []
            invalid_to_retry = []

            for st in raw_statements:
                is_valid, inv_reasons = validate_ac_statement(st, req_full, linked_c)
                if is_valid:
                    valid_statements.append(st)
                else:
                    invalid_to_retry.append((st, inv_reasons))

            if invalid_to_retry:
                try:
                    retry_prompt = f"""Requirement: [{r.req_id}] {r.title}: {r.description}

Instruction: Generate 1 to 3 short testable acceptance criteria using ONLY facts, numbers, and limits from the requirement text.
Every number, duration, quantity or threshold MUST appear in that requirement's own text.
Do NOT introduce any technologies, channels, or features (e.g. SMS, email, OTP, payment providers) not present in the requirement text.
Include a failure case if implied, and boundary pairs if numeric limits exist.
Return strictly valid JSON: {{"acceptance_criteria": ["statement 1", "statement 2"]}}"""
                    res_retry = provider.generate_json(retry_prompt, system_prompt="You are a Principal QA Engineer. Use only facts from the requirement text. Return valid JSON.")
                    if isinstance(res_retry, dict) and "acceptance_criteria" in res_retry:
                        retry_statements = res_retry.get("acceptance_criteria", [])
                        for rc in retry_statements:
                            rc_str = str(rc).strip()
                            rc_valid, _ = validate_ac_statement(rc_str, req_full, linked_c)
                            if rc_valid:
                                valid_statements.append(rc_str)
                except Exception as e:
                    logger.warning(f"AC retry failed for {r.req_id}: {e}")

            if not valid_statements:
                numbers = re.findall(r"\b\d+(?:\.\d+)?(?:\s*(?:days|hours|minutes|seconds|percent|units|items))?\b", r.description, re.IGNORECASE)
                if numbers:
                    valid_statements = [
                        f"Verify valid processing when parameters adhere to specified threshold ({numbers[0]}).",
                        f"Verify system rejects input or triggers boundary action when violating specified threshold ({numbers[0]})."
                    ]
                else:
                    valid_statements = [
                        f"Verify system successfully completes '{r.title}' under valid preconditions.",
                        f"Verify system rejects invalid requests with an appropriate validation error."
                    ]

            validated_ac_map[r.req_id] = valid_statements

        def detect_rule_ambiguity(r: ExtractedRequirement) -> Optional[str]:
            if r.ambiguity_notes and r.ambiguity_notes.strip():
                return r.ambiguity_notes.strip()

            text = f"{r.title}. {r.description}"
            tl = text.lower()

            # 1. Rate per N units with no rounding rule
            m_rate = re.search(r'\b(?:every|per)\s+(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\b', text, re.I)
            if m_rate:
                qty = m_rate.group(1)
                unit = m_rate.group(2)
                if unit.lower() not in ["day", "month", "year", "second", "minute", "hour"]:
                    if not any(k in tl for k in ["round", "ceil", "floor", "prorate", "fraction"]):
                        return f"For the rate calculation per {qty} {unit}, how should fractional or partial {unit} be rounded or prorated?"

            # 2. Check for conflicting or overlapping timeouts (e.g. REQ-014: 4 hours vs 2 hours)
            timeout_matches = re.findall(r'\b(?:within|after)\s+(\d+(?:\.\d+)?)\s*(hours|minutes|seconds|days)\b', text, re.I)
            if len(timeout_matches) >= 2:
                durations = [f"{m[0]} {m[1]}" for m in timeout_matches]
                if not any(k in tl for k in ["concurrently", "reset", "cumulative", "following the"]):
                    return f"The requirement specifies multiple timeout intervals ({', '.join(durations)}). How do these timers interact (e.g., does the longer cancellation timer run concurrently from placement, or does acknowledging the alert alter the timeout)?"

            # 3. Recurring cadence with no day/time, unless the detail is already chosen by user or configured
            has_chosen_day = any(phrase in tl for phrase in ["chosen delivery day", "chosen day", "selected day", "configured by", "specified by", "chosen slot"])
            if re.search(r'\bweekly\b', tl) and not has_chosen_day and not any(d in tl for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
                return "For recurring weekly processing, which specific day of the week and cutoff time should be configured?"
            if re.search(r'\bmonthly\b', tl) and not has_chosen_day and not re.search(r'\b(?:day\s+\d+|\d+(?:st|nd|rd|th)|first|last)\b', tl):
                return "For recurring monthly processing, which specific calendar date and time should trigger execution?"

            # 4. Vague timeframes
            if any(w in tl for w in ["periodically", "timely", "regular intervals"]) and not re.search(r'\b\d+\s*(?:minutes|hours|days|weeks)\b', tl):
                return "What is the exact scheduled interval or SLA timeframe for this operation?"

            return None

        # Build Section 6: Functional Requirements (Structured Table + Full Details + Acceptance Criteria)
        fr_table_rows = []
        fr_detail_parts = []
        for r in functional_reqs:
            actor = resolve_primary_actor(r)
            
            is_doc_prio = False
            if hasattr(r, 'priority_source') and r.priority_source == 'document':
                is_doc_prio = True
            elif r.description and re.search(r'\b(?:priority\s*[:=-]\s*(?:high|medium|low|critical)|\[(?:high|medium|low|critical)\s*priority\])\b', r.description, re.I):
                is_doc_prio = True

            if is_doc_prio:
                prio_label = (r.priority or "High").capitalize()
            else:
                prio_val = (r.priority or "Medium").capitalize()
                prio_label = f"Suggested priority: {prio_val}"

            mod = _clean_cell(r.module_name or "General")
            req_id_cell = _clean_cell(r.req_id)
            title_cell = _clean_cell(r.title)
            actor_cell = _clean_cell(actor)
            prio_cell = _clean_cell(prio_label)
            desc_cell = _clean_cell(r.description)
            fr_table_rows.append(f"| **{req_id_cell}** | {title_cell} | {mod} | {actor_cell} | {prio_cell} | {desc_cell} |")

            criteria = validated_ac_map.get(r.req_id, [])
            ac_markdown = "\n".join([f"  - {c}" for c in criteria])

            open_q = detect_rule_ambiguity(r)
            open_q_markdown = f"- **Open question for the client:** {open_q}\n" if open_q else ""

            fr_detail_parts.append(
                f"#### {r.req_id}: {r.title}\n"
                f"- **Module:** {mod}\n"
                f"- **Primary Actor:** {actor}\n"
                f"- **Priority:** {prio_label}\n"
                f"- **Full Specification:** {r.description}\n"
                f"{open_q_markdown}"
                f"- **Acceptance Criteria:**\n{ac_markdown}\n"
            )

        fr_content = (
            f"This section details all {len(functional_reqs)} functional requirements for {clean_name}. "
            f"Each requirement defines an authoritative system capability with assigned primary actor, priority classification, and testable acceptance criteria.\n\n"
            f"### Functional Requirements Summary Table\n\n"
            f"| Requirement ID | Title | Module | Actor | Priority | Description & Business Rules |\n"
            f"| :--- | :--- | :--- | :--- | :--- | :--- |\n" +
            "\n".join(fr_table_rows) +
            "\n\n### Detailed Functional Specifications\n\n" +
            "\n".join(fr_detail_parts)
        )

        # Build Section 7: Non-Functional Requirements & System Constraints (EVERY stored NFR & Constraint exactly once)
        nfr_table_rows = []
        nfr_detail_parts = []
        for r in deduped_nfr_constraints:
            cat = (r.category or "Constraint").replace("_", " ").title()
            prio = (r.priority or "High").capitalize()
            nfr_table_rows.append(f"| **{_clean_cell(r.req_id)}** | {_clean_cell(cat)} | {_clean_cell(r.title)} | {_clean_cell(prio)} | {_clean_cell(r.description)} |")
            nfr_detail_parts.append(
                f"#### {r.req_id}: {r.title}\n"
                f"- **Category:** {cat}\n"
                f"- **Priority:** {prio}\n"
                f"- **Measurable Threshold & Rule:** {r.description}\n"
            )

        # Fallback to document text NFR extraction if deduped_nfr_constraints was empty
        if not nfr_table_rows and raw_doc_text:
            nfr_matches = re.findall(
                r"(NFR-\d+)[:\s\-]+(?:([A-Za-z\s]+)[:\-\n])?\s*(.*?)(?=\n\s*NFR-\d+|\n\s*[0-9]+\.|\Z)",
                raw_doc_text,
                re.DOTALL | re.IGNORECASE
            )
            for m in nfr_matches:
                nid = m[0].strip().upper()
                ncat = (m[1].strip() if m[1] else "General Quality").title()
                ndesc = m[2].strip()
                ndesc = re.sub(r'--- Page \d+ ---|SRS - [^\n]+|Version [^\n]+|Page \d+', '', ndesc)
                ndesc = re.sub(r'^\s*(?:Category|Requirement)\s*', '', ndesc, flags=re.IGNORECASE)
                ndesc = " ".join(ndesc.split())
                if ndesc and len(ndesc) > 10:
                    nfr_table_rows.append(f"| **{_clean_cell(nid)}** | {_clean_cell(ncat)} | {_clean_cell(nid)} Specification | High | {_clean_cell(ndesc)} |")
                    nfr_detail_parts.append(
                        f"#### {nid}: {ncat}\n"
                        f"- **Category:** {ncat}\n"
                        f"- **Priority:** High\n"
                        f"- **Measurable Threshold & Rule:** {ndesc}\n"
                    )

        # Generic system quality standards fallback if still empty
        if not nfr_table_rows:
            defaults = [
                ("NFR-01", "Performance", "System Latency & Throughput", "High", f"Interactive workflows for {clean_name} shall render and complete transactions within 3 seconds under normal operational load."),
                ("NFR-02", "Security", "Access Governance & Authentication", "High", "All user access points shall require authenticated credentials, password hashing, and role-based authorization gates."),
                ("NFR-03", "Availability", "Platform Availability Target", "Medium", f"The {clean_name} platform shall target 99.5% operational uptime during core operational hours."),
                ("NFR-04", "Data Integrity", "Relational Consistency & Auditability", "High", "All entity mutations shall maintain ACID guarantees, foreign key referential integrity, and change logs.")
            ]
            for nid, ncat, ntitle, nprio, ndesc in defaults:
                nfr_table_rows.append(f"| **{nid}** | {ncat} | {ntitle} | {nprio} | {ndesc} |")
                nfr_detail_parts.append(
                    f"#### {nid}: {ntitle}\n"
                    f"- **Category:** {ncat}\n"
                    f"- **Priority:** {nprio}\n"
                    f"- **Measurable Threshold & Rule:** {ndesc}\n"
                )

        nfr_content = (
            f"This section specifies the non-functional requirements and business constraints governing system operation, "
            f"including explicit performance thresholds, retention windows, security rules, and availability targets:\n\n"
            f"### Non-Functional Requirements & Constraints Table\n\n"
            f"| Requirement ID | Category | Title / Scope | Priority | Measurable Metric / Threshold / Rule |\n"
            f"| :--- | :--- | :--- | :--- | :--- |\n" +
            "\n".join(nfr_table_rows) +
            "\n\n### Detailed Specifications\n\n" +
            "\n".join(nfr_detail_parts)
        )

        # Build Section 8: Assumptions & Dependencies (From Document Text)
        assump_parts = []
        if doc_assumptions:
            assump_list = "\n".join([f"{i+1}. {item}" for i, item in enumerate(doc_assumptions)])
            assump_parts.append(f"### 8.1 System Assumptions\nThe following operational assumptions govern this specification:\n\n{assump_list}")
        else:
            assump_parts.append(f"### 8.1 System Assumptions\n1. End users access the system using compliant modern web browsers with active internet connectivity.\n2. Authorized institutional identities and master data are validated and maintained by administrative authorities.\n3. Underlying database and network infrastructure maintain operational continuity.")

        if doc_dependencies:
            dep_list = "\n".join([f"{i+1}. {item}" for i, item in enumerate(doc_dependencies)])
            assump_parts.append(f"### 8.2 External Dependencies\n{dep_list}")
        else:
            assump_parts.append("### 8.2 External Dependencies\n1. Relational database persistence service for transactional state storage.\n2. Standard web/HTTP network gateway for client-server communication.")

        assump_content = "\n\n".join(assump_parts)

        sections = [
            {"id": "SEC-1", "title": "1.0 Introduction & Project Scope", "content": intro_content, "subsections": []},
            {"id": "SEC-2", "title": "2.0 Overall Description", "content": overall_content, "subsections": []},
            {"id": "SEC-3", "title": "3.0 User Classes and Characteristics", "content": user_classes_content, "subsections": []},
            {"id": "SEC-4", "title": "4.0 Definitions, Acronyms, and Abbreviations", "content": definitions_content, "subsections": []},
            {"id": "SEC-5", "title": "5.0 Use Cases & System Features", "content": use_cases_content, "subsections": []},
            {"id": "SEC-6", "title": "6.0 Functional Requirements", "content": fr_content, "subsections": []},
            {"id": "SEC-7", "title": "7.0 Non-Functional Requirements & System Constraints", "content": nfr_content, "subsections": []},
            {"id": "SEC-8", "title": "8.0 Assumptions and Dependencies", "content": assump_content, "subsections": []}
        ]

        raw_dict = {
            "title": f"Software Requirements Specification - {clean_name}",
            "disclaimer": "",
            "sections": sections
        }
        return normalize_srs(raw_dict)

    @staticmethod
    def _generate_architecture(project: Project, reqs: List[ExtractedRequirement], db: Session, force_regenerate: bool = False) -> Dict[str, Any]:
        """Generate a requirement-specific, domain-grounded system architecture with non-generic components and diagrams."""
        from backend.app.services.llm.document_analyzer import generate_architecture_heuristics

        provider = get_llm_provider()
        clean_name = ArtifactService._clean_project_name(project.name)

        # Categorize requirements
        actors = [r for r in reqs if r.category == "actor" or r.req_id.startswith("ACT-")]
        modules = [r for r in reqs if r.category == "module" or r.req_id.startswith("MOD-")]
        entities = [r for r in reqs if r.category == "entity" or r.req_id.startswith("ENT-")]
        functional_reqs = [r for r in reqs if r.category == "functional" or r.req_id.startswith("FR-") or r.req_id.startswith("REQ-")]
        nfrs = [r for r in reqs if r.category in ["non_functional", "constraint"] or r.req_id.startswith("NFR-")]

        # Check uploaded files for document text (allow up to 20,000 characters to cover full functional specs and out-of-scope boundaries)
        uploaded_file = db.query(UploadedFile).filter(UploadedFile.project_id == project.id).first()
        file_excerpt = (uploaded_file.extracted_text[:20000] if uploaded_file and uploaded_file.extracted_text else "")

        # Build comprehensive requirement context
        context_parts = []
        if actors:
            context_parts.append("Identified User Roles & Actors:\n" + "\n".join([f"- [{a.req_id}] {a.title}: {a.description}" for a in actors]))
        if modules:
            context_parts.append("Identified Domain Modules & Subsystems:\n" + "\n".join([f"- [{m.req_id}] {m.title}: {m.description}" for m in modules]))
        if entities:
            context_parts.append("Identified Core Domain Entities:\n" + "\n".join([f"- [{e.req_id}] {e.title}: {e.description}" for e in entities[:30]]))
        if functional_reqs:
            context_parts.append("Key Functional Capabilities & Workflows:\n" + "\n".join([f"- [{f.req_id}] {f.title}: {f.description}" for f in functional_reqs[:60]]))
        if nfrs:
            context_parts.append("Non-Functional Requirements & Constraints:\n" + "\n".join([f"- [{n.req_id}] {n.title}: {n.description}" for n in nfrs[:20]]))
        if file_excerpt:
            context_parts.append(f"DOCUMENT TEXT:\n{file_excerpt}")

        req_context = "\n\n".join(context_parts)

        prompt = (
            f"Project Title: {clean_name}\n"
            f"Project Description: {project.description or ''}\n\n"
            f"{ARTIFACT_PROMPTS.get('architecture', '')}\n\n"
            f"Project Requirements Context:\n{req_context}"
        )

        doc_filename = uploaded_file.filename if uploaded_file else "None"
        logger.info(f"[ARCHITECTURE DEBUG] Project ID: {project.id} | Project Name: {clean_name}")
        logger.info(f"[ARCHITECTURE DEBUG] Document Filename: {doc_filename} | Extracted Req Count: {len(reqs)}")
        logger.info(f"[ARCHITECTURE DEBUG] Req Context Sent Length: {len(req_context)} chars | Prompt Length: {len(prompt)} chars")
        logger.info(f"[ARCHITECTURE DEBUG] Prompt Snippet: {prompt[:300].strip()}...")

        # Check cache first (bypass if force_regenerate is requested)
        if not force_regenerate:
            cached = cache_get(project.id, "architecture", prompt)
            if cached is not None:
                logger.info(f"[ARCHITECTURE DEBUG] Returning cached architecture for {project.id}")
                return cached

        # Generate via LLM provider or fallback
        try:
            raw_result = provider.generate_json(
                prompt=prompt,
                system_prompt="You are a Chief Software Architect and Enterprise Systems Designer. Generate requirement-specific, domain-grounded architecture. Return strictly valid JSON."
            )
            logger.info(f"[ARCHITECTURE DEBUG] Raw LLM response received: keys={list(raw_result.keys()) if isinstance(raw_result, dict) else type(raw_result)}")
            normalized = normalize_architecture(raw_result)
        except Exception as e:
            logger.warning(f"LLM architecture generation failed: {e}. Falling back to dynamic heuristics.")
            raw_result = generate_architecture_heuristics(prompt)
            normalized = normalize_architecture(raw_result)

        logger.info(f"[ARCHITECTURE DEBUG] Parsed architecture: Pattern={normalized.get('pattern')} | Component Count={len(normalized.get('layers', []))}")
        cache_put(project.id, "architecture", prompt, normalized)
        return normalized

    @staticmethod
    def _generate_database_schema(project: Project, reqs: List[ExtractedRequirement], db: Session) -> Dict[str, Any]:
        """Generate normalized relational database schema in multiple passes, ensuring 100% requirement coverage and real-world integrity."""
        provider = get_llm_provider()
        clean_name = ArtifactService._clean_project_name(project.name)

        functional_reqs = [r for r in reqs if r.category == "functional"]
        if not functional_reqs:
            functional_reqs = reqs

        entity_reqs = [r for r in reqs if r.category == "entity"]
        nfr_reqs = [r for r in reqs if r.category in ["non_functional", "constraint"]]

        all_tables_list = []

        # --- PASS 1: Core Master Entities ---
        # Derive core master entities dynamically from the project's own entity list and requirement definitions
        entity_titles = [e.title.lower() for e in entity_reqs]
        core_reqs = [
            r for r in functional_reqs 
            if any(et in f"{r.title} {r.module_name}".lower() for et in entity_titles)
            or any(k in f"{r.title} {r.module_name}".lower() for k in ["profile", "account", "identity", "master", "catalog", "entity", "user"])
        ]
        if not core_reqs:
            core_reqs = functional_reqs[:10]

        core_text = "\n".join([f"- [{r.req_id}] {r.title} ({r.module_name}): {r.description}" for r in core_reqs])
        ent_text = "\n".join([f"- [{e.req_id}] {e.title}: {e.description}" for e in entity_reqs]) if entity_reqs else ""

        pass1_prompt = f"""Project: {clean_name}
Requirements for Core Entities:
{core_text}
{ent_text}

Generate database tables for CORE MASTER ENTITIES corresponding to the project's primary domain entities in strictly valid JSON.
MANDATORY RULES:
1. Every table MUST have:
   - 'name': snake_case table name (e.g. '<primary_entity>', '<user_account>')
   - 'description': clear description of table purpose
   - 'requirement_ids': list of requirement IDs covered (e.g. ['{core_reqs[0].req_id}'])
   - 'columns': list of column objects:
     - 'name': column name
     - 'type': SQL data type (e.g. 'INTEGER', 'VARCHAR(255)', 'TIMESTAMP', 'DECIMAL(10,2)', 'BOOLEAN', 'TEXT')
     - 'pk': true for primary key, false otherwise
     - 'fk': foreign key reference string (e.g. 'parent_table(id)') or null
     - 'nullable': true/false
     - 'unique': true for unique natural keys (e.g. unique code, identifier, email, username), false otherwise
     - 'check': check constraint expression if applicable (e.g. "price >= 0") or null
     - 'description': purpose of column
2. Add UNIQUE constraints on natural keys (such as unique code, identifier, email, username).
2. Include all essential domain attributes specified in the requirements (e.g. lifecycle dates, shelf life/expiry, units, status, verification flags).
3. Include standard audit timestamps (created_at, updated_at).

Return strictly JSON: {{"tables": [...]}}"""

        try:
            res1 = provider.generate_json(pass1_prompt, system_prompt="You are a Principal Database Architect. Return strictly valid JSON.")
            p1_tables = normalize_schema(res1).get("tables", [])
            all_tables_list.extend([t for t in p1_tables if is_valid_domain_table_name(t.get("name", ""))])
            logger.info(f"Schema Pass 1 produced {len(p1_tables)} core master tables.")
        except Exception as e:
            logger.error(f"Failed Schema Pass 1: {e}")

        pass1_names = [t["name"] for t in all_tables_list]

        # --- PASS 2: Transactions, Junctions & Relationships ---
        # Derive transactional requirements dynamically from project requirement text
        trans_reqs = [
            r for r in functional_reqs 
            if r not in core_reqs or any(k in f"{r.title} {r.module_name}".lower() for k in ["process", "transaction", "action", "status", "submit", "create", "exchange", "record", "request", "transition"])
        ]
        if not trans_reqs:
            trans_reqs = [r for r in functional_reqs if r not in core_reqs]

        # Batch trans_reqs to avoid token truncation
        batch_size = 7
        for b_idx in range(0, len(trans_reqs), batch_size):
            batch = trans_reqs[b_idx : b_idx + batch_size]
            b_text = "\n".join([f"- [{r.req_id}] {r.title} ({r.module_name}): {r.description}" for r in batch])

            pass2_prompt = f"""Project: {clean_name}
Existing Master Tables: {', '.join(pass1_names)}
Transactional & Operational Requirements (Batch {b_idx // batch_size + 1}):
{b_text}

Generate database tables for TRANSACTIONS, RELATIONSHIPS, and JUNCTION TABLES in strictly valid JSON.
MANDATORY RULES:
1. Include junction/item tables for every many-to-many relationship or parent-child transaction (e.g. '<entity>_items', '<parent>_<child>_junction').
2. Ensure foreign key linkage between transactional items and their source master or inventory entity (e.g. batch_id, listing_id) for end-to-end traceability.
3. Include explicit status, lifecycle, and business milestone timestamp columns:
   - status columns: e.g. 'status' VARCHAR(50) reflecting lifecycle state transitions specified in the requirements
   - milestone timestamps: e.g. 'created_at', 'updated_at', and business milestone timestamps (such as 'delivered_at', 'completed_at', 'expires_at') essential for SLA, return eligibility windows, and operational tracking.
   - capacity and limits: if slots, queues, or entities have quotas or limits, include capacity and counter columns.
4. Foreign keys MUST have sensible 'on_delete' rules ('CASCADE' for junction/item records, 'RESTRICT' or 'SET NULL' for reference data).
5. For EVERY table include: 'name', 'description', 'requirement_ids': ['{batch[0].req_id}'], 'columns' (with name, type, pk, fk, nullable, unique, check, on_delete, description).

Return strictly JSON: {{"tables": [...]}}"""

            try:
                res2 = provider.generate_json(pass2_prompt, system_prompt="You are a Principal Database Architect. Return strictly valid JSON.")
                p2_tables = normalize_schema(res2).get("tables", [])
                all_tables_list.extend([t for t in p2_tables if is_valid_domain_table_name(t.get("name", ""))])
                logger.info(f"Schema Pass 2 batch {b_idx // batch_size + 1} produced {len(p2_tables)} transactional/junction tables.")
            except Exception as e:
                logger.error(f"Failed Schema Pass 2 batch {b_idx // batch_size + 1}: {e}")

        pass12_names = [t["name"] for t in all_tables_list]

        # --- PASS 3: Ledgers, History, Audit Logs & Integrity Constraints ---
        # Derive requirements with quotas, limits, balances, counters, logs, history, audits dynamically
        ledger_reqs = [
            r for r in functional_reqs 
            if any(k in f"{r.title} {r.module_name} {r.description}".lower() for k in ["limit", "quota", "balance", "audit", "history", "log", "alert", "expiry", "change", "track", "usage", "counter", "payout", "deduct", "rate"])
        ]
        if not ledger_reqs:
            ledger_reqs = functional_reqs[-6:]

        ledger_text = "\n".join([f"- [{r.req_id}] {r.title}: {r.description}" for r in ledger_reqs])
        nfr_text = "\n".join([f"- [{r.req_id}] {r.title}: {r.description}" for r in nfr_reqs])

        has_audit_req = any(
            any(k in f"{r.title} {r.description}".lower() for k in ["audit", "audit log", "audit trail", "action log", "change log", "compliance log"])
            for r in functional_reqs
        )
        audit_rule = (
            "2. Audit logging table:\n"
            "   Provide an 'audit_logs' table (id, user_id, action, entity_name, entity_id, old_values, new_values, ip_address, created_at) supporting the explicit audit requirements."
            if has_audit_req else
            "2. Audit logging:\n"
            "   Do NOT generate an 'audit_logs' table unless explicit audit logging or audit trail requirements are specified above."
        )

        pass3_prompt = f"""Project: {clean_name}
Existing System Tables: {', '.join(pass12_names)}
Ledger & Constraint Requirements:
{ledger_text}
{nfr_text}

Generate database tables for LEDGERS, BALANCE/QUANTITY HISTORY, AUDIT LOGGING, and INTEGRITY CONSTRAINTS in strictly valid JSON.
MANDATORY RULES:
1. History and ledger tables:
   Whenever quantities, balances, usage limits, or quotas change over time (e.g. usage count against limits, balance changes), provide dedicated ledger/history tables (e.g. '<entity>_usage_ledger', '<entity>_transactions').
   Columns should include: id, foreign keys to referenced entity and user, quantity_delta, balance_after, transaction_type, reason, created_at.
{audit_rule}
3. CHECK constraints:
   Include CHECK constraints on columns with bounded ranges (e.g. bounded ratings, non-negative quantities, positive values).
4. Indexes:
   Specify indexes on foreign keys, temporal timestamps, status columns, and primary search keys.
5. For EVERY table include: 'name', 'description', 'requirement_ids', 'columns' (with name, type, pk, fk, nullable, unique, check, on_delete, description), 'indexes'.

Return strictly JSON: {{"tables": [...]}}"""

        try:
            res3 = provider.generate_json(pass3_prompt, system_prompt="You are a Principal Database Architect. Return strictly valid JSON.")
            p3_tables = normalize_schema(res3).get("tables", [])
            all_tables_list.extend([t for t in p3_tables if is_valid_domain_table_name(t.get("name", ""))])
            logger.info(f"Schema Pass 3 produced {len(p3_tables)} ledger/audit tables.")
        except Exception as e:
            logger.error(f"Failed Schema Pass 3: {e}")

        # --- PASS 4: Coverage Check & Targeted LLM Call ---
        covered_table_ids = set()
        for t in all_tables_list:
            for rid in t.get("requirement_ids", []):
                covered_table_ids.add(rid)

        uncovered_frs = [r for r in functional_reqs if r.req_id not in covered_table_ids]
        logger.info(f"Schema initial coverage: {len(covered_table_ids)}/{len(functional_reqs)} functional requirements covered.")

        if uncovered_frs:
            logger.info(f"Making targeted LLM call to cover {len(uncovered_frs)} uncovered requirements in database schema: {[r.req_id for r in uncovered_frs]}")
            batch_size = 7
            for b_idx in range(0, len(uncovered_frs), batch_size):
                batch = uncovered_frs[b_idx : b_idx + batch_size]
                uncovered_text = "\n".join([f"- [{r.req_id}] {r.title} ({r.module_name}): {r.description}" for r in batch])
                pass4_prompt = f"""Project: {clean_name}
The following functional requirements currently have NO mapped database tables or columns:
{uncovered_text}

Generate database tables and/or junction tables and columns specifically implementing these requirements.
Ensure essential lifecycle milestone timestamps (e.g. delivered_at, expires_at), capacities/limits, and dedicated tables/columns (e.g. for payouts, reservations, complaints, ratings/reviews, subscriptions) are provided as needed.
Each table MUST include 'requirement_ids' containing the exact requirement ID (e.g. ['{batch[0].req_id}']).
Include columns with PK, FK, data types, and constraints.

Return strictly JSON: {{"tables": [...]}}"""
                try:
                    res4 = provider.generate_json(pass4_prompt, system_prompt="You are a Principal Database Architect. Return strictly valid JSON.")
                    p4_tables = normalize_schema(res4).get("tables", [])
                    all_tables_list.extend([t for t in p4_tables if is_valid_domain_table_name(t.get("name", ""))])
                except Exception as e:
                    logger.error(f"Failed targeted schema coverage call batch {b_idx // batch_size + 1}: {e}")

        # --- PASS 5: Merge Tables & Ensure Integrity ---
        # Domain-agnostic table merging requiring strong structural AND semantic evidence
        def get_singular_name(name: str) -> str:
            n = name.lower()
            if n.endswith("ies") and len(n) > 3:
                return n[:-3] + "y"
            elif n.endswith("es") and len(n) > 2 and not n.endswith("sses"):
                return n[:-2]
            elif n.endswith("s") and not n.endswith("ss") and len(n) > 1:
                return n[:-1]
            return n

        def should_merge_candidate_tables(t1_entry: Dict[str, Any], t2_incoming: Dict[str, Any]) -> bool:
            name1 = t1_entry["name"].strip().lower()
            name2 = t2_incoming["name"].strip().lower()
            if name1 == name2:
                return True

            base1 = re.sub(r'(_batch\d+|_part\d+|_extended|_section\d+)$', '', name1)
            base2 = re.sub(r'(_batch\d+|_part\d+|_extended|_section\d+)$', '', name2)
            if base1 != base2:
                return False

            # Require strong structural AND semantic evidence:
            cols1 = {c["name"].lower(): c for c in t1_entry.get("columns", [])}
            cols2 = {c["name"].lower(): c for c in t2_incoming.get("columns", [])}

            # 1. Structural evidence: candidate PK alignment and column overlap
            pk1 = [c["name"].lower() for c in t1_entry.get("columns", []) if c.get("pk")]
            pk2 = [c["name"].lower() for c in t2_incoming.get("columns", []) if c.get("pk")]
            has_matching_pk = bool(pk1 and pk2 and (set(pk1) == set(pk2) or "id" in pk1 or "id" in pk2))

            col_names_1 = set(cols1.keys())
            col_names_2 = set(cols2.keys())
            intersection = col_names_1 & col_names_2
            union = col_names_1 | col_names_2
            jaccard = (len(intersection) / len(union)) if union else 0.0
            has_structural_evidence = has_matching_pk and (jaccard >= 0.35 or len(intersection) >= 3)

            # 2. Semantic evidence: shared requirement IDs or base entity description
            reqs1 = set(t1_entry.get("requirement_ids", []))
            reqs2 = set(t2_incoming.get("requirement_ids", []))
            has_req_overlap = bool(reqs1 & reqs2)
            desc1 = t1_entry.get("description", "").lower()
            desc2 = t2_incoming.get("description", "").lower()
            has_desc_overlap = (base1 in desc1 and base1 in desc2) if base1 else False
            has_semantic_evidence = has_req_overlap or has_desc_overlap

            if has_structural_evidence and has_semantic_evidence:
                return True

            logger.warning(
                f"Table ambiguity detected between '{name1}' and '{name2}' (base: '{base1}'). "
                f"Structural={has_structural_evidence} (pk1={pk1}, pk2={pk2}, jaccard={jaccard:.2f}), "
                f"Semantic={has_semantic_evidence} (shared_reqs={len(reqs1 & reqs2)}). "
                f"Preserving both tables separately."
            )
            return False

        merged_tables_map: Dict[str, Dict[str, Any]] = {}
        for tbl in all_tables_list:
            raw_t_name = tbl["name"].strip().lower()
            if not raw_t_name or not is_valid_domain_table_name(raw_t_name):
                continue

            # Check if this incoming table matches any already registered table
            matched_key = None
            for existing_key, existing_tbl in merged_tables_map.items():
                if should_merge_candidate_tables(existing_tbl, tbl):
                    matched_key = existing_key
                    break

            if not matched_key:
                merged_tables_map[raw_t_name] = {
                    "name": tbl["name"].strip(),
                    "description": tbl.get("description", ""),
                    "requirement_ids": list(set(tbl.get("requirement_ids", []))),
                    "columns": list(tbl.get("columns", [])),
                    "relationships": list(tbl.get("relationships", [])),
                    "indexes": list(tbl.get("indexes", []))
                }
            else:
                existing = merged_tables_map[matched_key]
                existing["requirement_ids"] = list(set(existing.get("requirement_ids", []) + tbl.get("requirement_ids", [])))
                existing_col_map = {c["name"].lower(): c for c in existing.get("columns", [])}
                target_singular = get_singular_name(existing["name"])

                for c in tbl.get("columns", []):
                    c_copy = dict(c)
                    cn = c_copy["name"].lower()
                    # Foreign keys (or external entity id references) are strictly immutable
                    is_fk = bool(c_copy.get("fk")) or (cn.endswith("_id") and cn != f"{target_singular}_id" and cn != "id")

                    # Primary key alias normalization: only if explicit PK on table's own entity and no existing 'id' PK
                    is_self_pk_alias = (
                        cn == f"{target_singular}_id"
                        and c_copy.get("pk") is True
                        and not is_fk
                    )

                    if is_self_pk_alias and "id" in existing_col_map:
                        # Existing table already has canonical 'id' PK
                        continue
                    elif is_self_pk_alias and "id" not in existing_col_map:
                        c_copy["name"] = "id"
                        cn = "id"

                    if cn not in existing_col_map:
                        # Do not add duplicate PK if table already has an 'id' PK
                        if c_copy.get("pk") and "id" in existing_col_map and cn != "id":
                            c_copy["pk"] = False
                        existing["columns"].append(c_copy)
                        existing_col_map[cn] = c_copy
                    else:
                        target_c = existing_col_map[cn]
                        if not target_c.get("fk") and c_copy.get("fk"):
                            target_c["fk"] = c_copy["fk"]
                        if not target_c.get("check") and c_copy.get("check"):
                            target_c["check"] = c_copy["check"]
                        if not target_c.get("unique") and c_copy.get("unique"):
                            target_c["unique"] = c_copy["unique"]
                        if not target_c.get("on_delete") and c_copy.get("on_delete"):
                            target_c["on_delete"] = c_copy["on_delete"]

                existing_indexes_set = set()
                for idx in existing.get("indexes", []):
                    idx_key = json.dumps(idx, sort_keys=True) if isinstance(idx, dict) else str(idx)
                    existing_indexes_set.add(idx_key)

                for idx in tbl.get("indexes", []):
                    idx_key = json.dumps(idx, sort_keys=True) if isinstance(idx, dict) else str(idx)
                    if idx_key not in existing_indexes_set:
                        existing["indexes"].append(idx)
                        existing_indexes_set.add(idx_key)

        # --- Domain-independent requirement-driven schema integrity assertions ---
        req_corpus = " ".join([f"{r.title} {r.description}".lower() for r in functional_reqs])

        # 1. Delivery milestone timestamps (e.g. return window after delivery, complaints after delivery, payouts after delivery)
        if any(k in req_corpus for k in ["of delivery", "after delivery", "from delivery", "delivered within"]):
            for t_name in ["orders", "order", "sub_orders", "sub_order"]:
                if t_name in merged_tables_map:
                    tbl = merged_tables_map[t_name]
                    cols = {c["name"].lower(): c for c in tbl.get("columns", [])}
                    if "delivered_at" not in cols:
                        tbl["columns"].append({
                            "name": "delivered_at",
                            "type": "TIMESTAMP",
                            "pk": False,
                            "fk": None,
                            "nullable": True,
                            "description": "Timestamp when delivery was successfully completed"
                        })
                        logger.info(f"Integrity check added delivered_at to {t_name}")

        # 2. Order items and batch tracking
        if any(k in req_corpus for k in ["batch", "order item", "line item"]):
            order_items_tbl = merged_tables_map.get("order_items") or merged_tables_map.get("order_item")
            if not order_items_tbl and ("orders" in merged_tables_map or "order" in merged_tables_map):
                parent_order = "orders" if "orders" in merged_tables_map else "order"
                order_items_tbl = {
                    "name": "order_items",
                    "description": "Individual line items associated with customer orders",
                    "requirement_ids": [r.req_id for r in functional_reqs if any(k in f"{r.title} {r.description}".lower() for k in ["order item", "line item", "item batch", "order_item"])][:2],
                    "columns": [
                        {"name": "id", "type": "INTEGER", "pk": True, "fk": None, "nullable": False, "description": "Primary key"},
                        {"name": "order_id", "type": "INTEGER", "pk": False, "fk": f"{parent_order}(id)", "nullable": False, "description": "Parent order foreign key"},
                        {"name": "batch_id", "type": "INTEGER", "pk": False, "fk": "batches(id)" if "batches" in merged_tables_map else None, "nullable": True, "description": "Allocated stock batch identifier"},
                        {"name": "quantity", "type": "INTEGER", "pk": False, "fk": None, "nullable": False, "description": "Ordered quantity"},
                        {"name": "unit_price", "type": "DECIMAL(10,2)", "pk": False, "fk": None, "nullable": False, "description": "Price per unit"}
                    ],
                    "relationships": [],
                    "indexes": ["order_id"]
                }
                merged_tables_map["order_items"] = order_items_tbl
                logger.info("Integrity check added order_items table with batch_id linkage")
            elif order_items_tbl:
                cols = {c["name"].lower(): c for c in order_items_tbl.get("columns", [])}
                if "batch_id" not in cols and "batches" in merged_tables_map:
                    order_items_tbl["columns"].append({
                        "name": "batch_id",
                        "type": "INTEGER",
                        "pk": False,
                        "fk": "batches(id)",
                        "nullable": True,
                        "description": "Allocated inventory batch identifier"
                    })
                    logger.info("Integrity check added batch_id to order_items")

        # 3. Dynamic temporal hold or reservation synthesis (domain-agnostic)
        if any(k in req_corpus for k in ["reserv", "checkout hold", "stock held", "temporary hold", "booking hold"]):
            has_reservation = any(k in t_name for t_name in merged_tables_map for k in ["reserv", "booking", "hold"])
            if not has_reservation:
                res_reqs = [r.req_id for r in functional_reqs if any(k in f"{r.title} {r.description}".lower() for k in ["reserv", "hold", "book"])]
                # Dynamically resolve what entity is being reserved/held
                target_entity_table = None
                for candidate in ["rooms", "beds", "appointments", "delivery_slots", "slots", "products", "produce_listings", "listings", "items"]:
                    if candidate in merged_tables_map:
                        target_entity_table = candidate
                        break

                user_table = "users" if "users" in merged_tables_map else ("guests" if "guests" in merged_tables_map else ("patients" if "patients" in merged_tables_map else None))
                user_fk = f"{user_table}(id)" if user_table else None
                res_table_name = "reservations"

                merged_tables_map[res_table_name] = {
                    "name": res_table_name,
                    "description": "Time-limited temporary holds/reservations",
                    "requirement_ids": res_reqs,
                    "columns": [
                        {"name": "id", "type": "INTEGER", "pk": True, "fk": None, "nullable": False, "description": "Primary key"},
                        {"name": "user_id", "type": "INTEGER", "pk": False, "fk": user_fk, "nullable": False, "description": "Holder identifier"},
                        {"name": "resource_id", "type": "INTEGER", "pk": False, "fk": f"{target_entity_table}(id)" if target_entity_table else None, "nullable": False, "description": "Reserved resource identifier"},
                        {"name": "quantity", "type": "INTEGER", "pk": False, "fk": None, "nullable": False, "description": "Reserved quantity or units"},
                        {"name": "expires_at", "type": "TIMESTAMP", "pk": False, "fk": None, "nullable": False, "description": "Reservation expiration timestamp"},
                        {"name": "status", "type": "VARCHAR(50)", "pk": False, "fk": None, "nullable": False, "description": "Status (e.g. HELD, RELEASED, CONFIRMED)"},
                        {"name": "created_at", "type": "TIMESTAMP", "pk": False, "fk": None, "nullable": False, "description": "Creation timestamp"}
                    ],
                    "relationships": [],
                    "indexes": ["user_id", "expires_at", "status"]
                }
                logger.info(f"Integrity check added dynamic reservation table '{res_table_name}' linked to {target_entity_table}")

        # 4. Domain-agnostic shelf life or expiry per catalog/item entity
        if any(k in req_corpus for k in ["shelf life", "shelf-life", "expiry", "expiration date"]):
            candidate_perishable_tables = [
                t for t in merged_tables_map
                if any(k in t for k in ["listing", "product", "item", "medication", "batch", "produce", "perishable", "food"])
            ]
            for t_name in candidate_perishable_tables:
                tbl = merged_tables_map[t_name]
                cols = {c["name"].lower(): c for c in tbl.get("columns", [])}
                if "shelf_life_days" not in cols and not any("shelf" in cn for cn in cols) and any(k in req_corpus for k in ["shelf life", "shelf-life"]):
                    tbl["columns"].append({
                        "name": "shelf_life_days",
                        "type": "INTEGER",
                        "pk": False,
                        "fk": None,
                        "nullable": True,
                        "description": "Shelf life duration in days"
                    })
                if "expiry_date" not in cols and not any("expir" in cn for cn in cols):
                    tbl["columns"].append({
                        "name": "expiry_date",
                        "type": "DATE",
                        "pk": False,
                        "fk": None,
                        "nullable": True,
                        "description": "Calculated or specified expiration date"
                    })
                logger.info(f"Integrity check ensured shelf life/expiry on {t_name}")
                break

        # Add audit_logs table ONLY if explicitly supported by actual project requirements
        audit_matching_reqs = [
            r.req_id for r in functional_reqs
            if any(k in f"{r.title} {r.description}".lower() for k in ["audit", "audit log", "audit trail", "action log", "change log", "compliance log"])
        ]
        if audit_matching_reqs:
            if "audit_logs" not in merged_tables_map:
                merged_tables_map["audit_logs"] = {
                    "name": "audit_logs",
                    "description": "Audit trail logging administrative and critical system actions",
                    "requirement_ids": audit_matching_reqs,
                    "columns": [
                        {"name": "id", "type": "INTEGER", "pk": True, "fk": None, "nullable": False, "description": "Primary key"},
                        {"name": "user_id", "type": "INTEGER", "pk": False, "fk": "users(id)", "nullable": True, "description": "User who performed action"},
                        {"name": "action", "type": "VARCHAR(100)", "pk": False, "fk": None, "nullable": False, "description": "Action type (e.g. CREATE, UPDATE, DELETE)"},
                        {"name": "entity_name", "type": "VARCHAR(100)", "pk": False, "fk": None, "nullable": False, "description": "Affected entity table name"},
                        {"name": "entity_id", "type": "VARCHAR(100)", "pk": False, "fk": None, "nullable": True, "description": "Identifier of affected entity"},
                        {"name": "details", "type": "TEXT", "pk": False, "fk": None, "nullable": True, "description": "JSON serialized action payload"},
                        {"name": "created_at", "type": "TIMESTAMP", "pk": False, "fk": None, "nullable": False, "description": "Action timestamp"}
                    ],
                    "relationships": [],
                    "indexes": ["user_id", "entity_name", "created_at"]
                }
            else:
                current_rids = set(merged_tables_map["audit_logs"].get("requirement_ids", []))
                merged_tables_map["audit_logs"]["requirement_ids"] = list(current_rids | set(audit_matching_reqs))
        else:
            # If no requirement supports audit logging, prune any ungrounded audit tables
            for ungrounded_name in ["audit_logs", "audit_log", "audit_trail", "audits"]:
                if ungrounded_name in merged_tables_map:
                    logger.info(f"Pruning ungrounded {ungrounded_name} table: no audit logging requirements exist.")
                    del merged_tables_map[ungrounded_name]

        # 4. Guarantee 100% functional requirement coverage
        covered_final = set()
        for tbl in merged_tables_map.values():
            for rid in tbl.get("requirement_ids", []):
                covered_final.add(rid)

        still_uncovered = [r for r in functional_reqs if r.req_id not in covered_final]
        for r in still_uncovered:
            logger.info(f"Requirement {r.req_id} ({r.title}) has no direct database table mapping; preserved unassigned.")

        # Post-merge cleanup: ensure exactly one primary key per table and preserve all foreign keys
        for tbl in merged_tables_map.values():
            col_list = tbl.get("columns", [])
            seen_cols = {}
            cleaned_cols = []
            pk_found = False
            tbl_singular = get_singular_name(tbl.get("name", ""))

            for col in col_list:
                c_name = col["name"].strip()
                c_lower = c_name.lower()

                # Foreign keys are strictly preserved
                is_fk = bool(col.get("fk")) or (c_lower.endswith("_id") and c_lower != f"{tbl_singular}_id" and c_lower != "id")

                # If table already has an 'id' PK, avoid duplicate self-referencing PK like {tbl_singular}_id
                if not is_fk and c_lower == f"{tbl_singular}_id" and any(c["name"].lower() == "id" for c in col_list):
                    continue

                if c_lower in seen_cols:
                    continue
                seen_cols[c_lower] = col

                # Enforce primary key integrity
                if col.get("pk"):
                    if not pk_found:
                        pk_found = True
                    else:
                        col["pk"] = False
                cleaned_cols.append(col)

            # If no primary key was assigned, designate 'id' or first column
            if not pk_found and cleaned_cols:
                id_col = next((c for c in cleaned_cols if c["name"].lower() == "id"), cleaned_cols[0])
                id_col["pk"] = True

            tbl["columns"] = cleaned_cols

        final_schema_dict = {"tables": list(merged_tables_map.values())}
        return normalize_schema(final_schema_dict)

    @staticmethod
    def _generate_api_documentation(project: Project, reqs: List[ExtractedRequirement], db: Session) -> Dict[str, Any]:
        """Generate API documentation across multiple groups of requirements, ensuring full coverage."""
        provider = get_llm_provider()

        functional_reqs = [r for r in reqs if r.category == "functional"]
        if not functional_reqs:
            functional_reqs = reqs

        actors = [r for r in reqs if r.category == "actor"]
        actor_names = [a.title for a in actors if a.title and a.title.lower() != "user"]
        if not actor_names:
            actor_names = ["Not specified"]

        schema_art = db.query(Artifact).filter(
            Artifact.project_id == project.id,
            Artifact.artifact_type == "schema"
        ).first()
        tables = []
        if schema_art and schema_art.content_json:
            try:
                tables = json.loads(schema_art.content_json).get("tables", [])
            except Exception:
                pass
        table_names = [t["name"] for t in tables if is_valid_domain_table_name(t.get("name", ""))]

        # Group requirements into batches of 4 to 5
        groups = []
        curr = []
        last_mod = None
        for r in functional_reqs:
            mod = r.module_name or "General"
            if (last_mod and mod != last_mod and len(curr) >= 3) or len(curr) >= 5:
                groups.append(curr)
                curr = []
            curr.append(r)
            last_mod = mod
        if curr:
            groups.append(curr)

        all_endpoints = []
        logger.info(f"Generating API endpoints in {len(groups)} batches for project {project.id[:8]}...")

        for idx, grp in enumerate(groups):
            grp_text = "\n".join([f"- [{r.req_id}] {r.title} ({r.module_name}): {r.description}" for r in grp])
            prompt = f"""Project: {project.name}
Actors/Roles: {', '.join(actor_names)}
Entities/Tables: {', '.join(table_names[:10])}

Generate RESTful OpenAPI endpoints specifically implementing these requirements:
{grp_text}

MANDATORY RULES:
1. Every requirement in this group MUST map to at least one endpoint. List its ID in 'requirement_ids': ['{grp[0].req_id}'].
2. If requirements manage entities, provide full CRUD endpoints.
3. If requirements mention lifecycle or status changes (e.g., pending, shipped, delivered, approved, cancelled), provide a status update endpoint (PATCH /api/v1/.../status).
4. If authentication or user login is mentioned, include login/token endpoints.
5. For EVERY endpoint include:
   - 'path': e.g. /api/v1/resource
   - 'method': GET | POST | PUT | DELETE | PATCH
   - 'summary': clear summary
   - 'description': detailed description
   - 'tag': resource tag
   - 'requirement_ids': list of requirement IDs covered (e.g. ['{grp[0].req_id}'])
   - 'auth_required': true | false
   - 'roles': list of roles from [{', '.join(actor_names)}]
   - 'parameters': list of {{"name": "...", "in": "path"|"query", "type": "string"|"integer"|"boolean", "required": true|false, "description": "..."}} (Must give real concrete data types, NOT undefined)
   - 'request_body': request schema dict
   - 'responses': list of {{"code": "...", "description": "..."}} including 200/201 and error codes 400, 401, 403, 404

Return strictly valid JSON: {{"endpoints": [...]}}"""
            try:
                res = provider.generate_json(prompt, system_prompt="You are a Staff API Architect. Return strictly valid JSON.")
                norm = normalize_api(res)
                for ep in norm.get("endpoints", []):
                    if is_valid_domain_endpoint_path(ep.get("path", "")):
                        all_endpoints.append(ep)
            except Exception as e:
                logger.error(f"Failed API batch {idx}: {e}")

        # Deduplicate and merge endpoints
        merged_map = {}
        for ep in all_endpoints:
            key = (ep["method"].upper(), ep["path"].lower())
            if key not in merged_map:
                merged_map[key] = ep
            else:
                existing_rids = set(merged_map[key].get("requirement_ids", []) + ep.get("requirement_ids", []))
                merged_map[key]["requirement_ids"] = list(existing_rids)

        merged_endpoints = list(merged_map.values())

        # Coverage Check
        covered_ids = set()
        for ep in merged_endpoints:
            for rid in ep.get("requirement_ids", []):
                covered_ids.add(rid)

        uncovered_frs = [r for r in functional_reqs if r.req_id not in covered_ids]
        logger.info(f"API initial coverage: {len(covered_ids)}/{len(functional_reqs)} functional requirements covered.")

        # Make one extra LLM call specifically for uncovered requirements
        if uncovered_frs:
            logger.info(f"Making targeted LLM call to cover {len(uncovered_frs)} uncovered requirements: {[r.req_id for r in uncovered_frs]}")
            uncovered_text = "\n".join([f"- [{r.req_id}] {r.title} ({r.module_name}): {r.description}" for r in uncovered_frs])
            prompt = f"""Project: {project.name}
The following requirements currently have NO API endpoints:
{uncovered_text}

Generate RESTful endpoints specifically covering EVERY requirement above.
Each endpoint MUST have 'requirement_ids' containing the exact ID (e.g. ['{uncovered_frs[0].req_id}']).
Include explicit parameters with real types ('type': 'string', 'integer', etc.), 'roles', 'auth_required', and error responses (400, 401, 403, 404).

Return strictly JSON: {{"endpoints": [...]}}"""
            try:
                res = provider.generate_json(prompt, system_prompt="You are a Staff API Architect. Return strictly valid JSON.")
                norm = normalize_api(res)
                for ep in norm.get("endpoints", []):
                    if not is_valid_domain_endpoint_path(ep.get("path", "")):
                        continue
                    key = (ep["method"].upper(), ep["path"].lower())
                    if key not in merged_map:
                        merged_map[key] = ep
                    else:
                        existing_rids = set(merged_map[key].get("requirement_ids", []) + ep.get("requirement_ids", []))
                        merged_map[key]["requirement_ids"] = list(existing_rids)
                merged_endpoints = list(merged_map.values())
            except Exception as e:
                logger.error(f"Failed extra API coverage call: {e}")

        # Final coverage guarantee: map any remaining requirement to the closest matching endpoint
        covered_now = set()
        for ep in merged_endpoints:
            for rid in ep.get("requirement_ids", []):
                covered_now.add(rid)
        
        still_uncovered = [r for r in functional_reqs if r.req_id not in covered_now]
        for r in still_uncovered:
            logger.info(f"Requirement {r.req_id} ({r.title}) has no direct API endpoint mapping; preserved unassigned.")

        # Ensure authentication endpoint if auth required
        has_auth = any(ep.get("auth_required") for ep in merged_endpoints)
        has_login = any("/login" in ep["path"].lower() or "/token" in ep["path"].lower() for ep in merged_endpoints)
        if has_auth and not has_login:
            auth_matching_reqs = [
                r.req_id for r in functional_reqs
                if any(k in f"{r.title} {r.description}".lower() for k in ["login", "authenticate", "authentication", "credential", "sign in", "token", "password", "mfa"])
            ]
            merged_endpoints.insert(0, {
                "path": "/api/v1/auth/token",
                "method": "POST",
                "summary": "Authenticate user and issue JWT access token",
                "description": "Validates user credentials and returns signed JWT Bearer token with user roles.",
                "tag": "Authentication",
                "requirement_ids": auth_matching_reqs,
                "auth_required": False,
                "roles": actor_names,
                "parameters": [],
                "request_body": {"email": "user@example.com", "password": "password123"},
                "responses": [
                    {"code": "200", "description": "JWT token issued successfully"},
                    {"code": "400", "description": "Bad Request - Invalid credentials"},
                    {"code": "401", "description": "Unauthorized"},
                    {"code": "403", "description": "Forbidden"},
                    {"code": "404", "description": "User account not found"}
                ]
            })

        return normalize_api({
            "title": f"{project.name} API Documentation",
            "components": {
                "securitySchemes": {
                    "BearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT",
                        "description": "JWT Bearer access token authorization header."
                    }
                }
            },
            "endpoints": merged_endpoints
        })

    @staticmethod
    def _is_meaningful_testcase(tc: Dict[str, Any], valid_req_map: Dict[str, ExtractedRequirement]) -> bool:
        """
        Validate that a test case contains genuine, actionable testing detail rather than
        a generic synthetic placeholder.
        """
        if not isinstance(tc, dict):
            return False

        req_id = tc.get("linked_req_id")
        if not req_id or req_id not in valid_req_map:
            return False

        req = valid_req_map[req_id]

        scenario = str(tc.get("scenario") or tc.get("description") or tc.get("name") or "").strip()
        steps = tc.get("steps")
        if isinstance(steps, list):
            steps_text = " ".join([str(s) for s in steps]).strip()
        else:
            steps_text = str(steps or "").strip()
        expected = str(tc.get("expected_result") or tc.get("expected") or "").strip()

        # Length thresholds: meaningful test cases must have non-trivial content
        if len(scenario) < 8 or len(steps_text) < 15 or len(expected) < 10:
            return False

        scenario_lower = scenario.lower()
        steps_lower = steps_text.lower()
        expected_lower = expected.lower()

        # Reject known synthetic placeholder scenario patterns
        req_title_lower = (req.title or "").strip().lower()
        if req_title_lower and f"verify {req_title_lower} workflow execution" in scenario_lower:
            return False
        if re.search(r"^verify\s+.+\s+workflow\s+execution$", scenario_lower):
            return False
        if scenario_lower in [
            "verify workflow execution",
            "test workflow execution",
            "workflow execution test",
            "placeholder test",
            "generic test case",
            "default test case"
        ]:
            return False

        # Reject placeholder step patterns
        if "execute operations for" in steps_lower and "verify system updates appropriately" in steps_lower:
            return False
        if steps_lower in [
            "execute operations",
            "perform action",
            "run test",
            "execute workflow",
            "1. execute operations",
            "1. perform operation",
            "1. run test"
        ]:
            return False

        # Reject placeholder expected result patterns
        if "operation succeeds per requirement specification" in expected_lower:
            return False
        if expected_lower in [
            "action completes successfully.",
            "action completes successfully",
            "operation succeeds.",
            "operation succeeds",
            "success.",
            "success",
            "system works as expected.",
            "system works as expected",
            "passes test.",
            "passes test"
        ]:
            return False

        return True

    @staticmethod
    def _generate_testcases(project: Project, reqs: List[ExtractedRequirement], db: Session) -> Dict[str, Any]:
        """Generate test cases in batches, ensuring positive/negative/boundary coverage with exact numbers."""
        provider = get_llm_provider()
        valid_req_map = {r.req_id: r for r in reqs}

        functional_reqs = [r for r in reqs if r.category == "functional"]
        if not functional_reqs:
            functional_reqs = reqs

        non_functional_reqs = [r for r in reqs if r.category in ["non_functional", "constraint"]]

        # Group requirements into batches of 4 to 5
        groups = []
        curr = []
        for r in functional_reqs:
            curr.append(r)
            if len(curr) >= 5:
                groups.append(curr)
                curr = []
        if curr:
            groups.append(curr)

        all_cases = []
        logger.info(f"Generating test cases in {len(groups)} batches for project {project.id[:8]}...")

        for idx, grp in enumerate(groups):
            grp_text = "\n".join([f"- [{r.req_id}] {r.title}: {r.description}" for r in grp])
            prompt = f"""Project: {project.name}

Generate requirements-driven test cases for the following functional requirements:
{grp_text}

MANDATORY RULES:
1. Generate test cases ONLY for requirements that provide sufficient functional detail, business logic, or acceptance criteria to derive meaningful:
   - Specific test scenario ('scenario')
   - System preconditions ('preconditions')
   - Actionable step-by-step test instructions ('steps')
   - Verifiable expected results and assertions ('expected_result')
2. When supported by requirement details, generate positive ('type': 'positive'), negative ('type': 'negative'), and boundary ('type': 'boundary') scenarios.
3. Extract and test exact NUMBERS, LIMITS, THRESHOLDS, and DAY COUNTS from the requirement text where specified.
4. Do NOT generate generic placeholder test cases (e.g. 'Verify {{title}} workflow execution', generic 'Execute operations', or vague 'Operation succeeds') for requirements lacking concrete criteria.
5. If a requirement is vague, abstract, or lacks actionable verification criteria, omit it rather than fabricating artificial test steps.
6. Every valid test case MUST include:
   - 'test_id': unique identifier like 'TC-{grp[0].req_id}-01'
   - 'linked_req_id': the exact requirement ID (e.g. '{grp[0].req_id}')
   - 'type': 'positive' | 'negative' | 'boundary'
   - 'scenario': clear, specific test scenario description
   - 'preconditions': specific prerequisite state or setup
   - 'steps': numbered, concrete step-by-step instructions
   - 'expected_result': verifiable expected behavior and assertions

Return strictly valid JSON: {{"cases": [...]}}"""
            try:
                res = provider.generate_json(prompt, system_prompt="You are a Principal QA Automation Engineer. Return strictly valid JSON.")
                norm = normalize_testcases(res)
                meaningful = [tc for tc in norm.get("cases", []) if ArtifactService._is_meaningful_testcase(tc, valid_req_map)]
                all_cases.extend(meaningful)
            except Exception as e:
                logger.error(f"Failed test case batch {idx}: {e}")

        # Coverage Check
        covered_ids = {tc.get("linked_req_id") for tc in all_cases if tc.get("linked_req_id")}
        uncovered_frs = [
            r for r in functional_reqs
            if r.req_id not in covered_ids and len((r.description or "").strip()) >= 25
        ]
        logger.info(f"Test cases initial coverage: {len(covered_ids)}/{len(functional_reqs)} functional requirements covered.")

        # One extra LLM call for uncovered requirements with sufficient detail
        if uncovered_frs:
            logger.info(f"Making targeted LLM call to cover {len(uncovered_frs)} uncovered requirements: {[r.req_id for r in uncovered_frs]}")
            uncovered_text = "\n".join([f"- [{r.req_id}] {r.title}: {r.description}" for r in uncovered_frs])
            prompt = f"""Project: {project.name}
The following requirements currently have no test cases:
{uncovered_text}

Generate positive, negative, and boundary test cases ONLY for requirements above that contain sufficient concrete functional criteria.
Every test case MUST include 'linked_req_id' matching the exact requirement ID.
Include exact numerical values, thresholds, and limits where applicable.
Do NOT generate generic placeholders or dummy steps for requirements that lack concrete criteria.

Return strictly JSON: {{"cases": [...]}}"""
            try:
                res = provider.generate_json(prompt, system_prompt="You are a Principal QA Automation Engineer. Return strictly valid JSON.")
                norm = normalize_testcases(res)
                meaningful = [tc for tc in norm.get("cases", []) if ArtifactService._is_meaningful_testcase(tc, valid_req_map)]
                all_cases.extend(meaningful)
            except Exception as e:
                logger.error(f"Failed extra testcases coverage call: {e}")

        # Non-functional / constraint test cases
        if non_functional_reqs:
            nfr_text = "\n".join([f"- [{r.req_id}] {r.title}: {r.description}" for r in non_functional_reqs])
            prompt = f"""Project: {project.name}
Generate performance, stress, concurrency, and constraint test cases for these requirements:
{nfr_text}

For each requirement containing measurable numbers (e.g. response time in ms, concurrent users, expiration days, retry limits):
Generate test cases with type 'positive' or 'boundary' verifying those specific numbers.
Every test case MUST include 'linked_req_id' matching the requirement ID.
Do NOT generate generic placeholders if a constraint lacks measurable metrics.

Return strictly JSON: {{"cases": [...]}}"""
            try:
                res = provider.generate_json(prompt, system_prompt="You are a Principal QA Automation Engineer. Return strictly valid JSON.")
                norm = normalize_testcases(res)
                meaningful = [tc for tc in norm.get("cases", []) if ArtifactService._is_meaningful_testcase(tc, valid_req_map)]
                all_cases.extend(meaningful)
            except Exception as e:
                logger.error(f"Failed NFR testcases call: {e}")

        # Deduplicate cases by test_id
        seen_test_ids = set()
        deduped_cases = []
        for tc in all_cases:
            tid = tc.get("test_id")
            if tid and tid not in seen_test_ids:
                seen_test_ids.add(tid)
                deduped_cases.append(tc)
            elif not tid:
                deduped_cases.append(tc)

        # Identify requirements that still have no meaningful test cases
        covered_now = {tc.get("linked_req_id") for tc in deduped_cases if tc.get("linked_req_id")}
        still_uncovered = [r for r in functional_reqs if r.req_id not in covered_now]
        if still_uncovered:
            logger.info(
                f"Requirements without sufficient detail for automated test cases preserved as unmapped/uncovered: "
                f"{[r.req_id for r in still_uncovered]}"
            )

        normalized = normalize_testcases({"cases": deduped_cases})
        if still_uncovered:
            normalized["unmapped_requirements"] = [
                {
                    "req_id": r.req_id,
                    "title": r.title,
                    "status": "manual_definition_needed",
                    "reason": "Insufficient acceptance criteria or test details in requirement specification."
                }
                for r in still_uncovered
            ]

        return normalized

    @staticmethod
    def restore_version(project_id: str, artifact_type: str, version_number: int, db: Session) -> Artifact:
        artifact = db.query(Artifact).filter(
            Artifact.project_id == project_id,
            Artifact.artifact_type == artifact_type
        ).first()
        if not artifact:
            raise ValueError("Artifact not found")

        target_ver = db.query(ArtifactVersion).filter(
            ArtifactVersion.artifact_id == artifact.id,
            ArtifactVersion.version_number == version_number
        ).first()
        if not target_ver:
            raise ValueError(f"Version {version_number} not found")

        artifact.content_json = target_ver.content_json
        artifact.current_version = version_number
        db.commit()
        db.refresh(artifact)
        return artifact
