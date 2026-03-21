"""Plugin registry."""

from __future__ import annotations

from dramalab_studio.plugin_protocol import DramaLabPlugin

_registry: dict[str, DramaLabPlugin] = {}


def register_plugin(plugin: DramaLabPlugin) -> None:
    _registry[plugin.name] = plugin


def get_plugin(name: str) -> DramaLabPlugin | None:
    return _registry.get(name)


def list_plugins() -> list[dict]:
    return [{"name": p.name, "display_name": p.display_name} for p in _registry.values()]
