import os
import json
import logging
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.models.project import Project, UploadedFile
from backend.app.models.requirement import ExtractedRequirement
from backend.app.models.artifact import Artifact
from backend.app.models.rag_chunk import DocumentChunk
from backend.app.schemas.rag import QueryRequest, QueryResponse, Citation
from backend.app.services.llm.factory import get_llm_provider

logger = logging.getLogger(__name__)

# Initialize ChromaDB persistent client
try:
    import chromadb
    chroma_client = chromadb.PersistentClient(path=str(settings.CHROMA_DIR))
except Exception as e:
    logger.warning(f"ChromaDB persistent client error: {e}. Fallback to in-memory.")
    chroma_client = None

class RagService:
    @staticmethod
    def _collection_name(project_id: str) -> str:
        return f"project_{project_id.replace('-', '_')}"

    @staticmethod
    def index_project_chunks(project_id: str, db: Session):
        """Index all document chunks, extracted requirements, and generated artifacts for a project into ChromaDB."""
        if not chroma_client:
            return

        coll_name = RagService._collection_name(project_id)
        try:
            # Recreate collection to prevent cross-project or stale data leakage
            try:
                chroma_client.delete_collection(name=coll_name)
            except Exception:
                pass

            collection = chroma_client.create_collection(name=coll_name)

            ids = []
            documents = []
            metadatas = []

            # 1. Document chunks
            chunks = db.query(DocumentChunk).filter(DocumentChunk.project_id == project_id).all()
            for c in chunks:
                ids.append(f"chunk_{c.id}")
                documents.append(c.chunk_text)
                metadatas.append({"source": c.source_file, "type": "document_chunk"})

            # 2. Extracted Requirements
            reqs = db.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == project_id).all()
            for r in reqs:
                ids.append(f"req_{r.id}")
                documents.append(f"[{r.req_id}] {r.title}: {r.description} (Category: {r.category}, Module: {r.module_name or 'General'})")
                metadatas.append({"source": f"Requirement [{r.req_id}]", "type": "requirement"})

            # 3. Artifacts (SRS, Architecture, Database Schema, API, Skeleton Code, Test Cases)
            artifacts = db.query(Artifact).filter(Artifact.project_id == project_id).all()
            for art in artifacts:
                if not art.content_json:
                    continue
                try:
                    content = json.loads(art.content_json)
                    atype = art.artifact_type

                    if atype == "architecture":
                        # Index architecture pattern and justification
                        pattern = content.get("pattern", "Layered Architecture")
                        justification = content.get("justification", "")
                        arch_summary = f"System Architecture Pattern: {pattern}. Justification: {justification}"
                        ids.append("artifact_architecture_overview")
                        documents.append(arch_summary)
                        metadatas.append({"source": "Architecture Design Artifact", "type": "architecture"})

                        # Index each architectural layer
                        for idx, layer in enumerate(content.get("layers", [])):
                            lname = layer.get("name", f"Layer {idx+1}")
                            ltech = layer.get("tech", "")
                            lresp = layer.get("responsibility", "")
                            ids.append(f"artifact_arch_layer_{idx}")
                            documents.append(f"Architecture Layer: {lname}. Technologies: {ltech}. Responsibility: {lresp}")
                            metadatas.append({"source": f"Architecture: {lname}", "type": "architecture"})

                    elif atype == "srs":
                        # Index each section of the Software Requirements Specification
                        for sec in content.get("sections", []):
                            sec_id = sec.get("id", "SEC")
                            sec_title = sec.get("title", "")
                            sec_content = sec.get("content", "")
                            ids.append(f"artifact_srs_{sec_id}")
                            # Keep meaningful length for chunk search
                            documents.append(f"SRS Section {sec_title}: {sec_content[:800]}")
                            metadatas.append({"source": f"SRS: {sec_title}", "type": "srs"})

                    elif atype == "schema":
                        for t in content.get("tables", []):
                            cols = ", ".join([c.get("name", "") for c in t.get("columns", [])])
                            tname = t.get("name", "table")
                            tdesc = t.get("description", "")
                            rids = ", ".join(t.get("requirement_ids", []))
                            ids.append(f"schema_{tname}")
                            documents.append(f"Database table {tname}: {tdesc}. Columns: {cols}. Covered requirements: {rids}")
                            metadatas.append({"source": f"Schema: {tname}", "type": "schema"})

                    elif atype == "api":
                        for idx, ep in enumerate(content.get("endpoints", [])):
                            method = ep.get("method", "GET")
                            path = ep.get("path", "")
                            summary = ep.get("summary", "")
                            rids = ", ".join(ep.get("requirement_ids", []))
                            ids.append(f"api_{idx}")
                            documents.append(f"API {method} {path}: {summary}. Linked requirements: {rids}")
                            metadatas.append({"source": f"API: {path}", "type": "api"})

                    elif atype == "skeleton":
                        for idx, file_obj in enumerate(content.get("files", [])):
                            fpath = file_obj.get("path", "")
                            fdesc = file_obj.get("description", "")
                            ids.append(f"artifact_skeleton_{idx}")
                            documents.append(f"Backend Skeleton File {fpath}: {fdesc}")
                            metadatas.append({"source": f"Backend Code: {fpath}", "type": "skeleton"})

                    elif atype == "testcases":
                        for idx, tc in enumerate(content.get("cases", [])[:40]):
                            tcid = tc.get("test_id", f"TC-{idx+1}")
                            scenario = tc.get("scenario", "")
                            linked = tc.get("linked_req_id", "")
                            ttype = tc.get("type", "")
                            ids.append(f"artifact_test_{idx}")
                            documents.append(f"Test Case [{tcid}] ({ttype}) for {linked}: {scenario}")
                            metadatas.append({"source": f"Test Case [{tcid}]", "type": "testcases"})

                except Exception as ex:
                    logger.warning(f"Error parsing artifact {art.artifact_type} for indexing: {ex}")

            if documents:
                collection.add(ids=ids, documents=documents, metadatas=metadatas)
                logger.info(f"Indexed {len(documents)} items into ChromaDB collection {coll_name}.")
        except Exception as e:
            logger.error(f"Error indexing chunks to ChromaDB: {e}")

    @staticmethod
    def delete_project_collection(project_id: str):
        """Remove ChromaDB collection when a project is deleted."""
        if not chroma_client:
            return
        coll_name = RagService._collection_name(project_id)
        try:
            chroma_client.delete_collection(name=coll_name)
        except Exception:
            pass

    @staticmethod
    def _rewrite_query(question: str, project_name: str, domain_summary: str = "") -> str:
        """Expand vague or overview-style questions using project context to improve retrieval."""
        q_lower = question.lower()
        expanded_parts = [question]

        if "architecture" in q_lower or "system architecture" in q_lower or "design" in q_lower:
            expanded_parts.append(f"{project_name} system architecture layers pattern components services microservices")
        elif "actor" in q_lower or "role" in q_lower or "user classes" in q_lower:
            expanded_parts.append(f"{project_name} actors users roles permissions participants access level responsibilities")
        elif "module" in q_lower or "feature" in q_lower or "component" in q_lower:
            expanded_parts.append(f"{project_name} modules functional requirements system features scope capabilities")
        elif "non-functional" in q_lower or "nfr" in q_lower or "constraint" in q_lower:
            expanded_parts.append(f"{project_name} non-functional requirements performance security latency scalability constraints SLA")
        elif "auth" in q_lower or "login" in q_lower or "password" in q_lower:
            expanded_parts.append(f"{project_name} authentication authorization identity credentials password token session security")
        elif any(k in q_lower for k in ["payment", "fee", "billing", "settlement", "transaction", "payout"]):
            expanded_parts.append(f"{project_name} financial transactions billing payments settlements fee calculations balances")

        return " ".join(expanded_parts)

    @staticmethod
    def _get_direct_artifact_contexts(project_id: str, question: str, db: Session) -> List[Dict[str, str]]:
        """Fetch matching stored artifact or requirement groups for overview-style questions."""
        q_lower = question.lower()
        contexts: List[Dict[str, str]] = []

        # 1. Architecture Overview
        if any(k in q_lower for k in ["architecture", "system architecture", "tech stack", "layers", "design pattern"]):
            arch_art = db.query(Artifact).filter(Artifact.project_id == project_id, Artifact.artifact_type == "architecture").first()
            if arch_art and arch_art.content_json:
                try:
                    c = json.loads(arch_art.content_json)
                    pattern = c.get("pattern", "Layered Architecture")
                    justification = c.get("justification", "")
                    layers_str = "; ".join([f"{l.get('name')}: {l.get('responsibility', '')} (Tech: {l.get('tech', '')})" for l in c.get("layers", [])])
                    snippet = f"Pattern: {pattern}. Justification: {justification}. Layers: {layers_str}."
                    contexts.append({
                        "source": "Architecture Design Artifact",
                        "snippet": snippet[:1000]
                    })
                except Exception:
                    pass

        # 2. Actors / Roles
        if any(k in q_lower for k in ["actor", "actors", "user classes", "roles", "who uses"]):
            actors = db.query(ExtractedRequirement).filter(
                ExtractedRequirement.project_id == project_id,
                ExtractedRequirement.category == "actor"
            ).order_by(ExtractedRequirement.req_id.asc()).all()
            if actors:
                act_str = "; ".join([f"[{a.req_id}] {a.title}: {a.description}" for a in actors])
                contexts.append({
                    "source": "Extracted Actors Specification",
                    "snippet": f"System Actors and Roles: {act_str}"[:1000]
                })

        # 3. Modules / Features
        if any(k in q_lower for k in ["module", "modules", "system features", "functional areas", "list all modules"]):
            reqs = db.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == project_id).all()
            modules_dict = {}
            for r in reqs:
                mod = r.module_name or "General"
                modules_dict.setdefault(mod, []).append(r.title)
            if modules_dict:
                mod_str = "; ".join([f"Module '{m}' ({len(items)} requirements: {', '.join(items[:3])}...)" for m, items in modules_dict.items()])
                contexts.append({
                    "source": "Project Functional Modules",
                    "snippet": f"Identified System Modules: {mod_str}"[:1000]
                })

        # 4. Non-Functional Requirements & Constraints
        if any(k in q_lower for k in ["non-functional", "nfr", "performance", "availability", "sla"]):
            nfrs = db.query(ExtractedRequirement).filter(
                ExtractedRequirement.project_id == project_id,
                ExtractedRequirement.category.in_(["non_functional", "constraint"])
            ).all()
            if nfrs:
                nfr_str = "; ".join([f"[{n.req_id}] {n.title}: {n.description}" for n in nfrs])
                contexts.append({
                    "source": "Non-Functional Requirements & Constraints",
                    "snippet": f"NFRs and System Constraints: {nfr_str}"[:4000]
                })

        # 5. Authentication Details
        if any(k in q_lower for k in ["authentication", "auth method", "login credentials", "how do users log in"]):
            auth_reqs = db.query(ExtractedRequirement).filter(
                ExtractedRequirement.project_id == project_id,
                (ExtractedRequirement.title.ilike("%login%") | ExtractedRequirement.title.ilike("%auth%") | ExtractedRequirement.description.ilike("%login%"))
            ).all()
            if auth_reqs:
                auth_str = "; ".join([f"[{r.req_id}] {r.title}: {r.description}" for r in auth_reqs])
                contexts.append({
                    "source": "Authentication Requirements",
                    "snippet": f"Authentication Specifications: {auth_str}"[:1000]
                })

        # 6. Database Schema Summary
        if any(k in q_lower for k in ["database schema", "list all tables", "all tables", "schema overview"]):
            schema_art = db.query(Artifact).filter(Artifact.project_id == project_id, Artifact.artifact_type == "schema").first()
            if schema_art and schema_art.content_json:
                try:
                    c = json.loads(schema_art.content_json)
                    tables = c.get("tables", [])
                    t_str = "; ".join([f"{t.get('name')}: {t.get('description', '')}" for t in tables])
                    contexts.append({
                        "source": "Database Schema Specification",
                        "snippet": f"Database Tables: {t_str}"[:1000]
                    })
                except Exception:
                    pass

        # 7. API List Overview
        if any(k in q_lower for k in ["list all apis", "api list", "all endpoints", "available endpoints"]):
            api_art = db.query(Artifact).filter(Artifact.project_id == project_id, Artifact.artifact_type == "api").first()
            if api_art and api_art.content_json:
                try:
                    c = json.loads(api_art.content_json)
                    endpoints = c.get("endpoints", [])
                    ep_str = "; ".join([f"{e.get('method')} {e.get('path')}: {e.get('summary', '')}" for e in endpoints[:15]])
                    contexts.append({
                        "source": "API Documentation",
                        "snippet": f"API Endpoints: {ep_str}"[:1000]
                    })
                except Exception:
                    pass

        return contexts

    @staticmethod
    def query_project(project_id: str, request: QueryRequest, db: Session) -> QueryResponse:
        """Execute RAG pipeline: question -> rewrite -> retrieve chunks + direct artifacts -> LLM with citations."""
        question = request.question.strip()
        if not question:
            raise ValueError("Empty question")

        project = db.query(Project).filter(Project.id == project_id).first()
        project_name = project.name if project else "Project"

        q_lower = question.lower()
        retrieved_contexts: List[Dict[str, str]] = []
        retrieval_scores: List[float] = []
        coll_name = RagService._collection_name(project_id)

        # 0. Check for natural greetings and conversational openings
        greeting_patterns = [
            r"^(hi|hello|hey|howdy|greetings|good\s+(morning|afternoon|evening|day))(\s+there)?[\s!?,.]*$",
            r"^(who\s+are\s+you|what\s+can\s+you\s+do|how\s+can\s+you\s+help)[\s!?,.]*$"
        ]
        if any(re.match(p, q_lower.strip()) for p in greeting_patterns):
            project_display = f" for '{project_name}'" if project_name and project_name != "Project" else ""
            return QueryResponse(
                question=question,
                answer=(
                    f"Hello! I am your AI Query Support Assistant{project_display}. "
                    "I can help you explore requirements, architecture designs, database schemas, API specifications, and test cases. "
                    "What would you like to know about the project?"
                ),
                citations=[],
                grounded=True,
                confidence="high"
            )

        # 1. Step A: Check for Overview-style question direct context matching
        direct_contexts = RagService._get_direct_artifact_contexts(project_id, question, db)
        for dc in direct_contexts:
            retrieved_contexts.append(dc)
            retrieval_scores.append(0.0) # High relevance (exact domain match)

        # 2. Step B: Semantic Vector Search with Query Rewriting via ChromaDB
        best_distance = 999.0
        if chroma_client:
            try:
                collection = chroma_client.get_collection(name=coll_name)
                rewritten_q = RagService._rewrite_query(question, project_name)
                
                # Query both original question and rewritten expansion
                results = collection.query(
                    query_texts=[question, rewritten_q],
                    n_results=4,
                    include=["documents", "metadatas", "distances"]
                )
                if results and "documents" in results and results["documents"]:
                    # Merge and deduplicate by source snippet
                    seen_snippets = set(c["snippet"][:50] for c in retrieved_contexts)
                    for query_idx in range(len(results["documents"])):
                        docs = results["documents"][query_idx]
                        metas = results["metadatas"][query_idx] if "metadatas" in results else []
                        dists = results["distances"][query_idx] if "distances" in results else []
                        for d, m, dist in zip(docs, metas, dists):
                            if dist < best_distance:
                                best_distance = dist
                            # Only accept chunks with distance <= 1.45 to prevent off-topic noise
                            if dist <= 1.45:
                                snip = d[:400]
                                if snip[:50] not in seen_snippets:
                                    seen_snippets.add(snip[:50])
                                    source = m.get("source", "Requirement Document")
                                    retrieved_contexts.append({
                                        "source": source,
                                        "snippet": snip,
                                        "score": float(dist)
                                    })
                                    retrieval_scores.append(float(dist))
            except Exception as e:
                logger.warning(f"ChromaDB query error or collection not found for {coll_name}: {e}")

        # 3. Step C: Fallback Keyword Search over DB chunks & requirements
        if len(retrieved_contexts) < 2:
            q_words = set(re.findall(r"\b[a-z]{3,}\b", q_lower)) - {
                "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
                "explain", "does", "system", "tell", "show", "long", "wait", "list", "all"
            }
            
            # Check Document Chunks
            chunks = db.query(DocumentChunk).filter(DocumentChunk.project_id == project_id).all()
            scored_chunks = []
            for c in chunks:
                words = set(re.findall(r"\b[a-z]{3,}\b", c.chunk_text.lower()))
                overlap = len(q_words.intersection(words))
                if overlap > 0:
                    scored_chunks.append((overlap, c))
            scored_chunks.sort(key=lambda x: x[0], reverse=True)
            for ov, c in scored_chunks[:2]:
                retrieved_contexts.append({
                    "source": f"{c.source_file} (Chunk {c.chunk_index + 1})",
                    "snippet": c.chunk_text[:350],
                    "score": 1.0 / (ov + 1)
                })

            # Check Requirements
            reqs = db.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == project_id).all()
            for r in reqs:
                text = f"{r.title} {r.description}".lower()
                matched = [w for w in q_words if w in text]
                if matched:
                    retrieved_contexts.append({
                        "source": f"Requirement [{r.req_id}]",
                        "snippet": f"{r.title}: {r.description}",
                        "score": 0.5
                    })
                    if len(retrieved_contexts) >= 5:
                        break

        # 4. Step D: Add relevant artifact context if explicitly requested
        if request.include_artifacts:
            artifacts = db.query(Artifact).filter(Artifact.project_id == project_id).all()
            for art in artifacts:
                if not art.content_json:
                    continue
                try:
                    content = json.loads(art.content_json)
                    if art.artifact_type == "schema" and any(k in q_lower for k in ["table", "schema", "database", "entity", "column", "foreign key"]):
                        tables = content.get("tables", [])
                        table_summaries = [f"{t.get('name')} ({', '.join([c['name'] for c in t.get('columns', [])[:4]])})" for t in tables]
                        retrieved_contexts.append({
                            "source": "Database Schema Specification",
                            "snippet": f"Defined tables: {'; '.join(table_summaries)}. Enforces relational foreign key constraints."
                        })
                    elif art.artifact_type == "architecture" and any(k in q_lower for k in ["architecture", "layer", "design", "pattern", "component", "gateway"]):
                        pattern = content.get("pattern", "Layered Architecture")
                        layers = [l.get("name") for l in content.get("layers", [])]
                        retrieved_contexts.append({
                            "source": "Architecture Design Artifact",
                            "snippet": f"Pattern: {pattern}. Layer breakdown: {', '.join(layers)}."
                        })
                    elif art.artifact_type == "api" and any(k in q_lower for k in ["api", "endpoint", "route", "http", "rest", "swagger", "openapi"]):
                        endpoints = content.get("endpoints", [])
                        routes = [f"{e.get('method')} {e.get('path')}" for e in endpoints[:4]]
                        retrieved_contexts.append({
                            "source": "API Documentation",
                            "snippet": f"Key endpoints: {', '.join(routes)}."
                        })
                except Exception:
                    pass

        # 5. Check relevance and handle general technical vs off-topic queries
        q_content_words = set(re.findall(r"\b[a-z]{4,}\b", q_lower)) - {
            "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
            "explain", "does", "system", "tell", "show", "long", "wait", "list", "all",
            "about", "have", "with", "from", "each", "every", "many", "much", "current"
        }
        all_context_corpus = " ".join([c.get("snippet", "") for c in retrieved_contexts]).lower()
        has_content_word_match = any(w in all_context_corpus for w in q_content_words) if q_content_words else True

        is_unrelated_general_topic = False
        unrelated_patterns = [
            r"\bworld cup\b", r"\bpresident\b", r"\bcapital of\b", r"\bmovie\b", r"\bweather in\b",
            r"\bwho is the prime minister\b", r"\bwho won\b", r"\bcelebrity\b", r"\btemperature in\b",
            r"\bantarctica\b"
        ]
        for pat in unrelated_patterns:
            if re.search(pat, q_lower):
                is_unrelated_general_topic = True
                break

        # Check for general technical / engineering concepts
        technical_patterns = [
            r"\bjwt\b", r"\brest\b", r"\bapi\b", r"\bprimary key\b", r"\bforeign key\b",
            r"\bacid\b", r"\borm\b", r"\bsql\b", r"\bnosql\b", r"\bmicroservice",
            r"\bmonolith", r"\boauth", r"\bhttp", r"\bhttps\b", r"\bgraphql\b",
            r"\barchitecture\b", r"\bdatabase\b", r"\bcache\b", r"\bredis\b",
            r"\bdocker\b", r"\bcontainer", r"\bunit test", r"\bintegration test",
            r"\bswagger\b", r"\bopenapi\b", r"\bcrud\b", r"\bci/cd\b"
        ]
        is_general_technical = any(re.search(p, q_lower) for p in technical_patterns)

        if (not retrieved_contexts and not is_general_technical) or is_unrelated_general_topic or (not has_content_word_match and not is_general_technical):
            return QueryResponse(
                question=question,
                answer=(
                    f"I could not find information about this topic in the project context. "
                    f"This topic is not covered in the current project's requirement specifications or generated artifacts. "
                    f"Please ask a question related to '{project_name}' (such as its requirements, architecture, database schema, APIs, or test cases)."
                ),
                citations=[],
                grounded=False,
                confidence="low"
            )

        # 6. Formulate Prompt & Call LLM
        context_block = "\n\n".join([f"[{c['source']}]:\n{c['snippet']}" for c in retrieved_contexts[:5]]) if retrieved_contexts else "No direct project context found."
        
        system_prompt = (
            f"You are the project-aware Query Support Assistant for '{project_name}'. "
            "Communicate in a natural, professional, and friendly engineering tone. "
            "Guidelines:"
            "\n1. For project-specific questions, base your response strictly on the provided PROJECT CONTEXT. Do not invent or assume requirements, entities, or APIs that are not stated in the sources."
            "\n2. When information regarding a specific project feature is unavailable in the project context, state clearly that it could not be found in the current project documents (e.g., 'This information is not covered in the current project documents or artifacts')."
            "\n3. For general technical or software engineering questions (e.g., explaining REST, JWT, microservices, databases), provide a helpful general explanation while clearly noting that this is general technical context and distinguishing it from project-specific specifications."
            "\n4. Avoid robotic boilerplate refusals or repetitive disclaimers."
        )

        user_prompt = f"""PROJECT CONTEXT:
{context_block}

USER QUESTION:
{question}

Provide an accurate, clear answer following the guidelines above."""

        provider = get_llm_provider()
        answer = provider.generate_text(user_prompt, system_prompt=system_prompt)

        # Check if the model itself refused or gave ungrounded answer
        is_grounded = "not covered in the current project" not in answer.lower() and bool(retrieved_contexts) and has_content_word_match

        citations = [
            Citation(source=c["source"], snippet=c["snippet"][:200])
            for c in retrieved_contexts[:4]
        ] if is_grounded else []

        return QueryResponse(
            question=question,
            answer=answer,
            citations=citations,
            grounded=is_grounded,
            confidence="high" if is_grounded else "low"
        )

    @staticmethod
    def get_suggested_questions(project_id: str, db: Session) -> List[Dict[str, str]]:
        """Generate project-specific suggested questions dynamically from actual project entities."""
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return []

        project_name = project.name

        # Find schema tables or entities
        schema_art = db.query(Artifact).filter(Artifact.project_id == project_id, Artifact.artifact_type == "schema").first()
        tables = []
        if schema_art and schema_art.content_json:
            try:
                tables = json.loads(schema_art.content_json).get("tables", [])
            except Exception:
                pass

        # Fallback to extracted entities
        if not tables:
            ents = db.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == project_id, ExtractedRequirement.category == "entity").all()
            main_entity = ents[0].title if ents else "Domain"
        else:
            # Pick a non-users table if available
            cand = [t["name"] for t in tables if t["name"] not in {"users", "accounts"}]
            main_entity = cand[0] if cand else tables[0]["name"]

        entity_display = main_entity.capitalize()

        return [
            {
                "label": f"{entity_display} Rationale",
                "q": f"Why is the {main_entity} table required?"
            },
            {
                "label": "Architecture Overview",
                "q": f"Explain the system architecture of {project_name}."
            },
            {
                "label": "Non-Functional Specs",
                "q": "What are the non-functional requirements?"
            },
            {
                "label": "Authentication Details",
                "q": "What authentication method is required?"
            }
        ]
