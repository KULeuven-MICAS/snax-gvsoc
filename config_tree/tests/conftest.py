import pytest
from config_tree.config import Config
from config_tree.register_field_types import MarkdownFieldList


@pytest.fixture(autouse=True)
def _reset_config_registry():
    """Clear all Config registries and caches before each test."""
    Config.reset()
    MarkdownFieldList.clear_cache()
