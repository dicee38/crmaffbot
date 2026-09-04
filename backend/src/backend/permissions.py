from fastapi import Depends, HTTPException, status

from backend.deps import get_current_user
from shared.enums import Role
from shared.models import User


def require_role(*roles: Role):
    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return checker
