# quiz/question-response Specification

## Purpose

Defines how many response records a user's answer to a quiz question may produce, based on the question's response type, and what a single response record may contain.

## Requirements

### Requirement: Response cardinality matches question response type
The system SHALL snapshot the question's response type onto each response record at the moment it is created, and SHALL enforce that a question with response type `SINGLE` or `DEFINITION` has at most one recorded response per quiz form, while a question with response type `MULTIPLE` may have one recorded response per selected answer choice, with no answer choice repeated.

#### Scenario: Recording a single-choice answer
- **WHEN** a user answers a `SINGLE` question by selecting one answer choice
- **THEN** exactly one response record is stored for that quiz form and question

#### Scenario: Rejecting a duplicate single-choice answer
- **WHEN** a second response record is submitted for a quiz form and question that already has a recorded response, and the question's response type is `SINGLE`
- **THEN** the system rejects the second response

#### Scenario: Recording a multiple-choice answer
- **WHEN** a user answers a `MULTIPLE` question by selecting several answer choices
- **THEN** one response record is stored per selected answer choice, and none of them duplicate an already-selected answer choice for that quiz form and question

#### Scenario: Rejecting a duplicate choice on a multiple-choice answer
- **WHEN** the same answer choice is submitted twice for the same quiz form and question, and the question's response type is `MULTIPLE`
- **THEN** the system rejects the duplicate submission

#### Scenario: Recording a free-text answer
- **WHEN** a user answers a `DEFINITION` question with free text
- **THEN** exactly one response record is stored for that quiz form and question, containing the text and no answer choice

### Requirement: Each response record contains exactly one answer
A response record SHALL contain exactly one of: a selected answer choice, or a free-text definition. It SHALL never contain both, and never contain neither.

#### Scenario: Selecting an answer choice
- **WHEN** a response record references an answer choice
- **THEN** its free-text definition SHALL be empty

#### Scenario: Providing a free-text definition
- **WHEN** a response record contains a free-text definition
- **THEN** its answer choice reference SHALL be empty
