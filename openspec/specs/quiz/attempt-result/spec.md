# quiz/attempt-result Specification

## Purpose

Defines the uniqueness rules for a user's current quiz result and for the append-only historical record of every attempt, correctly scoped whether or not the user is affiliated with a tenant.

## Requirements

### Requirement: One current result per user and quiz
The system SHALL allow at most one current result per user per quiz, regardless of whether the user is affiliated with a tenant (a tenant-user is recorded) or not (no tenant-user is recorded).

#### Scenario: Tenant-affiliated user already has a current result
- **WHEN** a tenant-affiliated user already has a current result for a quiz
- **THEN** creating a second current result for the same user, tenant-user, and quiz is rejected

#### Scenario: Unaffiliated user already has a current result
- **WHEN** a user with no tenant affiliation already has a current result for a quiz
- **THEN** creating a second current result for the same user and quiz is rejected, even though no tenant-user is recorded on either

### Requirement: One historical record per attempt, scoped per quiz
The system SHALL allow at most one historical result record per user, per quiz, per attempt number, regardless of tenant affiliation, so that attempt numbering for one quiz never collides with attempt numbering for a different quiz taken by the same user.

#### Scenario: Distinct quizzes reuse attempt numbers independently
- **WHEN** the same user completes attempt number 1 of quiz A and attempt number 1 of quiz B
- **THEN** both historical records are stored without conflict

#### Scenario: Duplicate attempt rejected
- **WHEN** a second historical record is submitted for the same user, quiz, and attempt number
- **THEN** the system rejects it, whether or not a tenant-user is recorded
