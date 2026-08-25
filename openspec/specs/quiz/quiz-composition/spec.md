# quiz/quiz-composition Specification

## Purpose

Defines the limits a quiz's contents must respect — how many questions a quiz may hold, how many answer choices a question may offer, and how few questions leave a quiz unfit to put in front of a student — together with the rule for which contents count toward those limits.

## Requirements

### Requirement: A quiz declares its own composition limits
A quiz's configuration SHALL declare the maximum number of questions the quiz may hold, the minimum number of questions below which the quiz may not be exposed to a student, and the maximum number of answer choices any of its questions may offer. The system SHALL reject a configuration whose minimum number of questions is not a positive number, whose minimum exceeds its maximum, or whose maximum number of answer choices is not a positive number.

#### Scenario: Configuration with a minimum above the maximum
- **WHEN** a quiz configuration declares a minimum number of questions greater than the maximum
- **THEN** the system rejects the configuration and the quiz is not created

#### Scenario: Configuration with a non-positive answer choice limit
- **WHEN** a quiz configuration declares a maximum number of answer choices of zero or less
- **THEN** the system rejects the configuration and the quiz is not created

#### Scenario: Configuration predating the composition limits
- **WHEN** a quiz's stored configuration declares no minimum number of questions and no maximum number of answer choices
- **THEN** the system applies its defaults and reading that quiz does not fail

### Requirement: Composition limits are enforced when a quiz is created
When a quiz is created, the system SHALL verify that the number of submitted questions does not exceed the configured maximum, and that no submitted question offers more answer choices than the configured maximum. A violation SHALL be reported to the caller as a validation failure identifying the limit that was exceeded, and SHALL prevent the quiz and all of its questions from being created.

#### Scenario: Submitting more questions than allowed
- **WHEN** a quiz is created with more questions than its configuration allows
- **THEN** the caller receives a validation failure, and neither the quiz nor any of its questions is created

#### Scenario: Submitting a question with too many answer choices
- **WHEN** a quiz is created containing a question offering more answer choices than its configuration allows
- **THEN** the caller receives a validation failure, and neither the quiz nor any of its questions is created

#### Scenario: Submitting exactly the allowed number
- **WHEN** a quiz is created with exactly the maximum allowed number of questions, each offering exactly the maximum allowed number of answer choices
- **THEN** the quiz and its questions are created

#### Scenario: Violation reported as a validation failure
- **WHEN** a composition limit is exceeded
- **THEN** the failure is reported as a validation error naming the exceeded limit, not as an unexpected internal error

### Requirement: Only active, non-deleted contents count toward composition
When counting a quiz's questions or a question's answer choices for the purpose of composition limits, the system SHALL count only those that are active and have not been logically deleted. Logically deleted or deactivated contents SHALL be excluded from every such count.

#### Scenario: Counting a quiz with a logically deleted question
- **WHEN** a quiz holds questions of which some have been logically deleted
- **THEN** the logically deleted questions are excluded from the quiz's question count

#### Scenario: Counting a quiz with a deactivated question
- **WHEN** a quiz holds questions of which some have been deactivated
- **THEN** the deactivated questions are excluded from the quiz's question count

### Requirement: A quiz below its minimum question count may not be exposed to a student
The system SHALL treat a quiz as unfit for a student whenever its count of active, non-deleted questions is below the minimum declared in its configuration, and as fit otherwise. This fitness SHALL be derived from the current count each time it is needed rather than recorded as a stored state, so that it always reflects the quiz's present contents.

#### Scenario: Quiz holding fewer questions than its minimum
- **WHEN** a quiz's count of active, non-deleted questions is below its configured minimum
- **THEN** the quiz is reported as unfit to expose to a student

#### Scenario: Quiz holding exactly its minimum
- **WHEN** a quiz's count of active, non-deleted questions equals its configured minimum
- **THEN** the quiz is reported as fit to expose to a student

#### Scenario: Deleting a question drops a quiz below its minimum
- **WHEN** an author logically deletes a question and the quiz's remaining count of active, non-deleted questions falls below its configured minimum
- **THEN** the deletion is carried out, and the quiz is thereafter reported as unfit to expose to a student

#### Scenario: Restoring a question brings a quiz back to its minimum
- **WHEN** an author restores or reactivates a question and the quiz's count of active, non-deleted questions reaches its configured minimum again
- **THEN** the quiz is reported as fit to expose to a student, with no further action required

#### Scenario: Author sees a quiz's fitness
- **WHEN** an author lists quizzes
- **THEN** each quiz shows whether it is currently fit to expose to a student
