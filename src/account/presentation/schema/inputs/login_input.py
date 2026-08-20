from typing import Optional

import strawberry


@strawberry.input
class LoginInput:
    email: str
    password: str
    tenant_id: Optional[strawberry.ID] = None
