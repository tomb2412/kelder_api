from fastapi import APIRouter

router = APIRouter(tags = ["Health"])

@router.get("/health_check")
def read_root():
    return True
