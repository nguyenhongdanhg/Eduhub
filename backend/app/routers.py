from fastapi import APIRouter

from app.controllers.ai import router as ai_router
from app.controllers.auth import router as auth_router
from app.controllers.ioffice import router as ioffice_router
from app.controllers.learning import router as learning_router
from app.controllers.management import router as management_router
from app.controllers.rag import router as rag_router
from app.controllers.system import router as system_router
from app.controllers.system_config import router as system_config_router
from app.controllers.teaching import router as teaching_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(system_router, prefix="/system", tags=["system"])
router.include_router(system_config_router, tags=["system_config"])
router.include_router(management_router, prefix="/management", tags=["management"])
router.include_router(teaching_router, prefix="/teaching", tags=["teaching"])
router.include_router(learning_router, prefix="/learning", tags=["learning"])
router.include_router(rag_router, prefix="/rag", tags=["rag"])
router.include_router(ai_router, prefix="/ai", tags=["ai"])
router.include_router(ioffice_router, prefix="/ioffice", tags=["ioffice"])

