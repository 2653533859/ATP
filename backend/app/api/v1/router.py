from fastapi import APIRouter
from app.api.v1 import auth, projects, cases, environments, scripts, devices, apks, device_mirror, suites, plans, webhook, exports

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(projects.router)
router.include_router(cases.router)
router.include_router(environments.router)
router.include_router(scripts.router)
router.include_router(devices.router)
router.include_router(apks.router)
router.include_router(device_mirror.router)
router.include_router(suites.router)
router.include_router(plans.router)
router.include_router(webhook.router)
router.include_router(exports.router)
