"""Import the plugin against the AstrBot v4.28.2 decorator contract.

The contract mirrors the relevant return types in AstrBot v4.28.2 commit
3c7adafa1397e182d60b1016bf88759265113c8a, specifically
astrbot/core/star/register/star_handler.py. A command_group call returns a
plain decorator function; only applying it creates a RegisteringCommandable
with ``command`` and ``custom_filter`` methods. This caught a real plugin
import failure that syntax and pure-logic tests could not detect.
"""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class _CustomFilter:
    def __init__(self, raise_error: bool = True) -> None:
        self.raise_error = raise_error


class _RegisteringCommandable:
    def __init__(self, group_name: str) -> None:
        self.group_name = group_name
        self.commands: dict[str, object] = {}
        self.custom_filters: list[_CustomFilter] = []

    def command(self, command_name: str):
        def decorator(handler):
            self.commands[command_name] = handler
            return handler

        return decorator

    def custom_filter(self, custom_type_filter):
        return _register_custom_filter(custom_type_filter)


def _register_command_group(group_name: str):
    """Return a function, as v4.28.2 register_command_group does."""

    def decorator(handler):
        del handler
        return _RegisteringCommandable(group_name)

    return decorator


def _register_custom_filter(custom_type_filter):
    """Attach a CustomFilter to an already-created command group."""

    custom_filter = custom_type_filter(True)

    def decorator(commandable):
        if not isinstance(commandable, _RegisteringCommandable):
            raise TypeError("Custom filter expected a registered command group")
        commandable.custom_filters.append(custom_filter)
        return commandable

    return decorator


def _register_hook():
    def decorator(handler):
        return handler

    return decorator


class _Star:
    def __init__(self, context: object) -> None:
        self.context = context


class AstrBotPluginRegistrationTests(unittest.TestCase):
    def test_command_group_returns_plain_decorator_before_application(self) -> None:
        decorator = _register_command_group("probe")
        self.assertTrue(callable(decorator))
        self.assertFalse(hasattr(decorator, "custom_filter"))
        self.assertIsInstance(decorator(lambda: None), _RegisteringCommandable)

    def test_plugin_import_registers_group_filter_and_all_subcommands(self) -> None:
        """Decorator evaluation must work before any Star is instantiated."""

        astrbot = types.ModuleType("astrbot")
        api = types.ModuleType("astrbot.api")
        event = types.ModuleType("astrbot.api.event")
        provider = types.ModuleType("astrbot.api.provider")
        star = types.ModuleType("astrbot.api.star")

        api.AstrBotConfig = dict
        api.logger = types.SimpleNamespace()
        event.AstrMessageEvent = object
        event.filter = types.SimpleNamespace(
            CustomFilter=_CustomFilter,
            command_group=_register_command_group,
            custom_filter=_register_custom_filter,
            on_waiting_llm_request=_register_hook,
            on_llm_request=_register_hook,
            on_plugin_error=_register_hook,
        )
        provider.ProviderRequest = object
        star.Context = object
        star.Star = _Star

        modules = {
            "astrbot": astrbot,
            "astrbot.api": api,
            "astrbot.api.event": event,
            "astrbot.api.provider": provider,
            "astrbot.api.star": star,
        }
        plugin_path = (
            Path(__file__).resolve().parents[1]
            / "plugins"
            / "astrbot_plugin_yuuk1_core"
            / "main.py"
        )
        module_name = "plugins.astrbot_plugin_yuuk1_core._registration_test"
        spec = importlib.util.spec_from_file_location(module_name, plugin_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        plugin = importlib.util.module_from_spec(spec)

        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(plugin)

        command_group = plugin.Yuuk1CorePlugin.yuuk1
        self.assertIsInstance(command_group, _RegisteringCommandable)
        self.assertEqual(command_group.group_name, "yuuk1")
        self.assertEqual(set(command_group.commands), {"help", "status", "reset"})
        self.assertEqual(len(command_group.custom_filters), 1)
        self.assertIsInstance(
            command_group.custom_filters[0], plugin.Yuuk1CommandAllowlistFilter
        )


if __name__ == "__main__":
    unittest.main()
