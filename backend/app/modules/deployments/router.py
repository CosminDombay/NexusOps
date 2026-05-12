from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_deployments() -> list[dict[str, str]]:
    return []
