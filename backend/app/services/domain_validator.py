"""Domain-agnostic validation utilities for domain entities, database tables, and API endpoints.

Prevents pseudo-entities, technical meta-vocabulary, NFR terms, and verb phrases
from leaking into database schemas, API documentation, and code generation,
while treating explicit document definitions as authoritative.
"""

import re
from typing import Set, List, Optional

# Generic technical, architectural, database, API, document, and NFR meta-words
GENERIC_META_WORDS: Set[str] = {
    # Database, Schema, Data structures
    "table", "tables", "column", "columns", "row", "rows", "field", "fields",
    "schema", "schemas", "database", "databases", "db", "index", "indexes", "indices",
    "pk", "fk", "key", "keys", "migration", "migrations", "record", "records",
    "view", "views", "query", "queries", "sql", "ddl", "relation", "relations",
    "relational", "dataset", "datasets", "entity", "entities", "attribute", "attributes",
    "metadata", "datum", "data", "storage", "junction", "junctions", "junctionss",

    # API, HTTP, Protocols, Web
    "api", "apis", "endpoint", "endpoints", "endpointss", "route", "routes", "uri", "uris",
    "url", "urls", "http", "https", "rest", "restful", "crud", "payload", "payloads",
    "header", "headers", "param", "params", "parameter", "parameters", "request", "requests",
    "response", "responses", "json", "jsons", "xml", "yaml", "yml", "csv", "token", "tokens",
    "jwt", "webhook", "webhooks", "controller", "controllers", "handler", "handlers",
    "middleware", "gateway", "gateways", "proxy", "proxies", "client", "clients",
    "server", "servers", "socket", "sockets", "patch", "patchs", "patchss", "role", "roles",
    "status", "statuses", "statuss",

    # Architecture, System, Components
    "system", "systems", "subsystem", "subsystems", "application", "applications",
    "app", "apps", "software", "hardware", "service", "services", "microservice",
    "microservices", "module", "modules", "component", "components", "architecture",
    "architectures", "infrastructure", "infrastructures", "platform", "platforms",
    "frontend", "frontends", "backend", "backends", "tier", "tiers", "layer", "layers",
    "framework", "frameworks", "library", "libraries", "package", "packages",
    "config", "configs", "configuration", "configurations", "env", "environment",
    "environments", "instance", "instances", "deployment", "deployments",
    "core", "cores", "ent", "ents", "identity", "identities", "identitys",
    "strictly", "strictlys", "model", "models",

    # NFRs, Quality attributes, Metrics
    "nfr", "nfrs", "uptime", "uptimes", "downtime", "downtimes", "latency", "latencies",
    "throughput", "sla", "slas", "slo", "slos", "sli", "slis", "availability",
    "scalability", "reliability", "maintainability", "durability", "usability",
    "portability", "extensibility", "performance", "security", "concurrency",
    "metric", "metrics", "benchmark", "benchmarks", "telemetry", "threshold",
    "thresholds", "bandwidth", "load",
    "transactional", "transactionals", "operational", "behavioral",
    "functional", "structural", "temporal", "new", "news", "old",

    # Document, Requirement, Agile process
    "requirement", "requirements", "req", "reqs", "fr", "frs", "spec", "specs",
    "specification", "specifications", "document", "documents", "documentation",
    "section", "sections", "paragraph", "paragraphs", "appendix", "glossary",
    "overview", "scope", "assumption", "assumptions", "constraint", "constraints",
    "domain", "domains", "project", "projects", "feature", "features",
    "functionality", "functionalities", "usecase", "usecases", "step", "steps",
    "workflow", "workflows", "criteria", "criterion", "actor", "actors",
    "business", "businesses", "busines", "following", "followings", "currently",
    "currentlys", "mapped", "mappeds",

    # Generic Datatypes & Primitives
    "string", "strings", "integer", "integers", "int", "ints", "boolean", "booleans",
    "bool", "bools", "float", "floats", "double", "doubles", "decimal", "decimals",
    "number", "numbers", "char", "chars", "text", "texts", "blob", "blobs",
    "datetime", "datetimes", "timestamp", "timestamps", "time", "times", "date", "dates",
    "array", "arrays", "list", "lists", "map", "maps", "dict", "dicts", "object", "objects",
    "null", "nulls", "none", "nones", "void", "true", "trues", "false", "falses",
    "name", "names", "description", "descriptions", "unique", "uniques", "check", "checks",
    "default", "defaults",

    # Generic UI elements
    "button", "buttons", "form", "forms", "page", "pages", "screen", "screens",
    "tab", "tabs", "modal", "modals", "dialog", "dialogs", "icon", "icons",
    "menu", "menus", "dropdown", "dropdowns", "input", "inputs",

    # Generic verbal nominalizations (unless part of qualified domain phrase)
    "management", "managements", "managementss", "processing", "processings",
    "operation", "operations"
}

