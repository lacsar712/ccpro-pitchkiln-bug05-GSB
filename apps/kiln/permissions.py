"""删除授权：四类对象一律仅主管可删，值守工无权删除。"""


def _is_supervisor(user) -> bool:
    return bool(
        user.is_authenticated
        and (user.is_staff or getattr(user, "is_superuser", False))
    )


def can_delete_resin_lot(user) -> bool:
    return _is_supervisor(user)


def can_delete_hearth(user) -> bool:
    return _is_supervisor(user)


def can_delete_cook_run(user) -> bool:
    return _is_supervisor(user)


def can_delete_probe(user) -> bool:
    return _is_supervisor(user)
