from src.shared.domain.enums import EnumChoices


class TenantTypeEnum(EnumChoices):
    COMPANY = "COMPANY"
    SCHOOL = "SCHOOL"
    UNIVERSITY = "UNIVERSITY"


class TenantUserRoleEnum(EnumChoices):
    ADMIN = "ADMIN"
    DIRECTOR = "DIRECTOR"
    COLLABORATOR = "COLLABORATOR"
    GUEST = "GUEST"
