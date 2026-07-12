# PreReqAI

Turns a research paper into something you can actually learn from: a prerequisite
tree, a mathematical dependency map, intuition-first explanations, and an
implementation roadmap — instead of just a summary.

Focused initially on transformers, diffusion, RL, and graph ML papers.

**Status:** early development, not yet usable.

## Prerequisite Explorer

Upload a research paper to receive:

- Required prerequisite concepts
- Missing knowledge analysis
- Personalized learning plan
- Curated learning resources
- Estimated preparation time
- Difficulty assessment
- Readiness tracking

## Interactive Learning

After prerequisite analysis, learners can begin an interactive tutoring session.

Features include:

- Context-aware question answering
- Multiple pedagogical teaching strategies
- Adaptive quizzes
- Learning gap analysis
- Personalized recommendations
- Persistent learning sessions

## Navigation History

Every navigation event is recorded during exploration.

Example:

```
Attention
        │
        ▼
Equation (3)
        │
        ▼
Figure 2
        │
        ▼
Experiment 1
        │
        ▼
Related Paper
        │
        ▼
Navigation Timeline
```

## Personalized Navigation

Navigation recommendations adapt to the learner's exploration history.

Example:

```
Attention
        │
        ▼
Recommended:

• Equation (3)
• Figure 2
• Experiment 1
        │
        ▼
Continue Exploration
```

## Research Navigation Pipeline

Every navigation request follows a unified execution flow.

```
Navigation Request
        │
        ▼
Paper Navigator
        │
        ▼
Specialized Navigator
        │
        ▼
Navigation History
        │
        ▼
Recommendation Engine
        │
        ▼
Unified Navigation Response
```

## Workflow-Oriented Tutoring

Every learner request is transformed into an educational execution plan.

Example:

```
Explain Attention
        │
        ▼
Explanation Workflow
        │
        ▼
Example Workflow
        │
        ▼
Follow-up Workflow
        │
        ▼
Unified Learning Response
```

## Interactive Research Objects

Each research object exposes only the educational actions appropriate for its type.

Example:

```
Concept
    │
    ▼
Explain
Visualize
Compare
Quiz
Show Prerequisites
```

## Concept Actions

Selecting an action on a concept runs the real learning workflow behind it and returns the tutor's response, not just the workflow's name.

Example:

```
Attention
    │
    ▼
Explain
    │
    ▼
Explanation Workflow
    │
    ▼
Tutor Response
```

## Figure Actions

Diagrams and plots run the same real workflows too, so explaining a figure or exploring its related concepts returns an actual tutor response.

Example:

```
Figure 2
    │
    ▼
Explain
    │
    ▼
Explanation Workflow
    │
    ▼
Tutor Response
```

## Experiment Actions

Experimental evaluations run the same real workflows too, so comparing baselines or explaining results returns an actual tutor response.

Example:

```
Experiment 1
    │
    ▼
Compare
    │
    ▼
Comparison Workflow
    │
    ▼
Tutor Response
```

## Reference Actions

Cited papers run the same real workflows too, so exploring a reference's related work returns an actual tutor response instead of a bibliography entry.

Example:

```
Attention Is All You Need
    │
    ▼
Show Relations
    │
    ▼
Follow-up Workflow
    │
    ▼
Tutor Response
```

## Equation Actions

Mathematical expressions run the same real workflows as concepts, so explaining, visualizing, or implementing an equation returns an actual tutor response.

Example:

```
Equation (3)
    │
    ▼
Explain
    │
    ▼
Explanation Workflow
    │
    ▼
Tutor Response
```

## Personalized Object Actions

Recommended actions adapt to what a learner has already completed on an object, instead of showing the same static list to everyone.

Example:

```
Attention (first visit)
    │
    ▼
Explain, Visualize, Compare, Implement, Quiz

Attention (after completing Explain)
    │
    ▼
Visualize, Compare, Implement, Quiz
```

## Interaction History

Every educational interaction is recorded throughout the learning session, driving the personalized recommendations above.

Attention

↓

Explain

↓

Equation (3)

↓

Visualize

↓

Experiment 1

↓

Compare

↓

Interaction Timeline

