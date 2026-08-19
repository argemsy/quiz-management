## Purpose

Lets a user prove their identity, operate within one tenant at a time, and have permission changes take effect on their session promptly instead of only at token expiry.

## ADDED Requirements

### Requirement: Login issues a session scoped to one active tenant
The system SHALL authenticate a user by email and password and, on success, issue a session representing that user's identity and, unless the user is staff-only, one active tenant membership. The system SHALL NOT issue a session that carries more than one tenant's permissions at a time.

#### Scenario: Successful login with valid credentials and a tenant
- **WHEN** a user submits a valid email, password, and a `tenant_id` for which they have an active membership
- **THEN** the system issues a session carrying that user's identity, the given tenant as active, and the role from that membership

#### Scenario: Successful login for a staff user without a tenant
- **WHEN** a superuser submits valid credentials without a `tenant_id`
- **THEN** the system issues a session carrying staff-level access and no active tenant

#### Scenario: Login rejected for invalid credentials
- **WHEN** a user submits an email/password combination that does not authenticate
- **THEN** the system rejects the login and issues no session

#### Scenario: Login rejected for a tenant the user does not belong to
- **WHEN** a user submits valid credentials with a `tenant_id` for which they have no active membership
- **THEN** the system rejects the login and issues no session

### Requirement: Switching the active tenant does not require re-authentication
An already-authenticated user SHALL be able to change their session's active tenant to any tenant they hold an active membership in, without resubmitting a password.

#### Scenario: Switch to a tenant the user belongs to
- **WHEN** an authenticated user requests to switch their active tenant to one they have an active membership in
- **THEN** the system issues a new session reflecting that tenant as active and the corresponding role

#### Scenario: Switch rejected for a tenant the user does not belong to
- **WHEN** an authenticated user requests to switch their active tenant to one they have no active membership in
- **THEN** the system rejects the switch and the existing session's active tenant is unchanged

### Requirement: Session verification does not require a stored server-side session
The system SHALL be able to verify a session's validity and current permissions using only the data carried by the session token, without a database lookup, when that token's permissions are current.

#### Scenario: Valid, current session is accepted without a database lookup
- **WHEN** a request carries a session token whose permissions are still current
- **THEN** the system accepts the request without querying the primary datastore for permission data

#### Scenario: Request without a session token is treated as anonymous
- **WHEN** a request carries no session token, or one that cannot be verified
- **THEN** the system treats the request as unauthenticated rather than rejecting the request outright

### Requirement: A permission change invalidates the affected session's authority promptly
When a user's staff status or a tenant membership's role changes, any session whose permissions reflect the old value SHALL stop being treated as current on that user's (or that membership's) next request, without waiting for the token's expiry.

#### Scenario: Role change invalidates the affected membership's session
- **WHEN** a `UserTenant` membership's role changes
- **THEN** a session issued for that membership before the change is no longer treated as current

#### Scenario: Staff status change invalidates the affected user's staff-scoped sessions
- **WHEN** a user's staff (superuser) status changes
- **THEN** a session issued for that user before the change is no longer treated as current

#### Scenario: Unrelated changes do not invalidate a session
- **WHEN** a `Tenant` or `UserTenant` field unrelated to permissions changes
- **THEN** sessions for that tenant or membership continue to be treated as current

### Requirement: A stale session is distinguishable from an unauthenticated or forbidden request
When a session's permissions are no longer current, the system SHALL signal this as a distinct, machine-readable condition rather than a generic authentication failure, so a client can attempt a refresh instead of prompting the user to log in again.

#### Scenario: Stale session produces a distinct signal
- **WHEN** a request carries a session token that verifies successfully but whose permissions are no longer current
- **THEN** the system responds with a distinct "session stale" condition, not the same response used for missing or invalid credentials

### Requirement: A stale session can be refreshed without re-entering credentials
The system SHALL allow a session whose identity is still valid but whose permissions are stale to be reissued with current permissions, without requiring the password again.

#### Scenario: Refresh of a stale-but-valid session succeeds
- **WHEN** a refresh is requested with a session token whose identity is still valid but whose permissions are stale
- **THEN** the system issues a new session reflecting the user's and/or membership's current permissions

#### Scenario: Refresh rejected for an invalid or expired session
- **WHEN** a refresh is requested with a session token that has expired or fails identity verification
- **THEN** the system rejects the refresh and issues no new session

### Requirement: Session verification degrades safely when the permission-freshness check is unavailable
If the store used to determine whether a session's permissions are current is unreachable, the system SHALL continue to accept sessions based on the token's own claims rather than rejecting all requests, bounded by the session's expiry.

#### Scenario: Freshness store unreachable
- **WHEN** a request carries a valid, unexpired session token and the permission-freshness store cannot be reached
- **THEN** the system accepts the request using the token's own claims

#### Scenario: Freshness data absent but the store is reachable
- **WHEN** a request carries a session token and the freshness store is reachable but holds no data for that session's scope
- **THEN** the system treats the session as stale, not as a store outage

### Requirement: Sessions expire
Every session token SHALL carry an expiry, after which it SHALL be rejected regardless of whether its permissions were current.

#### Scenario: Expired session rejected
- **WHEN** a request carries a session token past its expiry
- **THEN** the system rejects the request even if the permissions in the token are otherwise current
