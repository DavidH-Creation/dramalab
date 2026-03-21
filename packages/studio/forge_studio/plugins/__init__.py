"""Plugin registry."""

from __future__ import annotations

from forge_studio.plugin_protocol import ForgePlugin

_registry: dict[str, ForgePlugin] = {}


def register_plugin(plugin: ForgePlugin) -> None:
    _registry[plugin.name] = plugin


def get_plugin(name: str) -> ForgePlugin | None:
    return _registry.get(name)


def list_plugins() -> list[dict]:
    return [{"name": p.name, "display_name": p.display_name} for p in _registry.values()]
