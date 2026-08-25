import strawberry


@strawberry.input
class RefreshSessionInput:
    """`token` travels as an explicit input field, not the `Authorization`
    header: a stale-but-unexpired token sent via the header would be
    401'd by `AuthMiddleware` before this mutation's resolver ever runs
    (see design.md - Decisions, `AuthMiddleware`). The client's refresh
    call must omit `Authorization` and pass the stale token here instead.
    """

    token: str
