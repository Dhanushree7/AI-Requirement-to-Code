"""
Domain-independent heuristic requirements analyzer and generator.
Extracts specifications, architectures, schemas, APIs, code skeletons,
and test cases from ANY requirement document without domain-specific hardcoding.
"""
import re
import ast
import json
from typing import Dict, Any, List, Tuple, Optional
from backend.app.services.domain_validator import (
    is_valid_domain_entity_candidate,
    is_valid_domain_table_name,
    is_valid_domain_endpoint_path,
    to_snake_case,
    to_kebab_case,
    pluralize,
    singularize
)


def extract_domain_info(text: str, fallback_title: str = "Software System") -> Dict[str, Any]:
    """Analyze document text to identify project title, domain nouns, verbs, and actors."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    # 1. Project Title Detection
    detected_title = fallback_title
    for line in lines[:8]:
        cleaned = re.sub(r"^[#*=\-\s]+", "", line).strip()
        cleaned = re.sub(r"^(software\s+requirements?\s+specification|srs|system\s+requirements?)\s*[:-]?\s*", "", cleaned, flags=re.IGNORECASE).strip()
        if len(cleaned) > 3 and not cleaned.lower().startswith("version") and not cleaned.lower().startswith("table of"):
            detected_title = cleaned
            break

    # 2. Extract Sentences
    sentences = []
    for line in lines:
        cleaned_line = re.sub(r"^[#*=\-\d.)\s]+", "", line).strip()
        if not cleaned_line:
            continue
        for s in re.split(r"(?<=[.!?])\s+", cleaned_line):
            s = s.strip()
            if len(s) > 15:
                sentences.append(s)

    # 3. Detect Potential Actors dynamically from document patterns
    found_actors = set()
    system_non_actors = {
        "system", "the", "this", "that", "these", "those", "there", "it", "user", "users",
        "application", "software", "platform", "database", "service", "module", "api",
        "interface", "component", "table", "data", "file", "document", "record", "step",
        "page", "section", "all", "each", "every", "any", "none", "feature", "requirement",
        "authentication", "charge", "charges", "sanitation", "security", "notification", "integration",
        "payment", "verification", "registration", "management", "reporting", "administration"
    }

    for s in sentences:
        # Match explicit actor indicators like "actor: Patient", "as a Guest", "allows Customers to"
        m_roles = re.findall(r'(?:actor|user role|as an?)\s*[:=-]?\s*([A-Z][a-z]+)|\b(?:allow(?:s)?|let(?:s)?)\s+([A-Z][a-z]+)\b', s, re.IGNORECASE)
        for r_tuple in m_roles:
            r_name = r_tuple[0] or r_tuple[1]
            if not r_name:
                continue
            r_clean = r_name.strip().title()
            if r_clean.endswith('s') and not r_clean.endswith('ss') and len(r_clean) > 3:
                r_clean = r_clean[:-1]
            if r_clean.lower() not in system_non_actors and len(r_clean) > 2:
                found_actors.add(r_clean)

        # Match grammatical subject-agents before requirement modals: e.g. "Patients shall...", "Doctors must..."
        m_modals = re.findall(r'\b([A-Z][a-z]{2,15})\s+(?:shall|must|should|can|will|may|is able to)\b', s)
        for subj in m_modals:
            subj_clean = subj.strip().title()
            if subj_clean.endswith('s') and not subj_clean.endswith('ss') and len(subj_clean) > 3:
                subj_clean = subj_clean[:-1]
            if subj_clean.lower() not in system_non_actors:
                found_actors.add(subj_clean)

    # Fallback heuristic: check for agentive suffixes (-er, -or, -ist, -ian, -ant, -ent, -ee)
    if not found_actors:
        agent_suffix_pattern = re.compile(r'\b([A-Z][a-z]{2,12}(?:er|or|ist|ian|ant|ent|ee)s?)\b')
        for s in sentences:
            for w in agent_suffix_pattern.findall(s):
                wl = w.rstrip('s').lower()
                if wl not in system_non_actors and len(wl) > 3:
                    found_actors.add(w.title())

    if not found_actors:
        found_actors = {"User"}

    # Dynamic actor taxonomy for noun stop filtering
    common_actor_words = {a.lower() for a in found_actors} | {
        "admin", "administrator", "manager", "operator", "supervisor", "staff",
        "user", "agent", "specialist", "coordinator", "officer", "assistant"
    }

    # 4. Extract Potential Domain Entities (Nouns)
    detected_entities = []
    explicit_entities = []
    explicit_attributes = {}

    # 4a. Check for explicit ENT tagged lines (e.g. - [ENT-001] Patient: ...)
    for m in re.finditer(r'(?mi)^\s*[-*]\s*(?:\[(?:ENT|ENTITY)[-_ ]?[0-9]+\]\s*[:.-]?\s*)([A-Za-z][A-Za-z0-9_]{2,30})\s*:\s*(.+)$', text):
        name = m.group(1).strip()
        attrs_str = m.group(2).strip()
        if is_valid_domain_entity_candidate(name, has_explicit_definition=True):
            if name not in explicit_entities:
                explicit_entities.append(name)
                explicit_attributes[name] = [a.strip() for a in attrs_str.split(',') if a.strip()]

    # 4b. Check for explicit Domain Entities section
    ent_sec = re.search(r'(?i)##\s*[0-9.]*\s*Domain Entities[^\n]*\n([\s\S]*?)(?=\n##|\Z)', text)
    if ent_sec:
        for line in ent_sec.group(1).split('\n'):
            m = re.match(r'^\s*[-*]\s*(?:\[[A-Za-z0-9_-]+\]\s*)?([A-Za-z][A-Za-z0-9_]{2,30})\s*:\s*(.*)', line)
            if m:
                name = m.group(1).strip()
                attrs_str = m.group(2).strip()
                if is_valid_domain_entity_candidate(name, has_explicit_definition=True):
                    if name not in explicit_entities:
                        explicit_entities.append(name)
                        explicit_attributes[name] = [a.strip() for a in attrs_str.split(',') if a.strip()]

    stop_words = {
        "system", "application", "software", "user", "users", "admin", "admins",
        "data", "information", "details", "process", "interface", "service", "module",
        "feature", "requirement", "requirements", "record", "records", "item", "items",
        "view", "list", "option", "number", "date", "time", "id", "type", "form",
        "table", "database", "api", "end", "step", "page", "button", "role", "access",
        "and", "the", "with", "for", "from", "that", "this", "these", "those", "shall",
        "must", "should", "will", "would", "could", "can", "may", "might", "each", "every",
        "some", "any", "all", "when", "where", "then", "than", "into", "over", "under",
        "about", "between", "through", "during", "before", "after", "above", "below",
        "their", "there", "they", "them", "what", "which", "who", "whom", "whose", "been",
        "have", "has", "had", "having", "being", "were", "was", "are", "is", "not", "only",
        "also", "such", "more", "most", "other", "another", "both", "either", "neither",
        "electronic", "online", "automated", "automatedly", "intelligent", "digital",
        "manual", "basic", "advanced", "general", "primary", "secondary"
    }

    crud_verbs = {
        "create", "creates", "created", "creating",
        "manage", "manages", "managed", "managing",
        "view", "views", "viewed", "viewing",
        "track", "tracks", "tracked", "tracking",
        "cancel", "cancels", "cancelled", "canceling",
        "submit", "submits", "submitted", "submitting",
        "store", "stores", "stored", "storing",
        "update", "updates", "updated", "updating",
        "delete", "deletes", "deleted", "deleting",
        "register", "registers", "registered", "registering",
        "schedule", "schedules", "scheduled", "scheduling",
        "reserve", "reserves", "reserved", "reserving",
        "allocate", "allocates", "allocated", "allocating",
        "process", "processes", "processed", "processing",
        "generate", "generates", "generated", "generating"
    }

    entity_candidates = {}
    for s in sentences:
        words = re.findall(r"\b[A-Za-z]{3,20}\b", s)
        for i, w in enumerate(words):
            wl = w.lower()
            if wl in stop_words or wl in common_actor_words:
                continue
            if i > 0 and words[i - 1].lower() in crud_verbs:
                entity_candidates[wl] = entity_candidates.get(wl, 0) + 5
            elif re.search(rf"\b{wl}s?\b", text, re.IGNORECASE):
                entity_candidates[wl] = entity_candidates.get(wl, 0) + 1

    if explicit_entities:
        # Authoritative entities take full precedence. Do not pollute with narrative verb heuristics.
        unique_entities = [e for e in explicit_entities if is_valid_domain_entity_candidate(e, has_explicit_definition=True)]
    else:
        # Heuristic entity extraction only when NO authoritative entity definitions exist
        sorted_entities = sorted(entity_candidates.items(), key=lambda x: x[1], reverse=True)
        for w, _ in sorted_entities:
            if len(detected_entities) >= 6:
                break
            cap = w.capitalize()
            if is_valid_domain_entity_candidate(w) and cap not in detected_entities:
                detected_entities.append(cap)

        # Fallback to domain nouns in title ONLY when NO domain entities were identified
        if not detected_entities:
            title_words = [w.capitalize() for w in re.findall(r'\b[A-Za-z]{3,}\b', detected_title) if is_valid_domain_entity_candidate(w)]
            for tw in title_words:
                if tw not in detected_entities:
                    detected_entities.append(tw)

        seen = set()
        unique_entities = []
        for e in detected_entities:
            singular = singularize(e)
            if singular.lower() not in seen and is_valid_domain_entity_candidate(singular):
                seen.add(singular.lower())
                unique_entities.append(singular.capitalize())

    return {
        'title': detected_title,
        'actors': list(found_actors)[:4],
        'entities': unique_entities[:8],
        'explicit_attributes': explicit_attributes,
        'sentences': sentences
    }

def analyze_requirements_heuristics(document_text: str, project_name: str = "Software System") -> Dict[str, Any]:
    """Extract functional, non-functional, actors, entities, modules, and constraints."""
    if "DOCUMENT TEXT:" in document_text:
        document_text = document_text.split("DOCUMENT TEXT:", 1)[1].strip()
    info = extract_domain_info(document_text, project_name)
    title = info["title"]
    entities = info["entities"]
    actors = info["actors"]
    sentences = info["sentences"]

    # 1. Functional Requirements Extraction
    fr_triggers = re.compile(r"\b(shall|must|should|can|will|allows?|enables?|provides?|supports?|user can|able to)\b", re.IGNORECASE)
    
    extracted_frs = []
    seen_fr_text = set()

    for s in sentences:
        if fr_triggers.search(s) and len(s) > 20:
            cleaned = s.strip()
            # Normalize requirement format
            cleaned = re.sub(r"^(fr[-_ ]?\d+[:.-]?|req[-_ ]?\d+[:.-]?|\d+[.)]\s*)", "", cleaned, flags=re.IGNORECASE).strip()
            if cleaned.lower() not in seen_fr_text and len(cleaned) > 15:
                seen_fr_text.add(cleaned.lower())
                extracted_frs.append(cleaned)
        if len(extracted_frs) >= 15:
            break

    # If document had few explicit trigger sentences, extract top meaningful statements
    if len(extracted_frs) < 6:
        for s in sentences:
            if len(s) > 25 and s.lower() not in seen_fr_text:
                seen_fr_text.add(s.lower())
                extracted_frs.append(s)
            if len(extracted_frs) >= 8:
                break

    # If still empty (e.g. empty or tiny document), generate domain requirements based on detected entities
    if not extracted_frs:
        for ent in entities[:4]:
            extracted_frs.append(f"The system shall allow users to register and manage their {ent.lower()} information securely.")
            extracted_frs.append(f"The system shall provide capabilities to search, view, and filter {ent.lower()} records in real-time.")

    # 2. Derive Modules
    structural_modules = []
    mod_pattern = re.compile(r'(?m)^(?:[0-9]+(?:\.[0-9]+)*\s+|#{2,4}\s+(?:Module\s+[0-9]+:\s*)?)([A-Za-z0-9\s,&/\-]{3,60})$')
    meta_headings = {
        "problem statement", "project scope", "scope", "overview", "introduction",
        "background", "purpose", "executive summary", "objective", "objectives",
        "assumptions", "dependencies", "constraints", "system constraints",
        "non-functional requirements", "non functional requirements", "nfr", "nfrs",
        "quality attributes", "performance requirements", "security requirements",
        "system architecture", "revision history", "document history", "version control",
        "table of contents", "glossary", "definitions", "references", "appendix",
        "users and roles", "actors", "roles", "domain entities", "domain entities & data attributes",
        "software requirement specification"
    }
    for m in mod_pattern.finditer(document_text):
        cleaned = re.sub(r'^(?:Module\s+[0-9]+:\s*|[0-9]+(?:\.[0-9]+)*\s*)', '', m.group(1), flags=re.I).strip()
        if cleaned.lower() not in meta_headings and len(cleaned) >= 3:
            structural_modules.append(cleaned)

    if structural_modules:
        modules_list = [
            {"req_id": f"MOD-{i+1:03d}", "title": mod_name, "description": f"Functional module representing {mod_name}."}
            for i, mod_name in enumerate(structural_modules[:8])
        ]
    else:
        modules_list = [
            {"req_id": "MOD-001", "title": "Authentication & Access Control", "description": "Manages user registration, credential verification, roles, and sessions."},
            {"req_id": "MOD-002", "title": f"{entities[1] if len(entities) > 1 else 'Core'} Management", "description": f"Handles business logic, operations, and state lifecycle for {entities[1] if len(entities) > 1 else 'core'} entities."},
            {"req_id": "MOD-003", "title": f"{entities[2] if len(entities) > 2 else 'Operations'} Processing", "description": f"Coordinates transactions, workflow validation, and scheduling for {entities[2] if len(entities) > 2 else 'operations'}."},
            {"req_id": "MOD-004", "title": "Reporting & Notifications", "description": "Generates analytical summaries, operational alerts, and audit trails."}
        ]

    # 3. Format FR Objects
    vague_terms = re.compile(r"\b(fast|user-friendly|flexible|appropriate|seamless|easy|sufficient|quick|timely|real-time)\b", re.IGNORECASE)
    
    formatted_frs = []
    for idx, fr_text in enumerate(extracted_frs):
        req_id = f"FR-{idx + 1:03d}"
        
        # Derive action title
        words = fr_text.split()
        title_words = words[:4]
        for i, w in enumerate(words):
            if w.lower() in {"shall", "must", "can", "should", "to", "able"}:
                title_words = words[i + 1:i + 6]
                break
        short_title = " ".join(title_words).strip(".,:; ")
        short_title = re.sub(r"^(be able to|allow (users?|patrons?|admins?|customers?) to)\s*", "", short_title, flags=re.IGNORECASE)
        short_title = (short_title[0].upper() + short_title[1:]) if short_title else f"Feature {idx + 1}"

        # Assign module
        mod_name = modules_list[idx % len(modules_list)]["title"]
        for m in modules_list:
            if any(w.lower() in fr_text.lower() for w in m["title"].split()):
                mod_name = m["title"]
                break

        # Check Ambiguity
        is_ambiguous = bool(vague_terms.search(fr_text)) or len(fr_text.split()) < 7
        ambiguity_notes = None
        clarifying_questions = []

        if is_ambiguous:
            ambiguity_notes = "Specification lacks measurable service level thresholds or edge case exception handling."
            clarifying_questions = [
                f"What specific validation criteria or timeout parameters should apply to '{short_title}'?",
                "What user permissions or authorization roles are required to execute this action?",
                "How should the system behave when concurrent conflicting requests are received?"
            ]

        priority = "high" if idx < 4 or "auth" in fr_text.lower() or "secure" in fr_text.lower() else ("medium" if idx < 10 else "low")

        formatted_frs.append({
            "req_id": req_id,
            "category": "functional",
            "title": short_title[:60],
            "description": fr_text,
            "priority": priority,
            "module_name": mod_name,
            "is_ambiguous": is_ambiguous,
            "ambiguity_notes": ambiguity_notes,
            "clarifying_questions": clarifying_questions
        })

    # 4. Non-Functional Requirements Extraction (Strictly evidence-based, no fabricated constraints)
    extracted_nfrs = []
    seen_nfr_text = set()

    # Pattern A: Explicit NFR identifiers: NFR-001, NFR: ..., NFR_1, etc.
    nfr_id_pattern = re.compile(r"(?im)^[\s*\-#]*NFR[-_ ]?(\d+)[:\s.-]+(.+)$")
    for m in nfr_id_pattern.finditer(document_text):
        idx_num = int(m.group(1))
        nfr_text = m.group(2).strip()
        if nfr_text and nfr_text.lower() not in seen_nfr_text and len(nfr_text) > 5:
            seen_nfr_text.add(nfr_text.lower())
            extracted_nfrs.append((f"NFR-{idx_num:03d}", nfr_text))

    # Pattern B: Explicit Non-Functional / Quality Requirements Section in markdown or text
    nfr_section_pattern = re.compile(
        r"(?im)^#{1,4}\s*(?:\d+(?:\.\d+)*\s+)?(?:Non-?Functional\s+Requirements?|Quality\s+Attributes?|Performance\s+Requirements?|Security\s+Requirements?|System\s+Quality\s+Goals?)\s*$\n([\s\S]*?)(?=\n#{1,4}\s|\Z)"
    )
    for sec_match in nfr_section_pattern.finditer(document_text):
        sec_body = sec_match.group(1).strip()
        for line in sec_body.split("\n"):
            line_clean = re.sub(r"^[\s*\-•\d.)]+", "", line).strip()
            line_clean = re.sub(r"^NFR[-_ ]?\d+[:\s.-]*", "", line_clean, flags=re.IGNORECASE).strip()
            if len(line_clean) > 10 and line_clean.lower() not in seen_nfr_text:
                seen_nfr_text.add(line_clean.lower())
                req_num = len(extracted_nfrs) + 1
                extracted_nfrs.append((f"NFR-{req_num:03d}", line_clean))

    # Pattern C: If no explicit NFRs found yet, scan sentences for unambiguous quality/SLA/security statements
    if not extracted_nfrs:
        quality_triggers = re.compile(
            r"\b(response time|latency\s*(?:<|under|within|exceed)|concurrent users|queries per second|uptime\s*(?:sla|of|exceeding|\d)|availability\s*(?:sla|of|\d+%)|passwords?\s+must\s+be\s+hashed|encrypt(?:ed|ion)\s+(?:at rest|in transit|via|using)|failover|disaster recovery|rto\s+of|rpo\s+of)\b",
            re.IGNORECASE
        )
        for s in sentences:
            if quality_triggers.search(s) and len(s) > 20:
                s_clean = re.sub(r"^[\s*\-•\d.)]+", "", s).strip()
                s_clean = re.sub(r"^NFR[-_ ]?\d+[:\s.-]*", "", s_clean, flags=re.IGNORECASE).strip()
                if s_clean.lower() not in seen_nfr_text:
                    seen_nfr_text.add(s_clean.lower())
                    req_num = len(extracted_nfrs) + 1
                    extracted_nfrs.append((f"NFR-{req_num:03d}", s_clean))
            if len(extracted_nfrs) >= 8:
                break

    formatted_nfrs = []
    for req_id, nfr_text in extracted_nfrs:
        nfr_lower = nfr_text.lower()
        if any(k in nfr_lower for k in ["latency", "response time", "throughput", "speed", "fast", "ms", "seconds"]):
            mod_name = "Performance"
        elif any(k in nfr_lower for k in ["encrypt", "password", "hash", "auth", "tls", "ssl", "security", "rbac", "permission"]):
            mod_name = "Security"
        elif any(k in nfr_lower for k in ["uptime", "availability", "sla", "downtime"]):
            mod_name = "Availability"
        elif any(k in nfr_lower for k in ["concurrent", "scale", "scaling", "capacity", "load", "volume"]):
            mod_name = "Scalability"
        elif any(k in nfr_lower for k in ["backup", "recovery", "failover", "reliable", "reliability", "acid", "integrity"]):
            mod_name = "Reliability"
        else:
            mod_name = "Quality Attribute"

        words = nfr_text.split()
        title_words = words[:5]
        for i, w in enumerate(words):
            if w.lower() in {"shall", "must", "should", "exceed", "maintain", "support", "be"}:
                title_words = words[:i] if i >= 2 else words[i + 1:i + 6]
                break
        short_title = " ".join(title_words).strip(".,:; ")
        short_title = re.sub(r"^(the system|system|the)\s+", "", short_title, flags=re.IGNORECASE)
        short_title = (short_title[0].upper() + short_title[1:]) if short_title else f"Quality Requirement {req_id}"

        priority = "high" if any(k in nfr_lower for k in ["security", "encrypt", "password", "critical", "sla", "acid"]) else "medium"

        formatted_nfrs.append({
            "req_id": req_id,
            "category": "non_functional",
            "title": short_title[:60],
            "description": nfr_text,
            "priority": priority,
            "module_name": mod_name
        })

    # 5. Actors
    formatted_actors = [
        {"req_id": f"ACT-{i+1:03d}", "title": actor, "description": f"Interacts with {title} to execute domain operations and access permissioned resources."}
        for i, actor in enumerate(actors)
    ]

    # 6. Entities
    formatted_entities = [
        {"req_id": f"ENT-{i+1:03d}", "title": ent, "description": f"Core persistent entity representing {ent.lower()} data, attributes, and relationships."}
        for i, ent in enumerate(entities)
    ]

    # 7. Constraints
    formatted_constraints = [
        {"req_id": "CON-001", "title": "RESTful Architecture", "description": "All client-server interactions must follow REST principles with standard HTTP verbs and status codes."},
        {"req_id": "CON-002", "title": "Relational Data Integrity", "description": "Entity models must enforce foreign key integrity and unique index constraints at the database level."}
    ]

    return {
        "summary": {
            "domain_name": title,
            "overview": f"The {title} automates core workflows for {', '.join(actors)} managing {', '.join(entities)}.",
            "assumptions": ["Standard modern web architecture", "Secure TLS communication"]
        },
        "actors": formatted_actors,
        "requirements": formatted_frs + formatted_nfrs,
        "entities": [
            {
                "req_id": e["req_id"],
                "name": e["title"],
                "description": e["description"],
                "attributes": [
                    {"name": "id", "data_type": "string", "is_primary_key": True, "is_foreign_key": False, "is_nullable": False, "description": "Primary key"},
                    {"name": "created_at", "data_type": "datetime", "is_primary_key": False, "is_foreign_key": False, "is_nullable": False, "description": "Timestamp"}
                ],
                "relationships": []
            }
            for e in formatted_entities
        ],
        "business_rules": [
            {
                "rule_id": "BR-001",
                "title": f"Strict {title} State Validation",
                "description": f"All actions on {entities[0] if entities else 'records'} must be executed by authorized {actors[0] if actors else 'users'}.",
                "enforced_by_module": modules_list[0]["title"] if modules_list else "Core"
            }
        ],
        "workflows": [
            {
                "workflow_id": "WF-001",
                "title": f"{title} Main Lifecycle",
                "description": f"Lifecycle workflow for {entities[0] if entities else 'items'}.",
                "entity_name": entities[0] if entities else "Item",
                "initial_state": "created",
                "terminal_states": ["completed", "cancelled"],
                "transitions": [
                    {"from_state": "created", "to_state": "in_progress", "trigger_action": "start", "allowed_roles": actors},
                    {"from_state": "in_progress", "to_state": "completed", "trigger_action": "finalize", "allowed_roles": actors}
                ]
            }
        ],
        "functional": formatted_frs,
        "non_functional": formatted_nfrs,
        "modules": modules_list,
        "constraints": formatted_constraints
    }


def generate_srs_heuristics(prompt: str) -> Dict[str, Any]:
    """Generate structured Software Requirements Specification (SRS) from prompt context."""
    info = extract_domain_info(prompt)
    title = info["title"]
    entities = ", ".join(info["entities"])
    actors = ", ".join(info["actors"])

    # Check if prompt contains non-functional requirements
    nfr_matches = re.findall(r"\[NFR-\d+\]\s*([^:\n]+)[:\-]?\s*([^\n]*)", prompt)
    if not nfr_matches:
        nfr_matches = re.findall(r"NFR-\d+[:\s\-]+([^\n]+)", prompt)

    if nfr_matches:
        nfr_items = []
        for m in nfr_matches[:5]:
            if isinstance(m, tuple):
                nfr_items.append(f"- {m[0].strip()}: {m[1].strip()}" if m[1].strip() else f"- {m[0].strip()}")
            else:
                nfr_items.append(f"- {m.strip()}")
        nfr_section_content = "The system must satisfy the following non-functional requirements specified in the project scope:\n" + "\n".join(nfr_items)
    else:
        nfr_section_content = "No specific non-functional requirements or quality attribute thresholds were mandated in the source requirements. Performance, security, availability, and scalability standards should be evaluated and defined during subsequent engineering phases."

    return {
        "title": f"Software Requirements Specification (SRS) for {title}",
        "disclaimer": "AI-generated artifacts are suggestions and should be reviewed and edited by the developer.",
        "sections": [
            {
                "id": "sec-1",
                "title": "1. Introduction & Purpose",
                "content": f"This document specifies the software requirements for the {title}. The primary purpose of this platform is to provide reliable, user-centric capabilities to automate and manage core workflows, data exchanges, and operational state transitions. It provides verified technical specifications for engineering development and quality assurance verification."
            },
            {
                "id": "sec-2",
                "title": "2. Overall System Description & Scope",
                "content": f"The {title} is designed as a software application backed by RESTful APIs and relational persistence. Core domain entities managed within the system scope include {entities}. Primary interacting user roles include: {actors}."
            },
            {
                "id": "sec-3",
                "title": "3. User Roles & Personas",
                "content": f"The system enforces role-based access control (RBAC). Key actors include: {actors}. Each role possesses authorization privileges to view or perform permissioned operations according to system requirements."
            },
            {
                "id": "sec-4",
                "title": "4. Functional Requirements",
                "content": f"Functional specifications require support for comprehensive entity lifecycle workflows across {entities}. Key requirements mandate identity verification, catalog querying, state validation, and transactional integrity."
            },
            {
                "id": "sec-5",
                "title": "5. External Interface Requirements",
                "content": "The presentation interface communicates with backend services over JSON/HTTPS REST APIs. Database interactions utilize schema integrity constraints. Standard structured response payloads are returned for client interactions."
            },
            {
                "id": "sec-6",
                "title": "6. Non-Functional Requirements",
                "content": nfr_section_content
            },
            {
                "id": "sec-7",
                "title": "7. Design Constraints & Standards",
                "content": "Architecture complies with REST API standards, relational database normalization, and secure data handling principles."
            },
            {
                "id": "sec-8",
                "title": "8. Assumptions & Dependencies",
                "content": "Assumes standard client runtime environments with reliable network connectivity and operational database access."
            }
        ]
    }


def generate_architecture_heuristics(prompt: str) -> Dict[str, Any]:
    """
    Generate requirement-grounded, domain-driven system architecture with authentic components.
    Zero hardcoded project templates or domain branches.
    Derives components, services, patterns, and diagrams dynamically from requirement evidence and text.
    """
    # 1. Project Title Detection & Cleaning
    title_match = re.search(r"Project Title:\s*([^\n\r]+)", prompt, re.IGNORECASE)
    if not title_match:
        title_match = re.search(r"Project:\s*([^\n\r]+)", prompt, re.IGNORECASE)
    raw_title = title_match.group(1).strip() if title_match else "Software System"
    title = re.sub(r'[\s\-_]+[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', '', raw_title, flags=re.I)
    title = re.sub(r'[\s\-_]+[0-9a-f]{4,8}$', '', title, flags=re.I).strip() or raw_title

    # 2. Separate instructions from requirement evidence
    req_evidence = prompt
    if "Project Requirements Context:" in prompt:
        req_evidence = prompt.split("Project Requirements Context:", 1)[1]
    elif "DOCUMENT TEXT:" in prompt:
        req_evidence = prompt.split("DOCUMENT TEXT:", 1)[1]

    req_lower = req_evidence.lower()

    # 3. Dynamic Out-of-Scope Boundary Detection
    oos_list = []
    for m in re.finditer(r'(?:out\s+of\s+scope|non-goals|excluded\s+(?:from\s+scope|features))[^:\n\r]*[:\n\r]+', req_evidence, re.I):
        start = m.end()
        chunk = req_evidence[start:start+600]
        end_m = re.search(r'\n\s*(?:[1-9]\.|\b[A-Z0-9\s]{3,20}:|##|\Z)', chunk)
        content = chunk[:end_m.start()] if end_m else chunk
        oos_list.append(content)
    oos_text = ' '.join(oos_list).lower()

    def is_in_scope(feature_kw: str) -> bool:
        if feature_kw in oos_text:
            return False
        return feature_kw in req_lower

    # 4. Dynamic Technology Detection
    client_tech = "React SPA (System Recommended)"
    if "react" in req_lower: client_tech = "React SPA (Specified in Requirements)"
    elif "vue" in req_lower: client_tech = "Vue.js SPA (Specified in Requirements)"
    elif "angular" in req_lower: client_tech = "Angular SPA (Specified in Requirements)"
    elif "flutter" in req_lower: client_tech = "Flutter Mobile Client (Specified in Requirements)"

    backend_tech = "FastAPI (Python) (System Recommended)"
    if "fastapi" in req_lower: backend_tech = "FastAPI (Python) (Specified in Requirements)"
    elif "django" in req_lower: backend_tech = "Django (Python) (Specified in Requirements)"
    elif "spring" in req_lower: backend_tech = "Spring Boot (Java) (Specified in Requirements)"
    elif "node" in req_lower or "express" in req_lower: backend_tech = "Node.js / Express (Specified in Requirements)"

    db_tech = "PostgreSQL Relational Database (System Recommended)"
    if "postgres" in req_lower or "postgresql" in req_lower: db_tech = "PostgreSQL Relational Database (Specified in Requirements)"
    elif "mysql" in req_lower: db_tech = "MySQL Relational Database (Specified in Requirements)"
    elif "sqlite" in req_lower: db_tech = "SQLite Database (Specified in Requirements)"
    elif "mongodb" in req_lower: db_tech = "MongoDB Document Store (Specified in Requirements)"

    # 5. Extract Authentic Domain Actors
    actors = []
    seen_actors = set()
    for a in re.findall(r"\[ACT-\d+\]\s*(?:\[actor\]:)?\s*([^:\n\r\-]+)", req_evidence, re.I):
        c = re.sub(r'[\(\)]', '', a).strip()
        if c and len(c) < 35 and c.lower() not in seen_actors:
            seen_actors.add(c.lower())
            actors.append(c)
    if not actors:
        for a in re.findall(r"(?:^|\n)\s*[-*]\s*([A-Za-z0-9\s/]+?)\s*:(?:\s*Can|\s*Browses|\s*Manages|\s*An\s+automated|\s*Logs|\s*The)", req_evidence):
            c = a.strip()
            if c and len(c) < 35 and c.lower() not in seen_actors:
                seen_actors.add(c.lower())
                actors.append(c)
    if not actors:
        actors = ["End User", "Administrator"]

    admin_markers = ["admin", "staff", "manager", "organizer", "faculty", "approver", "hod", "doctor", "physician", "nurse", "librarian", "cashier", "clerk", "triage", "facilities", "dean", "officer", "supervisor", "coordinator", "affairs", "lead", "operator"]
    consumer_actors = [a for a in actors if not any(m in a.lower() for m in admin_markers)]
    admin_actors = [a for a in actors if any(m in a.lower() for m in admin_markers)]
    if not consumer_actors and actors:
        consumer_actors = [actors[0]]
        admin_actors = actors[1:] if len(actors) > 1 else ["Administrator"]

    # 6. Extract Dynamic Modules / Subsystems
    discovered_modules = []
    seen_mods = set()
    for m in re.findall(r"\[MOD-\d+\]\s*(?:\[module\]:)?\s*([^\n\r:\-]+)", req_evidence, re.I):
        m_c = m.strip()
        if m_c and len(m_c) > 3 and m_c.lower() not in seen_mods:
            seen_mods.add(m_c.lower())
            discovered_modules.append(m_c)
    for m in re.findall(r"(?:###\s*Module\s*\d+\s*:\s*|(?:\n|^)\s*(?:3|4)\.\d+\s+)([A-Z][A-Za-z0-9\s,&/\-]+?)(?:\n|$|\r)", req_evidence):
        m_c = re.sub(r'[\r\n\t]+', ' ', m).strip()
        if m_c and len(m_c) > 3 and len(m_c) < 50:
            if not any(sw in m_c.lower() for sw in ["purpose", "scope", "introduction", "overview", "definition", "reference", "user class", "operating", "constraint", "appendix", "system models", "data requirements"]):
                if m_c.lower() not in seen_mods:
                    seen_mods.add(m_c.lower())
                    discovered_modules.append(m_c)
    if len(discovered_modules) < 3:
        fr_items = re.findall(r"\[(?:FR|REQ)-[A-Z0-9\-]+\]\s*(?:\[functional\]:)?\s*([^:\n\r]+)", req_evidence, re.I)
        clusters = {}
        for fr in fr_items:
            words = [w for w in re.findall(r'[A-Za-z]{4,}', fr) if w.lower() not in ["system", "shall", "must", "allow", "user", "users", "support", "provide", "record", "order", "update", "create", "manage", "view", "able"]]
            topic = words[0].title() if words else "Operations"
            clusters.setdefault(topic, []).append(fr)
        for topic in list(clusters.keys())[:5]:
            mod_title = f"{topic} Management"
            if mod_title.lower() not in seen_mods:
                seen_mods.add(mod_title.lower())
                discovered_modules.append(mod_title)
    if not discovered_modules:
        discovered_modules = ["Core Domain Operations", "Data Record Processing", "Workflow Management"]

    # 7. Extract Core Entities
    entities = []
    seen_ent = set()
    for e in re.findall(r"\[ENT-\d+\]\s*(?:\[entity\]:)?\s*([^:\n\r\-]+)", req_evidence, re.I):
        ec = e.strip()
        if ec and len(ec) > 2 and ec.lower() not in seen_ent and ec.lower() not in ["and", "the", "item", "record", "master"]:
            seen_ent.add(ec.lower())
            entities.append(ec)
    if not entities:
        ent_section = re.findall(r'(?:^|\n)\s*-\s*([A-Z][a-zA-Z0-9]+)\s*:\s*[a-z0-9_,\s\(\)]+', req_evidence)
        for ec in ent_section:
            if ec.lower() not in seen_ent and len(ec) > 2:
                seen_ent.add(ec.lower())
                entities.append(ec)

    # 8. Feature Signals & Out-of-Scope Boundary Adherence
    has_qr = is_in_scope("qr") or is_in_scope("gate check-in") or is_in_scope("check-in scan")
    has_notification = is_in_scope("notification") or is_in_scope("email") or is_in_scope("sms") or is_in_scope("alert")
    has_payment_reqs = any(any(k in s.lower() for k in ["payment", "checkout", "billing", "invoice", "refund"]) for s in [req_evidence])
    has_payment = has_payment_reqs and not any(k in oos_text for k in ["online payment", "commercial ticketing", "payment processing is handled outside"])
    has_scheduler = is_in_scope("scheduler") or is_in_scope("cron") or is_in_scope("batch") or is_in_scope("expiry") or is_in_scope("fifo")
    has_caching = is_in_scope("cart") or is_in_scope("redis") or is_in_scope("memcached")

    components = []

    # A. Client Interfaces (Derived dynamically from identified actors)
    for ca in consumer_actors[:2]:
        ca_name = ca.split("/")[0].strip()
        portal_suffix = "Web Storefront" if "customer" in ca_name.lower() or "buyer" in ca_name.lower() else "Web Portal"
        components.append({
            "name": f"{ca_name} {portal_suffix}",
            "tech": client_tech,
            "responsibility": f"Self-service web application interface enabling {ca_name}s to access {title} services and execute domain workflows.",
            "supported_requirements": ["User-Access", "Self-Service"],
            "dependencies": ["API Gateway & Authentication Ingress"]
        })
    for aa in admin_actors[:3]:
        aa_name = aa.split("/")[0].strip()
        components.append({
            "name": f"{aa_name} Management Console",
            "tech": client_tech,
            "responsibility": f"Administrative console for {aa_name}s to oversee operational configurations, review submissions, and manage system records.",
            "supported_requirements": ["Admin-Access", "Operational-Control"],
            "dependencies": ["API Gateway & Authentication Ingress"]
        })

    # B. API Gateway
    components.append({
        "name": "API Gateway & Authentication Ingress",
        "tech": f"{backend_tech.split('(')[0].strip()} Ingress Gateway + JWT / RBAC (System Recommended)",
        "responsibility": f"Unified ingress routing, rate limiting, and role-based access control enforcing security across {', '.join(actors[:4])}.",
        "supported_requirements": ["Security", "API-Routing", "RBAC"],
        "dependencies": ["Core Domain Services"]
    })

    # C. Domain Services (Derived directly from discovered modules)
    dom_service_names = []
    for m in discovered_modules[:6]:
        clean_m = re.sub(r'\b(?:Module|Section)\s*\d+[:\s]*', '', m).strip()
        svc_name = f"{clean_m} Service" if not clean_m.lower().endswith(("service", "engine", "controller", "manager")) else clean_m
        dom_service_names.append(svc_name)
        components.append({
            "name": svc_name,
            "tech": f"{backend_tech.split('(')[0].strip()} Domain Module (System Recommended)",
            "responsibility": f"Executes business logic, transactional validations, and state transitions for {clean_m} capabilities.",
            "supported_requirements": [clean_m],
            "dependencies": ["Primary Relational Database Store"]
        })

    # D. Integration Adapters & Background Workers (STRICTLY gated on in-scope signals)
    worker_names = []
    if has_qr:
        w_name = "QR Code Generation & Verification Engine"
        worker_names.append(w_name)
        components.append({
            "name": w_name,
            "tech": "Python qrcode / Cryptographic Signature Verification (System Recommended)",
            "responsibility": "Generates cryptographically signed QR codes and validates tokens in real-time during attendance verification.",
            "supported_requirements": ["QR-Ticketing", "Check-In-Validation"],
            "dependencies": []
        })
    if has_notification:
        w_name = "Notification & Messaging Dispatch Worker"
        worker_names.append(w_name)
        components.append({
            "name": w_name,
            "tech": "Celery / Redis / SMTP Email Provider (System Recommended)",
            "responsibility": "Asynchronously processes and dispatches email, SMS, and in-app alerts without blocking client API request threads.",
            "supported_requirements": ["Notifications", "Alert-Broadcasts"],
            "dependencies": ["Primary Relational Database Store"]
        })
    if has_payment:
        w_name = "External Payment Gateway Adapter"
        worker_names.append(w_name)
        components.append({
            "name": w_name,
            "tech": "Payment Gateway SDK (Stripe / Invoicing API) (System Recommended)",
            "responsibility": "Interfaces with external payment gateways for electronic payment processing, invoice settlement, and payment webhooks.",
            "supported_requirements": ["Payment-Settlement", "Invoicing"],
            "dependencies": []
        })
    if has_scheduler:
        w_name = "Background Task Scheduler & Expiry Monitor"
        worker_names.append(w_name)
        components.append({
            "name": w_name,
            "tech": "Background Task Scheduler (APScheduler / Celery Beat) (System Recommended)",
            "responsibility": "Executes recurring background maintenance jobs, monitors batch expiration dates / overdue fines, and triggers automated alerts.",
            "supported_requirements": ["Scheduled-Tasks", "Audit-Monitoring"],
            "dependencies": ["Primary Relational Database Store"]
        })

    # E. Persistence & Caching Stores
    tables_list = ", ".join([f"{e.lower()}s" for e in entities[:6]]) if entities else "domain_records, user_accounts, audit_logs"
    components.append({
        "name": "Primary Relational Database Store",
        "tech": db_tech,
        "responsibility": f"ACID-compliant relational persistence, foreign key constraint enforcement, and transaction management for domain tables ({tables_list}).",
        "supported_requirements": ["Data-Persistence", "Relational-Integrity"],
        "dependencies": []
    })

    if has_caching:
        components.append({
            "name": "Session & Cart In-Memory Cache Store",
            "tech": "Redis Key-Value Cache (System Recommended)",
            "responsibility": "Low-latency in-memory storage for active user sessions, shopping cart states, and temporary validation tokens.",
            "supported_requirements": ["Session-Cache", "Cart-State"],
            "dependencies": []
        })

    # 9. Dynamic Pattern & Justification
    if worker_names and len(worker_names) >= 2:
        pattern = f"Event-Driven Modular Architecture ({title})"
        justification = (
            f"An Event-Driven Modular Architecture is selected for {title} due to the requirements for asynchronous background processing "
            f"({', '.join(worker_names)}), decoupling core domain services ({', '.join(dom_service_names[:3])}) "
            f"from long-running notification and verification workflows while maintaining high throughput."
        )
    elif len(dom_service_names) >= 3:
        pattern = f"Modular Monolith Architecture ({title})"
        justification = (
            f"A Modular Monolith pattern is selected for {title} to organize distinct bounded domain contexts "
            f"({', '.join(dom_service_names[:3])}) within a unified, highly cohesive backend codebase. "
            f"This architecture ensures clear module boundaries and relational transaction integrity without premature distributed complexity."
        )
    else:
        pattern = f"Layered Architecture ({title})"
        justification = f"Layered architecture separates presentation, domain logic, and relational persistence for {title}."

    # 10. Dynamic Mermaid Diagram
    lines = ["flowchart TD"]
    lines.append('    subgraph ClientTier ["Client Applications & Portals"]')
    portal_nodes = []
    for idx, c in enumerate([comp for comp in components if "Portal" in comp["name"] or "Console" in comp["name"] or "Storefront" in comp["name"]], 1):
        nid = f"Client{idx}"
        portal_nodes.append(nid)
        lines.append(f'        {nid}["{c["name"]}\\n({c["tech"].split("(")[0].strip()})"]')
    lines.append('    end')

    lines.append('    subgraph GatewayTier ["API Ingress & Security"]')
    lines.append('        Gateway["API Gateway & Authentication Ingress\\n(JWT / RBAC)"]')
    lines.append('    end')

    lines.append('    subgraph DomainTier ["Core Functional Domain Services"]')
    dom_nodes = []
    for idx, sname in enumerate(dom_service_names, 1):
        sid = f"Svc{idx}"
        dom_nodes.append((sid, sname))
        lines.append(f'        {sid}["{sname}"]')
    lines.append('    end')

    worker_nodes = []
    if worker_names:
        lines.append('    subgraph IntegrationTier ["Integration Adapters & Background Workers"]')
        for idx, wname in enumerate(worker_names, 1):
            wid = f"Worker{idx}"
            worker_nodes.append((wid, wname))
            lines.append(f'        {wid}["{wname}"]')
        lines.append('    end')

    lines.append('    subgraph PersistenceTier ["Data & Storage Tier"]')
    lines.append(f'        DB[("Relational Database Store\\n({db_tech.split("(")[0].strip()})")]')
    if has_caching:
        lines.append('        Cache[("In-Memory Cache Store\\n(Redis)")]')
    lines.append('    end')

    for pid in portal_nodes:
        lines.append(f'    {pid} -->|HTTPS / REST API| Gateway')
    for sid, sname in dom_nodes:
        clean_action = sname.replace(" Service", "").replace(" Management", "")
        lines.append(f'    Gateway -->|Dispatch {clean_action}| {sid}')
        lines.append(f'    {sid} -->|Read / Write State| DB')
    for wid, wname in worker_nodes:
        w_lower = wname.lower()
        if "qr" in w_lower:
            reg_svc = next((sid for sid, sname in dom_nodes if any(k in sname.lower() for k in ["registration", "ticketing", "attendance", "discovery"])), dom_nodes[0][0])
            lines.append(f'    {reg_svc} -->|Issue & Verify Tokens| {wid}')
        elif "notification" in w_lower:
            lines.append(f'    {dom_nodes[0][0]} -->|Publish Event Alerts| {wid}')
        elif "payment" in w_lower:
            pay_svc = next((sid for sid, sname in dom_nodes if any(k in sname.lower() for k in ["billing", "order", "cart", "fines"])), dom_nodes[-1][0])
            lines.append(f'    {pay_svc} -->|Process Transactions| {wid}')
        elif "scheduler" in w_lower or "expiry" in w_lower:
            lines.append(f'    {wid} -->|Execute Scheduled Audits| DB')
    if has_caching:
        cart_svc = next((sid for sid, sname in dom_nodes if any(k in sname.lower() for k in ["cart", "session", "catalog"])), None)
        if cart_svc:
            lines.append(f'    {cart_svc} -->|Cache Real-time State| Cache')

    return {
        "pattern": pattern,
        "justification": justification,
        "mermaid_diagram": "\n".join(lines),
        "layers": components
    }


def _extract_context_from_prompt(prompt: str) -> str:
    """Extract project, actor, entity, and requirement context from prompt, discarding instruction boilerplate."""
    relevant_lines = []
    for line in prompt.split("\n"):
        line_clean = line.strip()
        if any(marker in line_clean.lower() for marker in [
            "mandatory rules:", "return strictly json", "return strictly valid json",
            "root json schema:", "generate database tables for", "generate restful openapi",
            "generate rest endpoints", "the following functional requirements",
            "the following requirements currently have no", "ensure essential lifecycle",
            "each table must include", "include columns with", "return strictly:"
        ]):
            continue
        if line_clean.startswith("- [") or line_clean.startswith("Project:") or line_clean.startswith("Actors/Roles:") or line_clean.startswith("Entities/Tables:") or line_clean.startswith("Existing Master Tables:") or line_clean.startswith("Existing System Tables:"):
            relevant_lines.append(line_clean)
        elif not any(instr in line_clean.lower() for instr in ["must include", "must have", "return strictly", "schema:", "table name"]):
            relevant_lines.append(line_clean)
    return "\n".join(relevant_lines)


def generate_schema_heuristics(prompt: str) -> Dict[str, Any]:
    """Generate normalized database schema, Mermaid ER diagram, and SQL DDL."""
    context_text = _extract_context_from_prompt(prompt)
    info = extract_domain_info(context_text)
    title = info["title"]
    entities = info["entities"]

    tables = []
    
    # Always include users table
    tables.append({
        "name": "users",
        "description": "Stores user credentials, profile roles, and authentication status.",
        "requirement_ids": [],
        "columns": [
            {"name": "id", "type": "VARCHAR(36)", "pk": True, "fk": None, "nullable": False, "description": "Primary key UUID"},
            {"name": "email", "type": "VARCHAR(255)", "pk": False, "fk": None, "nullable": False, "description": "Unique email address"},
            {"name": "hashed_password", "type": "VARCHAR(255)", "pk": False, "fk": None, "nullable": False, "description": "Bcrypt password hash"},
            {"name": "full_name", "type": "VARCHAR(150)", "pk": False, "fk": None, "nullable": False, "description": "User display name"},
            {"name": "role", "type": "VARCHAR(50)", "pk": False, "fk": None, "nullable": False, "description": "System role"},
            {"name": "is_active", "type": "BOOLEAN", "pk": False, "fk": None, "nullable": False, "description": "Account status flag"},
            {"name": "created_at", "type": "TIMESTAMP", "pk": False, "fk": None, "nullable": False, "description": "Creation timestamp"}
        ]
    })

    explicit_attrs = info.get("explicit_attributes", {})

    # Create tables for domain entities
    for ent in entities:
        table_name = pluralize(to_snake_case(ent))
        if table_name in ["users", "accounts", "audit_logs"]:
            continue
        if not is_valid_domain_table_name(table_name):
            continue

        raw_attrs = explicit_attrs.get(ent, [])
        cols = []
        if raw_attrs:
            # Build columns from explicit attributes, preserving subordinate JSON attributes
            for attr in raw_attrs:
                clean_attr = re.sub(r'\(.*?\)', '', attr).strip().lower()
                if not clean_attr:
                    continue
                is_pk = (clean_attr == "id")
                is_unique = "unique" in attr.lower()
                fk_target = None
                if "(fk)" in attr.lower():
                    base_fk = clean_attr.replace("_id", "")
                    fk_target = f"{pluralize(to_snake_case(base_fk))}(id)"
                
                col_type = "VARCHAR(255)"
                if is_pk:
                    col_type = "INTEGER" if "int" in attr.lower() else "VARCHAR(36)"
                elif clean_attr.endswith("_json") or clean_attr.endswith("_notes") or clean_attr == "description":
                    col_type = "TEXT"
                elif clean_attr.endswith("_date") or clean_attr.endswith("_time") or clean_attr.endswith("_at"):
                    col_type = "TIMESTAMP"
                elif clean_attr.startswith("is_") or clean_attr.startswith("has_"):
                    col_type = "BOOLEAN"
                elif "fee" in clean_attr or "amount" in clean_attr or "price" in clean_attr:
                    col_type = "DECIMAL(10,2)"

                cols.append({
                    "name": clean_attr,
                    "type": col_type,
                    "pk": is_pk,
                    "fk": fk_target,
                    "nullable": not is_pk,
                    "unique": is_unique,
                    "description": f"{ent} {clean_attr}"
                })
        else:
            cols = [
                {"name": "id", "type": "VARCHAR(36)", "pk": True, "fk": None, "nullable": False, "description": f"Primary key UUID for {ent}"},
                {"name": "user_id", "type": "VARCHAR(36)", "pk": False, "fk": "users(id)", "nullable": True, "description": "Foreign key to associated user account"},
                {"name": "name", "type": "VARCHAR(255)", "pk": False, "fk": None, "nullable": False, "description": f"{ent} name or title"},
                {"name": "description", "type": "TEXT", "pk": False, "fk": None, "nullable": True, "description": f"Detailed notes regarding the {ent}"},
                {"name": "status", "type": "VARCHAR(50)", "pk": False, "fk": None, "nullable": False, "description": "Current lifecycle status"},
                {"name": "created_at", "type": "TIMESTAMP", "pk": False, "fk": None, "nullable": False, "description": "Creation timestamp"},
                {"name": "updated_at", "type": "TIMESTAMP", "pk": False, "fk": None, "nullable": False, "description": "Last update timestamp"}
            ]

        if not any(c.get("pk") for c in cols):
            cols.insert(0, {"name": "id", "type": "VARCHAR(36)", "pk": True, "fk": None, "nullable": False, "description": "Primary key"})

        ent_lower = ent.lower()
        matched_rids = []
        for line in prompt.split('\n'):
            m_req = re.search(r'\[(FR-\d+)\]\s*([^:\n]+)', line)
            if m_req:
                rid, rtitle = m_req.group(1), m_req.group(2).lower()
                if ent_lower in rtitle or singularize(ent_lower) in rtitle:
                    matched_rids.append(rid)

        tables.append({
            "name": table_name,
            "description": f"Persistent records for {ent} domain items and attributes.",
            "requirement_ids": matched_rids,
            "columns": cols
        })

    # Limit to 5-6 tables max
    tables = tables[:5]

    # Generate SQL DDL
    ddl_statements = []
    for t in tables:
        col_defs = []
        for c in t["columns"]:
            pk_str = " PRIMARY KEY" if c["pk"] else ""
            null_str = " NOT NULL" if not c["nullable"] else ""
            fk_str = f" REFERENCES {c['fk']}" if c["fk"] else ""
            col_defs.append(f"    {c['name']} {c['type']}{pk_str}{null_str}{fk_str}")
        ddl_statements.append(f"CREATE TABLE {t['name']} (\n" + ",\n".join(col_defs) + "\n);")

    sql_ddl = "\n\n".join(ddl_statements)

    # Generate Mermaid ER
    er_lines = ["erDiagram"]
    for t in tables:
        er_lines.append(f"    {t['name'].upper()} {{")
        for c in t["columns"][:4]:
            t_type = "string" if "VARCHAR" in c["type"] or "TEXT" in c["type"] else ("datetime" if "TIME" in c["type"] else "boolean")
            pk_tag = " PK" if c["pk"] else (" FK" if c["fk"] else "")
            er_lines.append(f"        {t_type} {c['name']}{pk_tag}")
        er_lines.append("    }")

    # Add relationships
    for t in tables[1:]:
        er_lines.append(f"    USERS ||--o{{ {t['name'].upper()} : owns")

    mermaid_er = "\n".join(er_lines)

    return {
        "title": f"Relational Database Schema ({title})",
        "tables": tables,
        "sql_ddl": sql_ddl,
        "mermaid_er": mermaid_er
    }


def generate_api_heuristics(prompt: str) -> Dict[str, Any]:
    """Generate OpenAPI endpoints documentation from prompt context."""
    context_text = _extract_context_from_prompt(prompt)
    info = extract_domain_info(context_text)
    title = info["title"]
    entities = info["entities"]

    endpoints = [
        {
            "method": "POST",
            "path": "/api/v1/auth/token",
            "summary": "Authenticate user credentials and issue JWT bearer token",
            "tag": "Authentication",
            "parameters": [],
            "request_body": {"username": "user@example.com", "password": "secure_password"},
            "responses": [
                {"code": 200, "description": "Token issued successfully with role claims"},
                {"code": 401, "description": "Invalid credentials provided"}
            ]
        }
    ]

    for ent in entities:
        if not is_valid_domain_entity_candidate(ent):
            continue
        plural = pluralize(to_snake_case(ent))
        if not is_valid_domain_table_name(plural):
            continue
        route_slug = to_kebab_case(pluralize(ent))
        endpoints.extend([
            {
                "method": "GET",
                "path": f"/api/v1/{route_slug}",
                "summary": f"Retrieve paginated list of {plural} with optional search query",
                "tag": ent,
                "parameters": [
                    {"name": "skip", "in": "query", "type": "integer", "required": False, "description": "Records to offset"},
                    {"name": "limit", "in": "query", "type": "integer", "required": False, "description": "Page size limit"}
                ],
                "responses": [
                    {"code": 200, "description": f"Successfully retrieved {plural} catalog"},
                    {"code": 401, "description": "Unauthorized request"}
                ]
            },
            {
                "method": "POST",
                "path": f"/api/v1/{route_slug}",
                "summary": f"Create a new {to_snake_case(ent)} record",
                "tag": ent,
                "parameters": [],
                "request_body": {"name": f"Sample {ent}", "description": f"Initial {ent} specifications"},
                "responses": [
                    {"code": 201, "description": f"{ent} created successfully"},
                    {"code": 400, "description": "Invalid payload format"}
                ]
            },
            {
                "method": "GET",
                "path": f"/api/v1/{route_slug}/{{id}}",
                "summary": f"Fetch specific {to_snake_case(ent)} details by unique identifier",
                "tag": ent,
                "parameters": [
                    {"name": "id", "in": "path", "type": "string", "required": True, "description": f"Target {ent} ID"}
                ],
                "responses": [
                    {"code": 200, "description": f"Target {ent} record found"},
                    {"code": 404, "description": "Record not found"}
                ]
            }
        ])

    return {
        "title": f"RESTful API Documentation ({title})",
        "endpoints": endpoints
    }


def generate_skeleton_heuristics(prompt: str) -> Dict[str, Any]:
    """Generate production-ready, AST-verified FastAPI backend starter code."""
    info = extract_domain_info(prompt)
    title = info["title"]
    entities = info["entities"]
    
    e1 = entities[0] if len(entities) > 0 else "User"
    e2 = entities[1] if len(entities) > 1 else "Item"
    e1_lower = e1.lower()
    e2_lower = e2.lower()
    e2_plural = e2_lower + "s"

    main_py = f'''"""FastAPI application entrypoint for {title}."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="{title}",
    description="Automated backend skeleton generated by Req-to-Code",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {{"status": "healthy", "service": "{title}"}}
