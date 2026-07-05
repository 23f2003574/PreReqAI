# Knowledge Graph

The Knowledge Graph is the central reasoning
structure used throughout PreReqAI.

Current capabilities:

- Graph Nodes
- Graph Relationships
- Deterministic Dependencies
- Paragraph Co-occurrence
- Breadth-First Traversal

Future capabilities:

- Prerequisite Tree Generation
- Mathematical Dependency Maps
- Personalized Reading Paths
- Interactive Concept Explorer
- Graph Visualization

## Query Engine

The Knowledge Graph now exposes a reusable
query layer supporting:

- Node lookup
- Type filtering
- Outgoing neighbor lookup
- Incoming neighbor lookup

Future graph-powered features should use
this interface instead of directly iterating
over graph nodes and edges.
