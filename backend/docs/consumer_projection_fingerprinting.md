# Consumer Projection Fingerprinting and Semantic Change Detection

## Overview

Commit #12 introduces deterministic projection fingerprinting and semantic change detection to PreReqAI's consumer read execution architecture. This addresses the critical operational question:

**Did the consumer-facing state actually change?**

Previously, the system could answer "What happened?" (diagnostics), "Why did this happen?" (provenance), and "Is the source current?" (freshness). But it could not reliably answer whether two projection states were semantically equivalent or what specific sections changed.

## Architecture

### Core Pipeline

```
Consumer Projection
      ↓
Fingerprint Policy (projection-specific)
      ↓
Extract Semantic Sections
      ↓
Normalize Each Section
      ↓
Canonicalize to Primitives
      ↓
Deterministically Serialize
      ↓
Compute Section Fingerprints (SHA-256)
      ↓
Compute Overall Fingerprint
      ↓
Build Immutable Snapshot
```

### Key Components

#### 1. ConsumerProjectionFingerprintAlgorithm
Enum specifying supported hashing algorithms. Currently supports SHA256.

```python
class ConsumerProjectionFingerprintAlgorithm(str, Enum):
    SHA256 = "sha256"
```

#### 2. ConsumerProjectionFingerprint
Immutable value object representing a fingerprint.

```python
@dataclass(frozen=True)
class ConsumerProjectionFingerprint:
    algorithm: ConsumerProjectionFingerprintAlgorithm
    value: str  # lowercase hexadecimal
```

#### 3. ConsumerProjectionSectionFingerprint
Identifies a logical section and its fingerprint within a projection.

```python
@dataclass(frozen=True)
class ConsumerProjectionSectionFingerprint:
    section_name: str
    fingerprint: ConsumerProjectionFingerprint
```

#### 4. ConsumerProjectionFingerprintSnapshot
Immutable snapshot of a projection's semantic identity at one point in time.

```python
@dataclass(frozen=True)
class ConsumerProjectionFingerprintSnapshot:
    projection_name: str
    contract_version: Optional[str]
    overall: ConsumerProjectionFingerprint
    sections: tuple[ConsumerProjectionSectionFingerprint, ...]
```

#### 5. ConsumerProjectionChangeStatus
Indicates whether two snapshots represent identical or different semantic state.

```python
class ConsumerProjectionChangeStatus(str, Enum):
    UNCHANGED = "unchanged"      # Fingerprints match
    CHANGED = "changed"          # Fingerprints differ
    INCOMPARABLE = "incomparable"  # Cannot compare safely
```

#### 6. ConsumerProjectionSectionChangeStatus
Identifies how a specific section changed.

```python
class ConsumerProjectionSectionChangeStatus(str, Enum):
    UNCHANGED = "unchanged"  # Section fingerprints match
    CHANGED = "changed"      # Section fingerprints differ
    ADDED = "added"          # Section exists only in current
    REMOVED = "removed"      # Section exists only in previous
```

#### 7. ConsumerProjectionSectionChange
Details the change in one logical section.

```python
@dataclass(frozen=True)
class ConsumerProjectionSectionChange:
    section_name: str
    status: ConsumerProjectionSectionChangeStatus
    previous_fingerprint: Optional[ConsumerProjectionFingerprint]
    current_fingerprint: Optional[ConsumerProjectionFingerprint]
```

#### 8. ConsumerProjectionChangeReport
Immutable report comparing two snapshots.

```python
@dataclass(frozen=True)
class ConsumerProjectionChangeReport:
    projection_name: str
    status: ConsumerProjectionChangeStatus
    previous: ConsumerProjectionFingerprintSnapshot
    current: ConsumerProjectionFingerprintSnapshot
    section_changes: tuple[ConsumerProjectionSectionChange, ...]
```

### Services

#### ConsumerProjectionCanonicalizer
Converts semantic projection values to deterministic primitive representations.

**Supported types:**
- None → null
- bool → boolean
- int → number
- float → number (finite only)
- str → string
- Enum → string (stable value)
- datetime → ISO 8601 UTC string (rejects naive)
- date → ISO 8601 string
- tuple → array
- list → array
- dict/Mapping → object (sorted keys)
- dataclass → object
- Pydantic model → object

**Rejects:**
- Non-finite floats (NaN, ±∞)
- Naive datetimes (must be timezone-aware)
- Unsupported object types

#### ConsumerProjectionFingerprintPolicy (Protocol)
Projection-specific policy defining:
- Which sections are semantically meaningful
- How each section should be normalized
- Which fields to include/exclude
- Whether ordering matters

