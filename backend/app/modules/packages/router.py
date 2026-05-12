from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_package_runs() -> list[dict[str, str]]:
    return []
