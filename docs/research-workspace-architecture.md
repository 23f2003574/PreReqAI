# Research Workspace Architecture

## Overview

The PreReqAI research workspace is a persistent, branchable, searchable, portable, auditable, and reactive domain subsystem for managing long-running research sessions.

## Public Entry Point

External consumers should access research workspace functionality through:

`ResearchWorkspaceGateway`, exposed as `application.research_workspace`.

The gateway provides a stable application-facing capability surface while hiding internal service and persistence topology. It does not contain business logic itself — it delegates every operation to `PreReqAIApplication`, which owns the real orchestration.

## Architecture

```
Consumer
    -> ResearchWorkspaceGateway
    -> Application orchestration (PreReqAIApplication)
    -> Domain services and stores
    -> Persistent workspace state
```

Successful semantic mutations additionally produce:

```
Domain mutation
    -> Workspace change event
    -> Persistent change feed
    -> In-process subscribers
```

Human-readable historical actions are stored separately in the research activity timeline.

## Major Capabilities

### Sessions

Research sessions represent independent long-running research contexts. Sessions are identified by an explicit `session_id` rather than generated from a search query — creation is always `create_session(session_id, ...)`.

### Lineage

Sessions may be branched into independent research paths while preserving ancestry. Branching operates from a session's most recent checkpoint (creating one automatically if none exists yet), not directly from the session itself — this mirrors the underlying `branch_research_checkpoint` capability.

### Discovery

Sessions can be searched, filtered, sorted, and paginated.

### Comparison

Related or independent sessions can be compared for shared ancestry and divergence.

### Organization

Tags and collections provide user-defined workspace organization. Tags are referenced by name throughout the gateway (not by a separately-issued tag ID) — assigning a tag to a session implicitly creates it if it doesn't already exist.

### Activity

The research activity timeline records meaningful historical actions. The gateway exposes both workspace-wide (`get_activity()`) and session-scoped (`get_activity(session_id=...)`) views over the same underlying timeline.

### Insights

Workspace insights summarize research activity and structure.

### Snapshots

Portable versioned snapshots provide storage-independent export boundaries.

### Transactional Import

Snapshots can be previewed, conflict-checked, identity-remapped, and restored transactionally.

### Integrity

The workspace auditor detects structural, referential, graph, and semantic inconsistencies.

Repair planning proposes explicit actions without blindly mutating state.

### Reactive Change Feed

Machine-oriented workspace changes are stored as monotonically ordered events and can be consumed using sequence cursors or in-process subscriptions.

## Important Boundaries

### Activity History vs Change Feed

Activity history is human-oriented historical meaning.

The change feed is machine-oriented synchronization state.

They are intentionally separate.

### Normal Creation vs Snapshot Restoration

Normal creation may generate identities, timestamps, activity, and reactive events.

Snapshot restoration preserves historical state and must not route through normal creation pathways.

### Audit vs Repair

Auditing is read-only.

Repair planning is read-only.

Only explicit repair execution may mutate workspace state.

### Export Schema vs Internal Persistence

Portable research snapshots are stable external contracts.

Store rollback state is an internal persistence concern.

The two representations must remain separate.

## Frontend Integration

A future frontend should depend on the research workspace gateway or an HTTP transport adapter over that gateway.

The frontend should not directly depend on internal stores or domain services.

The expected architecture is:

```
HTML / CSS / JavaScript
    -> HTTP / SSE / WebSocket adapter
    -> ResearchWorkspaceGateway
    -> Application
    -> Domain subsystem
```
