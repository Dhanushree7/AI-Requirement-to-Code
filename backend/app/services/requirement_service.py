import json
import re

import logging
from typing import List, Optional, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.app.models.project import Project, UploadedFile
from backend.app.models.requirement import ExtractedRequirement, RequirementChangeHistory
from backend.app.schemas.requirement import (
    RequirementCreate, RequirementUpdate, RequirementResponse, RequirementsSummary, RequirementHistoryResponse
)
from backend.app.schemas.domain_model import DomainModel
from backend.app.services.llm.factory import get_llm_provider, get_extraction_provider
from backend.app.prompts.common import PROMPT_RULE
from backend.app.services.domain_validator import is_valid_domain_entity_candidate

logger = logging.getLogger(__name__)

DOMAIN_MODEL_PROMPT = f"""Analyze the software requirement document text and build a complete, validated Domain Model in JSON format.
{PROMPT_RULE}

CRITICAL: Extract ALL functional modules, primary domain entities, actors, constraints, and requirements present in the document.
First identify the core functional modules/subsystems and primary data entities, then extract each requirement and explicitly assign its module_name matching one of the modules. Keep descriptions concise and faithful to the source.

JSON schema must match:
{{
  "summary": {{
    "domain_name": "string",
    "overview": "string",
    "assumptions": ["string"]
  }},
  "actors": [
    {{"req_id": "ACT-001", "title": "string", "description": "string"}}
  ],
  "modules": [
    {{"req_id": "MOD-001", "name": "string", "description": "string"}}
  ],
  "entities": [
    {{"req_id": "ENT-001", "name": "string", "description": "string"}}
  ],
  "constraints": [
    {{"req_id": "CON-001", "title": "string", "description": "string"}}
  ],
  "requirements": [
    {{
      "req_id": "FR-001",
      "category": "functional|non_functional",
      "title": "string",
      "description": "string",
      "priority": "high|medium|low",
      "module_name": "string",
      "is_ambiguous": false,
      "ambiguity_notes": null,
      "clarifying_questions": []
    }}
  ]
}}

DOCUMENT TEXT:
{{document_text}}
"""


META_SECTION_HEADINGS = {
    "problem statement", "project scope", "scope", "overview", "introduction",
    "background", "purpose", "executive summary", "objective", "objectives",
    "assumptions", "dependencies", "constraints", "system constraints",
    "non-functional requirements", "non functional requirements", "nfr", "nfrs",
    "quality attributes", "performance requirements", "security requirements",
    "system architecture", "revision history", "document history", "version control",
    "table of contents", "glossary", "definitions", "acronyms", "abbreviations",
    "references", "appendix", "users and roles", "actors", "roles", "user classes",
    "stakeholders", "functional requirements", "domain entities", "domain entities & data attributes",
    "software requirement specification"
}

def _extract_functional_modules_from_text(text: str) -> List[Dict[str, Any]]:
    """Extract structural section headers that unambiguously represent functional modules."""
    pattern = re.compile(r'(?m)^(?:[0-9]+(?:\.[0-9]+)*\s+|#{2,4}\s+(?:Module\s+[0-9]+:\s*)?)([A-Za-z0-9\s,&/\-]{3,60})$')
    raw_matches = list(pattern.finditer(text))
    modules = []

    for i, m in enumerate(raw_matches):
        raw_name = m.group(1).strip()
        cleaned = re.sub(r'^(?:Module\s+[0-9]+:\s*|[0-9]+(?:\.[0-9]+)*\s*)', '', raw_name, flags=re.I).strip()
        cl = cleaned.lower()

        if cl in META_SECTION_HEADINGS or len(cleaned) < 3:
            continue

        start_pos = m.start()
        end_pos = raw_matches[i + 1].start() if i + 1 < len(raw_matches) else len(text)
        section_text = text[start_pos:end_pos]

        # Validate that the section contains functional requirement indicators (modals, IDs, or CRUD actions)
        has_req_indicators = bool(re.search(r'\b(shall|must|should|can|will|allows?|enables?|creates?|manages?|REQ-\d+|FR-\d+)\b', section_text, re.I))
        if has_req_indicators:
            modules.append({
                "name": cleaned,
                "start": start_pos,
                "end": end_pos
            })

    return modules

