"""
LangGraph StateGraph — Autonomous Support Architect (Phase 01)

Topology (DAG):
                          ┌──────────────┐
                          │   classify   │
                          └──────┬───────┘
                                 │
                          ┌──────▼───────┐
                          │    verify    │
                          └──────┬───────┘
                    verified?    │    not verified?
              ┌──────────────────┤
              ▼                  ▼
     ┌────────────────┐    ┌──────────┐
     │ fetch_context  │    │ escalate │◄──────────────────┐
     └────────┬───────┘    └──────────┘                   │
              │                                           │
     ┌────────▼───────┐                                   │
     │  rag_retrieve  │                          confidence < 0.75
     └────────┬───────┘                                   │
              │                                           │
     ┌────────▼───────┐                                   │
     │    resolve     │───────────────────────────────────┘
     └────────────────┘
              │ confidence >= 0.75
              ▼
            END
"""

from langgraph.graph import StateGraph, END
from app.state import SupportState
from app.graph.nodes.classify import classify
from app.graph.nodes.verify import verify
from app.graph.nodes.fetch_context import fetch_context
from app.graph.nodes.rag_retrieve import rag_retrieve
from app.graph.nodes.resolve import resolve
from app.graph.nodes.escalate import escalate
from app.graph.routing import route_after_verify, route_after_resolution


def build_graph() -> StateGraph:
    builder = StateGraph(SupportState)

    # --- Nodes ---
    builder.add_node("classify", classify)
    builder.add_node("verify", verify)
    builder.add_node("fetch_context", fetch_context)
    builder.add_node("rag_retrieve", rag_retrieve)
    builder.add_node("resolve", resolve)
    builder.add_node("escalate", escalate)

    # --- Entry point ---
    builder.set_entry_point("classify")

    # --- Fixed edges ---
    builder.add_edge("classify", "verify")
    builder.add_edge("fetch_context", "rag_retrieve")
    builder.add_edge("rag_retrieve", "resolve")
    builder.add_edge("escalate", END)

    # --- Conditional edges ---
    builder.add_conditional_edges(
        "verify",
        route_after_verify,
        {
            "fetch_context": "fetch_context",
            "escalate": "escalate",
        },
    )

    builder.add_conditional_edges(
        "resolve",
        route_after_resolution,
        {
            "escalate": "escalate",
            "__end__": END,
        },
    )

    return builder.compile()


# Module-level compiled graph (singleton, reused across requests)
support_graph = build_graph()
