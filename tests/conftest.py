"""Fixtures for Labs Experience Controller tests."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom integrations from this repo in every test."""
    return