def _map_requirements_to_modules(text: str, req_items: List[Dict[str, Any]], module_spans: List[Dict[str, Any]]) -> None:
    """Unambiguously assign each requirement to a module based on document position, preserving None if ambiguous."""
    for item in req_items:
        current_mod = item.get("module_name")
        if current_mod and str(current_mod).strip().lower() not in ["string", "none", "null", "general", "unknown", ""]:
            continue

        req_id = item.get("req_id", "")
        title = item.get("title", "")

        pos = -1
        if req_id and req_id in text:
            pos = text.find(req_id)
        elif title and title in text:
            pos = text.find(title)

        if pos >= 0 and module_spans:
            enclosing = [m for m in module_spans if m["start"] <= pos < m["end"]]
            if len(enclosing) == 1:
                item["module_name"] = enclosing[0]["name"]
            else:
                item["module_name"] = None
        else:
            item["module_name"] = None

def _extract_validated_domain_entities(text: str, functional_reqs: List[Dict[str, Any]], known_actors: set) -> List[Dict[str, Any]]:
    """Extract and validate domain entities from explicit entity sections and requirement statements."""
    entities = {}

    # 1. Check for explicit Domain Entities section
    ent_sec = re.search(r'(?i)##\s*[0-9.]*\s*Domain Entities[^\n]*\n([\s\S]*?)(?=\n##|\Z)', text)
    if ent_sec:
        for line in ent_sec.group(1).split('\n'):
            m = re.match(r'^\s*[-*]\s*([A-Za-z][A-Za-z0-9_]{2,30})\s*:\s*(.*)', line)
            if m:
                name = m.group(1).strip()
                desc = m.group(2).strip() or f"Domain entity representing {name}."
                if name.lower() not in known_actors and is_valid_domain_entity_candidate(name, has_explicit_definition=True):
                    entities[name.lower()] = {"name": name, "description": desc}

    # 2. Extract from requirement statements if fewer than 3 entities discovered
    if len(entities) < 3:
        stop_words = {
            'system', 'application', 'software', 'service', 'database', 'table', 'column',
            'api', 'module', 'user', 'users', 'role', 'roles', 'actor', 'actors', 'status',
            'details', 'option', 'options', 'item', 'items', 'list', 'lists', 'form', 'forms',
            'page', 'pages', 'button', 'buttons', 'process', 'step', 'steps', 'requirement',
            'requirements', 'value', 'values', 'access', 'number', 'date', 'time', 'id', 'type'
        } | known_actors

        req_corpus = " ".join([f"{r.get('title','')} {r.get('description','')}" for r in functional_reqs]) or text

        # Match direct objects of CRUD and operational verbs
        verb_pattern = re.compile(r'\b(?:create|creates|manage|manages|view|views|update|updates|cancel|cancels|submit|submits|track|tracks|allocate|allocates|reserve|reserves|process|processes)\s+(?:a|an|the)?\s*([a-zA-Z]{3,20})\b', re.IGNORECASE)
        for m in verb_pattern.finditer(req_corpus):
            raw = m.group(1)
            singular = raw.rstrip('s').capitalize()
            if singular.lower() not in stop_words and len(singular) >= 3 and is_valid_domain_entity_candidate(singular):
                if singular.lower() not in entities:
                    entities[singular.lower()] = {
                        "name": singular,
                        "description": f"Domain entity representing {singular.lower()} operations."
                    }

    return list(entities.values())

