"""Nango integration layer for BAM.

Handles OAuth, token refresh, rate limiting, and credential storage for external
SaaS tools so BAM's business graph can be fed live data and can execute
initiatives against real systems.

Modules:
    nango     — Nango REST client (proxy, connections, connect sessions)
    providers — canonical field -> provider endpoint registry
    connector — NangoConnector(BaseConnector) adapter for the orchestrator
    store     — SQLite store for connection IDs and sync runs
    sync      — read path: pull canonical fields into the graph
"""

from .nango import NangoClient, NangoError, available, client_from_env
from .providers import (
    ProviderSpec, get_spec, all_specs, providers_for_field,
    fields_for_provider, coverage_report,
)
from .connector import NangoConnector, build_nango_connector
from . import store, sync

__all__ = [
    "NangoClient", "NangoError", "available", "client_from_env",
    "ProviderSpec", "get_spec", "all_specs", "providers_for_field",
    "fields_for_provider", "coverage_report",
    "NangoConnector", "build_nango_connector",
    "store", "sync",
]
