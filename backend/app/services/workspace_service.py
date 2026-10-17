from sqlalchemy.orm import Session
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate

def create_workspace(db: Session, data: WorkspaceCreate, owner_id: int) -> Workspace:
    workspace = Workspace(
        name=data.name,
        description=data.description,
        owner_id=owner_id,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace

def get_user_workspaces(db: Session, owner_id: int) -> list[Workspace]:
    return db.query(Workspace).filter(Workspace.owner_id == owner_id).all()

def get_workspace_by_id(db: Session, workspace_id: int, owner_id: int) -> Workspace | None:
    return db.query(Workspace).filter(
        Workspace.id == workspace_id, Workspace.owner_id == owner_id
    ).first()

def delete_workspace(db: Session, workspace_id: int, owner_id: int) -> bool:
    workspace = get_workspace_by_id(db, workspace_id, owner_id)
    if not workspace:
        return False
    
    # Clean up physical files and dataset tables before deleting workspace
    from app.models.dataset import Dataset
    import os
    from sqlalchemy import create_engine, text
    from app.core.config import settings
    
    datasets = db.query(Dataset).filter(Dataset.workspace_id == workspace_id).all()
    if datasets:
        engine = create_engine(settings.DATABASE_URL)
        try:
            with engine.begin() as conn:
                for ds in datasets:
                    if ds.file_path and os.path.exists(ds.file_path):
                        try:
                            os.remove(ds.file_path)
                        except Exception:
                            pass
                    if ds.cleaned_table_name:
                        conn.execute(text(f'DROP TABLE IF EXISTS "{ds.cleaned_table_name}"'))
        except Exception as e:
            import logging
            logging.error(f"Failed to drop dataset tables during workspace delete: {e}")
        finally:
            engine.dispose()
            
    # Due to cascade="all, delete-orphan", all related datasets, entities, etc. will also be deleted from the database
    db.delete(workspace)
    db.commit()
    return True