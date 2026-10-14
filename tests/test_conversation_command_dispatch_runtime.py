"""Integration checks against the pinned AstrBot command and wake filters.

This module runs in AstrBot's v4.28.2 Python environment. It is skipped by the
host-only suite when AstrBot is not installed; the same file can be piped into
the running image as a separate, synthetic-event test without touching runtime
configuration, Conversations, QQ, or a Provider.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

if importlib.util.find_spec("astrbot") is None:
    raise unittest.SkipTest("requires the pinned AstrBot runtime package")

PLUGIN_ROOT = Path("/AstrBot/data/plugins")
if PLUGIN_ROOT.is_dir():
    sys.path.insert(0, str(PLUGIN_ROOT))

import astrbot_plugin_yuuk1_core.main as plugin  # noqa: E402
from astrbot.core.message.components import Plain  # noqa: E402
from astrbot.core.message.message_event_result import MessageEventResult  # noqa: E402
from astrbot.core.pipeline.waking_check import stage as waking_check  # noqa: E402
from astrbot.core.platform.message_type import MessageType  # noqa: E402
from astrbot.core.star.session_plugin_manager import SessionPluginManager  # noqa: E402
from astrbot.core.star.star_handler import EventType, star_handlers_registry  # noqa: E402


class SyntheticEvent:
    """Duck-typed QQ event accepted by AstrBot's real filter pipeline."""

    def __init__(
        self,
        message: str,
        *,
        sender_id: str = "900000002",
        sender_name: str = "QQ member",
        group_id: str = "12345",
        private: bool = False,
        platform_name: str = "aiocqhttp",
    ) -> None:
        self.message_str = message
        self.message_obj = SimpleNamespace(
            type=(MessageType.FRIEND_MESSAGE if private else MessageType.GROUP_MESSAGE)
        )
        self.role = "member"
        self.is_at_or_wake_command = False
        self.is_wake = False
        self._extras: dict[str, object] = {}
        self._force_stopped = False
        self.sent: list[object] = []
        self.sender_id = sender_id
        self.sender_name = sender_name
        self.group_id = "" if private else group_id
        self.private = private
        self.platform_name = platform_name
        self.platform_id = "napcat"
        self.session_id = sender_id if private else self.group_id

    @property
    def unified_msg_origin(self) -> str:
        if self.private:
            return f"{self.platform_id}:FriendMessage:{self.session_id}"
        return f"{self.platform_id}:GroupMessage:{self.session_id}"

    def get_message_str(self) -> str:
        return self.message_str

    def get_messages(self) -> list[object]:
        return [Plain(self.message_str)]

    def get_extra(self, key: str | None = None, default: object = None):
        if key is None:
            return self._extras
        return self._extras.get(key, default)

    def set_extra(self, key: str, value: object) -> None:
        self._extras[key] = value

    def get_sender_id(self) -> str:
        return self.sender_id

    def get_self_id(self) -> str:
        return "bot"

    def get_group_id(self) -> str:
        return self.group_id

    def get_platform_name(self) -> str:
        return self.platform_name

    def get_platform_id(self) -> str:
        return self.platform_id

    def is_private_chat(self) -> bool:
        return self.private

    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_stopped(self) -> bool:
        return self._force_stopped

    def stop_event(self) -> None:
        self._force_stopped = True

    def plain_result(self, text: str) -> MessageEventResult:
        return MessageEventResult().message(text)

    async def send(self, result: object) -> None:
        self.sent.append(result)


def build_handlers():
    """Use handlers registered by the plugin's actual AstrBot decorators."""
    registered = star_handlers_registry.get_handlers_by_event_type(
        EventType.AdapterMessageEvent,
        plugins_name=None,
    )
    command_names = {
        "main_jjctx",
        "main_jjctx_new",
        "main_jjctx_current",
        "main_jjctx_list",
        "main_jjctx_switch",
    }
    handlers = [
        handler
        for handler in registered
        if handler.handler_full_name.split(".")[-1] in command_names
    ]
    if len(handlers) != len(command_names):
        raise AssertionError("the real AstrBot registry is missing a /jjctx handler")
    return handlers


def settings(admins: list[str] | None = None, groups: list[str] | None = None):
    return plugin.normalize_config(
        {
            "admin_users": ["900000002"] if admins is None else admins,
            "allowed_groups": ["12345"] if groups is None else groups,
            "allow_private_chat": False,
        }
    )


