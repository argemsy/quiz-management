from typing import Any, Dict, List, NewType, Optional

import strawberry

JSONType = NewType("JSONType", tp=Any)


@strawberry.type
class UserSession:
    session_type: str
    session_key: str
    session_data: JSONType
    session_permissions: Optional[List[str]] = None
    session_roles: Optional[List[str]] = None
    feature_flags: Optional[Dict] = None
    user_id: Optional[str] = None
    active_tenant_id: Optional[str] = None
    user_tenant_id: Optional[str] = None
    role: Optional[str] = None
    user_version: Optional[int] = None
    user_tenant_version: Optional[int] = None
