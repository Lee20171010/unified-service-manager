"""Explicit trusted registrations. Add implementations here and ship a new image."""

from .applications import MAGPIE, SERVERBOX
from .compose import ComposeAdapter
from .demo import DemoComposeAdapter
from .registry import Registry
from .webdav import WebDAVStorage


def builtins(config):
    service = (
        DemoComposeAdapter(config) if config.mode == "demo" else ComposeAdapter(config)
    )
    return Registry([service], [MAGPIE, SERVERBOX], [WebDAVStorage(config)])