async def run_waking_check(
    event: SyntheticEvent,
    astrbot_admins: list[str],
    handlers,
):
    stage = waking_check.WakingCheckStage()
    stage.ctx = SimpleNamespace(
        astrbot_config={
            "admins_id": astrbot_admins,
            "wake_prefix": ["/"],
            "plugin_set": ["*"],
        }
    )
    stage.unique_session = False
    stage.ignore_bot_self_message = False
    stage.ignore_at_all = False
    stage.friend_message_needs_wake_prefix = False
    stage.disable_builtin_commands = False
    stage.no_permission_reply = True
    stage._umo_auto_name_recorder = SimpleNamespace(schedule=lambda _event: None)

    async def keep_handlers(_event, activated):
        return activated

    with (
        patch.object(
            star_handlers_registry,
            "get_handlers_by_event_type",
            return_value=handlers,
        ),
        patch.object(SessionPluginManager, "filter_handlers_by_session", keep_handlers),
        patch.object(
            waking_check,
            "star_map",
            {
                handler.handler_module_path: SimpleNamespace(name="Yuuk1 Core")
                for handler in handlers
            },
        ),
    ):
        await stage.process(event)
    return event.get_extra("activated_handlers", [])


class ConversationCommandDispatchRuntimeTests(unittest.TestCase):
    def test_real_wake_and_registered_filters_dispatch_all_commands(self) -> None:
        async def exercise() -> None:
            handlers = build_handlers()
            cases = (
                ("/jjctx new", "jjctx_new", {}),
                ("/jjctx current", "jjctx_current", {}),
                ("/jjctx list", "jjctx_list", {"page": "1"}),
                (
                    "/jjctx switch 00000000-1111-4222-8333-444444444444",
                    "jjctx_switch",
                    {"conversation_id": "00000000-1111-4222-8333-444444444444"},
                ),
            )
            for raw_message, expected_handler, expected_params in cases:
                with self.subTest(command=expected_handler):
                    event = SyntheticEvent(raw_message)
                    with patch.object(plugin, "_ACTIVE_SETTINGS", settings()):
                        activated = await run_waking_check(
                            event,
                            astrbot_admins=["astrbot-global-admin"],
                            handlers=handlers,
                        )
                        self.assertEqual(
                            len(activated),
                            1,
                        )
                        self.assertTrue(
                            activated[0].handler_full_name.endswith(expected_handler)
                        )
                        self.assertEqual(event.message_str, raw_message[1:])
                        self.assertTrue(event.is_at_or_wake_command)
                        self.assertFalse(event._force_stopped)
                        parsed = event.get_extra("handlers_parsed_params", {})
                        params = next(
                            value
                            for name, value in parsed.items()
                            if name.endswith(expected_handler)
                        )
                        self.assertEqual(params, expected_params)
                        self.assertEqual(event.role, "member")

        asyncio.run(exercise())

    def test_project_admin_without_native_admin_dispatches_command(self) -> None:
        async def exercise() -> None:
            event = SyntheticEvent("/jjctx current")
            handlers = build_handlers()
            configured = settings()
            with patch.object(plugin, "_ACTIVE_SETTINGS", configured):
                activated = await run_waking_check(
                    event, astrbot_admins=["astrbot"], handlers=handlers
                )
                self.assertEqual(
                    len(activated),
                    1,
                )
                self.assertTrue(activated[0].handler_full_name.endswith("jjctx_current"))
                self.assertFalse(event.is_admin())
                self.assertFalse(event._force_stopped)
                self.assertEqual(event.sent, [])

        asyncio.run(exercise())

    def test_unauthorized_members_cannot_dispatch_even_with_matching_nickname(self) -> None:
        async def exercise() -> None:
            cases = (
                SyntheticEvent("/jjctx list", sender_id="900000003", sender_name="Yuuk1"),
                SyntheticEvent("/jjctx switch deadbeef", sender_id="900000003"),
                SyntheticEvent("/jjctx new", group_id="54321"),
                SyntheticEvent("/jjctx current", private=True),
                SyntheticEvent("/jjctx list", platform_name="other-platform"),
            )
            handlers = build_handlers()
            for event in cases:
                with self.subTest(message=event.message_str, group=event.group_id):
                    # Even an AstrBot global admin is outside this plugin's explicit scope.
                    native_admins = [event.get_sender_id()]
                    with patch.object(plugin, "_ACTIVE_SETTINGS", settings()):
                        activated = await run_waking_check(event, native_admins, handlers)
                    self.assertEqual(activated, [])
                    self.assertTrue(event._force_stopped)
                    self.assertEqual(len(event.sent), 1)
                    denial = event.sent[0].chain[0].text
                    self.assertIn("仅限允许的 QQ 群", denial)
                    self.assertNotIn(event.get_sender_id(), denial)

        asyncio.run(exercise())

    def test_missing_switch_argument_is_reported_by_real_command_filter(self) -> None:
        async def exercise() -> None:
            event = SyntheticEvent("/jjctx switch")
            handlers = build_handlers()
            with patch.object(plugin, "_ACTIVE_SETTINGS", settings()):
                activated = await run_waking_check(
                    event,
                    astrbot_admins=[event.get_sender_id()],
                    handlers=handlers,
                )
            self.assertEqual(activated, [])
            self.assertTrue(event._force_stopped)
            self.assertEqual(len(event.sent), 1)

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
