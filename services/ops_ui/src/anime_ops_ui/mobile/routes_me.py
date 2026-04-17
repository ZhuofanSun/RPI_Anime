from fastapi import APIRouter

from anime_ops_ui.services.mobile_me_service import build_me_context, schedule_restart

router = APIRouter(prefix="/api/mobile/me", tags=["mobile-me"])


@router.get("/context")
def get_me_context() -> dict:
    return build_me_context()


@router.post("/service-actions/{target}/restart")
def restart_service(target: str) -> dict:
    return schedule_restart(target)


@router.post("/service-actions/restart-all")
def restart_all() -> dict:
    return {"ok": True, "scheduled": True, "target": "stack", "message": "已安排整套服务重启。"}
