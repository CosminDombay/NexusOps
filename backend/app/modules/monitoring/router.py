from fastapi import APIRouter

router = APIRouter()


@router.get("/metrics")
async def list_metrics() -> list[dict[str, str]]:
    return []
