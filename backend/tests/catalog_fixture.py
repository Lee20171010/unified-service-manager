"""Offline official catalog fixture; production transport is never used by these tests."""
import os
from pathlib import Path
PLUGINS = Path(os.getenv('PLUGIN_FIXTURES', str(Path(__file__).resolve().parents[2] / 'plugins')))
CATALOG = Path(os.getenv('CATALOG_FIXTURES', str(Path(__file__).resolve().parents[2] / 'catalog')))

def seed_catalog(app):
    def fetch(relative, limit):
        raw = (CATALOG / relative).read_bytes()
        assert len(raw) <= limit
        return raw
    app.plugins.remote._fetch = fetch
    result = app.plugins.remote.refresh()
    assert result['error'] is None
