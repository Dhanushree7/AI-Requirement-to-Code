import sys, os, re, json
from typing import Dict, List, Set, Any
from collections import defaultdict

# Add project root to sys.path
sys.path.insert(0, os.path.abspath("."))

from backend.app.core.database import SessionLocal
from backend.app.models.project import Project
from backend.app.models.requirement import ExtractedRequirement
from backend.app.models.artifact import Artifact
from backend.app.models.graph import GraphData
from backend.app.models.rag_chunk import DocumentChunk

STOP_WORDS = {
    "system", "shall", "allow", "allows", "must", "will", "user", "users", "admin", "admins",
    "data", "view", "views", "list", "lists", "time", "times", "date", "dates", "status",
    "create", "creates", "created", "update", "updates", "updated", "delete", "deletes", "deleted",
    "edit", "edits", "manage", "manages", "role", "roles", "access", "record", "records",
    "value", "values", "level", "levels", "state", "states", "type", "types", "field", "fields",
    "table", "tables", "module", "modules", "detail", "details", "check", "checks", "checked",
    "valid", "validate", "validates", "validation", "error", "errors", "message", "messages",
    "notification", "notifications", "notify", "notifies", "notified", "request", "requests",
    "response", "responses", "parameter", "parameters", "endpoint", "endpoints", "service", "services",
    "action", "actions", "feature", "features", "item", "items", "first", "second", "third",
    "number", "numbers", "minimum", "maximum", "total", "totals", "count", "counts", "period",
    "range", "ranges", "start", "starts", "started", "stop", "stops", "stopped", "before", "after",
    "every", "within", "between", "include", "includes", "included", "including", "require",
    "requires", "required", "requirement", "requirements", "support", "supports", "supported",
    "process", "processes", "processed", "processing", "provide", "provides", "provided",
    "assign", "assigns", "assigned", "assignment", "report", "reports", "reported", "reporting",
    "generate", "generates", "generated", "generation", "unique", "optional", "default", "defaults",
    "automatic", "automatically", "online", "active", "inactive", "enabled", "disabled",
    "failure", "failures", "success", "successful", "successfully", "fail", "fails", "failed",
    "pass", "passes", "passed", "test", "tests", "case", "cases", "scenario", "scenarios",
    "steps", "preconditions", "postconditions", "result", "results", "expected", "unit", "units",
    "currency", "hours", "hour", "minutes", "minute", "seconds", "second", "days", "day",
    "weeks", "week", "months", "month", "years", "year", "amount", "amounts", "rate", "rates",
    "description", "title", "name", "names", "info", "information", "entry", "entries", "flag", "flagged",
    "method", "methods", "does", "done", "each", "find", "give", "gives", "given", "handle", "handles",
    "handled", "handling", "hashed", "having", "hold", "holds", "held", "into", "keep", "keeps", "kept",
    "like", "more", "most", "much", "many", "same", "show", "shows", "shown", "such", "than", "that",
    "them", "then", "there", "these", "they", "this", "those", "through", "under", "used", "uses", "using",
    "well", "what", "when", "where", "which", "while", "whose", "with", "without", "daily", "weekly",
    "monthly", "management", "allocation", "allowed", "apply", "available", "average", "based", "current",
    "address", "account", "filtering", "approval", "accepted", "accepts", "accepting", "above", "award",
    "best", "earliest", "earned", "exceeds", "select", "selected", "selection", "platform", "operation",
    "operational", "operations", "summary", "submit", "submits", "submitted", "submission", "overview",
    "audit", "inventory", "catalog", "calculate", "calculation", "cancel", "cancelled", "cancellation",
    "capacity", "change", "changes", "configured", "containing", "creation", "during", "next",
    "recorded", "reject", "rejected", "constraint", "constraints", "concurrent", "concurrency",
    "return", "returns", "returned", "pack", "packing", "packed", "placement", "product", "products",
    "purchase", "purchases", "receive", "received", "receiving", "review", "reviews", "were",
    "shipped", "shipping", "expire", "expires", "expired", "expiry", "acceptance", "availability",
    "order", "orders", "customer", "customers", "band", "bands", "category", "categories",
    "limit", "limits", "window", "windows", "setting", "settings", "spec", "specification",
    "compliance", "session", "sessions", "alerting", "trigger", "triggers", "statistics", "stats",
    "suspended", "suspension", "exceed", "run", "runs", "running", "step", "steps",
    "cannot", "contains", "contain", "combination", "batch", "batches", "dashboard", "dashboards",
    "full", "fully", "verification", "verified", "verify", "verifies", "refund", "refunds", "refunded",
    "refunding", "logging", "performance", "life", "encrypted", "encryption", "encrypt", "load",
    "loads", "loaded", "loading", "passwords", "password", "personal", "multi", "partial", "partially",
    "least", "searches", "prices", "price", "pricing", "sell", "sells", "selling", "sold",
    "save", "saved", "saving", "restriction", "restrictions", "grade", "grades", "issue", "issues",
    "mobile", "multiple", "security", "since", "organic", "shelf"
}

