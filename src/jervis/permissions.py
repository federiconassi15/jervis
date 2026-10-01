from __future__ import annotations

from .models import Permission

ROLE_ORDER = {
    "guest": 0,
    "known": 1,
    "trusted": 2,
    "owner": 3,
}


def allowed(state, user_id: str | None, required: Permission, authenticated: bool) -> bool:
    if required is Permission.PUBLIC:
        return True
    if user_id is None:
        return False

    user = state.user(user_id)
    if user is None:
        return False

    level = ROLE_ORDER.get(str(user["role"]), 0)
    if required is Permission.KNOWN_USER:
        return level >= ROLE_ORDER["known"]
    if required is Permission.TRUSTED_USER:
        return level >= ROLE_ORDER["trusted"] or authenticated
    if required is Permission.OWNER:
        return level >= ROLE_ORDER["owner"] and authenticated
    if required is Permission.AUTH_REQUIRED:
        return authenticated
    return False


def describe_role(role: str) -> str:
    level = ROLE_ORDER.get(role, 0)
    return " · ".join(
        [
            "public",
            *([] if level < 1 else ["known-user"]),
            *([] if level < 2 else ["trusted-user"]),
            *([] if level < 3 else ["owner"]),
        ]
    )
