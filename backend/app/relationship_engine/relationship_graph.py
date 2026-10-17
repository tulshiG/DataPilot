from collections import deque
from sqlalchemy.orm import Session
from app.models.relationship import DatasetRelationship
from app.models.dataset import Dataset


def build_relationship_graph(db: Session, workspace_id: int) -> dict:
    """
    Build an adjacency list from validated dataset relationships:
    { dataset_id: [ {neighbor_id, source_column, target_column, direction}, ... ] }
    Edges are added in both directions since a join works either way.
    """
    rels = db.query(DatasetRelationship).filter(
        DatasetRelationship.workspace_id == workspace_id,
        DatasetRelationship.is_validated == "valid",
    ).all()

    graph = {}
    for rel in rels:
        graph.setdefault(rel.source_dataset_id, []).append({
            "neighbor_id": rel.target_dataset_id,
            "local_column": rel.source_column,
            "remote_column": rel.target_column,
        })
        graph.setdefault(rel.target_dataset_id, []).append({
            "neighbor_id": rel.source_dataset_id,
            "local_column": rel.target_column,
            "remote_column": rel.source_column,
        })
    return graph


def find_join_path(db: Session, workspace_id: int, start_dataset_id: int, end_dataset_id: int, max_hops: int = 4) -> list[dict] | None:
    """
    BFS shortest path between two datasets through the validated relationship graph.
    Returns an ordered list of join steps, e.g.:
    [
      {"from_dataset_id": 1, "to_dataset_id": 2, "local_column": "customer_id", "remote_column": "id"},
      {"from_dataset_id": 2, "to_dataset_id": 3, "local_column": "product_id", "remote_column": "id"},
    ]
    Returns None if no path exists within max_hops (avoids runaway joins across
    unrelated datasets that happen to share a coincidental relationship chain).
    """
    if start_dataset_id == end_dataset_id:
        return []

    graph = build_relationship_graph(db, workspace_id)
    if start_dataset_id not in graph:
        return None

    visited = {start_dataset_id}
    queue = deque([(start_dataset_id, [])])

    while queue:
        current_id, path = queue.popleft()
        if len(path) >= max_hops:
            continue

        for edge in graph.get(current_id, []):
            neighbor_id = edge["neighbor_id"]
            if neighbor_id in visited:
                continue

            new_path = path + [{
                "from_dataset_id": current_id,
                "to_dataset_id": neighbor_id,
                "local_column": edge["local_column"],
                "remote_column": edge["remote_column"],
            }]

            if neighbor_id == end_dataset_id:
                return new_path

            visited.add(neighbor_id)
            queue.append((neighbor_id, new_path))

    return None


def resolve_join_path_to_spec_joins(db: Session, path: list[dict]) -> list[dict]:
    """
    Convert a BFS join path (dataset IDs) into the {table, left_table, left_column,
    right_column} format your sql_generator.py already expects for spec["joins"].
    """
    if not path:
        return []

    dataset_cache = {}

    def get_table_name(dataset_id: int) -> str:
        if dataset_id not in dataset_cache:
            ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            dataset_cache[dataset_id] = ds.cleaned_table_name if ds else None
        return dataset_cache[dataset_id]

    spec_joins = []
    for hop in path:
        left_table = get_table_name(hop["from_dataset_id"])
        right_table = get_table_name(hop["to_dataset_id"])
        if not left_table or not right_table:
            continue
        spec_joins.append({
            "table": right_table,
            "left_table": left_table,
            "left_column": hop["local_column"],
            "right_column": hop["remote_column"],
        })
    return spec_joins