## Interactive Object Pipeline

Every interaction follows one execution flow, regardless of object type.

```
Research Object
    │
    ▼
Dispatcher
    │
    ▼
Action Engine
    │
    ▼
Workflow
    │
    ▼
Interaction History
    │
    ▼
Action Recommendations
    │
    ▼
Unified Response
```

## Interaction Orchestration

Educational actions can be coordinated into structured learning experiences.

Attention

↓

Explain

↓

Visualize

↓

Quiz

↓

Complete Learning Session

## Interactive Research Engine

Every educational interaction flows through one high-level engine, whether it's a single action or a multi-action plan.

```
Research Object
    │
    ▼
Interactive Research Engine
    │
    ▼
Interaction Pipeline
    │
    ▼
Action Engine
    │
    ▼
Learning Workflow
    │
    ▼
Adaptive Tutor
```

## Platform Architecture

```
Research Paper
        │
        ▼
Analysis Layer
        │
        ▼
Knowledge Graph
        │
        ▼
Navigation Layer
        │
        ▼
Interaction Layer
        │
        ▼
Learning Workflows
        │
        ▼
Adaptive Tutor
```

Every subsystem is coordinated through the
`PreReqAIPlatform`.

## Visual Research Workspace

PreReqAI provides a unified workspace for exploring and learning from research papers.

The workspace is organized into five primary regions:

- Workspace Header
- Research Explorer
- Main Research View
- Research Object Inspector
- Learning Timeline

The workspace maintains shared state across paper navigation, research object selection, learning workflows, and educational interactions.

## Modular Workspace Panels

Visual capabilities are registered as modular workspace panels rather than being hardcoded into the workspace layout.

Each panel defines:

- A unique identifier
- A display title
- A workspace region
- A component contract
- Visibility state
- Optional metadata

This allows the research workspace to dynamically host features such as paper exploration, knowledge graph visualization, object inspection, learning timelines, and future research tools.

## Research Object Inspector

Selecting a research object opens a contextual inspector containing:

- Object identity
- Research object type
- Description
- Paper metadata
- Available educational actions

The inspector uses the unified research object model, allowing concepts, equations, figures, experiments, and references to share a consistent inspection experience.

## Interactive Action Menu

Selected research objects expose executable educational actions through the visual workspace.

Example:

```
Attention
    │
    ▼
Explain
Visualize
Implement
Compare
Quiz
    │
    ▼
Interactive Research Engine
    │
    ▼
Educational Workflow
```

The action menu validates object capabilities before forwarding interactions to the platform's educational interaction engine.

## Paper Outline Explorer

The visual research workspace provides a hierarchical representation of the paper's document structure.

Extracted sections and subsections are transformed into navigable outline nodes that preserve:

- Section identity
- Section title
- Hierarchical level
- Section numbering
- Page location
- Parent-child relationships

This allows learners to explore research papers structurally rather than relying exclusively on linear scrolling or conversational navigation.

## Knowledge Graph Workspace

The visual research workspace can represent a paper as an interconnected knowledge graph.

Backend graph entities are transformed into visual nodes and edges containing:

- Node identity
- Node type
- Description
- Source context
- Relationships
- Selection state

Learners can switch between the paper view and knowledge graph view while remaining inside the same research session.

## Contextual Navigation Breadcrumbs

The visual research workspace maintains a contextual navigation trail as learners move through papers, sections, knowledge graph nodes, and interactive research objects.

Example:

```
Attention Is All You Need
    →
Model Architecture
    →
Multi-Head Attention
    →
Equation (3)
```

Breadcrumbs preserve the current research path and allow learners to return to earlier contexts without losing the structure of their exploration.

## Learning Workflow Timeline

The visual research workspace exposes the progress of structured educational workflows.

Example:

```
✓ Explanation
      ↓
✓ Example
      ↓
● Visualization
      ↓
○ Quiz
      ↓
○ Reflection
```

Each timeline step can be represented as:

- Pending
- Active
- Completed
- Failed
- Skipped

This allows learners to understand where they are inside a multi-step educational experience rather than treating workflow execution as an opaque backend process.

## Contextual Learning Panel