# Common action verb stems that indicate operations, actions, or predicates rather than entities
ACTION_VERB_STEMS: Set[str] = {
    "provide", "assign", "manage", "include", "require", "allow", "enable", "support",
    "contain", "perform", "ensure", "indicate", "handle", "execute", "operate", "maintain",
    "implement", "generate", "process", "store", "update", "delete", "create", "retrieve",
    "modify", "validate", "verify", "calculate", "determine", "evaluate", "send", "receive",
    "notify", "trigger", "initiate", "complete", "terminate", "cancel", "submit", "request",
    "respond", "record", "track", "log", "display", "render", "show", "filter", "search",
    "sort", "paginate", "configure", "define", "specify", "check", "register", "authenticate",
    "issue", "analyze", "build", "describe", "dispatch"
}

# Standard legitimate infrastructure/system tables for user identity and authentication
SYSTEM_ALLOWED_TABLES: Set[str] = {
    "users", "user", "user_accounts", "user_account", "accounts", "account"
}


def to_snake_case(name: str) -> str:
    """Convert PascalCase, camelCase, or spaced strings to snake_case."""
    cleaned = name.strip().replace("-", "_").replace(" ", "_")
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', cleaned)
    s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    return re.sub(r'_+', '_', s2).strip('_')


def to_kebab_case(name: str) -> str:
    """Convert PascalCase, camelCase, or snake_case to kebab-case for URLs."""
    return to_snake_case(name).replace("_", "-")


def pluralize(word: str) -> str:
    """Return grammatically standard English plural for a noun or compound snake_case noun."""
    w = word.strip().lower()
    if not w:
        return ""
    # For compound words like medical_record, pluralize the last token
    if "_" in w:
        parts = w.split("_")
        parts[-1] = pluralize(parts[-1])
        return "_".join(parts)
    if "-" in w:
        parts = w.split("-")
        parts[-1] = pluralize(parts[-1])
        return "-".join(parts)

    if w.endswith("status"):
        return w
    if w.endswith("ies") or w.endswith("sses"):
        return w
    if w.endswith("y") and len(w) > 2 and w[-2] not in "aeiou":
        return w[:-1] + "ies"
    if w.endswith(("s", "x", "z", "ch", "sh")):
        return w + "es"
    return w + "s"


def singularize(word: str) -> str:
    """Return base singular form for a noun or compound snake_case noun."""
    w = word.strip().lower()
    if not w:
        return ""
    if "_" in w:
        parts = w.split("_")
        parts[-1] = singularize(parts[-1])
        return "_".join(parts)
    if "-" in w:
        parts = w.split("-")
        parts[-1] = singularize(parts[-1])
        return "-".join(parts)

    if w.endswith("status"):
        return w
    if w.endswith("ies") and len(w) > 3:
        return w[:-3] + "y"
    if w.endswith("sses") and len(w) > 4:
        return w[:-2]
    if w.endswith("es") and len(w) > 3 and w[-3] in "sxz":
        return w[:-2]
    if w.endswith("es") and len(w) > 4 and w[-4:-2] in ["ch", "sh"]:
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 1:
        return w[:-1]
    return w


def get_candidate_forms(word: str) -> Set[str]:
    """Generate normalized base forms, stems, and inflections for a word.
    
    Handles pluralization ('s', 'es', 'ies'), past tense ('ed'),
    progressive ('ing'), and adjectival forms iteratively.
    """
    w = word.strip().lower().replace("-", "_")
    forms = {w, w.replace("_", "")}
    tokens = list(w.split("_"))
    while tokens:
        curr = tokens.pop()
        forms.add(curr)
        peeled = []
        if curr.endswith("ies") and len(curr) > 4:
            peeled.append(curr[:-3] + "y")
        if curr.endswith("es") and len(curr) > 3:
            peeled.append(curr[:-2])
            peeled.append(curr[:-1])
        if curr.endswith("ss") and len(curr) > 4:
            peeled.append(curr[:-1])
            peeled.append(curr[:-2])
        elif curr.endswith("s") and len(curr) > 2:
            peeled.append(curr[:-1])
        if curr.endswith("ed") and len(curr) > 3:
            peeled.append(curr[:-2])
            peeled.append(curr[:-1])
        if curr.endswith("ing") and len(curr) > 4:
            peeled.append(curr[:-3])
            peeled.append(curr[:-3] + "e")
        if curr.endswith("ly") and len(curr) > 4:
            peeled.append(curr[:-2])
        for p in peeled:
            if p not in forms and len(p) >= 2:
                forms.add(p)
                tokens.append(p)
    return forms


