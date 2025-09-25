from __future__ import annotations

from typing import Dict

PROVIDER_STATUS: Dict[str, str] = {
    "greenhouse": "supported",
    "github": "supported",
    "ashby": "experimental",
    "workday": "experimental",
    "lever": "experimental",
    "microsoft": "planned",
    "coalition": "planned",
}

SUPPORTED_STATUSES = {"supported"}
EXPERIMENTAL_STATUSES = {"experimental"}


def is_provider_visible(name: str, enable_experimental: bool) -> bool:
    status = PROVIDER_STATUS.get(name, "planned")
    if status in SUPPORTED_STATUSES:
        return True
    if enable_experimental and status in EXPERIMENTAL_STATUSES:
        return True
    return False


def visible_providers(enable_experimental: bool) -> set[str]:
    return {
        name
        for name, status in PROVIDER_STATUS.items()
        if is_provider_visible(name, enable_experimental)
    }
