"""VisionMCP integration. Importing this package does not import torch."""

from __future__ import annotations

from searcher.integrations.visionmcp.compatibility import (
    ADAPTER_VERSION,
    PINNED_SHA,
    PINNED_VERSION,
)

__all__ = ["ADAPTER_VERSION", "PINNED_SHA", "PINNED_VERSION"]
