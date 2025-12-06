from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import jwt
import structlog
from datetime import datetime, timedelta

from app.config import settings

logger = structlog.get_logger()
security = HTTPBearer(auto_error=False)


class AuthMiddleware:
    """Authentication middleware for JWT and API key authentication"""
    
    async def __call__(self, request: Request, call_next):
        # Skip authentication for health checks and docs
        if self._is_public_path(request.url.path):
            return await call_next(request)
        
        # Try JWT authentication first
        credentials = await security(request)
        if credentials:
            try:
                payload = self._verify_jwt_token(credentials.credentials)
                request.state.user_id = payload.get("sub")
                request.state.permissions = payload.get("permissions", [])
                logger.info("JWT authentication successful", user_id=request.state.user_id)
            except jwt.PyJWTError as e:
                logger.warning("JWT authentication failed", error=str(e))
                raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        else:
            # Try API key authentication
            api_key = request.headers.get("X-API-Key")
            if api_key:
                if self._verify_api_key(api_key):
                    request.state.user_id = "api_user"
                    request.state.permissions = ["read", "write"]
                    logger.info("API key authentication successful")
                else:
                    raise HTTPException(status_code=401, detail="Invalid API key")
            else:
                # No authentication provided
                raise HTTPException(status_code=401, detail="Authentication required")
        
        return await call_next(request)
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (doesn't require authentication)"""
        public_paths = [
            "/",
            "/health",
            "/ready", 
            "/live",
            "/docs",
            "/redoc",
            "/openapi.json"
        ]
        return path in public_paths or path.startswith("/static")
    
    def _verify_jwt_token(self, token: str) -> dict:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.algorithm]
            )
            
            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
                raise jwt.PyJWTError("Token has expired")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise jwt.PyJWTError("Token has expired")
        except jwt.InvalidTokenError:
            raise jwt.PyJWTError("Invalid token")
    
    def _verify_api_key(self, api_key: str) -> bool:
        """Verify API key (this would typically check against a database)"""
        # For demo purposes, accept a hardcoded key
        # In production, this would verify against a secure store
        valid_keys = [
            "demo-api-key-12345",
            "test-api-key-67890"
        ]
        return api_key in valid_keys


def create_jwt_token(user_id: str, permissions: list = None) -> str:
    """Create a JWT token for a user"""
    payload = {
        "sub": user_id,
        "permissions": permissions or ["read"],
        "exp": datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes),
        "iat": datetime.utcnow()
    }
    
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)