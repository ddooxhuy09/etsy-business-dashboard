"""
Middleware to protect all /api/* routes except /api/auth/*.
"""
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from api.auth import verify_supabase_jwt


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to verify JWT token for all /api/* routes except /api/auth/*.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth for public routes
        if self._is_public_route(request.url.path):
            return await call_next(request)
        
        # Skip auth for non-API routes
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            print(f"[AuthMiddleware] Missing Authorization header for: {request.url.path}")
            print(f"[AuthMiddleware] All headers: {dict(request.headers)}")
            return Response(
                content='{"detail":"Missing or invalid Authorization header"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token = auth_header.replace("Bearer ", "").strip()
        print(f"[AuthMiddleware] Verifying token for: {request.url.path}")
        print(f"[AuthMiddleware] Token length: {len(token)}, Token preview: {token[:20]}...")
        
        payload = verify_supabase_jwt(token)
        
        if payload is None:
            print(f"[AuthMiddleware] Token verification failed for: {request.url.path}")
            return Response(
                content='{"detail":"Invalid or expired token"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        print(f"[AuthMiddleware] Token verified successfully for: {request.url.path}, user_id: {payload.get('sub')}")
        # Attach user info to request state for use in route handlers
        request.state.user = payload
        
        return await call_next(request)
    
    def _is_public_route(self, path: str) -> bool:
        """Check if route is public (no auth required)."""
        public_paths = [
            "/api/auth/",
            "/api/docs",
            "/api/openapi.json",
            "/api/redoc",
        ]
        return any(path.startswith(public) for public in public_paths)
