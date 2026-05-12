from abc import ABC, abstractmethod


class Adapter(ABC):
    """Base contract for infrastructure adapter boundaries."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable adapter implementation name."""
