"""
Component 2: Query Routing with Semantic Router + RBAC Intersection

Semantic router decides which collection(s) to target based on query intent.
Route output is then intersected with user role to determine accessible collections.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from semantic_router import Route
from semantic_router.routers import SemanticRouter
from semantic_router.encoders import HuggingFaceEncoder


# Configure logging for auditability
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Role-to-collection access matrix (same as Component 1)
ROLE_TO_COLLECTIONS = {
    "employee": ["general"],
    "finance": ["general", "finance"],
    "engineering": ["general", "engineering"],
    "marketing": ["general", "marketing"],
    "c_level": ["general", "finance", "engineering", "marketing"],
}


@dataclass(frozen=True)
class SemanticRouteDecision:
    """Result of semantic routing operation."""
    route_name: str
    route_collections: list[str]
    user_role: str
    accessible_collections: list[str]
    is_accessible: bool
    message: str


def _build_routes() -> list[Route]:
    """Define semantic routes for different query intents."""
    
    finance_route = Route(
        name="finance_route",
        utterances=[
            "What are our Q3 revenue figures?",
            "Show me the quarterly financial report",
            "What's the budget allocation for next year?",
            "How much did we spend on operations?",
            "What are our profit margins?",
            "Show me investor relations documents",
            "What's our cash flow status?",
            "How are we performing financially?",
            "What are the department budgets?",
            "Show me vendor payment summaries",
            "What's our year-over-year growth?",
            "Tell me about our financial projections",
        ],
    )

    engineering_route = Route(
        name="engineering_route",
        utterances=[
            "What's our system architecture?",
            "How do I set up the development environment?",
            "What are the API endpoints?",
            "Tell me about incident management",
            "What's our SLA for system uptime?",
            "How do we handle code deployment?",
            "What are the engineering best practices?",
            "Show me the sprint metrics",
            "What's our current system performance?",
            "How do we onboard engineers?",
            "Tell me about our microservices",
            "What are the testing requirements?",
        ],
    )

    marketing_route = Route(
        name="marketing_route",
        utterances=[
            "What was our Q1 campaign performance?",
            "Show me our brand guidelines",
            "How are we acquiring customers?",
            "What's our market share?",
            "Tell me about our competitor analysis",
            "What's our customer acquisition cost?",
            "How are our campaigns performing?",
            "What's our marketing strategy?",
            "Show me campaign ROI metrics",
            "What are our customer demographics?",
            "Tell me about our market positioning",
            "Show me customer feedback analysis",
        ],
    )

    hr_general_route = Route(
        name="hr_general_route",
        utterances=[
            "What's the leave policy?",
            "How many casual leaves can I take?",
            "What are the health benefits?",
            "What's the maternity leave duration?",
            "How do I apply for time off?",
            "What's the work-from-home policy?",
            "Tell me about company culture",
            "What are the holiday schedules?",
            "How does the 401k plan work?",
            "What are the employee benefits?",
            "Tell me about training opportunities",
            "What's the dress code policy?",
        ],
    )

    cross_department_route = Route(
        name="cross_department_route",
        utterances=[
            "Tell me about the company",
            "What's our company mission?",
            "Who are our key stakeholders?",
            "What are our company values?",
            "Tell me about company announcements",
            "What's the organizational structure?",
            "How many employees do we have?",
            "What's our company history?",
            "Tell me about company policies",
            "What are the company goals for this year?",
        ],
    )

    return [
        finance_route,
        engineering_route,
        marketing_route,
        hr_general_route,
        cross_department_route,
    ]


class SemanticRoutingService:
    """
    Semantic router with RBAC intersection.
    Routes queries to collections based on intent, then checks if user has access.
    """

    def __init__(self, encoder_model: str = "Qwen/Qwen3-Embedding-0.6B"):
        self.routes = _build_routes()
        self.encoder = HuggingFaceEncoder(name=encoder_model)
        self.router = SemanticRouter(
            encoder=self.encoder,
            routes=self.routes,
            auto_sync="local",
        )
        
        # Map route names to collections
        self.route_to_collections = {
            "finance_route": ["finance"],
            "engineering_route": ["engineering"],
            "marketing_route": ["marketing"],
            "hr_general_route": ["general"],
            "cross_department_route": ["general", "finance", "engineering", "marketing"],
        }

    def route(
        self,
        query: str,
        user_role: str,
    ) -> SemanticRouteDecision:
        """
        Route a query based on semantic intent and intersect with user role.

        Args:
            query: User query string
            user_role: One of employee|finance|engineering|marketing|c_level

        Returns:
            SemanticRouteDecision with route name, accessible collections, and auditability log
        """
        if user_role not in ROLE_TO_COLLECTIONS:
            raise ValueError(f"Unknown role: {user_role}")

        # Run semantic router
        semantic_result = self.router(query)
        
        if not semantic_result or not semantic_result.name:
            # Default to cross_department for off-route queries
            route_name = "cross_department_route"
        else:
            route_name = semantic_result.name

        # Get collections targeted by this route
        route_collections = self.route_to_collections.get(
            route_name, ["general"]
        )

        # Get collections accessible by this role
        role_collections = ROLE_TO_COLLECTIONS[user_role]

        # Intersect: collections that are both routed AND accessible
        accessible_collections = [
            c for c in route_collections if c in role_collections
        ]

        # Determine accessibility
        is_accessible = len(accessible_collections) > 0

        # Build message
        if is_accessible:
            message = f"Route '{route_name}' → collections {accessible_collections}"
        else:
            blocked_collections = [
                c for c in route_collections if c not in role_collections
            ]
            message = (
                f"Access Denied: Role '{user_role}' cannot access "
                f"collections {blocked_collections} (required by route '{route_name}'). "
                f"You have access to: {role_collections}"
            )

        result = SemanticRouteDecision(
            route_name=route_name,
            route_collections=route_collections,
            user_role=user_role,
            accessible_collections=accessible_collections,
            is_accessible=is_accessible,
            message=message,
        )

        # Log for auditability
        logger.info(
            f"Query routing | Route: {route_name} | User: {user_role} | "
            f"IsAccessible: {is_accessible} | Accessible: {accessible_collections}"
        )

        return result
