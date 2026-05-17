from fastapi import APIRouter

router = APIRouter()


@router.get("/materials")
def list_materials():
  return {"items": []}