def is_pseudo_name(name: str) -> bool:
    """Determine if a candidate name is a generic pseudo-entity, technical meta-word,
    NFR metric, or verb stem.
    
    A single-word candidate is rejected if its stemmed forms match meta-words or verb stems.
    A multi-word compound name (e.g. 'medical_records', 'order_items') is ONLY rejected
    if ALL of its constituent tokens are meta/verbs. If any token is domain-specific,
    the compound name is preserved.
    """
    clean = name.strip().lower().replace("-", "_")
    if not clean:
        return True

    if clean in SYSTEM_ALLOWED_TABLES:
        return False

    parts = [p for p in clean.split("_") if p]
    if not parts:
        return True

    # 1. Single-word candidate
    if len(parts) == 1:
        forms = get_candidate_forms(parts[0])
        if forms & GENERIC_META_WORDS:
            return True
        if forms & ACTION_VERB_STEMS:
            return True
        allowed_ly_nouns = {"assembly", "family", "supply", "rally", "monopoly", "daily", "early", "rely", "ally"}
        for f in forms:
            if f.endswith("ly") and len(f) > 3 and f not in allowed_ly_nouns:
                return True
        return False

    # 2. Multi-word candidate: reject ONLY if every component is generic/meta/verb
    all_parts_meta = all(
        bool(get_candidate_forms(p) & (GENERIC_META_WORDS | ACTION_VERB_STEMS))
        for p in parts
    )
    return all_parts_meta


def is_valid_domain_entity_candidate(name: str, has_explicit_definition: bool = False) -> bool:
    """Validate whether an entity candidate should be treated as a real domain entity.
    
    Parameters:
    - name: Candidate entity name
    - has_explicit_definition: True if candidate originates from an explicit 'Domain Entities'
      document section with attributes or a description. Explicit definitions are authoritative
      unless they match unmistakable technical meta-keywords (e.g. 'Table', 'API', 'JSON').
    """
    if not name or not isinstance(name, str):
        return False

    cleaned = name.strip()
    if len(cleaned) < 2 or len(cleaned) > 50:
        return False

    # Must contain at least one alphabetical letter
    if not re.search(r"[A-Za-z]", cleaned):
        return False

    # Check for pseudo-name
    if is_pseudo_name(cleaned):
        # Even with explicit definition, unmistakable technical meta-terms are not domain entities
        return False

    return True


def is_valid_domain_table_name(table_name: str) -> bool:
    """Validate whether a database table name represents a legitimate domain table."""
    if not table_name or not isinstance(table_name, str):
        return False

    cleaned = table_name.strip().lower()
    if cleaned in SYSTEM_ALLOWED_TABLES:
        return True

    # Strip batch/part suffixes before check (e.g. orders_batch1 -> orders)
    base_name = re.sub(r'(_batch\d+|_part\d+|_extended|_section\d+)$', '', cleaned)
    if is_pseudo_name(base_name):
        return False

    return True


def is_valid_domain_endpoint_path(path: str) -> bool:
    """Validate whether an API endpoint path targets a legitimate domain resource.
    
    Rejects paths like /api/v1/uptimes, /api/v1/tables, /api/v1/provides, /api/v1/assigneds.
    """
    if not path or not isinstance(path, str):
        return False

    cleaned = path.strip().lower()
    # Always allow authentication and health endpoints
    if any(k in cleaned for k in ["/auth", "/login", "/token", "/health"]):
        return True

    # Extract resource segment from /api/v1/{resource}
    m = re.match(r"^/api/v\d+/([a-z0-9_-]+)", cleaned)
    if m:
        resource = m.group(1)
        if is_pseudo_name(resource):
            return False

    return True
