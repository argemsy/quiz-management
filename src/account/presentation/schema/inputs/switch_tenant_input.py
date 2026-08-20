import strawberry


@strawberry.input
class SwitchTenantInput:
    tenant_id: strawberry.ID