```python
class ConsumerProjectionFingerprintPolicy(Protocol):
    @property
    def projection_name(self) -> str: ...
    
    def extract_sections(
        self,
        projection: object,
    ) -> Mapping[str, object]: ...
    
    def normalize_section(
        self,
        *,
        section_name: str,
        value: object,
    ) -> object: ...
```

#### ConsumerProjectionFingerprintService
Orchestrates the fingerprinting pipeline:

```python
def fingerprint(
    self,
    *,
    projection: object,
    policy: ConsumerProjectionFingerprintPolicy,
    contract_version: Optional[str] = None,
) -> ConsumerProjectionFingerprintSnapshot:
    """Computes semantic fingerprint of a projection."""
```

Flow:
1. Extract semantic sections via policy
2. Normalize each section via policy
3. Canonicalize normalized values
4. Deterministically serialize to JSON
5. Compute SHA-256 section fingerprints
6. Compute overall fingerprint from ordered section map
7. Build immutable fingerprint snapshot

#### ConsumerProjectionChangeDetector
Compares two fingerprint snapshots:

```python
def compare(
    self,
    *,
    previous: ConsumerProjectionFingerprintSnapshot,
    current: ConsumerProjectionFingerprintSnapshot,
) -> ConsumerProjectionChangeReport:
    """Detects semantic changes between snapshots."""
```

Comparison logic:
- Fast path: if overall fingerprints match → UNCHANGED
- Validate comparability (same projection name, compatible versions)
- Compare section fingerprints to identify specific changes
- Return detailed change report

#### ConsumerProjectionFingerprintPolicyRegistry
Registry for projection-specific fingerprinting policies.

```python
def get_policy(
    self,
    projection_name: str,
) -> ConsumerProjectionFingerprintPolicy:
    """Retrieves a registered policy."""
```

Raises clear error if policy not registered (no fallback hashing).

### Built-in Policies

#### ResearchWorkspaceBootstrapFingerprintPolicy
Bootstrap projection policy extracting semantic sections:
- readiness: Core capability assessment
- attention: Items requiring attention
- actions: Available workspace actions
- recent_activity: Chronologically ordered events

Excludes:
- capabilities (static system metadata)
- overview (mostly metadata)
- recent_sessions (derived from activity)

#### ResearchWorkspaceAttentionFingerprintPolicy
Attention projection policy:
- Extracts: items (priority-ordered attention items)
- Excludes: count fields (derived from items)

#### ResearchWorkspaceActionFingerprintPolicy
Action projection policy:
- Extracts: actions (ranked action availability list)
- Excludes: count fields, scope, entity_id

#### ResearchWorkspaceReadinessFingerprintPolicy
Readiness assessment policy:
- Extracts: status, ready, blocking, warnings, blocking_reasons
- Excludes: checks (internal implementation details)

## Canonicalization Details

### Deterministic Serialization

Uses:
- Sorted keys for mappings
- Stable JSON separators: `(',', ':')`
- UTF-8 encoding
- No pretty-printing

```python
json.dumps(
    value,
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=False,
)
```

### Mapping Normalization

```python
{
    "z": 1,
    "a": 2,
    "m": 3,
}
```

Becomes (after sorting):

```python
{
    "a": 2,
    "m": 3,
    "z": 1,
}
```

### Datetime Normalization

All datetimes converted to UTC with microsecond precision:

```python
2026-07-14T10:00:00.000000Z
2026-07-14T15:30:00+05:30  # Same instant
```

Both produce identical canonical value.

### Enum Normalization

```python
class FreshnessStatus(str, Enum):
    STALE = "stale"
    FRESH = "fresh"

FreshnessStatus.STALE  # → "stale"
```

## What's NOT Included

### Excluded Metadata
- Request timestamps
- Execution duration
- Provenance node IDs
- Diagnostic counters
- Memory addresses
- Generated UUIDs
- Dictionary construction order