class RequirementService:
    @staticmethod
    def analyze_project_requirements(project_id: str, db: Session) -> Dict[str, Any]:
        """Extract all requirement categories using LLM provider and save to DB."""
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project not found with ID {project_id}.")

        files = db.query(UploadedFile).filter(UploadedFile.project_id == project_id).all()
        doc_texts = [f.extracted_text for f in files if f.extracted_text]
        full_text = "\n\n".join(doc_texts)

        if not full_text:
            raise ValueError("No extracted text available for this project. Please upload a document first.")

        project.status = "extracting"
        db.commit()

        try:
            # Call extraction LLM provider (using validated Pydantic model)
            provider = get_extraction_provider()
            prompt = DOMAIN_MODEL_PROMPT.replace("{document_text}", full_text[:12000])

            try:
                validated_model: DomainModel = provider.generate_validated_json(
                    prompt=prompt,
                    response_model=DomainModel,
                    system_prompt="You are an expert Systems Analyst and Requirements Engineer. Return strictly valid JSON matching the schema."
                )
                extracted_data = validated_model.model_dump()
            except Exception as e:
                logger.warning(f"Domain model validation failed, falling back to generate_json: {e}")
                raw_json = provider.generate_json(
                    prompt=prompt,
                    system_prompt="You are an expert Systems Analyst and Requirements Engineer."
                )
                if isinstance(raw_json, str):
                    from backend.app.services.llm.factory import robust_json_parse
                    raw_json = robust_json_parse(raw_json)
                extracted_data = raw_json

            # Persist full Domain Model JSON on the project
            project.domain_model_json = json.dumps(extracted_data)

            # Preserve existing requirements and only add new ones (idempotent analysis)
            existing_ids = {r.req_id for r in db.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == project_id).all()}
            created_records = []

            def insert_category(items: List[Dict[str, Any]], category: Optional[str] = None, id_prefix: Optional[str] = None):
                for item in items:
                    req_id = item.get("req_id")
                    if not req_id:
                        base = id_prefix or "REQ"
                        idx = 1
                        while f"{base}-{idx:03d}" in existing_ids:
                            idx += 1
                        req_id = f"{base}-{idx:03d}"
                    if req_id in existing_ids:
                        continue

                    prefix = req_id.split("-")[0].upper()
                    mapping = {
                        "REQ": "functional",
                        "FR": "functional",
                        "NFR": "non_functional",
                        "CON": "constraint",
                        "ACT": "actor",
                        "ENT": "entity",
                        "MOD": "module",
                    }
                    inferred_cat = mapping.get(prefix)
                    item_cat = item.get("category")
                    if item_cat in mapping.values():
                        final_category = item_cat
                    elif inferred_cat:
                        final_category = inferred_cat
                    else:
                        final_category = category or "functional"
                    if not final_category or str(final_category).lower() in ["unknown", "unk"]:
                        final_category = "functional"

                    clarifying = item.get("clarifying_questions", [])
                    clarifying_json = json.dumps(clarifying) if clarifying else None
                    candidate_title = (item.get("title") or item.get("name") or f"Requirement {req_id}").strip()

                    # Duplicate prevention for entities and modules by title
                    if final_category in ["entity", "module"]:
                        existing_same_cat = [
                            r for r in db.query(ExtractedRequirement).filter(
                                ExtractedRequirement.project_id == project_id,
                                ExtractedRequirement.category == final_category
                            ).all()
                        ] + [r for r in created_records if r.category == final_category]
                        if any(r.title.strip().lower() == candidate_title.lower() for r in existing_same_cat):
                            continue

                    record = ExtractedRequirement(
                        project_id=project_id,
                        req_id=req_id,
                        category=final_category,
                        title=candidate_title,
                        description=item.get("description") or candidate_title or "Description",
                        priority=item.get("priority", "medium"),
                        priority_source="document" if bool(re.search(r'\b(?:priority\s*[:=-]\s*(?:high|medium|low|critical)|\[(?:high|medium|low|critical)\s*priority\])\b', f"{item.get('title','')} {item.get('description','')}", re.I)) else "suggested",
                        module_name=item.get("module_name"),
                        is_ambiguous=bool(item.get("is_ambiguous", False)),
                        ambiguity_notes=item.get("ambiguity_notes"),
                        clarifying_questions=clarifying_json,
                    )
                    db.add(record)
                    created_records.append(record)
                    existing_ids.add(req_id)

            # Detect functional modules from document structure if omitted or empty
            doc_modules = _extract_functional_modules_from_text(full_text)
            extracted_modules = extracted_data.get("modules", [])
            if not extracted_modules and doc_modules:
                extracted_modules = [{"name": m["name"], "description": f"Functional module representing {m['name']}."} for m in doc_modules]
                extracted_data["modules"] = extracted_modules

            # Extract requirements from structured domain model
            req_items = extracted_data.get("requirements", [])

            # Map requirements to enclosing modules if module_name is missing or unassigned
            _map_requirements_to_modules(full_text, req_items, doc_modules)

            if req_items:
                for r in req_items:
                    item_prefix = str(r.get("req_id", "")).split("-")[0].upper()
                    default_cat = "non_functional" if item_prefix == "NFR" else "functional"
                    cat = r.get("category") or default_cat
                    insert_category([r], cat, "NFR" if cat == "non_functional" else "FR")
            else:
                insert_category(extracted_data.get("functional", []), "functional", "FR")
                insert_category(extracted_data.get("non_functional", []), "non_functional", "NFR")

            # Extract validated domain entities if omitted or empty
            known_actors_set = {a.get("title", "").lower() for a in extracted_data.get("actors", [])}
            extracted_entities = extracted_data.get("entities", [])
            if not extracted_entities:
                extracted_entities = _extract_validated_domain_entities(full_text, req_items, known_actors_set)
                extracted_data["entities"] = extracted_entities

            insert_category(extracted_data.get("actors", []), "actor", "ACT")
            validated_ents = [
                e for e in extracted_entities
                if is_valid_domain_entity_candidate(e.get("name") or e.get("title", ""), has_explicit_definition=True)
            ]
            insert_category(validated_ents, "entity", "ENT")
            insert_category(extracted_modules, "module", "MOD")
            insert_category(extracted_data.get("constraints", []), "constraint", "CON")

            # Auto-register module records for any functional requirements with validated module_names
            existing_modules = {
                r.title.strip().lower(): r
                for r in db.query(ExtractedRequirement).filter(
                    ExtractedRequirement.project_id == project_id,
                    ExtractedRequirement.category == "module"
                ).all()
            }
            functional_records = [r for r in created_records if r.category == "functional"]
            for fr in functional_records:
                if fr.module_name and fr.module_name.strip():
                    mod_title = fr.module_name.strip()
                    if mod_title.lower() not in existing_modules:
                        mod_idx = 1
                        while f"MOD-{mod_idx:03d}" in existing_ids:
                            mod_idx += 1
                        mod_id = f"MOD-{mod_idx:03d}"
                        mod_record = ExtractedRequirement(
                            project_id=project_id,
                            req_id=mod_id,
                            category="module",
                            title=mod_title,
                            description=f"Functional module representing {mod_title} capabilities.",
                            priority="medium",
                            priority_source="suggested",
                            module_name=mod_title
                        )
                        db.add(mod_record)
                        created_records.append(mod_record)
                        existing_ids.add(mod_id)
                        existing_modules[mod_title.lower()] = mod_record

            # Validate that all requirement IDs present in the raw document are stored
            strict_id_regex = r"(?m)^[\s>*-]*([A-Za-z]+-\d+)\b|\b([A-Za-z]+-\d+):"
            found_ids: set[str] = set()
            for match in re.finditer(strict_id_regex, full_text):
                rid = match.group(1) or match.group(2)
                if rid:
                    found_ids.add(rid)

            stored_ids = {r.req_id for r in db.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == project_id).all()}
            missing_ids = found_ids - stored_ids
            if missing_ids:
                logger.info(f"Missing requirement IDs detected: {missing_ids}, invoking LLM for extraction.")
                missing_prompt = (
                    "Given the following software requirement document text, extract the requirements whose IDs are listed, "
                    "and return a JSON array where each element contains: req_id, category (functional, non_functional, constraint, actor, entity, module), "
                    "title, description, priority (if applicable), module_name (if applicable).\n"
                    f"Missing IDs: {', '.join(sorted(missing_ids))}\n"
                    "Document Text:\n" + full_text[:12000]
                )
                try:
                    missing_json = provider.generate_json(prompt=missing_prompt, system_prompt="You are an expert Requirements Engineer. Return strictly valid JSON array of requirement objects.")
                    missing_data = json.loads(missing_json) if isinstance(missing_json, str) else missing_json
                    if isinstance(missing_data, dict):
                        missing_data = missing_data.get("requirements", missing_data.get("items", [missing_data]))
                    insert_category(missing_data)
                except Exception as e:
                    logger.warning(f"Failed to extract missing requirements via LLM: {e}")

            # Automatically update Graph and RAG index with the new domain model
            try:
                from backend.app.services.graph_service import GraphService
                from backend.app.services.rag_service import RagService
                GraphService.generate_knowledge_graph(project_id, db)
                RagService.index_project_chunks(project_id, db)
            except Exception as e:
                logger.warning(f"Could not immediately re-index graph/RAG after domain extraction: {e}")

            # Finalize project status
            project.status = "idle"
            project.current_step = "rag_llm"
            db.commit()

            logger.info(f"Successfully extracted {len(created_records)} requirements for project {project_id}.")
            return {
                "total_extracted": len(created_records),
                "functional_count": sum(1 for r in created_records if r.category == "functional"),
                "non_functional_count": sum(1 for r in created_records if r.category == "non_functional"),
                "actor_count": sum(1 for r in created_records if r.category == "actor"),
                "entity_count": sum(1 for r in created_records if r.category == "entity"),
                "module_count": sum(1 for r in created_records if r.category == "module"),
                "constraint_count": sum(1 for r in created_records if r.category == "constraint"),
            }
        except Exception as e:
            logger.error(f"Requirement extraction failed for project {project_id}: {e}")
            db.rollback()
            try:
                proj = db.query(Project).filter(Project.id == project_id).first()
                if proj:
                    proj.status = "error"
                    db.commit()
            except Exception as db_err:
                logger.error(f"Failed to record error status for project {project_id}: {db_err}")
                db.rollback()
            raise ValueError(f"Requirement extraction failed: {str(e)}") from e

    @staticmethod
    def get_requirements(project_id: str, category: Optional[str], db: Session) -> List[RequirementResponse]:
        query = db.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == project_id)
        if category:
            query = query.filter(ExtractedRequirement.category == category)
        records = query.order_by(ExtractedRequirement.req_id.asc()).all()

        results = []
        for r in records:
            clarifying = None
            if r.clarifying_questions:
                try:
                    clarifying = json.loads(r.clarifying_questions)
                except Exception:
                    clarifying = []
            results.append(
                RequirementResponse(
                    id=r.id,
                    project_id=r.project_id,
                    req_id=r.req_id,
                    category=r.category,
                    title=r.title,
                    description=r.description,
                    priority=r.priority,
                    priority_source=getattr(r, "priority_source", "suggested"),
                    module_name=r.module_name,
                    is_ambiguous=r.is_ambiguous,
                    ambiguity_notes=r.ambiguity_notes,
                    clarifying_questions=clarifying,
                    created_at=r.created_at,
                    updated_at=r.updated_at
                )
            )
        return results

    @staticmethod
    def get_summary(project_id: str, db: Session) -> RequirementsSummary:
        reqs = RequirementService.get_requirements(project_id, None, db)
        return RequirementsSummary(
            total=len(reqs),
            functional_count=sum(1 for r in reqs if r.category == "functional"),
            non_functional_count=sum(1 for r in reqs if r.category == "non_functional"),
            actor_count=sum(1 for r in reqs if r.category == "actor"),
            entity_count=sum(1 for r in reqs if r.category == "entity"),
            module_count=sum(1 for r in reqs if r.category == "module"),
            constraint_count=sum(1 for r in reqs if r.category == "constraint"),
            ambiguous_count=sum(1 for r in reqs if r.is_ambiguous),
            requirements=reqs
        )

    @staticmethod
    def create_requirement(project_id: str, data: RequirementCreate, db: Session) -> RequirementResponse:
        clarifying_json = json.dumps(data.clarifying_questions) if data.clarifying_questions else None
        req = ExtractedRequirement(
            project_id=project_id,
            req_id=data.req_id,
            category=data.category,
            title=data.title,
            description=data.description,
            priority=data.priority,
            module_name=data.module_name,
            is_ambiguous=data.is_ambiguous,
            ambiguity_notes=data.ambiguity_notes,
            clarifying_questions=clarifying_json
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        return RequirementResponse(
            id=req.id,
            project_id=req.project_id,
            req_id=req.req_id,
            category=req.category,
            title=req.title,
            description=req.description,
            priority=req.priority,
            priority_source=getattr(req, "priority_source", "suggested"),
            module_name=req.module_name,
            is_ambiguous=req.is_ambiguous,
            ambiguity_notes=req.ambiguity_notes,
            clarifying_questions=data.clarifying_questions,
            created_at=req.created_at,
            updated_at=req.updated_at
        )

    @staticmethod
    def update_requirement(req_id: str, data: RequirementUpdate, db: Session) -> Optional[RequirementResponse]:
        req = db.query(ExtractedRequirement).filter(ExtractedRequirement.id == req_id).first()
        if not req:
            return None

        # Snapshots of editable fields before mutation
        before_title = req.title
        before_desc = req.description
        before_prio = req.priority
        before_mod = req.module_name
        before_ambig = bool(req.is_ambiguous)
        before_notes = req.ambiguity_notes
        before_questions = req.clarifying_questions

        # Candidate new values (preserving stability of unpassed fields)
        target_title = data.title.strip() if data.title is not None else before_title
        target_desc = data.description.strip() if data.description is not None else before_desc
        target_prio = data.priority if data.priority is not None else before_prio
        target_mod = data.module_name if data.module_name is not None else before_mod
        target_ambig = bool(data.is_ambiguous) if data.is_ambiguous is not None else before_ambig
        target_notes = data.ambiguity_notes if data.ambiguity_notes is not None else before_notes
        target_questions = json.dumps(data.clarifying_questions) if data.clarifying_questions is not None else before_questions

        # Change detection: check if any field changed meaningfully
        changes = []
        if (before_title or "").strip() != target_title:
            changes.append("title")
        if (before_desc or "").strip() != target_desc:
            changes.append("description")
        if (before_prio or "") != target_prio:
            changes.append("priority")
        if (before_mod or None) != (target_mod or None):
            changes.append("module_name")
        if before_ambig != target_ambig:
            changes.append("is_ambiguous")
        if (before_notes or None) != (target_notes or None):
            changes.append("ambiguity_notes")
        if (before_questions or None) != (target_questions or None):
            changes.append("clarifying_questions")

        # If no meaningful change, return existing record without creating a spurious history entry
        if not changes:
            clarifying = None
            if req.clarifying_questions:
                try:
                    clarifying = json.loads(req.clarifying_questions)
                except Exception:
                    clarifying = []
            return RequirementResponse(
                id=req.id,
                project_id=req.project_id,
                req_id=req.req_id,
                category=req.category,
                title=req.title,
                description=req.description,
                priority=req.priority,
                priority_source=getattr(req, "priority_source", "suggested"),
                module_name=req.module_name,
                is_ambiguous=req.is_ambiguous,
                ambiguity_notes=req.ambiguity_notes,
                clarifying_questions=clarifying,
                created_at=req.created_at,
                updated_at=req.updated_at
            )

        # Categorize change type
        if "description" in changes or "title" in changes:
            change_type = "content_modified"
        elif "priority" in changes:
            change_type = "priority_modified"
        else:
            change_type = "metadata_modified"

        summary = f"Modified {', '.join(changes)}"

        # Compute next incremental version number for this requirement
        last_version = db.query(func.max(RequirementChangeHistory.version_number))\
            .filter(RequirementChangeHistory.requirement_id == req.id)\
            .scalar()
        next_version = (last_version or 0) + 1

        # Create history snapshot preserving complete before-and-after states
        history_entry = RequirementChangeHistory(
            requirement_id=req.id,
            project_id=req.project_id,
            req_id=req.req_id,
            version_number=next_version,
            title_before=before_title,
            title_after=target_title,
            description_before=before_desc,
            description_after=target_desc,
            priority_before=before_prio,
            priority_after=target_prio,
            module_name_before=before_mod,
            module_name_after=target_mod,
            is_ambiguous_before=before_ambig,
            is_ambiguous_after=target_ambig,
            ambiguity_notes_before=before_notes,
            ambiguity_notes_after=target_notes,
            clarifying_questions_before=before_questions,
            clarifying_questions_after=target_questions,
            change_type=change_type,
            change_summary=summary
        )
        db.add(history_entry)

        # Apply updates to requirement (keeping id and req_id strictly stable)
        req.title = target_title
        req.description = target_desc
        req.priority = target_prio
        req.module_name = target_mod
        req.is_ambiguous = target_ambig
        req.ambiguity_notes = target_notes
        req.clarifying_questions = target_questions

        # Atomic commit of requirement update and change history entry
        db.commit()
        db.refresh(req)

        clarifying = None
        if req.clarifying_questions:
            try:
                clarifying = json.loads(req.clarifying_questions)
            except Exception:
                clarifying = []

        return RequirementResponse(
            id=req.id,
            project_id=req.project_id,
            req_id=req.req_id,
            category=req.category,
            title=req.title,
            description=req.description,
            priority=req.priority,
            priority_source=getattr(req, "priority_source", "suggested"),
            module_name=req.module_name,
            is_ambiguous=req.is_ambiguous,
            ambiguity_notes=req.ambiguity_notes,
            clarifying_questions=clarifying,
            created_at=req.created_at,
            updated_at=req.updated_at
        )

    @staticmethod
    def delete_requirement(req_id: str, db: Session) -> bool:
        req = db.query(ExtractedRequirement).filter(ExtractedRequirement.id == req_id).first()
        if not req:
            return False
        # Do not rely solely on SQLite cascade deletion until foreign-key enforcement is active
        db.query(RequirementChangeHistory).filter(RequirementChangeHistory.requirement_id == req.id).delete(synchronize_session=False)
        db.delete(req)
        db.commit()
        return True

    @staticmethod
    def get_requirement_history(project_id: str, req_id: str, db: Session) -> List[RequirementHistoryResponse]:
        """Fetch chronological change history for a requirement by logical req_id or UUID."""
        req = db.query(ExtractedRequirement).filter(
            ExtractedRequirement.project_id == project_id,
            (ExtractedRequirement.req_id == req_id) | (ExtractedRequirement.id == req_id)
        ).first()
        if not req:
            return []

        history_records = db.query(RequirementChangeHistory)\
            .filter(RequirementChangeHistory.requirement_id == req.id)\
            .order_by(RequirementChangeHistory.version_number.desc())\
            .all()

        results = []
        for h in history_records:
            q_before = None
            if h.clarifying_questions_before:
                try:
                    q_before = json.loads(h.clarifying_questions_before)
                except Exception:
                    q_before = []
            q_after = None
            if h.clarifying_questions_after:
                try:
                    q_after = json.loads(h.clarifying_questions_after)
                except Exception:
                    q_after = []

            results.append(
                RequirementHistoryResponse(
                    id=h.id,
                    requirement_id=h.requirement_id,
                    project_id=h.project_id,
                    req_id=h.req_id,
                    version_number=h.version_number,
                    title_before=h.title_before,
                    title_after=h.title_after,
                    description_before=h.description_before,
                    description_after=h.description_after,
                    priority_before=h.priority_before,
                    priority_after=h.priority_after,
                    module_name_before=h.module_name_before,
                    module_name_after=h.module_name_after,
                    is_ambiguous_before=h.is_ambiguous_before,
                    is_ambiguous_after=h.is_ambiguous_after,
                    ambiguity_notes_before=h.ambiguity_notes_before,
                    ambiguity_notes_after=h.ambiguity_notes_after,
                    clarifying_questions_before=q_before,
                    clarifying_questions_after=q_after,
                    change_type=h.change_type,
                    change_summary=h.change_summary,
                    created_at=h.created_at
                )
            )
        return results