def extract_vocab(reqs: List[ExtractedRequirement]) -> Set[str]:
    text = " ".join([f"{r.title} {r.description}" for r in reqs])
    raw_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', text.lower()))
    return {w for w in raw_words if w not in STOP_WORDS}

def search_text_for_leaks(text: str, leak_words: Set[str]) -> List[tuple]:
    hits = []
    t_lower = text.lower()
    for w in sorted(leak_words):
        matches = [m.start() for m in re.finditer(r'\b' + re.escape(w) + r'\b', t_lower)]
        for pos in matches:
            start = max(0, pos - 40)
            end = min(len(text), pos + len(w) + 40)
            snippet = text[start:end].replace("\n", " ").strip()
            hits.append((w, snippet))
    return hits

def check_project_pair(pid1: str, pid2: str):
    db = SessionLocal()
    try:
        p1 = db.query(Project).filter(Project.id == pid1).first()
        p2 = db.query(Project).filter(Project.id == pid2).first()
        if not p1 or not p2:
            print(f"Error: Could not find projects: p1={p1}, p2={p2}")
            return

        print("=" * 80)
        print(f"CROSS-DOMAIN LEAK CHECK")
        print(f"Project 1: '{p1.name}' ({p1.id})")
        print(f"Project 2: '{p2.name}' ({p2.id})")
        print("=" * 80)

        r1 = db.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == pid1).all()
        r2 = db.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == pid2).all()

        v1 = extract_vocab(r1)
        v2 = extract_vocab(r2)

        distinct_to_1 = v1 - v2
        distinct_to_2 = v2 - v1

        print(f"\nDistinctive vocabulary for '{p1.name}' ({len(distinct_to_1)} terms):")
        print(f"  {', '.join(sorted(list(distinct_to_1))[:25])} ...")
        print(f"\nDistinctive vocabulary for '{p2.name}' ({len(distinct_to_2)} terms):")
        print(f"  {', '.join(sorted(list(distinct_to_2))[:25])} ...")

        def inspect_project_artifacts(target_pid: str, target_name: str, foreign_vocab: Set[str], foreign_name: str):
            print(f"\nChecking artifacts of '{target_name}' for leakage from '{foreign_name}'...")
            artifacts = db.query(Artifact).filter(Artifact.project_id == target_pid).all()
            total_hits = 0

            for art in artifacts:
                c_str = art.content_json or ""
                hits = search_text_for_leaks(c_str, foreign_vocab)
                if hits:
                    print(f"  [LEAK IN ARTIFACT: {art.artifact_type.upper()}] {len(hits)} hit(s):")
                    for w, snippet in hits[:10]:
                        print(f"    - Leaked term '{w}': ...{snippet}...")
                    if len(hits) > 10:
                        print(f"    ... and {len(hits) - 10} more hits in this artifact")
                    total_hits += len(hits)
                else:
                    print(f"  [CLEAN] {art.artifact_type.upper()} artifact: 0 foreign domain terms.")

            graph = db.query(GraphData).filter(GraphData.project_id == target_pid).first()
            if graph:
                g_str = f"{graph.nodes_json} {graph.edges_json}"
                hits = search_text_for_leaks(g_str, foreign_vocab)
                if hits:
                    print(f"  [LEAK IN GRAPH] {len(hits)} hit(s):")
                    for w, snippet in hits[:5]:
                        print(f"    - Leaked term '{w}': ...{snippet}...")
                    total_hits += len(hits)
                else:
                    print(f"  [CLEAN] Knowledge Graph: 0 foreign domain terms.")

            chunks = db.query(DocumentChunk).filter(DocumentChunk.project_id == target_pid).all()
            chunk_str = " ".join([c.chunk_text for c in chunks if c.chunk_text])
            if chunk_str:
                hits = search_text_for_leaks(chunk_str, foreign_vocab)
                if hits:
                    print(f"  [LEAK IN RAG INDEX] {len(hits)} hit(s):")
                    for w, snippet in hits[:5]:
                        print(f"    - Leaked term '{w}': ...{snippet}...")
                    total_hits += len(hits)
                else:
                    print(f"  [CLEAN] Query Assistant / RAG index: 0 foreign domain terms.")

            print(f"--> Total cross-domain leaks found in '{target_name}': {total_hits}")

        inspect_project_artifacts(pid2, p2.name, distinct_to_1, p1.name)
        inspect_project_artifacts(pid1, p1.name, distinct_to_2, p2.name)

        def check_ac_number_grounding(pid: str, pname: str):
            print(f"\n--- Checking Acceptance Criteria Numbers Grounding for '{pname}' ---")
            art = db.query(Artifact).filter(Artifact.project_id == pid, Artifact.artifact_type == "srs").first()
            if not art or not art.content_json:
                print("  No SRS artifact found.")
                return

            try:
                srs_data = json.loads(art.content_json)
            except Exception as e:
                print(f"  Error loading SRS JSON: {e}")
                return

            sec6 = next((s for s in srs_data.get("sections", []) if s.get("id") == "SEC-6" or "Functional Requirements" in s.get("title", "")), None)
            if not sec6:
                print("  Section 6 not found in SRS.")
                return

            req_records = {r.req_id: r for r in db.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == pid, ExtractedRequirement.category == "functional").all()}
            sec6_text = sec6.get("content", "")

            req_blocks = re.split(r'\n(?=####\s+[A-Za-z]+-\d+:)', sec6_text)
            ungrounded_count = 0

            for b in req_blocks:
                m_id = re.search(r'####\s+([A-Za-z]+-\d+):', b)
                if not m_id:
                    continue
                rid = m_id.group(1)
                m_ac = re.search(r'-\s+\*\*Acceptance Criteria:\*\*\n(.*?)(?=\n####|\n###|\Z)', b, re.DOTALL)
                if not m_ac:
                    continue

                req_obj = req_records.get(rid)
                req_text = f"{req_obj.title} {req_obj.description}" if req_obj else ""
                req_nums = set(re.findall(r'\b\d+(?:\.\d+)?\b', req_text))

                for line in m_ac.group(1).strip().splitlines():
                    clean_line = re.sub(r'^\s*[-*0-9\.\)]+\s*', '', line)
                    clean_line = re.sub(r'\b[A-Za-z]+-\d+\b', '', clean_line)
                    crit_nums = re.findall(r'\b\d+(?:\.\d+)?\b', clean_line)
                    for cn in crit_nums:
                        if cn not in req_nums and cn != "0":
                            print(f"  [UNGROUNDED NUMBER] {rid}: Number '{cn}' in criterion '{clean_line.strip()}' NOT found in requirement text '{req_text}'")
                            ungrounded_count += 1

            if ungrounded_count == 0:
                print("  All acceptance criteria numbers are 100% grounded in each requirement's own text.")
            else:
                print(f"  Total ungrounded numbers found: {ungrounded_count}")

        check_ac_number_grounding(pid1, p1.name)
        check_ac_number_grounding(pid2, p2.name)

    finally:
        db.close()

if __name__ == "__main__":
    p_id_1 = sys.argv[1] if len(sys.argv) > 1 else "65f0d22a-2969-42b8-873d-ff653651170b"
    p_id_2 = sys.argv[2] if len(sys.argv) > 2 else "024194af-bf30-48e5-bb7f-c2c24f086b62"
    check_project_pair(p_id_1, p_id_2)