### Non-Goals
- Caching (separate concern)
- Persistence (separate concern)
- Generic deep diffing
- Versioning logic (Commit #7)
- Provenance fingerprinting
- Diagnostics fingerprinting

## Examples

### Example 1: Identical Bootstrap State

Request A:
```python
{
    "readiness": "ready",
    "attention": [],
    "actions": [],
}
```

Request B:
```python
{
    "readiness": "ready",
    "attention": [],
    "actions": [],
}
```

Even with different request IDs, execution durations, or provenance:

```
Overall: UNCHANGED
Readiness: UNCHANGED
Attention: UNCHANGED
Actions: UNCHANGED
```

### Example 2: Attention Item Added

Previous:
```python
{
    "readiness": "ready",
    "attention": [],
    "actions": [],
}
```

Current:
```python
{
    "readiness": "ready",
    "attention": [{"code": "integrity_review"}],
    "actions": [],
}
```

Result:
```
Overall: CHANGED
Readiness: UNCHANGED
Attention: CHANGED
Actions: UNCHANGED
```

### Example 3: Action Reordering

Previous:
```python
actions: [
    {"code": "resolve_blocker", "priority": 1},
    {"code": "review_integrity", "priority": 2},
]
```

Current:
```python
actions: [
    {"code": "review_integrity", "priority": 1},
    {"code": "resolve_blocker", "priority": 2},
]
```

Result:
```
Overall: CHANGED
Actions: CHANGED
```

(Order is preserved since action ranking is consumer-meaningful)

### Example 4: Dictionary Key Order

Canonically equivalent:
```python
{"a": 1, "b": 2}
{"b": 2, "a": 1}
```

Same fingerprint produced.

## Error Handling

### Clear Failure Modes

**UnsupportedCanonicalValueError**
```python
try:
    canonicalizer.canonicalize(CustomObject())
except ResearchWorkspaceUnsupportedCanonicalValueError as e:
    # Cannot canonicalize type CustomObject: ...
```

**NaiveDatetimeCanonicalizationError**
```python
naive_dt = datetime(2026, 7, 14, 10, 0, 0)  # No timezone
try:
    canonicalizer.canonicalize(naive_dt)
except ResearchWorkspaceNaiveDatetimeCanonicalizationError as e:
    # Naive datetime not supported: ... All datetimes must be timezone-aware.
```

**ProjectionFingerprintPolicyNotFoundError**
```python
try:
    registry.get_policy("unknown.projection")
except ResearchWorkspaceProjectionFingerprintPolicyNotFoundError as e:
    # No fingerprinting policy found for projection: unknown.projection
```

**IncomparableProjectionSnapshotsError**
Can occur when snapshots are from different projection types or incompatible versions.

## Integration Points

### After Projection Construction

Fingerprinting happens AFTER final projection assembly:

```
Build Final Consumer Projection
         ↓
   Fingerprint Final Projection
         ↓
Build Immutable Snapshot
```

NOT during projection construction (which might be incomplete).

### With Execution Result

Fingerprint snapshots can be added to execution results:

```python
@dataclass
class ConsumerProjectionExecutionResult:
    projection: object
    diagnostics: DiagnosticReport
    provenance: ProvenanceReport
    fingerprint: Optional[FingerprintSnapshot]
```

### With Change Detection

Enable future integrations:
- HTTP ETags
- Conditional GET / If-None-Match
- Client synchronization
- Selective UI refresh
- Change notifications
- Duplicate update elimination

But these are future concerns. Commit #12 establishes the deterministic foundation.

## Testing

29 focused tests covering:

1. **Canonicalization** (12 tests)
   - Primitive types
   - Enum handling
   - Datetime handling
   - Collection ordering
   - Error cases

2. **Fingerprint Generation** (8 tests)
   - Determinism
   - Algorithm recording
   - Section ordering
   - Immutability

3. **Change Detection** (7 tests)
   - Unchanged detection
   - Changed detection
   - Section changes
   - Incomparability
   - Immutability

4. **Registry** (2 tests)
   - Policy registration
   - Missing policy errors

All tests verify:
- Deterministic behavior
- Correct error handling
- Immutability properties
- Semantic correctness

## Design Principles

### 1. Semantic Identity, Not Incidentals
Fingerprints encode consumer-meaningful state, not execution metadata.

### 2. Projection-Specific Policies
No universal rules; each projection type knows its own semantics.

### 3. Deterministic and Immutable
Same semantic state always produces same fingerprint. Snapshots cannot be modified.

### 4. Clear Failure Over Silent Fallback
Unsupported types raise clear errors, not arbitrary hashes.

### 5. Stateless Services
Services produce deterministic output from inputs, with no hidden state.

### 6. Separation of Concerns
- Fingerprinting ≠ Caching
- Fingerprinting ≠ Persistence
- Fingerprinting ≠ Versioning
- Fingerprinting ≠ Provenance

## Future Directions

This foundation enables:
- **HTTP ETags** for conditional requests
- **Change-based refresh strategies** for UI
- **Selective section updates** when only parts change
- **Projection deduplication** in storage
- **Change notification systems**
- **Semantic state timelines**
- **Regression detection** for quality assurance

All built on the deterministic, projection-specific semantic fingerprint foundation.