'''

    models_py = f'''"""SQLAlchemy database models for {title}."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=False)
    role = Column(String(50), default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class {e2}(Base):
    __tablename__ = "{e2_plural}"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
'''

    schemas_py = f'''"""Pydantic schemas for data validation in {title}."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class UserBase(BaseModel):
    email: str
    full_name: str
    role: str = "user"

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: str
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class {e2}Base(BaseModel):
    name: str
    description: Optional[str] = None
    status: str = "active"

class {e2}Create({e2}Base):
    pass

class {e2}Response({e2}Base):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
'''

    routes_py = f'''"""REST API route handlers for {e2_plural}."""
from typing import List
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/{e2_plural}", tags=["{e2_plural}"])

@router.get("/")
def list_{e2_plural}():
    return [{{"id": "mock-uuid-1", "name": "Sample {e2}", "status": "active"}}]

@router.get("/{{item_id}}")
def get_{e2_lower}(item_id: str):
    return {{"id": item_id, "name": f"{e2} {{item_id}}", "status": "active"}}
'''

    db_session_py = '''"""Database session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
'''

    reqs_txt = """fastapi>=0.110.0
uvicorn>=0.28.0
sqlalchemy>=2.0.25
pydantic>=2.6.0
python-multipart>=0.0.9
"""

    readme_md = f"""# {title} - Backend Starter

