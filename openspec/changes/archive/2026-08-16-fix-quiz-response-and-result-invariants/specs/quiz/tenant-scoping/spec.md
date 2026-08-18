## Purpose

Defines the required alignment between a tenant-affiliated user's organization and the tenant that owns the quiz they are interacting with.

## ADDED Requirements

### Requirement: Tenant-affiliated interactions must match the quiz's tenant
WHEN a quiz form records a tenant-user, the system SHALL require that tenant-user's tenant to match the tenant that owns the quiz being answered.

#### Scenario: Matching tenant
- **WHEN** a tenant-affiliated user starts a quiz form for a quiz owned by their own tenant
- **THEN** the quiz form is created normally

#### Scenario: Mismatched tenant rejected
- **WHEN** a tenant-affiliated user attempts to start a quiz form with a tenant-user recorded, for a quiz owned by a different tenant
- **THEN** the system rejects the attempt

#### Scenario: Unaffiliated user unaffected
- **WHEN** a user with no tenant-user starts a quiz form for any quiz
- **THEN** this invariant does not apply
