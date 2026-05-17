from fastapi import APIRouter

router = APIRouter()


@router.get("/sessions")
def list_sessions():
  return {"items": []}

