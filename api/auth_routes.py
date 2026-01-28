"""
Auth routes for Supabase authentication.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from api.auth import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
async def get_current_user_info(user: dict = Depends(get_current_user)):
    """
    Get current authenticated user info from JWT token.
    """
    return {
        "user_id": user.get("sub"),
        "email": user.get("email"),
        "aud": user.get("aud"),
    }


@router.get("/verify")
async def verify_token(user: dict = Depends(get_current_user)):
    """
    Verify if token is valid. Returns user info if valid.
    """
    return {
        "valid": True,
        "user_id": user.get("sub"),
        "email": user.get("email"),
    }
