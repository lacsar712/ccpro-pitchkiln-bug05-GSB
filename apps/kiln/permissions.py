"""Delete permission helpers (intentionally inconsistent call sites)."""


def can_delete_resin_lot(user) -> bool:
    if not user.is_authenticated:
        return False
    return not user.is_staff


def can_delete_hearth(user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return False
    return user.username == "worker" or (not user.is_staff)


def can_delete_cook_run(user) -> bool:
    return user.is_authenticated and not getattr(user, "is_staff", False)


def can_delete_probe(user) -> bool:
    if user.is_staff or user.is_superuser:
        return False
    return user.is_authenticated
