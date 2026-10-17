"""
Knowledge Graph — Graph Manager
=================================
Builds and maintains a directed property graph using NetworkX.

The graph models the entire data warehouse schema as nodes and edges:

    Node types:
        • table   — a dataset table (row_count, column_count, dataset_id)
        • column  — a column in a table (dtype, semantic_type, is_metric, is_dimension)

    Edge types:
        • HAS_COLUMN     — table → column
        • FK_REFERENCES  — column → column (foreign key relationship)
        • SAME_ENTITY    — column ↔ column (same values across tables)

Why this replaces the current approach:
    The existing ``relationship_engine/graph_builder.py`` stores relationships
    as flat DB rows and BFS join discovery is hardcoded in ``query_mapper.py``
    (~8000 lines).  A proper graph makes join path discovery, shortest-path
    queries, and relationship reasoning native O(V+E) operations.
"""

import logging
from typing import Any

import networkx as nx
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.relationship import DatasetRelationship
from app.metadata.models import ColumnMetadata, TableMetadata

logger = logging.getLogger(__name__)

# Module-level graph cache: one graph per workspace.
_graphs: dict[int, nx.DiGraph] = {}


def _node_id(node_type: str, *parts: str) -> str:
    """Create a unique node ID like 'table:orders' or 'column:orders.city'."""
    return f"{node_type}:{'.'.join(parts)}"


def build_graph(db: Session, workspace_id: int) -> nx.DiGraph:
    """
    Build (or rebuild) the knowledge graph for a workspace.

    Reads from TableMetadata, ColumnMetadata, and DatasetRelationship
    to construct a typed property graph.
    """
    G = nx.DiGraph()

    # ── 1. Add table nodes ──
    tables = db.query(TableMetadata).filter(
        TableMetadata.workspace_id == workspace_id
    ).all()

    for t in tables:
        nid = _node_id("table", t.table_name)
        G.add_node(nid, **{
            "type": "table",
            "name": t.table_name,
            "original_filename": t.original_filename,
            "row_count": t.row_count,
            "column_count": t.column_count,
            "dataset_id": t.dataset_id,
            "domain": t.domain,
        })

    # ── 2. Add column nodes + HAS_COLUMN edges ──
    columns = db.query(ColumnMetadata).filter(
        ColumnMetadata.workspace_id == workspace_id
    ).all()

    for c in columns:
        col_nid = _node_id("column", c.table_name, c.column_name)
        tbl_nid = _node_id("table", c.table_name)

        G.add_node(col_nid, **{
            "type": "column",
            "name": c.column_name,
            "table": c.table_name,
            "dtype": c.data_type,
            "semantic_type": c.semantic_type,
            "is_metric": c.is_metric,
            "is_dimension": c.is_dimension,
            "is_temporal": c.is_temporal,
            "is_identifier": c.is_identifier,
            "distinct_count": c.distinct_count,
            "dataset_id": c.dataset_id,
        })

        if G.has_node(tbl_nid):
            G.add_edge(tbl_nid, col_nid, type="HAS_COLUMN")

    # ── 3. Add FK_REFERENCES edges from DatasetRelationship ──
    datasets = db.query(Dataset).filter(
        Dataset.workspace_id == workspace_id,
        Dataset.is_processed == 1,
    ).all()
    ds_map = {d.id: d.cleaned_table_name for d in datasets}

    rels = db.query(DatasetRelationship).filter(
        DatasetRelationship.source_dataset_id.in_([d.id for d in datasets])
    ).all()

    for rel in rels:
        src_table = ds_map.get(rel.source_dataset_id)
        tgt_table = ds_map.get(rel.target_dataset_id)
        if not src_table or not tgt_table:
            continue

        src_col_nid = _node_id("column", src_table, rel.source_column)
        tgt_col_nid = _node_id("column", tgt_table, rel.target_column)

        if G.has_node(src_col_nid) and G.has_node(tgt_col_nid):
            edge_attrs = {
                "type": "FK_REFERENCES",
                "confidence": getattr(rel, "confidence", None),
                "overlap_pct": getattr(rel, "value_overlap_percent", None),
                "src_table": src_table,
                "tgt_table": tgt_table,
                "src_column": rel.source_column,
                "tgt_column": rel.target_column,
            }
            G.add_edge(src_col_nid, tgt_col_nid, **edge_attrs)
            # Add reverse edge for undirected join traversal
            G.add_edge(tgt_col_nid, src_col_nid, **{**edge_attrs, "type": "FK_REFERENCES_REV"})

    # ── 4. Detect SAME_ENTITY edges (columns with same name across tables) ──
    col_by_name: dict[str, list[str]] = {}
    for c in columns:
        clean = c.column_name.lower().strip()
        col_nid = _node_id("column", c.table_name, c.column_name)
        col_by_name.setdefault(clean, []).append(col_nid)

    for name, nids in col_by_name.items():
        if len(nids) > 1:
            for i, a in enumerate(nids):
                for b in nids[i + 1:]:
                    if not G.has_edge(a, b):
                        G.add_edge(a, b, type="SAME_ENTITY", shared_name=name)
                        G.add_edge(b, a, type="SAME_ENTITY", shared_name=name)

    # Cache and return
    _graphs[workspace_id] = G
    logger.info(
        f"Knowledge graph built for workspace {workspace_id}: "
        f"{G.number_of_nodes()} nodes, {G.number_of_edges()} edges"
    )
    return G


def get_graph(db: Session, workspace_id: int) -> nx.DiGraph:
    """Get the cached graph or build it if not present."""
    if workspace_id not in _graphs:
        build_graph(db, workspace_id)
    return _graphs[workspace_id]


def invalidate(workspace_id: int):
    """Remove cached graph (e.g. after ETL re-runs)."""
    _graphs.pop(workspace_id, None)


def get_table_nodes(G: nx.DiGraph) -> list[dict]:
    """Get all table nodes with their properties."""
    return [
        {"id": nid, **data}
        for nid, data in G.nodes(data=True)
        if data.get("type") == "table"
    ]


def get_columns_for_table(G: nx.DiGraph, table_name: str) -> list[dict]:
    """Get all column nodes for a given table."""
    tbl_nid = _node_id("table", table_name)
    if not G.has_node(tbl_nid):
        return []

    return [
        {"id": succ, **G.nodes[succ]}
        for succ in G.successors(tbl_nid)
        if G.nodes[succ].get("type") == "column"
    ]


def get_relationships(G: nx.DiGraph) -> list[dict]:
    """Get all FK relationship edges."""
    return [
        {"source": u, "target": v, **data}
        for u, v, data in G.edges(data=True)
        if data.get("type") == "FK_REFERENCES"
    ]


def get_graph_summary(G: nx.DiGraph) -> dict:
    """Summary stats for debugging and display."""
    tables = [n for n, d in G.nodes(data=True) if d.get("type") == "table"]
    columns = [n for n, d in G.nodes(data=True) if d.get("type") == "column"]
    fk_edges = [e for e in G.edges(data=True) if e[2].get("type") == "FK_REFERENCES"]
    same_edges = [e for e in G.edges(data=True) if e[2].get("type") == "SAME_ENTITY"]

    return {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "table_count": len(tables),
        "column_count": len(columns),
        "fk_relationships": len(fk_edges),
        "same_entity_links": len(same_edges) // 2,  # bidirectional, count once
        "edge_count": len(fk_edges) + len(same_edges) // 2,
    }
