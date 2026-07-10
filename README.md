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
