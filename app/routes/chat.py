from fastapi import APIRouter

router = APIRouter()

@router.get("/api/chat/test")
async def chat_test():
    return {"status": "chat router is working"}