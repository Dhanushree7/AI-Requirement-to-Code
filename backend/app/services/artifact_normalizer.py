"""
Artifact Normalizer: Enforces a single, strictly typed canonical schema for every artifact type.
Handles named keys, nested objects, camelCase/snake_case/PascalCase, OpenAPI 3.0 dictionaries,
entities vs tables, and file maps.
"""

import re
import json
from typing import Any, Dict, List, Optional

def _to_title_words(s: str) -> str:
    """Convert PascalCase, camelCase, or snake_case to readable words."""
    s = s.replace("_", " ").replace("-", " ")
    # Insert space before capital letters if preceded by lowercase
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s)
    return s.strip().title()

def normalize_srs(raw: Any) -> Dict[str, Any]:
    """
    Canonical SRS Schema:
    {
      "title": str,
      "disclaimer": str,
      "sections": [
        {
          "id": str,
          "title": str,
          "content": str,
          "subsections": list
        }
      ]
    }
    """
    if not isinstance(raw, dict):
        raw = {"content": str(raw)}

    title = raw.get("title") or "Software Requirements Specification"
    disclaimer = raw.get("disclaimer") or ""
    sections: List[Dict[str, Any]] = []

    # Case 1: Already has a sections list
    if isinstance(raw.get("sections"), list) and len(raw["sections"]) > 0:
        for idx, sec in enumerate(raw["sections"]):
            if isinstance(sec, dict):
                sec_id = str(sec.get("id") or f"SEC-{idx + 1}")
                sec_title = str(sec.get("title") or sec.get("name") or f"Section {idx + 1}")
                sec_content = sec.get("content") or sec.get("text") or sec.get("description") or ""
                if isinstance(sec_content, (dict, list)):
                    sec_content = json.dumps(sec_content, indent=2)
                sections.append({
                    "id": sec_id,
                    "title": sec_title,
                    "content": str(sec_content),
                    "subsections": sec.get("subsections", [])
                })
            else:
                sections.append({
                    "id": f"SEC-{idx + 1}",
                    "title": f"Section {idx + 1}",
                    "content": str(sec),
                    "subsections": []
                })
    else:
        # Case 2: Object with named section keys (e.g., Introduction, Purpose, Scope, etc.)
        idx = 1
        for k, v in raw.items():
            if k.lower() in ["title", "disclaimer", "sections"]:
                continue
            
            sec_title = _to_title_words(k)
            sec_content = ""
            if isinstance(v, str):
                sec_content = v
            elif isinstance(v, dict):
                parts = []
                for sub_k, sub_v in v.items():
                    sub_title = _to_title_words(sub_k)
                    if isinstance(sub_v, (dict, list)):
                        parts.append(f"### {sub_title}\n```json\n{json.dumps(sub_v, indent=2)}\n```")
                    else:
                        parts.append(f"**{sub_title}:** {sub_v}")
                sec_content = "\n\n".join(parts)
            elif isinstance(v, list):
                parts = []
                for item in v:
                    if isinstance(item, dict):
                        item_parts = [f"- **{_to_title_words(ik)}:** {iv}" for ik, iv in item.items()]
                        parts.append("\n  ".join(item_parts))
                    else:
                        parts.append(f"- {item}")
                sec_content = "\n".join(parts)
            else:
                sec_content = str(v)

            sections.append({
                "id": f"SEC-{idx}",
                "title": f"{idx}.0 {sec_title}",
                "content": sec_content,
                "subsections": []
            })
            idx += 1

    return {
        "title": title,
        "disclaimer": disclaimer,
        "sections": sections
    }

