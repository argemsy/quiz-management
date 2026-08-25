# shared/rate-limiting Specification

## Purpose

Bounds how many requests a single client IP can send to the GraphQL API in a given window, with a materially stricter bound on login attempts, so that a single client cannot flood the system with requests or brute-force credentials, including when it sends requests concurrently.

## Requirements

### Requirement: General per-IP request limit
The system SHALL bound the number of requests a single client IP can make within a rolling time window. A request that exceeds this limit SHALL be rejected before the system does any work on its behalf (no mutation or query execution), and the rejection SHALL indicate when the client may retry.

#### Scenario: Request within the limit
- **WHEN** a client IP has made fewer requests than the configured limit within the current window
- **THEN** the request is processed normally

#### Scenario: Request exceeds the limit
- **WHEN** a client IP has already reached the configured limit within the current window
- **THEN** the next request from that IP is rejected without executing any query or mutation, and the response indicates when to retry

#### Scenario: Concurrent requests from the same IP near the limit
- **WHEN** a client IP is at or near its limit and sends multiple requests at effectively the same time
- **THEN** no more requests are admitted than the configured limit allows, regardless of how many arrived concurrently

### Requirement: Stricter limit on login attempts
Login attempts from a single client IP SHALL be bounded by a separate, stricter limit than the general per-IP request limit, independent of how much of the general limit that IP has already used.

#### Scenario: Login attempts exceed the login-specific limit while under the general limit
- **WHEN** a client IP has exceeded the login-specific attempt limit but has not exceeded the general request limit
- **THEN** further login attempts from that IP are rejected

#### Scenario: Non-login requests are unaffected by the login-specific limit
- **WHEN** a client IP has exceeded the login-specific attempt limit
- **THEN** requests from that IP for mutations or queries other than login are still evaluated only against the general per-IP request limit

### Requirement: Rate limit identifies clients by actual connection address
The system SHALL identify the client for rate-limiting purposes using the actual network connection address, not a value supplied by the client itself, so the limit cannot be bypassed by altering a request header.

#### Scenario: Client supplies a forged address header
- **WHEN** a request arrives with a client-supplied header claiming a different origin address
- **THEN** the rate limit is still evaluated against the request's actual connection address, not the claimed one
