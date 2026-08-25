# quiz/question-ordering Specification

## Purpose

Defines the order in which a quiz's questions and their answer choices are presented: the canonical sequence the author establishes when writing the quiz, and the per-quiz strategy that turns that sequence into what a specific taker actually sees during an attempt.

## Requirements

### Requirement: Questions and answer choices have a total authored order
Every question SHALL carry a position within its quiz, and every answer choice SHALL carry a position within its question. The system SHALL order questions and answer choices by that position, resolving equal positions by creation time, so that repeating the same read returns the same sequence.

#### Scenario: Reading a quiz's questions twice
- **WHEN** the questions of a quiz are read twice without any intervening modification
- **THEN** both reads return the questions in the same sequence

#### Scenario: Two questions sharing a position
- **WHEN** two questions of the same quiz carry the same position
- **THEN** the earlier-created question is ordered first, and the sequence remains the same on every read

#### Scenario: Reading a question's answer choices
- **WHEN** the answer choices of a question are read
- **THEN** they are returned ordered by their position within that question

### Requirement: Authored order is derived from the creation sequence
When a quiz is created, the system SHALL assign each question a position matching its place in the submitted list of questions, and each answer choice a position matching its place in its question's submitted list of answer choices. Positions SHALL be assigned consecutively from the first position with no gaps.

#### Scenario: Creating a quiz with several questions
- **WHEN** a quiz is created with questions submitted in a given sequence
- **THEN** each question's position reflects its place in that sequence, and reading the quiz's questions returns them in the sequence they were submitted

#### Scenario: Creating a question with several answer choices
- **WHEN** a question is created with answer choices submitted in a given sequence
- **THEN** each answer choice's position reflects its place in that sequence

#### Scenario: Questions that existed before positions were introduced
- **WHEN** a quiz's questions were created before this capability existed
- **THEN** they are assigned consecutive positions ordered by their creation time, so their order is total and stable like any other quiz's

### Requirement: A quiz declares how its questions and answer choices are ordered for delivery
A quiz's configuration SHALL declare a strategy for presenting questions and a strategy for presenting answer choices. Each strategy SHALL be either presenting them in authored order, or presenting them in a shuffled order. When either strategy is absent from a quiz's configuration, the system SHALL treat it as authored order.

#### Scenario: Quiz configured for authored order
- **WHEN** a quiz declares the authored-order strategy for questions
- **THEN** an attempt presents that quiz's questions ordered by their authored position

#### Scenario: Quiz configured for shuffled answer choices
- **WHEN** a quiz declares the shuffled strategy for answer choices
- **THEN** an attempt presents each question's answer choices in an order that need not match their authored positions

#### Scenario: Quiz predating the ordering strategies
- **WHEN** a quiz's stored configuration contains no ordering strategies
- **THEN** the system presents both questions and answer choices in authored order, and reading that quiz does not fail

### Requirement: Shuffled order is stable and reproducible within an attempt
When a quiz uses the shuffled strategy, the presented order SHALL be determined by the attempt it belongs to, such that presenting the same attempt again yields the identical order. The order SHALL be reproducible from the attempt's identity alone, without storing the resulting sequence, and SHALL remain reproducible across restarts of the system.

#### Scenario: Taker reloads mid-attempt
- **WHEN** a taker reloads a shuffled quiz during the same attempt
- **THEN** the questions and answer choices appear in exactly the same order as before the reload

#### Scenario: Two takers of the same shuffled quiz
- **WHEN** two different attempts of the same shuffled quiz are presented
- **THEN** each attempt's order is independently determined by its own identity

#### Scenario: Reconstructing a past attempt's order
- **WHEN** the order presented during a completed attempt needs to be reconstructed after the system has been restarted
- **THEN** it can be recomputed from the attempt's identity and yields the order that was originally presented

### Requirement: A started attempt is unaffected by later reordering
The ordering strategy in force for an attempt SHALL be the one captured when that attempt started. Changing a quiz's ordering strategy, or changing its questions' authored positions, SHALL NOT change the order presented within an attempt that is already in progress.

#### Scenario: Author reorders questions during an open attempt
- **WHEN** an author changes the authored positions of a quiz's questions while a taker has an attempt in progress
- **THEN** that in-progress attempt continues to present questions in the order it started with

#### Scenario: Author switches ordering strategy during an open attempt
- **WHEN** an author changes a quiz's ordering strategy while a taker has an attempt in progress
- **THEN** that in-progress attempt continues to use the strategy captured when it started, and attempts started afterwards use the new one
