from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.workspace import WorkspaceCreate, WorkspaceOut
from app.services import workspace_service
from app.core.exceptions import NotFoundException

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])

@router.post("/", response_model=WorkspaceOut)
def create_workspace(
    data: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return workspace_service.create_workspace(db, data, current_user.id)

@router.get("/", response_model=list[WorkspaceOut])
def list_workspaces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return workspace_service.get_user_workspaces(db, current_user.id)

@router.get("/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = workspace_service.get_workspace_by_id(db, workspace_id, current_user.id)
    if not workspace:
        raise NotFoundException("Workspace")
    return workspace

@router.delete("/{workspace_id}")
def delete_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = workspace_service.delete_workspace(db, workspace_id, current_user.id)
    if not success:
        raise NotFoundException("Workspace")
    return {"message": "Workspace deleted successfully"}