def normalize_schema(raw: Any) -> Dict[str, Any]:
    """
    Canonical Database Schema:
    {
      "tables": [
        {
          "name": str,
          "description": str,
          "columns": [
            {
              "name": str,
              "type": str,
              "pk": bool,
              "fk": str or null,
              "nullable": bool,
              "description": str
            }
          ],
          "relationships": list
        }
      ],
      "mermaid_er": str,
      "mermaid": str,
      "sql_ddl": str,
      "ddl": str
    }
    """
    if not isinstance(raw, dict):
        raw = {}

    tables: List[Dict[str, Any]] = []

    # Extract tables from raw.tables or raw.entities
    raw_tables = raw.get("tables")
    raw_entities = raw.get("entities") or raw.get("models")

    if isinstance(raw_tables, list):
        candidate_tables = raw_tables
    elif isinstance(raw_tables, dict):
        candidate_tables = [{"name": k, **(v if isinstance(v, dict) else {})} for k, v in raw_tables.items()]
    elif isinstance(raw_entities, list):
        candidate_tables = raw_entities
    elif isinstance(raw_entities, dict):
        candidate_tables = [{"name": k, **(v if isinstance(v, dict) else {})} for k, v in raw_entities.items()]
    else:
        candidate_tables = []

    for t in candidate_tables:
        if not isinstance(t, dict):
            continue
        t_name = str(t.get("name") or t.get("table_name") or t.get("entity_name") or "UnnamedTable")
        t_desc = str(t.get("description") or t.get("desc") or f"{t_name} entity table")
        
        # Columns / Attributes
        raw_cols = t.get("columns") or t.get("attributes") or t.get("fields") or []
        cols: List[Dict[str, Any]] = []

        if isinstance(raw_cols, dict):
            raw_cols = [{"name": ck, **(cv if isinstance(cv, dict) else {"type": str(cv)})} for ck, cv in raw_cols.items()]

        for col in raw_cols:
            if not isinstance(col, dict):
                col_name = str(col)
                cols.append({
                    "name": col_name,
                    "type": "VARCHAR(255)",
                    "pk": col_name.lower() in ["id", f"{t_name.lower()}_id"],
                    "fk": None,
                    "nullable": col_name.lower() not in ["id", f"{t_name.lower()}_id"],
                    "description": ""
                })
                continue

            c_name = str(col.get("name") or col.get("column_name") or col.get("attribute_name") or "col")
            c_type = str(col.get("type") or col.get("data_type") or "VARCHAR(255)")
            c_pk = bool(col.get("pk") or col.get("is_primary_key") or col.get("primary_key") or False)
            if not c_pk and c_name.lower() in ["id", f"{t_name.lower()}_id"]:
                c_pk = True

            c_fk = col.get("fk") or col.get("foreign_key") or col.get("references")
            if isinstance(c_fk, bool):
                c_fk = None
            elif c_fk is not None:
                c_fk = str(c_fk).strip()
                if not c_fk or c_fk.lower() in ["none", "null", "false"] or "referenced_table" in c_fk.lower():
                    c_fk = None

            c_nullable = bool(col.get("nullable", not c_pk))
            c_desc = str(col.get("description") or "")

            c_unique = bool(col.get("unique") or col.get("is_unique") or False)
            c_check = col.get("check") or col.get("check_constraint")
            c_on_delete = col.get("on_delete") or ("CASCADE" if "item" in t_name.lower() or "detail" in t_name.lower() else "RESTRICT")

            cols.append({
                "name": c_name,
                "type": c_type,
                "pk": c_pk,
                "fk": c_fk,
                "nullable": c_nullable,
                "unique": c_unique,
                "check": c_check,
                "on_delete": c_on_delete if c_fk else None,
                "description": c_desc
            })

        # Table requirement_ids and indexes
        raw_rids = t.get("requirement_ids") or t.get("req_ids") or []
        if isinstance(raw_rids, str):
            rids = [raw_rids]
        elif isinstance(raw_rids, list):
            rids = [str(r) for r in raw_rids if r]
        else:
            rids = []

        indexes = t.get("indexes") or []
        if not isinstance(indexes, list):
            indexes = []

        tables.append({
            "name": t_name,
            "description": t_desc,
            "requirement_ids": rids,
            "columns": cols,
            "relationships": t.get("relationships", []),
            "indexes": indexes
        })

    # Mermaid ER Diagram - Generate from final tables and foreign keys
    mermaid_er = raw.get("mermaid_er") or raw.get("mermaid") or ""
    # Regenerate Mermaid ER to strictly match final merged tables and relationships
    lines = ["erDiagram"]
    # Collect relationships from FKs
    rel_lines = []
    for tbl in tables:
        clean_tbl_name = re.sub(r'\W+', '_', tbl["name"]).upper()
        lines.append(f"    {clean_tbl_name} {{")
        for col in tbl["columns"]:
            clean_col_type = re.sub(r'[\(\),]', '_', col["type"].lower()).split()[0]
            clean_col_name = re.sub(r'\W+', '_', col["name"])
            pk_marker = " PK" if col["pk"] else (" FK" if col["fk"] else "")
            lines.append(f"        {clean_col_type} {clean_col_name}{pk_marker}")
            
            # Infer relationship from FK
            if col["fk"]:
                fk_target = col["fk"].split("(")[0].strip()
                clean_target = re.sub(r'\W+', '_', fk_target).upper()
                if clean_target != clean_tbl_name:
                    rel_lines.append(f"    {clean_target} ||--o{{ {clean_tbl_name} : has")
        lines.append("    }")
    
    # Deduplicate relationships
    for r_line in sorted(list(set(rel_lines))):
        lines.append(r_line)
    mermaid_er = "\n".join(lines)

    # SQL DDL - Generate from final merged tables with constraints and indexes
    ddl_parts = []
    index_statements = []
    for tbl in tables:
        tbl_sql = [f"CREATE TABLE {tbl['name']} ("]
        col_lines = []
        fk_constraints = []
        
        pk_assigned = False
        for col in tbl["columns"]:
            line = f"    {col['name']} {col['type']}"
            if col["pk"] and not pk_assigned:
                line += " PRIMARY KEY"
                pk_assigned = True
            elif not col["nullable"]:
                line += " NOT NULL"
            if col.get("unique"):
                line += " UNIQUE"
            if col.get("check"):
                line += f" CHECK ({col['check']})"
            col_lines.append(line)

            # Foreign key constraint with ON DELETE (only if target table and column exist)
            if col.get("fk"):
                fk_spec = str(col["fk"]).strip()
                m_fk = re.match(r'([a-zA-Z0-9_]+)(?:\(|\.)([a-zA-Z0-9_]+)\)?', fk_spec)
                if m_fk:
                    target_table = m_fk.group(1).strip()
                    target_col = m_fk.group(2).strip()
                else:
                    target_table = fk_spec.split("(")[0].strip()
                    target_col = "id"

                # Validate against known table definitions
                known_tbl_names = {t["name"].lower(): t["name"] for t in tables}
                if target_table.lower() in known_tbl_names:
                    real_target_table = known_tbl_names[target_table.lower()]
                    target_tbl_obj = next(t for t in tables if t["name"].lower() == target_table.lower())
                    target_cols = {c["name"].lower(): c["name"] for c in target_tbl_obj.get("columns", [])}
                    
                    if target_col.lower() in target_cols:
                        real_target_col = target_cols[target_col.lower()]
                    elif "id" in target_cols:
                        real_target_col = target_cols["id"]
                    elif f"{real_target_table.lower()}_id" in target_cols:
                        real_target_col = target_cols[f"{real_target_table.lower()}_id"]
                    else:
                        real_target_col = next(iter(target_cols.values())) if target_cols else "id"

                    on_del = col.get("on_delete") or "RESTRICT"
                    fk_constraints.append(f"    FOREIGN KEY ({col['name']}) REFERENCES {real_target_table}({real_target_col}) ON DELETE {on_del}")
                    
                    # Auto-generate index for foreign keys
                    idx_name = f"idx_{tbl['name']}_{col['name']}"
                    index_statements.append(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {tbl['name']}({col['name']});")

        # Index foreign keys and columns that requirements filter on or use in time-based rules
        declared_indexes = [str(x).strip().lower() for x in tbl.get("indexes", []) if str(x).strip()]
        for col in tbl["columns"]:
            col_l = col["name"].lower()
            # Only index columns that are explicitly declared filter/time-rule indexes or unique natural keys
            if col_l in declared_indexes:
                idx_name = f"idx_{tbl['name']}_{col_l}"
                index_statements.append(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {tbl['name']}({col['name']});")

        all_table_lines = col_lines + fk_constraints
        tbl_sql.append(",\n".join(all_table_lines))
        tbl_sql.append(");")
        ddl_parts.append("\n".join(tbl_sql))

    # Append unique index statements
    if index_statements:
        ddl_parts.append("\n-- Indexes for performance and filtering\n" + "\n".join(sorted(list(set(index_statements)))))

    sql_ddl = "\n\n".join(ddl_parts)

    return {
        "tables": tables,
        "mermaid_er": mermaid_er,
        "mermaid": mermaid_er,
        "sql_ddl": sql_ddl,
        "ddl": sql_ddl
    }

def normalize_architecture(raw: Any) -> Dict[str, Any]:
    """
    Canonical Architecture Schema:
    {
      "pattern": str,
      "justification": str,
      "mermaid_diagram": str,
      "layers": [
        {
          "name": str,
          "tech": str,
          "responsibility": str
        }
      ]
    }
    """
    if not isinstance(raw, dict):
        raw = {}

    raw_pattern = raw.get("pattern") or raw.get("architecture_pattern")
    if isinstance(raw_pattern, str) and raw_pattern.strip():
        pattern = raw_pattern.strip()
    else:
        pattern = "Architecture Pattern Not Determined"
    justification = raw.get("justification") or raw.get("rationale") or raw.get("description") or "Modular layered architecture derived from system requirements."

    candidate_layers = raw.get("layers") or raw.get("components") or raw.get("tiers") or []
    if isinstance(candidate_layers, dict):
        candidate_layers = [{"name": k, **(v if isinstance(v, dict) else {"responsibility": str(v)})} for k, v in candidate_layers.items()]

    layers: List[Dict[str, Any]] = []
    for l in candidate_layers:
        if isinstance(l, dict):
            raw_tech = str(l.get("tech") or l.get("technology") or l.get("technologies") or "FastAPI / Python")
            if not raw_tech.lower().startswith("suggested technology") and not raw_tech.lower().startswith("technology:"):
                if "(specified" in raw_tech.lower() or "(system" in raw_tech.lower():
                    clean_tech = raw_tech
                else:
                    clean_tech = f"Suggested technology: {raw_tech}"
            else:
                clean_tech = raw_tech
            layers.append({
                "name": str(l.get("name") or "Component Layer"),
                "tech": clean_tech,
                "responsibility": str(l.get("responsibility") or l.get("responsibilities") or l.get("description") or ""),
                "supported_requirements": l.get("supported_requirements") or [],
                "dependencies": l.get("dependencies") or []
            })
        else:
            layers.append({
                "name": str(l),
                "tech": "FastAPI / Python (System Recommended)",
                "responsibility": "",
                "supported_requirements": [],
                "dependencies": []
            })

    mermaid_diagram = raw.get("mermaid_diagram") or raw.get("mermaid") or raw.get("diagram") or ""
    if not mermaid_diagram or not isinstance(mermaid_diagram, str) or ("graph" not in mermaid_diagram and "flowchart" not in mermaid_diagram):
        lines = ["flowchart TD"]
        for idx, layer in enumerate(layers):
            node_id = f"L{idx+1}"
            safe_name = layer["name"].replace('"', '')
            safe_tech = layer["tech"].replace('"', '')
            lines.append(f'    {node_id}["{safe_name}<br/>({safe_tech})"]')
            if idx > 0:
                lines.append(f"    L{idx} --> {node_id}")
        mermaid_diagram = "\n".join(lines)

    return {
        "pattern": pattern,
        "justification": justification,
        "mermaid_diagram": mermaid_diagram,
        "layers": layers
    }

def _normalize_param(p: Any) -> Dict[str, Any]:
    """Ensure parameter has a real, concrete data type and standard schema."""
    if not isinstance(p, dict):
        return {
            "name": str(p),
            "in": "query",
            "type": "string",
            "required": False,
            "description": ""
        }
    p_name = str(p.get("name") or "param")
    p_in = str(p.get("in") or "query")
    p_type = p.get("type")
    if not p_type and isinstance(p.get("schema"), dict):
        p_type = p["schema"].get("type") or p["schema"].get("format")
    
    if not p_type:
        p_name_l = p_name.lower()
        if p_name_l in ["id", "uuid"] or p_name_l.endswith(("_id", "id")):
            p_type = "string (UUID)"
        elif p_name_l in ["limit", "offset", "page", "count", "size", "quantity", "rating"]:
            p_type = "integer"
        elif p_name_l.startswith("is_") or p_name_l.startswith("has_"):
            p_type = "boolean"
        elif p_name_l in ["price", "amount", "discount", "total"]:
            p_type = "number (float)"
        else:
            p_type = "string"

    return {
        "name": p_name,
        "in": p_in,
        "type": str(p_type),
        "required": bool(p.get("required", p_in == "path")),
        "description": str(p.get("description") or "")
    }

def normalize_api(raw: Any) -> Dict[str, Any]:
    """
    Canonical API Documentation Schema:
    {
      "title": str,
      "components": {
        "securitySchemes": {
          "BearerAuth": {...}
        }
      },
      "endpoints": [
        {
          "path": str,
          "method": str,
          "summary": str,
          "description": str,
          "tag": str,
          "requirement_ids": list of str,
          "auth_required": bool,
          "roles": list of str,
          "parameters": list of dicts,
          "request_body": dict,
          "responses": list of dicts (with 400, 401, 403, 404)
        }
      ]
    }
    """
    if not isinstance(raw, dict):
        raw = {}

    title = raw.get("title") or (raw.get("info", {}).get("title") if isinstance(raw.get("info"), dict) else None) or "API Documentation"
    endpoints: List[Dict[str, Any]] = []

    std_error_responses = {
        "400": "Bad Request - Invalid parameters or request payload",
        "401": "Unauthorized - Missing or invalid Bearer token",
        "403": "Forbidden - Insufficient permissions / role",
        "404": "Not Found - Requested resource does not exist"
    }

    def _clean_endpoint(ep_dict: Dict[str, Any], path_url: str = "", method_str: str = "GET") -> Dict[str, Any]:
        path = str(ep_dict.get("path") or path_url or "/api")
        method = str(ep_dict.get("method") or method_str or "GET").upper()
        summary = str(ep_dict.get("summary") or f"{method} {path}")
        description = str(ep_dict.get("description") or "")
        
        tag = ep_dict.get("tag")
        if not tag and ep_dict.get("tags") and isinstance(ep_dict.get("tags"), list):
            tag = ep_dict["tags"][0]
        if not tag:
            tag = path.strip("/").split("/")[0].title() if path.strip("/") else "General"
        
        # Requirement IDs
        raw_rids = ep_dict.get("requirement_ids") or ep_dict.get("req_ids") or ep_dict.get("linked_req_ids")
        if isinstance(raw_rids, str):
            rids = [raw_rids]
        elif isinstance(raw_rids, list):
            rids = [str(r) for r in raw_rids if r]
        else:
            single_rid = ep_dict.get("linked_req_id") or ep_dict.get("requirement_id")
            rids = [str(single_rid)] if single_rid else []

        # Determine explicit public / auth_required flags
        if "is_public" in ep_dict:
            is_pub = bool(ep_dict["is_public"])
            auth_req = not is_pub
        elif "auth_required" in ep_dict:
            auth_req = bool(ep_dict["auth_required"])
            is_pub = not auth_req
        else:
            auth_req = bool(ep_dict.get("security") or False)
            is_pub = not auth_req
        
        # Roles / Allowed Roles
        raw_roles = ep_dict.get("allowed_roles") or ep_dict.get("roles") or ep_dict.get("required_roles") or []
        if isinstance(raw_roles, str):
            roles = [raw_roles]
        elif isinstance(raw_roles, list):
            roles = [str(rl) for rl in raw_roles if rl]
        else:
            roles = []
        allowed_roles = list(roles)

        # Parameters
        raw_params = ep_dict.get("parameters") or []
        parameters = [_normalize_param(p) for p in raw_params] if isinstance(raw_params, list) else []

        # Request body
        req_body = ep_dict.get("request_body") or ep_dict.get("requestBody") or {}

        # Responses with guaranteed error codes
        existing_resps = ep_dict.get("responses") or [{"code": "200", "description": "OK"}]
        resps_map = {}
        if isinstance(existing_resps, list):
            for r in existing_resps:
                if isinstance(r, dict) and "code" in r:
                    resps_map[str(r["code"])] = str(r.get("description") or "Response")
        elif isinstance(existing_resps, dict):
            for code, r_val in existing_resps.items():
                desc = r_val.get("description", "") if isinstance(r_val, dict) else str(r_val)
                resps_map[str(code)] = desc

        # Always guarantee 400, 401, 403, 404
        for err_code, err_desc in std_error_responses.items():
            if err_code not in resps_map:
                resps_map[err_code] = err_desc

        responses_list = [{"code": code, "description": desc} for code, desc in sorted(resps_map.items())]

        return {
            "path": path,
            "method": method,
            "summary": summary,
            "description": description,
            "tag": str(tag),
            "requirement_ids": rids,
            "is_public": is_pub,
            "auth_required": auth_req,
            "allowed_roles": allowed_roles,
            "roles": allowed_roles,
            "parameters": parameters,
            "request_body": req_body,
            "responses": responses_list
        }

    # Case 1: Already has endpoints list
    raw_endpoints = raw.get("endpoints")
    if isinstance(raw_endpoints, list) and len(raw_endpoints) > 0:
        for ep in raw_endpoints:
            if isinstance(ep, dict):
                endpoints.append(_clean_endpoint(ep))
    # Case 2: OpenAPI 3.0 paths object
    elif isinstance(raw.get("paths"), dict):
        for path_url, path_item in raw["paths"].items():
            if not isinstance(path_item, dict):
                continue
            for method, op in path_item.items():
                if method.upper() not in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    continue
                endpoints.append(_clean_endpoint(op if isinstance(op, dict) else {}, path_url, method))

    components = raw.get("components") or {}
    if not isinstance(components, dict):
        components = {}
    components.setdefault("securitySchemes", {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT Bearer token required for authorized endpoints."
        }
    })

    return {
        "title": title,
        "components": components,
        "endpoints": endpoints
    }

def normalize_skeleton(raw: Any) -> Dict[str, Any]:
    """
    Canonical Backend Skeleton Schema:
    {
      "directory_structure": list of str,
      "files": [
        {
          "path": str,
          "content": str,
          "language": str,
          "is_valid_python": bool or null
        }
      ]
    }
    """
    if not isinstance(raw, dict):
        raw = {}

    files: List[Dict[str, Any]] = []
    raw_files = raw.get("files", [])

    if isinstance(raw_files, dict):
        for fpath, fcontent in raw_files.items():
            files.append({
                "path": str(fpath),
                "content": str(fcontent),
                "language": "python" if str(fpath).endswith(".py") else "text",
                "is_valid_python": True if str(fpath).endswith(".py") else None
            })
    elif isinstance(raw_files, list):
        for f in raw_files:
            if isinstance(f, dict):
                fpath = str(f.get("path") or "main.py")
                files.append({
                    "path": fpath,
                    "content": str(f.get("content") or ""),
                    "language": str(f.get("language") or ("python" if fpath.endswith(".py") else "text")),
                    "is_valid_python": f.get("is_valid_python")
                })

    dir_struct = raw.get("directory_structure")
    if not isinstance(dir_struct, list) or len(dir_struct) == 0:
        dir_struct = [f["path"] for f in files]

    return {
        "directory_structure": dir_struct,
        "files": files
    }

def normalize_testcases(raw: Any) -> Dict[str, Any]:
    """
    Canonical Test Cases Schema:
    {
      "cases": [
        {
          "test_id": str,
          "linked_req_id": str,
          "scenario": str,
          "preconditions": str,
          "steps": str or list,
          "expected_result": str,
          "type": str
        }
      ]
    }
    """
    if isinstance(raw, list):
        raw_cases = raw
    elif isinstance(raw, dict):
        raw_cases = raw.get("cases") or raw.get("test_cases") or raw.get("tests") or []
    else:
        raw_cases = []

    cases: List[Dict[str, Any]] = []
    for idx, c in enumerate(raw_cases):
        if not isinstance(c, dict):
            continue
        
        steps = c.get("steps", "")
        if isinstance(steps, list):
            steps = "\n".join([f"{i+1}. {s}" for i, s in enumerate(steps)])
        else:
            steps = str(steps)

        c_type = str(c.get("type") or "positive").lower()
        if c_type not in ["positive", "negative", "boundary"]:
            c_type = "positive"

        cases.append({
            "test_id": str(c.get("test_id") or c.get("id") or f"TC-{idx+1:03d}"),
            "linked_req_id": str(c.get("linked_req_id") or c.get("requirement_id") or c.get("req_id") or "FR-001"),
            "scenario": str(c.get("scenario") or c.get("description") or c.get("name") or ""),
            "preconditions": str(c.get("preconditions") or c.get("precondition") or "System is running and accessible."),
            "steps": steps,
            "expected_result": str(c.get("expected_result") or c.get("expected") or "Action completes successfully."),
            "type": c_type
        })

    return {"cases": cases}

def normalize_artifact_content(artifact_type: str, raw_content: Any) -> Dict[str, Any]:
    """Route artifact payload to the exact normalizer."""
    if artifact_type == "srs":
        return normalize_srs(raw_content)
    elif artifact_type == "schema":
        return normalize_schema(raw_content)
    elif artifact_type == "architecture":
        return normalize_architecture(raw_content)
    elif artifact_type == "api":
        return normalize_api(raw_content)
    elif artifact_type == "skeleton":
        return normalize_skeleton(raw_content)
    elif artifact_type == "testcases":
        return normalize_testcases(raw_content)
    elif isinstance(raw_content, dict):
        return raw_content
    else:
        return {"content": raw_content}
