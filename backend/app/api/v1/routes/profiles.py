from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_profiles() -> list[dict[str, str]]:
    return []

