from fastapi import APIRouter
from app.api.v1 import auth, projects, cases, environments, scripts, devices

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(projects.router)
router.include_router(cases.router)
router.include_router(environments.router)
router.include_router(scripts.router)
router.include_router(devices.router)
