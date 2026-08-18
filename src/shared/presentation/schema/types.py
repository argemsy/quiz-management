from typing import Any, Dict, List, NewType, Optional

import strawberry

JSONType = NewType("JSONType", tp=Any)
JSON = strawberry.scalar(
    JSONType,
    description="The `JSON` scalar type represents JSON values as specified by ECMA-404",
    serialize=lambda v: v,
    parse_value=lambda v: v,
)


@strawberry.type
class UserSession:
    session_type: str
    session_key: str
    session_data: JSON
    session_permissions: Optional[List[str]] = None
    session_roles: Optional[List[str]] = None
    feature_flags: Optional[Dict] = None
