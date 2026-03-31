# LangGraph Workflow (Curriculum Agent)

This document visualizes the full LangGraph workflow implemented in:
- `backend/app/workflow/*` (main graph)
- `backend/app/entity_resolution/*` (entity-resolution subgraph, including clarifications via `interrupt()`)

## Visual Workflow

```mermaid
flowchart TD
  %% =========================
  %% Main Graph (backend/app/workflow)
  %% =========================
  A([Entry]) --> E[rewrite_question]

  E --> F[retrieve_tables]
  F --> G[retrieve_high_level_metadata]
  G --> H[filter_tables]
  H --> I[retrieve_metadata]
  I --> J[retrieve_join_paths]

  %% Join-path missing table handling
  J --> K{route_on_missing_tables}
  K -->|prune_columns| L[prune_columns]
  K -->|join_tables_are_missing| M[retrieve_missing_tables]
  M --> N[retrieve_metadata_for_missing]
  N --> L

  L --> P[entity_resolution (subgraph)]
  P --> Q[generate_query]
  Q --> U[validate_query]

  U --> V{route_on_validation}
  V -->|execute_query| W[execute_query]
  V -->|regenerate_query| Q
  V -->|unknown_error| Z[fallback]

  W --> X{route_on_execution}
  X -->|end| Y[summarize_result]
  X -->|regenerate_query| Q
  X -->|unknown_error| Z[fallback]

  Y --> FIN([END])
  Z --> FIN

  %% =========================
  %% Entity Resolution Subgraph (backend/app/entity_resolution)
  %% =========================
  subgraph ER[Entity Resolution Subgraph]
    direction TB
    ER_A([Entry]) --> ER_B[detect_entities]

    ER_B --> ER_C{route_after_detection}
    ER_C -->|resolve_entity_type| ER_D[resolve_entity_type]
    ER_C -->|rewrite_question| ER_REWRITE[rewrite_question]

    ER_D --> ER_E{route_after_type_resolution}
    ER_E -->|retrieve_candidates| ER_F[retrieve_candidates]
    ER_E -->|handle_clarification (type)| ER_G[handle_clarification]

    ER_F --> ER_H[rank_candidates]

    ER_H --> ER_I{route_after_ranking}
    ER_I -->|check_next_entity| ER_J[check_next_entity]
    ER_I -->|handle_clarification (value)| ER_G

    %% Clarification interruption inside entity resolution
    ER_G -->|interrupt (clarify type/value)| ER_INT[__interrupt__ (entity clarification)]
    ER_INT -->|resume| ER_G_POST[handle_clarification (post-interrupt)]

    ER_G_POST --> ER_K{route_after_clarification}
    ER_K -->|retrieve_candidates| ER_F
    ER_K -->|check_next_entity| ER_J
    ER_K -->|abort (question_changed)| ER_FIN([END])

    ER_J --> ER_L{route_check_next_entity}
    ER_L -->|resolve_entity_type (more entities)| ER_D

    ER_L -->|rewrite_question (done)| ER_REWRITE

    ER_REWRITE --> ER_FIN
  end
```

## Interrupts and Resumes (where the workflow pauses)

There is one `interrupt()`-driven clarification point:

1. **Entity-resolution clarification** (`backend/app/entity_resolution/nodes.py` → `handle_clarification`)
   - Trigger: when entity type is ambiguous (`clarification_type="type"`) or entity value is ambiguous (`clarification_type="value"`).
   - Interrupt payload shape:
     - `{"type": <"type" | "value">, "entity": <mention>, "options": [...]}`
   - Resume payload (what `chat_routes` sends for standard clarifications):
     - `{"selection_index": <0-based index>}`

Both interruptions rely on the same LangGraph thread mechanism:
- `backend/app/api/chat_routes.py` uses `conversation_id` as `config.configurable.thread_id`, so the graph can resume the exact paused step.

