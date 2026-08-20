## Purpose

Gives every audited entity in the system a queryable, immutable trail of who changed it, when, and what the change was — starting with tenant/tenant-membership changes made through Django admin.

## ADDED Requirements

### Requirement: Audit log entry on Tenant changes via Django admin
The system SHALL record an `AuditLog` entry whenever a `Tenant` is created, edited, or soft-deleted through Django admin.

#### Scenario: Tenant created via admin
- **WHEN** an admin user saves a new `Tenant` in Django admin
- **THEN** an `AuditLog` entry is recorded with `content_type=TENANT`, `action_type=ADDITION`, `source_type=ADMIN`, the acting user, and the tenant's own id

#### Scenario: Tenant edited via admin
- **WHEN** an admin user saves changes to an existing `Tenant` in Django admin
- **THEN** an `AuditLog` entry is recorded with `content_type=TENANT`, `action_type=CHANGE`, `source_type=ADMIN`, and both the pre-change and post-change field values

#### Scenario: Tenant soft-deleted via admin
- **WHEN** an admin user runs the soft-delete bulk action on one or more `Tenant` records in Django admin
- **THEN** a separate `AuditLog` entry with `action_type=DELETION` is recorded for each affected `Tenant`, not one aggregated entry for the whole action

### Requirement: Audit log entry on UserTenant changes via Django admin
The system SHALL record an `AuditLog` entry whenever a `UserTenant` (a user's membership in a tenant) is created, edited, or soft-deleted through Django admin.

#### Scenario: UserTenant created via admin
- **WHEN** an admin user saves a new `UserTenant` in Django admin
- **THEN** an `AuditLog` entry is recorded with `content_type=TENANT_USER`, `action_type=ADDITION`, `source_type=ADMIN`, and `tenant` set to the membership's tenant id

#### Scenario: UserTenant edited via admin
- **WHEN** an admin user saves changes to an existing `UserTenant` in Django admin
- **THEN** an `AuditLog` entry is recorded with `content_type=TENANT_USER`, `action_type=CHANGE`, `source_type=ADMIN`, and both the pre-change and post-change field values

#### Scenario: UserTenant soft-deleted via admin
- **WHEN** an admin user runs the soft-delete bulk action on one or more `UserTenant` records in Django admin
- **THEN** a separate `AuditLog` entry with `action_type=DELETION` is recorded for each affected `UserTenant`, not one aggregated entry for the whole action

### Requirement: Audit log entry captures actor, timestamp, and state snapshot
Every `AuditLog` entry recorded by this capability SHALL identify who made the change, when it happened, and the entity's state before and after the change.

#### Scenario: Actor and timestamp always present
- **WHEN** any `AuditLog` entry is recorded for a Tenant or UserTenant change
- **THEN** the entry has a non-null `user` (the Django admin user who made the change), a non-null `created_at` timestamp, and the changed record's `object_id`

#### Scenario: State snapshot reflects the change
- **WHEN** an `AuditLog` entry is recorded for a CHANGE or DELETION
- **THEN** `metadata.previous_state` reflects the record's field values before the change and `metadata.current_state` reflects them after
