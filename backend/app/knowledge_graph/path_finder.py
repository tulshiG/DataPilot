"""
Knowledge Graph — Path Finder
================================
Graph-based join path discovery between tables.

Replaces the BFS logic currently embedded in ``query_mapper.py`` with a
clean API that operates on the knowledge graph.  Supports:

    • Shortest join path between two tables
    • Multi-hop join chain for complex queries
    • Join condition extraction (which columns to join on)
    • Cost estimation (fewer hops = higher confidence)
"""

import logging
from typing import Optional

import networkx as nx

from app.knowledge_graph.graph_manager import _node_id

logger = logging.getLogger(__name__)


def find_join_path(
    G: nx.DiGraph,
    source_table: str,
    target_table: str,
    max_hops: int = 4,
) -> Optional[dict]:
    """
    Find the shortest join path between two tables.

    Parameters
    ----------
    G : nx.DiGraph
        The workspace knowledge graph.
    source_table : str
        Source table name.
    target_table : str
        Target table name.
    max_hops : int
        Maximum number of intermediate tables allowed.

    Returns
    -------
    dict or None
        Join path with: tables, joins (list of join conditions), hop count.
        None if no path exists within max_hops.
    """
    src_nid = _node_id("table", source_table)
    tgt_nid = _node_id("table", target_table)

    if not G.has_node(src_nid) or not G.has_node(tgt_nid):
        return None

    if source_table == target_table:
        return {"tables": [source_table], "joins": [], "hops": 0, "confidence": 1.0}

    # Build a simplified undirected table-level graph from FK edges
    table_graph = nx.Graph()
    for u, v, data in G.edges(data=True):
        if data.get("type") not in ("FK_REFERENCES", "SAME_ENTITY"):
            continue

        u_data = G.nodes.get(u, {})
        v_data = G.nodes.get(v, {})

        if u_data.get("type") != "column" or v_data.get("type") != "column":
            continue

        t1 = u_data.get("table")
        t2 = v_data.get("table")
        if not t1 or not t2 or t1 == t2:
            continue

        # Store the join condition on the edge
        edge_key = (t1, t2) if t1 < t2 else (t2, t1)
        if table_graph.has_edge(*edge_key):
            # Keep the higher-confidence join
            existing = table_graph.edges[edge_key]
            existing_conf = existing.get("confidence") or 0
            new_conf = data.get("confidence") or 0
            if new_conf <= existing_conf:
                continue

        table_graph.add_edge(t1, t2, **{
            "src_column": u_data.get("name"),
            "tgt_column": v_data.get("name"),
            "join_type": data.get("type"),
            "confidence": data.get("confidence"),
            "overlap_pct": data.get("overlap_pct"),
        })

    # Find shortest path
    try:
        path = nx.shortest_path(table_graph, source_table, target_table)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None

    if len(path) - 1 > max_hops:
        return None

    # Extract join conditions along the path
    joins = []
    for i in range(len(path) - 1):
        t1, t2 = path[i], path[i + 1]
        edge_data = table_graph.edges.get((t1, t2), table_graph.edges.get((t2, t1), {}))

        join = {
            "left_table": t1,
            "right_table": t2,
            "left_column": edge_data.get("src_column"),
            "right_column": edge_data.get("tgt_column"),
            "join_type": edge_data.get("join_type", "FK_REFERENCES"),
            "confidence": edge_data.get("confidence"),
        }
        joins.append(join)

    # Confidence decreases with each hop
    hop_count = len(joins)
    base_confidence = min((j.get("confidence") or 0.7) for j in joins) if joins else 1.0
    overall_confidence = max(0.3, base_confidence - (hop_count - 1) * 0.15)

    return {
        "tables": path,
        "joins": joins,
        "hops": hop_count,
        "confidence": round(overall_confidence, 2),
    }


def find_all_paths(
    G: nx.DiGraph,
    source_table: str,
    target_table: str,
    max_hops: int = 3,
) -> list[dict]:
    """
    Find ALL join paths between two tables (up to max_hops), ranked by hop count.
    Useful for showing alternatives when the shortest path has low confidence.
    """
    table_graph = _build_table_graph(G)

    try:
        all_paths = list(nx.all_simple_paths(table_graph, source_table, target_table, cutoff=max_hops))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []

    results = []
    for path in sorted(all_paths, key=len):
        joins = []
        for i in range(len(path) - 1):
            t1, t2 = path[i], path[i + 1]
            edge_data = table_graph.edges.get((t1, t2), table_graph.edges.get((t2, t1), {}))
            joins.append({
                "left_table": t1,
                "right_table": t2,
                "left_column": edge_data.get("src_column"),
                "right_column": edge_data.get("tgt_column"),
            })

        results.append({
            "tables": path,
            "joins": joins,
            "hops": len(joins),
        })

    return results


def get_joinable_tables(G: nx.DiGraph, table_name: str) -> list[str]:
    """Get all tables that can be joined to the given table (direct neighbors)."""
    table_graph = _build_table_graph(G)
    if table_name not in table_graph:
        return []
    return list(table_graph.neighbors(table_name))


def _build_table_graph(G: nx.DiGraph) -> nx.Graph:
    """Build a simplified table-level undirected graph from the full knowledge graph."""
    table_graph = nx.Graph()
    for u, v, data in G.edges(data=True):
        if data.get("type") not in ("FK_REFERENCES", "SAME_ENTITY"):
            continue
        u_data = G.nodes.get(u, {})
        v_data = G.nodes.get(v, {})
        if u_data.get("type") != "column" or v_data.get("type") != "column":
            continue
        t1, t2 = u_data.get("table"), v_data.get("table")
        if t1 and t2 and t1 != t2:
            table_graph.add_edge(t1, t2,
                                 src_column=u_data.get("name"),
                                 tgt_column=v_data.get("name"))
    return table_graph
