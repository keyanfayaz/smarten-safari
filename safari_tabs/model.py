"""Shared output contract for independently replaceable adapters."""

from dataclasses import dataclass, field


class QueryError(Exception):
    """A source cannot provide a reliable result."""

    def __init__(self, message: str, code: str = "source_unavailable"):
        super().__init__(message)
        self.code = code


@dataclass
class Scope:
    """A source-local window, group, or device; names need not be unique."""

    id: str
    name: str
    kind: str


@dataclass
class Tab:
    """A title and URL associated with a source-local scope."""

    id: str
    scope_id: str
    title: str | None
    url: str | None
    position: int | float | None = None


@dataclass
class Snapshot:
    """One observation; IDs are not comparable between different sources."""

    source: str
    scopes: list[Scope] = field(default_factory=list)
    tabs: list[Tab] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
