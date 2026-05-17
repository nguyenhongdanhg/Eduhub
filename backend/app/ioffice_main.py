from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

from app.controllers.ioffice import router as ioffice_router
from app.controllers.system import router as system_router
from app.controllers.rag import router as rag_router
from app.controllers.system_config import router as system_config_router
from app.controllers.ai import router as ai_router


app = FastAPI(title="iOffice Fetcher Service")
app.include_router(ioffice_router, prefix="/api/ioffice")
app.include_router(system_router, prefix="/api/system")
app.include_router(rag_router, prefix="/api/rag")
app.include_router(system_config_router, prefix="/api")
app.include_router(ai_router, prefix="/api/ai")

try:
  from app.services.ioffice_auto_summary import ioffice_auto_summary_worker

  @app.on_event("startup")
  def _start_auto_summary():
    ioffice_auto_summary_worker.start()
except Exception:
  pass

try:
  from app.services.ioffice_audio_schema import ensure_ioffice_audio_columns

  @app.on_event("startup")
  def _ensure_audio_schema():
    ensure_ioffice_audio_columns()
except Exception:
  pass

try:
  from app.services.ioffice_prompt_schema import ensure_ioffice_prompt_tables

  @app.on_event("startup")
  def _ensure_prompt_schema():
    ensure_ioffice_prompt_tables()
except Exception:
  pass


@app.get("/healthz")
def healthz():
  return {"ok": True}


try:
  from pathlib import Path

  dist_dir = (Path(__file__).resolve().parents[2] / "frontend" / "dist")
  if dist_dir.exists():
    views_dir = dist_dir / "views"
    assets_dir = dist_dir / "assets"
    static_dir = dist_dir / "static"
    if views_dir.exists():
      @app.get("/", include_in_schema=False)
      def _frontend_root():
        return RedirectResponse(url="/views/dashboard/index.html")

      app.mount("/views", StaticFiles(directory=str(views_dir), html=True), name="views")
    if assets_dir.exists():
      app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    if static_dir.exists():
      app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
except Exception:
  pass

