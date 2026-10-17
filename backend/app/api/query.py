# from fastapi import APIRouter, Depends
# from sqlalchemy.orm import Session

# from app.database.session import get_db
# from app.api.deps import get_current_user
# from app.models.user import User
# from app.schemas.query_history import QueryRequest, QueryResult, QueryHistoryOut
# from app.services.query_service import run_natural_language_query
# from app.services.history_service import get_query_history

# router = APIRouter(prefix="/query", tags=["Query"])

# @router.post("/{workspace_id}", response_model=QueryResult)
# def ask_query(
#     workspace_id: int,
#     data: QueryRequest,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user),
# ):
#     return run_natural_language_query(db, workspace_id, current_user.id, data.query)

# @router.get("/history/{workspace_id}", response_model=list[QueryHistoryOut])
# def query_history(
#     workspace_id: int,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user),
# ):
#     return get_query_history(db, workspace_id)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.query_history import QueryRequest, QueryResult, QueryHistoryOut
from app.services.query_service import run_natural_language_query
from app.services.history_service import get_query_history
from app.services import nlp_query_service

router = APIRouter(prefix="/query", tags=["Query"])

@router.get("/history/{workspace_id}", response_model=list[QueryHistoryOut])
def query_history(workspace_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_query_history(db, workspace_id)
@router.post("/{workspace_id}", response_model=QueryResult)
def ask_query(workspace_id: int, data: QueryRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return nlp_query_service.run_query(db, workspace_id, current_user.id, data.query, data.dataset_id)