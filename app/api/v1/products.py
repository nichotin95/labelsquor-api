"""
Product API endpoints (placeholder)
"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def list_products():
    """List products - to be implemented"""
    return {"message": "Products endpoint coming soon"}
