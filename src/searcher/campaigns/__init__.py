"""Campaign state machine, single-writer controller, resume, events."""

from __future__ import annotations

from searcher.campaigns.controller import CampaignController
from searcher.campaigns.models import ResumeSnapshot, TransitionContext
from searcher.campaigns.resume import reconstruct
from searcher.campaigns.runner import FixtureRunner
from searcher.campaigns.states import is_terminal
from searcher.campaigns.transitions import assert_legal

__all__ = [
    "CampaignController",
    "FixtureRunner",
    "ResumeSnapshot",
    "TransitionContext",
    "assert_legal",
    "is_terminal",
    "reconstruct",
]
