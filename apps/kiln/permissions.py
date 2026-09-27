"""Delete permission helpers: 仅主管（staff）有删权，值守工一律拒绝。"""


def _is_supervisor(user) -> bool:
    return user.is_authenticated and user.is_staff


def can_delete_resin_lot(user) -> bool:
    return _is_supervisor(user)


def can_delete_hearth(user) -> bool:
    return _is_supervisor(user)


def can_delete_cook_run(user) -> bool:
    return _is_supervisor(user)


def can_delete_probe(user) -> bool:
    return _is_supervisor(user)
