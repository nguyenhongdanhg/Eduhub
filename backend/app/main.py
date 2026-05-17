from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

from app.routers import router as api_router


app = FastAPI(title="EduAI Hub API")
app.include_router(api_router, prefix="/api")

@app.on_event("startup")
def _startup() -> None:
  try:
    from app.services.ioffice_auto_summary import ioffice_auto_summary_worker

    ioffice_auto_summary_worker.start()
  except Exception:
    pass
  try:
    from app.services.ioffice_rag_worker import ioffice_rag_worker

    ioffice_rag_worker.start()
  except Exception:
    pass

try:
  from pathlib import Path

  dist_dir = (Path(__file__).resolve().parents[2] / "frontend" / "dist")
  if dist_dir.exists():
    @app.get("/", include_in_schema=False)
    def _frontend_root():
      return RedirectResponse(url="/views/dashboard/index.html")

    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")
except Exception:
  pass