Educational content generated from research object interactions is presented inside a dedicated contextual learning surface.

The panel can represent:

- Explanations
- Visualizations
- Implementations
- Comparisons
- Quizzes
- Prerequisite guidance
- Follow-up learning content

Each learning output preserves its source research object, educational action, workflow context, and associated metadata.

Learners can move between the paper, knowledge graph, and learning content without losing their current research context.

## Workspace Interaction History

The visual research workspace exposes the learner's educational interaction history throughout the current research session.

Example:

```
Attention — Explained

Equation (3) — Visualized

Figure 2 — Explored

Experiment 1 — Compared
```

Workspace history is derived from the backend interaction history, preserving a single source of truth for educational interactions.

Historical entries can be selected and associated with previously generated learning content without automatically re-executing educational workflows.

## Personalized Next Actions

The visual research workspace can surface personalized recommendations for what the learner should explore next.

Example:

```
Recommended Next

- Visualize Attention
- Explore Equation (3)
- Test Your Understanding
```

Recommendations can be prioritized, selected, and explicitly executed when they target an action supported by the currently selected research object.

The workspace can also consume recommendations returned by educational interactions, allowing learning experiences to continuously suggest meaningful next steps.

## Workspace State Coordination

The visual research workspace coordinates major state transitions through a centralized event-driven state coordinator.

Workspace events include:

- Paper loading
- Section selection
- Research object selection
- Knowledge graph selection
- View changes
- Educational action execution
- Workflow loading and progress
- Learning content presentation
- Interaction history updates
- Recommendation updates

The coordinator maintains a consistent workspace state while allowing independent visual subsystems to react to shared user interactions.

Workspace events are also recorded as an ordered event history, providing a foundation for future debugging, session replay, state restoration, analytics, and undo or redo capabilities.

## Visual Research Workspace API

PreReqAI provides a unified visual environment for exploring and learning from research papers.

The workspace coordinates:

- Hierarchical paper exploration
- Knowledge graph navigation
- Contextual research object inspection
- Executable educational actions
- Learning workflow progress
- Contextual educational content
- Research navigation breadcrumbs
- Interaction history
- Personalized next-action recommendations
- Unified workspace state

### Research Experience

```text
Load Research Paper
        ↓
Explore Paper Structure
        ↓
Navigate Knowledge Graph
        ↓
Select Research Object
        ↓
Inspect Context and Capabilities
        ↓
Execute Educational Action
        ↓
Track Learning Workflow
        ↓
Present Contextual Learning Content
        ↓
Record Interaction History
        ↓
Recommend the Next Learning Step
        ↓
Continue Research
```

The `VisualResearchWorkspace` provides the application-facing interface for coordinating the complete research-learning experience.

## Persistent Research Sessions

PreReqAI can serialize active visual research workspaces into stable research session snapshots.

Session snapshots preserve durable research context including:

- Active paper
- Active workspace view
- Selected research object
- Selected paper section
- Selected knowledge graph node
- Navigation breadcrumbs
- Learning workflow progress
- Interaction history
- Personalized recommendations

Research session persistence is separated into:

- `ResearchSessionSnapshot` for stable serialized state
- `ResearchSessionSerializer` for workspace serialization
- `ResearchSessionStore` for persistence contracts
- `ResearchSessionManager` for application-level coordination

The initial in-memory store provides a development and testing implementation while preserving a storage abstraction that can later support database-backed persistence.

## Research Session Restoration

Persisted research sessions can be restored into live visual workspaces through runtime identifier resolution.

The restoration architecture includes:

- `ResearchRuntimeRegistry` for currently available runtime entities
- `ResearchRuntimeResolver` for resolving durable identifiers
- `ResearchSessionRestorer` for reconstructing workspace state
- `ResearchSessionRestorationResult` for reporting successful and unresolved restoration state

Restoration can recover:

- Active workspace view
- Selected research object
- Selected paper section
- Selected knowledge graph node
- Navigation breadcrumbs
- Learning workflow timeline
- Personalized recommendations

Historical educational actions are not re-executed during restoration.

Missing or outdated runtime references are reported explicitly rather than silently failing.
