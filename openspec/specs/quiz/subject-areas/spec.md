# quiz/subject-areas Specification

## Purpose

Defines how a tenant classifies its quizzes: a vocabulary of named areas the tenant defines for itself, organized in one optional level of sub-areas, and the relation binding a quiz to the areas it covers.

## Requirements

### Requirement: A tenant defines its own areas
An area SHALL belong to exactly one tenant and SHALL carry a name chosen by that tenant. The system SHALL NOT constrain the vocabulary a tenant uses, so that a school classifying by subject and a company classifying by department are served by the same mechanism.

#### Scenario: School defines subject areas
- **WHEN** a school's staff member creates areas named "Ciencias" and "Matemática"
- **THEN** both areas exist under that school's tenant

#### Scenario: Company defines department areas
- **WHEN** a company's staff member creates areas named "Tecnología" and "Recursos Humanos"
- **THEN** both areas exist under that company's tenant

#### Scenario: Areas do not cross tenants
- **WHEN** a tenant's areas are listed
- **THEN** only areas belonging to that tenant are returned, regardless of what other tenants have named their own areas

### Requirement: Areas form at most two levels
An area SHALL either be a root area with no parent, or a child of a root area. The system SHALL reject making an area a child of an area that already has a parent, and SHALL reject an area being its own parent. Because a cycle requires a node to be both a child and a parent, no cycle SHALL be representable.

#### Scenario: Creating a child area
- **WHEN** a staff member creates the area "Ciencias I" as a child of the root area "Ciencias"
- **THEN** the child area is created and "Ciencias" remains its parent

#### Scenario: Attempting a third level
- **WHEN** a staff member attempts to create an area whose parent is "Ciencias I", which itself is a child of "Ciencias"
- **THEN** the system rejects it and no area is created

#### Scenario: Attempting to make an area its own parent
- **WHEN** an area is assigned itself as its parent
- **THEN** the system rejects it

#### Scenario: Attempting to give a parent to an area that has children
- **WHEN** a staff member attempts to assign a parent to "Ciencias", which already has "Ciencias I" as a child
- **THEN** the system rejects it, because the change would create a third level

### Requirement: An area belongs to its organization, not to its author
An area's identity SHALL be the combination of its tenant, its parent, and its name, among areas that are active. The system SHALL record which user created an area, but that user SHALL NOT form part of the area's identity. Two members of the same tenant who create an area by the same name under the same parent SHALL resolve to the same area rather than to two separate ones.

#### Scenario: Second author reaches for an existing area
- **WHEN** a staff member creates an area named "Ciencias" and a second staff member of the same tenant later attempts to create an area named "Ciencias" with no parent
- **THEN** the second attempt is rejected as already existing, and both members work against the same area

#### Scenario: Authorship is retained
- **WHEN** an area has been created
- **THEN** the system records the user who created it, and that record does not change when other members use the area

#### Scenario: Same name under different parents
- **WHEN** a tenant creates an area named "General" under "Ciencias" and another named "General" under "Matemática"
- **THEN** both are created, because their parents differ

#### Scenario: Same name in different tenants
- **WHEN** two different tenants each create a root area named "Ciencias"
- **THEN** both are created, because their tenants differ

#### Scenario: Two root areas with the same name
- **WHEN** a tenant already has a root area named "Ciencias" and attempts to create another root area named "Ciencias"
- **THEN** the system rejects it, treating the absent parent of both as the same parent rather than as two distinct ones

### Requirement: Areas can be deactivated
An area SHALL be able to be deactivated, and the system SHALL record when that happened. A deactivated area SHALL be excluded from the identity check that prevents duplicate names, so that a name freed by deactivation can be used again. Reactivating an area SHALL clear the recorded deactivation time.

#### Scenario: Deactivating an area
- **WHEN** a staff member deactivates an area
- **THEN** the area is marked inactive and the time of deactivation is recorded

#### Scenario: Reusing the name of a deactivated area
- **WHEN** a tenant deactivates its area named "Ciencias" and then creates a new root area named "Ciencias"
- **THEN** the new area is created, and the deactivated one remains as it was

#### Scenario: Reactivating an area
- **WHEN** a staff member reactivates a previously deactivated area
- **THEN** the area is marked active and its recorded deactivation time is cleared

### Requirement: A quiz is related to the areas it covers
The system SHALL support relating a quiz to one or more areas, recording for each relation the tenant and the user who established it. The same quiz and area SHALL NOT be related more than once. A relation SHALL be able to reference an area at either level, whether a root area or a child.

#### Scenario: Classifying a quiz under one area
- **WHEN** a staff member relates a quiz to the area "Ciencias I"
- **THEN** the quiz is recorded as covering that area

#### Scenario: Classifying an integrative quiz
- **WHEN** a staff member relates one quiz to both "Ciencias" and "Matemática"
- **THEN** the quiz is recorded as covering both areas

#### Scenario: Repeating a relation
- **WHEN** a staff member relates a quiz to an area it is already related to
- **THEN** the system rejects the duplicate and the quiz remains related to that area exactly once

#### Scenario: Relating to a root area
- **WHEN** a staff member relates a quiz to a root area that has children
- **THEN** the relation is recorded against the root area itself, not against any of its children

#### Scenario: Quiz with no area
- **WHEN** a quiz has never been related to any area
- **THEN** the quiz remains valid and usable, with no areas recorded against it
