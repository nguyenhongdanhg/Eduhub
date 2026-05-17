from fastapi import APIRouter

router = APIRouter()


@router.get("/documents")
def list_official_documents():
  return {"items": []}

