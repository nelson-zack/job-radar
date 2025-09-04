from __future__ import annotations
from typing import Iterable, Protocol, Dict
from radar.core.normalize import NormalizedJob

class Provider(Protocol):
    name: str
    def fetch(self, company: dict) -> Iterable[NormalizedJob]: ...

# Provider registry (populated by module imports)
REGISTRY: Dict[str, Provider] = {}

def register(provider: Provider) -> None:
    REGISTRY[provider.name] = provider

def get(name: str) -> Provider:
    return REGISTRY[name]

# Import provider modules to self-register
try:
    from .greenhouse import GreenhouseProvider  # noqa: F401
    register(GreenhouseProvider())
except Exception:
    pass
try:
    from .lever import LeverProvider  # noqa: F401
    register(LeverProvider())
except Exception:
    pass
try:
    from .workday import WorkdayProvider  # noqa: F401
    register(WorkdayProvider())
except Exception:
    pass
