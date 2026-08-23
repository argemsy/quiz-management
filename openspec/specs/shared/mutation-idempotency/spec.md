# shared/mutation-idempotency Specification

## Purpose

Gives every GraphQL mutation a client-supplied correlation id for cross-system tracing and a separate client-supplied idempotency key that prevents the same logical user action from creating duplicate records when a client resubmits it without having seen the original response.

## Requirements

### Requirement: Mutation requests carry a correlation id for tracing
Every mutation request MUST include a client-supplied correlation id. The system SHALL reject a mutation request that omits it, SHALL include it in every log entry produced while handling that request, SHALL return it on the mutation's response, and SHALL propagate it to any event published as a result of handling that mutation so the same id ties together every downstream effect of the request.

#### Scenario: Correlation id is missing
- **WHEN** a mutation request is received without a correlation id
- **THEN** the system rejects the request without executing the mutation

#### Scenario: Correlation id propagates to a published event
- **WHEN** a mutation that publishes an event completes
- **THEN** the published event carries the same correlation id that was supplied on the mutation request

#### Scenario: Correlation id is echoed back
- **WHEN** a mutation completes, successfully or with an error
- **THEN** the response includes the same correlation id that was supplied on the request

### Requirement: Mutation requests carry a client-supplied idempotency key
Every mutation request MUST include a client-supplied idempotency key, distinct from the correlation id. The system SHALL reject a mutation request that omits it and SHALL NOT generate one on the server's behalf.

#### Scenario: Idempotency key is missing
- **WHEN** a mutation request is received without an idempotency key
- **THEN** the system rejects the request without executing the mutation

### Requirement: A completed mutation is not re-executed for a repeated idempotency key
When a mutation that already reached a definitive outcome (success or a business/validation error) is submitted again with the same idempotency key, the system SHALL return the original outcome without re-executing the mutation's business logic or creating an additional record.

#### Scenario: Repeated key after a successful mutation
- **WHEN** a mutation request is submitted with an idempotency key that already produced a successful result
- **THEN** the system returns that same successful result and does not create a new record

#### Scenario: Repeated key after a business validation error
- **WHEN** a mutation request is submitted with an idempotency key that already produced a business/validation error
- **THEN** the system returns that same error and does not re-execute the mutation

#### Scenario: Repeated key after an unexpected internal error
- **WHEN** a mutation request is submitted with an idempotency key whose previous attempt failed with an unexpected internal error (not a business/validation error)
- **THEN** the system re-executes the mutation as a new attempt

#### Scenario: Concurrent requests with the same idempotency key
- **WHEN** two requests carrying the same idempotency key arrive close enough together that the mutation's business logic has not finished executing for the first one
- **THEN** at most one of them results in a new record being created

### Requirement: Duplicate-record prevention does not depend on a fast-path cache
The prevention of duplicate records for a given idempotency key SHALL hold even when the fast-path check used to short-circuit repeated requests is unavailable.

#### Scenario: Fast-path cache is unavailable
- **WHEN** the same idempotency key is submitted more than once while the fast-path check is unavailable
- **THEN** no more than one record is created for that idempotency key