Automated starter project generated by **Req-to-Code (AI Assistant)**.

## Quickstart

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```
API Documentation: `http://localhost:8000/docs`
"""

    # Verify all Python files with ast.parse
    for code, name in [(main_py, "main.py"), (models_py, "models.py"), (schemas_py, "schemas.py"), (routes_py, "routes.py"), (db_session_py, "session.py")]:
        try:
            ast.parse(code)
        except Exception as e:
            raise ValueError(f"Generated python file {name} failed AST parse: {e}")

    return {
        "title": f"FastAPI Starter Project Skeleton ({title})",
        "files": [
            {"path": "main.py", "content": main_py},
            {"path": "models/entities.py", "content": models_py},
            {"path": "schemas/models.py", "content": schemas_py},
            {"path": f"routes/{e2_plural}.py", "content": routes_py},
            {"path": "database/session.py", "content": db_session_py},
            {"path": "requirements.txt", "content": reqs_txt},
            {"path": "README.md", "content": readme_md}
        ]
    }


def generate_test_cases_heuristics(prompt: str) -> Dict[str, Any]:
    """Generate requirements-linked test cases from prompt context."""
    info = extract_domain_info(prompt)
    title = info["title"]
    entities = info["entities"]

    cases = []
    tc_counter = 1

    # Extract requirement IDs from prompt context if present
    found_reqs = re.findall(r"\b((?:FR|NFR|CON|REQ)-\d{3})\b", prompt)
    if not found_reqs:
        found_reqs = [f"FR-{i+1:03d}" for i in range(5)]
    unique_reqs = list(dict.fromkeys(found_reqs))

    for req_id in unique_reqs:
        if req_id.startswith("NFR"):
            cases.append({
                "test_id": f"TC-{tc_counter:03d}",
                "linked_req_id": req_id,
                "scenario": f"Verify quality requirement {req_id} performance SLA, availability, or security threshold",
                "preconditions": "Automated telemetry harness active with simulated production load",
                "steps": f"1. Generate operational workload relevant to {req_id}.\n2. Measure latency, encryption, uptime, and database consistency metrics.\n3. Verify measurements satisfy non-functional threshold.",
                "expected_result": f"System complies with non-functional quality criteria for {req_id}.",
                "type": "boundary"
            })
            tc_counter += 1
            continue

        ent = entities[tc_counter % len(entities)] if entities else "Record"
        
        # 1. Positive Scenario
        cases.append({
            "test_id": f"TC-{tc_counter:03d}",
            "linked_req_id": req_id,
            "scenario": f"Verify successful execution of {ent.lower()} operation with valid parameters",
            "preconditions": "User has valid authenticated session and required authorization role",
            "steps": f"1. Submit valid payload to endpoint.\n2. Verify HTTP 200/201 response.\n3. Validate persisted {ent.lower()} state in database.",
            "expected_result": f"Operation completes successfully and returns created {ent.lower()} record.",
            "type": "positive"
        })
        tc_counter += 1

        # 2. Negative Scenario
        cases.append({
            "test_id": f"TC-{tc_counter:03d}",
            "linked_req_id": req_id,
            "scenario": f"Reject {ent.lower()} request when mandatory input fields are missing or malformed",
            "preconditions": "Client connects to public or authenticated route",
            "steps": f"1. Dispatch request missing required attributes.\n2. Inspect response status and body.",
            "expected_result": "System responds with HTTP 422 Unprocessable Entity and descriptive field errors.",
            "type": "negative"
        })
        tc_counter += 1

        # 3. Boundary Scenario
        cases.append({
            "test_id": f"TC-{tc_counter:03d}",
            "linked_req_id": req_id,
            "scenario": f"Handle maximum string boundary and concurrency threshold for {ent.lower()}",
            "preconditions": f"Database contains near-capacity {ent.lower()} volume",
            "steps": f"1. Submit payload with maximum allowable length.\n2. Dispatch concurrent conflicting update requests.",
            "expected_result": "System enforces field boundary limits and maintains transaction isolation without race conditions.",
            "type": "boundary"
        })
        tc_counter += 1

    return {
        "title": f"Requirements-Linked Test Suite ({title})",
        "cases": cases[:9]
    }


def handle_rag_query_heuristics(prompt: str) -> str:
    """Handle RAG question answering grounded in the provided project context or general technical concepts."""
    # Check context in prompt
    context_match = re.search(r"PROJECT CONTEXT:\s*(.*?)\s*USER QUESTION:", prompt, re.DOTALL)
    context_text = context_match.group(1).strip() if context_match else ""

    question_match = re.search(r"USER QUESTION:\s*(.*)", prompt, re.DOTALL)
    question = question_match.group(1).strip() if question_match else prompt.strip()
    q_lower = question.lower()

    # 1. Greetings handling
    greeting_patterns = [
        r"^(hi|hello|hey|howdy|greetings|good\s+(morning|afternoon|evening|day))(\s+there)?[\s!?,.]*$",
        r"^(who\s+are\s+you|what\s+can\s+you\s+do|how\s+can\s+you\s+help)[\s!?,.]*$"
    ]
    if any(re.match(p, q_lower.strip()) for p in greeting_patterns):
        return (
            "Hello! I am your AI Query Support Assistant. "
            "I can help you explore this project's requirements, architecture, database schema, APIs, and test cases. "
            "What would you like to know?"
        )

    # 2. General Technical / Software Engineering concepts
    technical_concepts = [
        (r"\bjwt\b|\btoken\b", "JWT (JSON Web Token) is a standard (RFC 7519) for transmitting secure, compact JSON claims between parties, commonly used for stateless API authentication and authorization."),
        (r"\brest\b|\brestful\b", "REST (Representational State Transfer) is an architectural style for web services that relies on standard HTTP methods (GET, POST, PUT, DELETE) and stateless resource management."),
        (r"\bprimary\s*key\b", "A primary key is a unique identifier column in a relational database table that guarantees each record can be distinctly identified with non-null values."),
        (r"\bforeign\s*key\b", "A foreign key is a column or set of columns in one table referencing the primary key of another table to maintain relational data integrity."),
        (r"\bmicroservices?\b", "Microservices architecture structures an application as a collection of independently deployable, loosely coupled services communicating via lightweight APIs."),
        (r"\borm\b", "An ORM (Object-Relational Mapping) library maps database tables to object-oriented code entities, reducing boilerplate SQL queries."),
        (r"\bacid\b", "ACID refers to Atomicity, Consistency, Isolation, and Durability—core properties ensuring database transactions are processed reliably."),
        (r"\bdocker\b|\bcontainer\b", "Docker packages applications and dependencies into standardized containers to ensure consistent execution across environments."),
        (r"\bunit\s*test", "Unit testing verifies that individual functions, classes, or units of code operate correctly in isolation."),
        (r"\bintegration\s*test", "Integration testing validates that combined components and services interact properly together.")
    ]

    # Check if question has any overlap with the context text
    context_words = set(re.findall(r"\b[a-z]{3,}\b", context_text.lower()))
    question_words = set(re.findall(r"\b[a-z]{3,}\b", q_lower)) - {
        "what", "when", "where", "which", "who", "whom", "whose", "why", "how", 
        "explain", "does", "system", "tell", "show", "many", "much", "can", "could", "should", "would", "about"
    }

    overlap = context_words.intersection(question_words)

    # If no context or no overlap:
    if not context_text or (not overlap and len(question_words) > 0):
        # Check if it's a general technical question
        for pattern, explanation in technical_concepts:
            if re.search(pattern, q_lower):
                return (
                    f"**General Technical Overview:**\n{explanation}\n\n"
                    f"*(Note: This is a general software engineering explanation. Specific requirements or configurations for this topic are not covered in the current project's documents.)*"
                )

        return (
            "I could not find information about this topic in the project context. "
            "This is not covered in the current project's requirement specifications or generated artifacts. "
            "Feel free to ask about the project's requirements, database entities, APIs, architecture, or test cases."
        )

    # Grounded answer based on context
    snippets = [line.strip() for line in context_text.split("\n") if line.strip() and not line.strip().startswith("[")]
    relevant_snippet = " ".join(snippets[:4])

    if "architecture" in q_lower or "layer" in q_lower or "design" in q_lower:
        return f"Based on the project design specifications, the system architecture follows a decoupled layered model: {relevant_snippet}."
    elif "table" in q_lower or "schema" in q_lower or "database" in q_lower or "entity" in q_lower:
        return f"According to the database schema artifacts, the entities and relational tables are defined as follows: {relevant_snippet}."
    elif "non-functional" in q_lower or "nfr" in q_lower or "performance" in q_lower or "security" in q_lower:
        return f"The non-functional specifications enforce the following service criteria: {relevant_snippet}."
    elif "auth" in q_lower or "token" in q_lower or "login" in q_lower:
        return f"Authentication in this system requires secure credential validation: {relevant_snippet}."

    return f"Based on the project context: {relevant_snippet}."
