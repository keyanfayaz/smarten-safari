"""Shared output contract for independently replaceable adapters."""

from dataclasses import asdict, dataclass, field


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
    profile_id: str | None = None
    profile_name: str | None = None
    group_id: str | None = None
    group_name: str | None = None
    window_uuid: str | None = None
    is_private: bool | None = None
    device_type: str | None = None


def scope_dict(scope: Scope) -> dict:
    """Keep optional source-specific relationships out of unrelated scope records."""
    return {key: value for key, value in asdict(scope).items() if value is not None}


@dataclass
class Tab:
    """A title and URL associated with a source-local scope."""

    id: str
    scope_id: str
    title: str | None
    url: str | None
    position: int | float | None = None
    group_id: str | None = None
    pinned: bool | None = None


@dataclass
class Snapshot:
    """One observation; IDs are not comparable between different sources."""

    source: str
    scopes: list[Scope] = field(default_factory=list)
    tabs: list[Tab] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    context: dict = field(default_factory=dict)
