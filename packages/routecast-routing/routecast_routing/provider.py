from __future__ import annotations

from abc import ABC, abstractmethod

from routecast_core.models import RouteRequest, RouteResponse


class RoutingProvider(ABC):
    """Abstract routing provider contract."""

    @abstractmethod
    def route(self, request: RouteRequest) -> RouteResponse:
        """Compute a route for the given request."""
        raise NotImplementedError
