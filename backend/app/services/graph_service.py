from backend.app.services.domain_validator import singularize
import json
import logging
from typing import Dict, Any, List, Optional
import networkx as nx
from sqlalchemy.orm import Session
from backend.app.models.project import Project
from backend.app.models.requirement import ExtractedRequirement
from backend.app.models.artifact import Artifact
from backend.app.models.graph import GraphData
from backend.app.schemas.graph import GraphNode, GraphEdge, TraceabilityRow, ImpactAnalysisResult

logger = logging.getLogger(__name__)

class GraphService:
    @staticmethod
    def generate_knowledge_graph(project_id: str, db: Session) -> Dict[str, Any]:
        """Build NetworkX directed graph connecting requirements, actors, modules, APIs, entities, and test cases."""
        G = nx.DiGraph()

        # 1. Fetch Requirements
        reqs = db.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == project_id).all()
        
        # 2. Fetch Artifacts for APIs, Tables, TestCases
        api_art = db.query(Artifact).filter(Artifact.project_id == project_id, Artifact.artifact_type == "api").first()
        schema_art = db.query(Artifact).filter(Artifact.project_id == project_id, Artifact.artifact_type == "schema").first()
        tc_art = db.query(Artifact).filter(Artifact.project_id == project_id, Artifact.artifact_type == "testcases").first()

        apis = []
        if api_art and api_art.content_json:
            try:
                apis = json.loads(api_art.content_json).get("endpoints", [])
            except Exception:
                pass

        tables = []
        if schema_art and schema_art.content_json:
            try:
                tables = json.loads(schema_art.content_json).get("tables", [])
            except Exception:
                pass

        test_cases = []
        if tc_art and tc_art.content_json:
            try:
                test_cases = json.loads(tc_art.content_json).get("cases", [])
            except Exception:
                pass

        # Build Graph Nodes & Edges
        nodes = []
        edges = []

        # Add Requirements, Actors, Modules, Entities from extracted requirements
        for r in reqs:
            node_type = "Requirement"
            if r.category == "actor":
                node_type = "Actor"
            elif r.category == "module":
                node_type = "Module"
            elif r.category == "entity":
                node_type = "Database Entity"

            G.add_node(r.req_id, label=r.title, type=node_type, category=r.category, description=r.description)
            nodes.append({
                "id": r.req_id,
                "label": r.title,
                "type": node_type,
                "category": r.category,
                "data": {"description": r.description, "priority": r.priority}
            })

            # Edge: Requirement belongs_to Module
            if r.module_name and r.category == "functional":
                # Find matching module req_id
                mod = next((m for m in reqs if m.category == "module" and (m.title.lower() in r.module_name.lower() or r.module_name.lower() in m.title.lower())), None)
                if mod:
                    edge_id = f"e_{r.req_id}_{mod.req_id}"
                    G.add_edge(r.req_id, mod.req_id, label="belongs_to")
                    edges.append({"id": edge_id, "source": r.req_id, "target": mod.req_id, "label": "belongs_to"})

        # Add Table Entities from schema if not already present
        table_node_map = {}
        for t in tables:
            t_name = t["name"].lower()
            t_id = f"ENT_{t['name']}"
            table_node_map[t_name] = t_id
            if not G.has_node(t_id):
                G.add_node(t_id, label=t['name'].capitalize(), type="Database Entity", category="entity")
                nodes.append({
                    "id": t_id,
                    "label": t['name'].capitalize(),
                    "type": "Database Entity",
                    "category": "entity",
                    "data": {"columns": len(t.get("columns", []))}
                })

        # Add Module nodes if not already present
        module_node_map = {}
        for r in reqs:
            if r.category == "module":
                module_node_map[r.title.lower()] = r.req_id
            elif r.module_name:
                mod_lower = r.module_name.lower()
                if mod_lower not in module_node_map:
                    mod_id = f"MOD_{r.module_name.replace(' ', '_').upper()}"
                    module_node_map[mod_lower] = mod_id
                    if not G.has_node(mod_id):
                        G.add_node(mod_id, label=r.module_name, type="Module", category="module")
                        nodes.append({
                            "id": mod_id,
                            "label": r.module_name,
                            "type": "Module",
                            "category": "module",
                            "data": {"description": f"{r.module_name} functional domain module"}
                        })

        # Add APIs
        api_nodes_map = {}
        for idx, api in enumerate(apis):
            api_id = f"API-{idx+1:03d}"
            label = f"{api['method']} {api['path']}"
            api_nodes_map[api_id] = api
            G.add_node(api_id, label=label, type="API", category="api")
            nodes.append({
                "id": api_id,
                "label": label,
                "type": "API",
                "category": "api",
                "data": {"summary": api.get("summary"), "requirement_ids": api.get("requirement_ids", [])}
            })

            # Edge: endpoint -> table
            api_path_lower = api['path'].lower()
            api_tag_lower = (api.get('tag') or '').lower()
            for t_name, t_id in table_node_map.items():
                t_stem = t_name[:-1] if t_name.endswith('s') and len(t_name) > 3 else t_name
                if t_name in api_path_lower or t_stem in api_path_lower or t_name in api_tag_lower or t_stem in api_tag_lower:
                    edge_id = f"e_{api_id}_{t_id}"
                    if not G.has_edge(api_id, t_id):
                        G.add_edge(api_id, t_id, label="accesses_table")
                        edges.append({"id": edge_id, "source": api_id, "target": t_id, "label": "accesses_table"})

        # Add Test Cases
        for tc in test_cases:
            tc_id = tc['test_id']
            G.add_node(tc_id, label=tc['test_id'], type="Test Case", category="testcase")
            nodes.append({
                "id": tc_id,
                "label": f"{tc['test_id']}: {tc.get('scenario', '')[:30]}...",
                "type": "Test Case",
                "category": "testcase",
                "data": {"scenario": tc.get("scenario"), "type": tc.get("type"), "linked_req_id": tc.get("linked_req_id")}
            })

            # Edge: requirement -> test case (linked_req_id)
            linked_req = tc.get("linked_req_id")
            if linked_req and G.has_node(linked_req):
                edge_id = f"e_{linked_req}_{tc_id}"
                if not G.has_edge(linked_req, tc_id):
                    G.add_edge(linked_req, tc_id, label="verified_by")
                    edges.append({"id": edge_id, "source": linked_req, "target": tc_id, "label": "verified_by"})

        # Edge: requirement -> endpoint (using requirement_ids)
        for api_id, api in api_nodes_map.items():
            for rid in api.get("requirement_ids", []):
                if G.has_node(rid):
                    edge_id = f"e_{rid}_{api_id}"
                    if not G.has_edge(rid, api_id):
                        G.add_edge(rid, api_id, label="implemented_by")
                        edges.append({"id": edge_id, "source": rid, "target": api_id, "label": "implemented_by"})

        # Edge: requirement -> database table (persists_to)
        # 1. Primary: explicit validated requirement_ids declared in schema tables
        for t in tables:
            t_name = (t.get("name") or "").lower()
            t_id = table_node_map.get(t_name)
            if not t_id or not G.has_node(t_id):
                continue
            for rid in t.get("requirement_ids", []):
                if G.has_node(rid):
                    edge_id = f"e_{rid}_{t_id}"
                    if not G.has_edge(rid, t_id):
                        G.add_edge(rid, t_id, label="persists_to")
                        edges.append({"id": edge_id, "source": rid, "target": t_id, "label": "persists_to"})

        # 2. Domain model entity requirements matching database tables
        for r in reqs:
            if r.category == "entity":
                r_title_clean = r.title.lower().strip()
                for t_name, t_id in table_node_map.items():
                    if r_title_clean == t_name or singularize(r_title_clean) == singularize(t_name):
                        edge_id = f"e_{r.req_id}_{t_id}"
                        if not G.has_edge(r.req_id, t_id):
                            G.add_edge(r.req_id, t_id, label="persists_to")
                            edges.append({"id": edge_id, "source": r.req_id, "target": t_id, "label": "persists_to"})

            # Edge: requirement -> module (genuine structural relationship)
            if r.module_name:
                mod_lower = r.module_name.lower()
                mod_id = module_node_map.get(mod_lower)
                if mod_id and G.has_node(mod_id):
                    edge_id = f"e_{r.req_id}_{mod_id}"
                    if not G.has_edge(r.req_id, mod_id):
                        G.add_edge(r.req_id, mod_id, label="belongs_to")
                        edges.append({"id": edge_id, "source": r.req_id, "target": mod_id, "label": "belongs_to"})

        # Edge: actor -> requirement
        actors = [r for r in reqs if r.category == "actor"]
        for act in actors:
            act_name_lower = act.title.lower()
            act_tokens = [w for w in act_name_lower.split() if len(w) > 3]
            for r in reqs:
                if r.category == "functional":
                    r_text = f"{r.title} {r.description}".lower()
                    if act_name_lower in r_text or any(tok in r_text for tok in act_tokens):
                        edge_id = f"e_{act.req_id}_{r.req_id}"
                        if not G.has_edge(act.req_id, r.req_id):
                            G.add_edge(act.req_id, r.req_id, label="initiates")
                            edges.append({"id": edge_id, "source": act.req_id, "target": r.req_id, "label": "initiates"})

        # Identify requirements without outgoing links for accurate unmapped reporting
        outgoing_counts = {r.req_id: 0 for r in reqs}
        for e in edges:
            if e["source"] in outgoing_counts:
                outgoing_counts[e["source"]] += 1

        unlinked_reqs = [r.req_id for r in reqs if outgoing_counts[r.req_id] == 0]
        if unlinked_reqs:
            logger.info(f"Requirements preserved explicitly unmapped/unlinked in Knowledge Graph: {unlinked_reqs}")

        # Build Traceability Matrix
        matrix = []
        for r in reqs:
            if r.category != "functional":
                continue
            
            # Trace connected APIs, entities, testcases from graph edges
            linked_apis = [api['label'] for api in nodes if api['type'] == 'API' and (G.has_edge(r.req_id, api['id']) or G.has_edge(api['id'], r.req_id))]
            linked_ents = [ent['label'] for ent in nodes if ent['type'] == 'Database Entity' and (G.has_edge(r.req_id, ent['id']) or G.has_edge(ent['id'], r.req_id))]
            linked_tcs = [tc['label'] for tc in nodes if tc['type'] == 'Test Case' and (G.has_edge(r.req_id, tc['id']) or G.has_edge(tc['id'], r.req_id))]

            if linked_apis and linked_ents and linked_tcs:
                status = "complete"
            elif linked_apis or linked_ents or linked_tcs:
                status = "partial"
            else:
                status = "unmapped" 

            matrix.append({
                "requirement_id": r.req_id,
                "requirement_title": r.title,
                "category": r.category,
                "module": r.module_name or "General",
                "apis": linked_apis[:2],
                "entities": linked_ents[:2],
                "test_cases": linked_tcs[:2],
                "coverage_status": status
            })

        # Save to DB
        graph_record = db.query(GraphData).filter(GraphData.project_id == project_id).first()
        if not graph_record:
            graph_record = GraphData(
                project_id=project_id,
                nodes_json=json.dumps(nodes),
                edges_json=json.dumps(edges),
                matrix_json=json.dumps(matrix)
            )
            db.add(graph_record)
        else:
            graph_record.nodes_json = json.dumps(nodes)
            graph_record.edges_json = json.dumps(edges)
            graph_record.matrix_json = json.dumps(matrix)

        db.commit()

        return {
            "nodes_count": len(nodes),
            "edges_count": len(edges),
            "matrix_rows": len(matrix)
        }

    @staticmethod
    def get_graph_data(project_id: str, db: Session) -> Dict[str, Any]:
        graph_record = db.query(GraphData).filter(GraphData.project_id == project_id).first()
        if not graph_record:
            # Generate if not exists
            GraphService.generate_knowledge_graph(project_id, db)
            graph_record = db.query(GraphData).filter(GraphData.project_id == project_id).first()

        nodes = json.loads(graph_record.nodes_json) if graph_record else []
        edges = json.loads(graph_record.edges_json) if graph_record else []
        matrix = json.loads(graph_record.matrix_json) if graph_record else []

        stats = {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "requirements": sum(1 for n in nodes if n["type"] == "Requirement"),
            "modules": sum(1 for n in nodes if n["type"] == "Module"),
            "apis": sum(1 for n in nodes if n["type"] == "API"),
            "entities": sum(1 for n in nodes if n["type"] == "Database Entity"),
            "test_cases": sum(1 for n in nodes if n["type"] == "Test Case")
        }

        return {
            "nodes": nodes,
            "edges": edges,
            "matrix": matrix,
            "stats": stats
        }

    @staticmethod
    def get_impact_analysis(project_id: str, node_id: str, db: Session) -> ImpactAnalysisResult:
        """Find all affected upstream and downstream nodes for a given requirement or entity."""
        data = GraphService.get_graph_data(project_id, db)
        nodes = {n["id"]: n for n in data["nodes"]}
        edges = data["edges"]

        # Build networkx graph
        G = nx.Graph()  # undirected for blast-radius impact
        for n in data["nodes"]:
            G.add_node(n["id"], **n)
        for e in edges:
            G.add_edge(e["source"], e["target"], label=e.get("label", ""))

        if not G.has_node(node_id):
            return ImpactAnalysisResult(
                selected_node_id=node_id,
                selected_node_type="Unknown",
                affected_nodes=[],
                affected_edges=[],
                impact_summary="Selected node not found in graph."
            )

        # BFS traversal up to max_depth = 2 over valid graph edges
        from collections import deque
        queue = deque([(node_id, 0)])
        visited = {node_id}
        while queue:
            curr_id, depth = queue.popleft()
            if depth < 2:
                for neighbor in G.neighbors(curr_id):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1))
        connected_ids = visited

        affected_nodes = [GraphNode(**nodes[nid]) for nid in connected_ids if nid in nodes]
        affected_edges = [GraphEdge(**e) for e in edges if e["source"] in connected_ids and e["target"] in connected_ids]

        selected_label = nodes.get(node_id, {}).get("label", node_id)
        selected_type = nodes.get(node_id, {}).get("type", "Node")

        req_affected = sum(1 for n in affected_nodes if n.type == "Requirement" and n.id != node_id)
        api_affected = sum(1 for n in affected_nodes if n.type == "API")
        ent_affected = sum(1 for n in affected_nodes if n.type == "Database Entity")
        tc_affected = sum(1 for n in affected_nodes if n.type == "Test Case")

        summary = (
            f"Modifying '{selected_label}' ({selected_type}) impacts {len(affected_nodes) - 1} system artifacts: "
            f"{api_affected} API endpoints, {ent_affected} database entities, and {tc_affected} test cases. "
            f"All linked test scenarios must be re-verified upon specification change."
        )

        return ImpactAnalysisResult(
            selected_node_id=node_id,
            selected_node_type=selected_type,
            affected_nodes=affected_nodes,
            affected_edges=affected_edges,
            impact_summary=summary
        )
