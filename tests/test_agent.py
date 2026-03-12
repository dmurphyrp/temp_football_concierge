"""Tests for agent.py (root_agent configuration).

Verifies that root_agent is correctly wired — name, model, and tools.
All other tool behaviour is tested in the per-tool test files.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_concierge.agent import root_agent


class TestRootAgentConfiguration:
    def test_agent_is_defined(self):
        assert root_agent is not None

    def test_agent_name(self):
        assert root_agent.name == "matchday_concierge"

    def test_agent_has_tools(self):
        assert hasattr(root_agent, "tools") or hasattr(root_agent, "_tools")

    def test_agent_model_is_gemini(self):
        assert "gemini" in root_agent.model.lower()
