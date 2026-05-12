from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_vms() -> list[dict[str, str]]:
    return []
