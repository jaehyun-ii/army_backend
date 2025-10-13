"""
Authentication service for handling login and token generation.

This service centralizes authentication business logic, eliminating
code duplication between /login and /login-json endpoints.

SOLID Principles:
- SRP: Single responsibility - authentication and token generation
- DIP: Depends on abstractions (CRUD, security functions)
"""
from datetime import timedelta
from typing import Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import UnauthorizedError, ForbiddenError
from app.core.security import create_access_token
from app.crud.user import authenticate_user
from app.schemas.user import Token


class AuthService:
    """
    Service for user authentication and token management.

    Centralizes authentication logic to avoid duplication across endpoints.
    """

    async def authenticate_and_create_token(
        self,
        db: AsyncSession,
        email: str,
        password: str,
    ) -> Token:
        """
        Authenticate user and create access token.

        Args:
            db: Database session
            email: User email
            password: User password

        Returns:
            Token with access_token and token_type

        Raises:
            UnauthorizedError: If credentials are invalid
            ForbiddenError: If user is inactive

        Example:
            token = await auth_service.authenticate_and_create_token(
                db, "user@example.com", "password123"
            )
        """
        # Step 1: Authenticate user
        user = await authenticate_user(db, email, password)
        if not user:
            raise UnauthorizedError(detail="Incorrect email or password")

        # Step 2: Check if user is active
        if not user.is_active:
            raise ForbiddenError(detail="Inactive user")

        # Step 3: Create access token
        access_token_expires = timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=access_token_expires
        )

        return Token(access_token=access_token, token_type="bearer")

    def create_token_response(self, token: Token) -> Dict[str, str]:
        """
        Create standardized token response dict.

        Args:
            token: Token object

        Returns:
            Dict with access_token and token_type
        """
        return {
            "access_token": token.access_token,
            "token_type": token.token_type
        }


# Global service instance
auth_service = AuthService()
