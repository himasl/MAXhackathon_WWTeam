from app.core.config import settings


def admin_ids() -> frozenset[int]:
    """MAX ids of the team (SUPPORT_MAX_USER_IDS): only they see the team panel."""
    return frozenset(settings.support_max_user_ids)
