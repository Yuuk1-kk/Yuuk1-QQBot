"""Import the plugin against the AstrBot v4.28.2 decorator contract.

The contract mirrors the relevant return types in AstrBot v4.28.2 commit
3c7adafa1397e182d60b1016bf88759265113c8a, specifically
astrbot/core/star/register/star_handler.py. A command_group call returns a
plain decorator function; only applying it creates a RegisteringCommandable
with ``command`` and ``custom_filter`` methods. This caught a real plugin
import failure that syntax and pure-logic tests could not detect.
"""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import sys
import time
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image as PillowImage

from plugins.astrbot_plugin_yuuk1_core.group_chat import GroupMessage
from plugins.astrbot_plugin_yuuk1_core.stickers import StickerCatalog

_REGISTERED_DIRECT_FILTERS: list[tuple[object, object]] = []


class _TextPart:
    def __init__(self, text: str) -> None:
        self.text = text
        self._no_save = False

    def mark_as_temp(self):
        self._no_save = True
        return self


class _Image:
    @staticmethod
    def fromFileSystem(path: str):
        return SimpleNamespace(path=path)


class _Plain:
    type = "Plain"

    def __init__(self, text: str) -> None:
        self.text = text


class _At:
    type = "At"

    def __init__(self, qq: str, name: str = "") -> None:
        self.qq = qq
        self.name = name


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


def _register_custom_filter(custom_type_filter, *_args, **_kwargs):
    """Mirror v4.28.2 filter registration for handlers and command groups."""

    custom_filter = custom_type_filter(True)

    def decorator(commandable):
        if isinstance(commandable, _RegisteringCommandable):
            commandable.custom_filters.append(custom_filter)
        else:
            _REGISTERED_DIRECT_FILTERS.append((commandable, custom_filter))
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
        message_components = types.ModuleType("astrbot.api.message_components")
        core = types.ModuleType("astrbot.core")
        core.__path__ = []
        core_agent = types.ModuleType("astrbot.core.agent")
        core_agent.__path__ = []
        core_agent_message = types.ModuleType("astrbot.core.agent.message")
        registered_listeners: list[tuple[object, object]] = []
        registered_tools: list[tuple[str | None, object]] = []
        log_records: list[tuple[str, str]] = []
        _REGISTERED_DIRECT_FILTERS.clear()

        def _capture_log(level):
            def write(message, *args, **_kwargs):
                rendered = message % args if args else str(message)
                log_records.append((level, rendered))

            return write

        def _register_event_message_type(event_type, **_):
            def decorator(handler):
                registered_listeners.append((event_type, handler))
                return handler

            return decorator

        def _register_llm_tool(name=None, **_):
            def decorator(handler):
                registered_tools.append((name, handler))
                return handler

            return decorator

        api.AstrBotConfig = dict
        api.logger = types.SimpleNamespace(
            debug=_capture_log("debug"),
            error=_capture_log("error"),
            info=_capture_log("info"),
            warning=_capture_log("warning"),
        )
        event.AstrMessageEvent = object
        event.MessageChain = list
        event_type = SimpleNamespace(GROUP_MESSAGE=object())
        event.filter = types.SimpleNamespace(
            CustomFilter=_CustomFilter,
            EventMessageType=event_type,
            command_group=_register_command_group,
            custom_filter=_register_custom_filter,
            event_message_type=_register_event_message_type,
            llm_tool=_register_llm_tool,
            on_waiting_llm_request=_register_hook,
            on_llm_request=_register_hook,
            on_plugin_error=_register_hook,
            on_decorating_result=_register_hook,
            after_message_sent=_register_hook,
        )
        provider.ProviderRequest = object
        star.Context = object
        star.Star = _Star
        star.StarTools = SimpleNamespace(
            get_data_dir=lambda _plugin_name: Path("/tmp/yuuk1-test-data")
        )
        message_components.Image = _Image
        message_components.Plain = _Plain
        core_agent_message.TextPart = _TextPart

        modules = {
            "astrbot": astrbot,
            "astrbot.api": api,
            "astrbot.api.event": event,
            "astrbot.api.provider": provider,
            "astrbot.api.star": star,
            "astrbot.api.message_components": message_components,
            "astrbot.core": core,
            "astrbot.core.agent": core_agent,
            "astrbot.core.agent.message": core_agent_message,
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
        self.assertEqual(len(registered_listeners), 1)
        self.assertEqual(registered_listeners[0][0], event_type.GROUP_MESSAGE)
        self.assertEqual(registered_listeners[0][1].__name__, "on_group_message")
        self.assertEqual(len(registered_tools), 1)
        self.assertEqual(registered_tools[0][0], "jingjing_sticker")
        self.assertEqual(
            list(inspect.signature(registered_tools[0][1]).parameters),
            ["self", "event", "category"],
        )
        group_observer = registered_listeners[0][1]
        observer_filter = next(
            custom_filter
            for handler, custom_filter in _REGISTERED_DIRECT_FILTERS
            if handler is group_observer
        )

        class FakeEvent:
            unified_msg_origin = "aiocqhttp:GroupMessage:12345"
            message_str = "你好"

            def __init__(
                self,
                attributes=None,
                result=None,
                *,
                message_str="你好",
                components=None,
                is_wake=False,
                is_at_or_wake_command=False,
                group_id="12345",
                sender_id="synthetic-user",
                self_id="synthetic-bot",
                sender_name="测试群友",
            ):
                self.extras = {}
                for name, value in (attributes or {}).items():
                    setattr(self, name, value)
                self.result = result
                self.message_str = message_str
                self.message_obj = SimpleNamespace(
                    message=components if components is not None else [_Plain(message_str)]
                )
                self.is_wake = is_wake
                self.is_at_or_wake_command = is_at_or_wake_command
                self.group_id = group_id
                self.sender_id = sender_id
                self.self_id = self_id
                self.sender_name = sender_name
                self.request_llm_calls = 0
                self.stopped = False
                self._has_send_oper = False

            def get_platform_name(self):
                return "aiocqhttp"

            def get_group_id(self):
                return self.group_id

            def get_sender_id(self):
                return self.sender_id

            def get_self_id(self):
                return self.self_id

            def get_platform_id(self):
                return "aiocqhttp"

            def get_sender_name(self):
                return self.sender_name

            def request_llm(self, **_):
                self.request_llm_calls += 1
                return SimpleNamespace(kind="provider_request")

            def get_extra(self, key, default=None):
                return self.extras.get(key, default)

            def set_extra(self, key, value):
                self.extras[key] = value

            def get_result(self):
                return self.result

            def stop_event(self):
                self.stopped = True

            def is_stopped(self):
                return self.stopped

        class FakeContext:
            def __init__(self, *, send_error=False):
                self.send_error = send_error
                self.decision = "SILENT"
                self.llm_calls = 0
                self.provider_error = None
                self.provider_id = "synthetic-provider"
                self.llm_error = None
                self.sent_messages = []
                self.last_prompt = ""
                self.last_system_prompt = ""
                self.conversation_manager = SimpleNamespace(
                    get_curr_conversation_id=self._get_current_conversation_id,
                    get_conversation=self._get_conversation,
                    new_conversation=self._new_conversation,
                )

            async def _get_current_conversation_id(self, _):
                return "synthetic-conversation"

            async def _get_conversation(self, *_):
                return SimpleNamespace(persona_id=None)

            async def _new_conversation(self, *_):
                return "synthetic-conversation"

            def get_config(self, *_):
                return {
                    "platform": [],
                }

            def get_platform_inst(self, _):
                return None

            async def send_message(self, _session, chain):
                if self.send_error:
                    raise RuntimeError("synthetic transport failure")
                self.sent_messages.append(list(chain))
                return True

            async def llm_generate(self, **_):
                self.llm_calls += 1
                self.last_prompt = str(_.get("prompt", ""))
                self.last_system_prompt = str(_.get("system_prompt", ""))
                if self.llm_error is not None:
                    raise self.llm_error
                return SimpleNamespace(completion_text=self.decision)

            async def get_current_chat_provider_id(self, _):
                if self.provider_error is not None:
                    raise self.provider_error
                return self.provider_id

        async def _exercise_plugin_hooks():
            context = FakeContext(send_error=True)
            disabled_instance = plugin.Yuuk1CorePlugin(
                context,
                {"allowed_groups": ["12345"], "stickers_enabled": True, "group_identity_enabled": False},
            )
            # Production assets are committed; model the empty-gallery case
            # explicitly instead of depending on the repository asset directory.
            disabled_instance.stickers = StickerCatalog({})
            empty_gallery_reply = await disabled_instance.jingjing_sticker_tool(
                FakeEvent(), "happy"
            )
            assert "没有可用" in empty_gallery_reply
            stickers_off_instance = plugin.Yuuk1CorePlugin(
                context,
                {"allowed_groups": ["12345"], "stickers_enabled": False},
            )
            stickers_off_event = FakeEvent()
            stickers_off_reply = await stickers_off_instance.jingjing_sticker_tool(
                stickers_off_event, "happy"
            )
            assert "当前关闭" in stickers_off_reply
            assert getattr(stickers_off_event, plugin._STICKER_SELECTION_ATTR, None) is None
            await stickers_off_instance.terminate()
            allowed_event = FakeEvent()
            assert not observer_filter.filter(allowed_event, {})
            instance = plugin.Yuuk1CorePlugin(
                context,
                {
                    "allowed_groups": ["12345"],
                    "free_talk_enabled": True,
                    "stickers_enabled": True,
                    "free_talk_probability": 0.35,
                    "free_talk_nickname_probability": 1.0,
                },
            )
            bot_reply_records = []
            record_bot_reply = instance._record_bot_reply

            def record_bot_reply_once(session, **kwargs):
                bot_reply_records.append((session, dict(kwargs)))
                return record_bot_reply(session, **kwargs)

            instance._record_bot_reply = record_bot_reply_once
            assert observer_filter.filter(allowed_event, {})

            # Identity-only operation updates names without retaining ordinary
            # message text when Free Talk and Idle Presence are disabled.
            identity_only_instance = plugin.Yuuk1CorePlugin(
                context,
                {"allowed_groups": ["12345"], "group_identity_enabled": True},
            )
            identity_only_event = FakeEvent(message_str="identity-only message")
            assert observer_filter.filter(identity_only_event, {})
            assert [
                item async for item in identity_only_instance.on_group_message(identity_only_event)
            ] == []
            assert identity_only_instance.group_identity.known_member_count() == 1
            assert identity_only_instance.group_context.recent(
                identity_only_event.unified_msg_origin, now=time.monotonic()
            ) == ()

            # Error logs must never serialize exception/traceback text, which
            # may contain user messages, prompts, provider IDs, or credentials.
            sensitive_traceback = (
                "message=private-message QQ=private-account "
                "group=private-group provider=private-provider "
                "prompt=private-prompt persona=private-persona "
                "conversation=private-conversation api_key=private-key token=private-token"
            )
            await instance.handle_plugin_error(
                FakeEvent(group_id="unapproved-group"),
                plugin.PLUGIN_NAME,
                "safe_log_test",
                RuntimeError(sensitive_traceback),
                sensitive_traceback,
            )
            rendered_logs = "\n".join(message for _, message in log_records)
            for marker in (
                "private-message",
                "private-account",
                "private-group",
                "private-provider",
                "private-prompt",
                "private-persona",
                "private-conversation",
                "private-key",
                "private-token",
            ):
                assert marker not in rendered_logs
            assert "error_type=RuntimeError" in rendered_logs

            class FakeResult:
                def __init__(self, text):
                    self.chain = [_Plain(text)]

                def is_llm_result(self):
                    return True

            class FakeReply:
                type = "Reply"

                def __init__(self, sender_id):
                    self.sender_id = sender_id

            # IDLE ordinary messages use the configured probability and then
            # exactly one classifier call. SILENT creates no native request.
            context.decision = "SILENT"
            context.provider_error = None
            context.llm_error = None
            instance.group_context.clear()
            instance.group_context.record_message(
                "aiocqhttp:GroupMessage:12345",
                sender_key="prior-user",
                display_name="",
                text="有点热",
                timestamp=time.time(),
                now=time.monotonic(),
            )
            silent_event = FakeEvent(message_str="今天群里真热闹")
            calls_before = context.llm_calls
            with patch.object(plugin.random, "random", return_value=0.34):
                silent_yields = [
                    item async for item in instance.on_group_message(silent_event)
                ]
            assert context.llm_calls == calls_before + 1
            assert silent_event.request_llm_calls == 0
            assert silent_yields == []
            assert not getattr(silent_event, plugin._ENGAGEMENT_PENDING_ATTR, False)
            assert not context.sent_messages
            assert not any("FT diag:" in message for _, message in log_records)

            # Direct calls bypass generic probability, recent-message minimum,
            # legacy cooldowns, and the SPEAK/SILENT classifier.
            direct_context = FakeContext()
            direct_instance = plugin.Yuuk1CorePlugin(
                direct_context,
                {
                    "allowed_groups": ["12345"],
                    "free_talk_enabled": True,
                    "rate_limit_enabled": False,
                    "free_talk_min_interval_seconds": 999,
                    "free_talk_decision_interval_seconds": 999,
                    "free_talk_nickname_probability": 0,
                    "free_talk_min_recent_messages": 100,
                },
            )
            direct_context.decision = "SILENT"
            direct_events = (
                FakeEvent(message_str="大肥鱼下士出列！", sender_name="奶龙鉴赏家"),
                FakeEvent(message_str="鲸鲸你觉得呢", sender_name="Yuuk1"),
            )
            with (
                patch.object(plugin.random, "random", return_value=0.99),
                patch.object(
                    plugin,
                    "should_run_decision",
                    side_effect=AssertionError("direct calls bypass probability"),
                ),
            ):
                for direct_event in direct_events[:1]:
                    direct_yields = [
                        item async for item in direct_instance.on_group_message(direct_event)
                    ]
                    assert len(direct_yields) == 1
                    assert direct_event.request_llm_calls == 1
                    assert getattr(direct_event, plugin._ENGAGEMENT_PENDING_ATTR)
                    current_message = getattr(direct_event, plugin._CURRENT_GROUP_MESSAGE_ATTR)
                    assert current_message.sender == "奶龙鉴赏家"
                    assert current_message.member_key.startswith("member_")
            assert direct_context.llm_calls == 0
            assert direct_instance.settings.free_talk_min_interval_seconds == 999
            assert direct_instance.settings.free_talk_decision_interval_seconds == 999

            # A successful three-part response becomes one bot turn and enters
            # engagement once. AstrBot's actual-send marker is required.
            direct_context.send_error = False
            first_direct = direct_events[0]
            first_direct.result = FakeResult(
                "在，怎么了？\n我刚才在忙。\n现在可以说。"
            )
            first_direct._has_send_oper = True
            await direct_instance.decorate_sticker_result(first_direct)
            assert len(first_direct.result.chain) == 1
            assert getattr(first_direct, plugin._PENDING_TEXT_PARTS_ATTR) == [
                "我刚才在忙。",
                "现在可以说。",
            ]
            await direct_instance.after_message_sent(first_direct)
            direct_session = first_direct.unified_msg_origin
            assert direct_instance.group_context.engagement_status(
                direct_session,
                now=time.monotonic(),
                enabled=True,
                timeout_seconds=300,
            )[0]
            bot_turns = [
                item
                for item in direct_instance.group_context.recent(
                    direct_session, now=time.monotonic()
                )
                if item.is_bot
            ]
            assert len(bot_turns) == 1
            assert bot_turns[0].text == "在，怎么了？\n我刚才在忙。\n现在可以说。"

            # The next direct address remains immediate after a successful
            # reply; it is not a chat cooldown and does not classify.
            second_direct_yields = [
                item async for item in direct_instance.on_group_message(direct_events[1])
            ]
            assert len(second_direct_yields) == 1
            assert direct_events[1].request_llm_calls == 1
            assert direct_context.llm_calls == 0

            # ENGAGED continuation bypasses random probability entirely and
            # enters the native Agent generation path without another classifier.
            related_event = FakeEvent(message_str="你刚才干嘛去了")
            direct_context.llm_calls = 0
            with (
                patch.object(plugin.random, "random", return_value=0.99),
                patch.object(
                    plugin,
                    "should_run_decision",
                    side_effect=AssertionError(
                        "ENGAGED continuation bypasses probability"
                    ),
                ),
            ):
                related_yields = [
                    item async for item in direct_instance.on_group_message(related_event)
                ]
            assert len(related_yields) == 1
            assert related_event.request_llm_calls == 1
            assert direct_context.llm_calls == 0

            # Ambiguous ENGAGED input gets one relevance classification; SILENT
            # does not refresh the existing engagement timestamp.
            context.decision = "SILENT"
            engagement_state = direct_instance.group_context._groups[direct_session]
            last_engaged_before_silent = engagement_state.last_engaged_at
            ambiguous_event = FakeEvent(
                message_str="Steam 下完了吗",
                sender_id="different-human",
            )
            calls_before_ambiguous = direct_context.llm_calls
            with patch.object(
                plugin,
                "should_run_decision",
                side_effect=AssertionError("ENGAGED does not reroll 0.35"),
            ):
                ambiguous_yields = [
                    item async for item in direct_instance.on_group_message(ambiguous_event)
                ]
            assert ambiguous_yields == []
            assert ambiguous_event.request_llm_calls == 0
            assert direct_context.llm_calls == calls_before_ambiguous + 1
            assert engagement_state.last_engaged_at == last_engaged_before_silent
            assert "在，怎么了？" in direct_context.last_prompt
            assert "你刚才干嘛去了" in direct_context.last_prompt
            assert "Steam 下完了吗" in direct_context.last_prompt
            assert "是否自然延续" in direct_context.last_prompt

            # A resolved Reply to another human is confidently unrelated.
            reply_other = FakeEvent(
                message_str="还没",
                components=[FakeReply("different-human"), _Plain("还没")],
                sender_id="third-human",
            )
            calls_before_other_reply = direct_context.llm_calls
            assert [
                item async for item in direct_instance.on_group_message(reply_other)
            ] == []
            assert direct_context.llm_calls == calls_before_other_reply
            assert reply_other.request_llm_calls == 0

            # A resolved Reply to this bot bypasses probability/classification.
            reply_to_bot = FakeEvent(
                message_str="你还在吗",
                components=[FakeReply("synthetic-bot"), _Plain("你还在吗")],
            )
            calls_before_bot_reply = direct_context.llm_calls
            reply_yields = [
                item async for item in direct_instance.on_group_message(reply_to_bot)
            ]
            assert len(reply_yields) == 1
            assert reply_to_bot.request_llm_calls == 1
            assert direct_context.llm_calls == calls_before_bot_reply
            reply_to_bot.result = FakeResult("在呀。")
            reply_to_bot._has_send_oper = True
            await direct_instance.decorate_sticker_result(reply_to_bot)
            await direct_instance.after_message_sent(reply_to_bot)
            assert direct_instance.group_context.engagement_status(
                direct_session,
                now=time.monotonic(),
                enabled=True,
                timeout_seconds=300,
            )[0]

            # Direct and continuation events whose native send failed do not
            # enter or refresh engagement merely because the after hook runs.
            failed_direct = FakeEvent(message_str="大肥鱼过来")
            failed_direct_yields = [
                item async for item in direct_instance.on_group_message(failed_direct)
            ]
            assert len(failed_direct_yields) == 1
            failed_direct.result = FakeResult("没发出去")
            failed_direct._has_send_oper = False
            failed_at = engagement_state.last_engaged_at
            await direct_instance.decorate_sticker_result(failed_direct)
            await direct_instance.after_message_sent(failed_direct)
            assert engagement_state.last_engaged_at == failed_at

            # IDLE generic Free Talk ignores legacy chat cooldown fields, keeps
            # probability=0.35, and SPEAK hands off to one normal generation.
            generic_context = FakeContext()
            generic_instance = plugin.Yuuk1CorePlugin(
                generic_context,
                {
                    "allowed_groups": ["12345"],
                    "free_talk_enabled": True,
                    "rate_limit_enabled": False,
                    "free_talk_min_interval_seconds": 999,
                    "free_talk_decision_interval_seconds": 999,
                    "free_talk_probability": 0.35,
                    "free_talk_min_recent_messages": 2,
                },
            )
            generic_instance.group_context.record_message(
                "aiocqhttp:GroupMessage:12345",
                sender_key="prior-user",
                display_name="",
                text="上一条普通消息",
                timestamp=time.time(),
                now=time.monotonic(),
            )
            generic_context.decision = "SPEAK"
            generic_event = FakeEvent(message_str="今天群里真热闹")
            with patch.object(plugin.random, "random", return_value=0.34):
                generic_yields = [
                    item async for item in generic_instance.on_group_message(generic_event)
                ]
            assert len(generic_yields) == 1
            assert generic_context.llm_calls == 1
            assert generic_event.request_llm_calls == 1
            assert generic_instance.settings.free_talk_min_interval_seconds == 999
            generic_event.result = FakeResult("确实挺热闹。")
            generic_event._has_send_oper = True
            await generic_instance.decorate_sticker_result(generic_event)
            await generic_instance.after_message_sent(generic_event)
            assert generic_instance.group_context.engagement_status(
                generic_event.unified_msg_origin,
                now=time.monotonic(),
                enabled=True,
                timeout_seconds=300,
            )[0]

            # After the exact 300-second timeout, the group lazily returns to
            # IDLE and an ordinary message must hit the 0.35 random gate again.
            generic_state = generic_instance.group_context._groups[
                generic_event.unified_msg_origin
            ]
            generic_state.last_engaged_at = time.monotonic() - 301
            expired_event = FakeEvent(message_str="新的独立话题")
            calls_before_expired = generic_context.llm_calls
            with patch.object(plugin.random, "random", return_value=0.99) as roll:
                expired_yields = [
                    item async for item in generic_instance.on_group_message(expired_event)
                ]
            assert expired_yields == []
            assert roll.call_count == 1
            assert generic_context.llm_calls == calls_before_expired
            assert generic_state.last_engaged_at is None

            # Provider failure and classifier exceptions fail closed without
            # logging prompt or exception contents.
            instance.group_context.clear()
            instance.group_context.record_message(
                "aiocqhttp:GroupMessage:12345",
                sender_key="prior-user",
                display_name="",
                text="有点热",
                timestamp=time.time(),
                now=time.monotonic(),
            )
            context.provider_error = RuntimeError("synthetic secret must stay hidden")
            provider_event = FakeEvent(message_str="今天群里真热闹")
            calls_before_provider = context.llm_calls
            with patch.object(plugin.random, "random", return_value=0.34):
                provider_yields = [
                    item async for item in instance.on_group_message(provider_event)
                ]
            assert provider_yields == []
            assert context.llm_calls == calls_before_provider
            assert any(
                "reason=provider_unavailable; error_type=RuntimeError" in message
                for _, message in log_records
            )
            assert all("synthetic secret" not in message for _, message in log_records)

            context.provider_error = None
            context.llm_error = ValueError("synthetic prompt contents stay hidden")
            exception_event = FakeEvent(message_str="今天群里真热闹")
            calls_before_exception = context.llm_calls
            with patch.object(plugin.random, "random", return_value=0.34):
                exception_yields = [
                    item async for item in instance.on_group_message(exception_event)
                ]
            assert exception_yields == []
            assert context.llm_calls == calls_before_exception + 1
            assert any(
                "decision failed; error_type=ValueError" in message
                for _, message in log_records
            )
            assert all(
                "synthetic prompt contents" not in message for _, message in log_records
            )
            context.llm_error = None

            # A five-turn burst remains under the project security request limit.
            limiter = plugin.TwoLevelRateLimiter(60, 8, 60, 30)
            for index in range(5):
                assert limiter.allow("normal-user", "12345", now=100 + index)[0]

            # Native @/wake follows AstrBot's existing path, gets no duplicate
            # decision request, and enters engagement only after a sent reply.
            native_wake = FakeEvent(
                message_str="你好",
                components=[_At("synthetic-bot"), _Plain("你好")],
                is_at_or_wake_command=True,
            )
            calls_before_wake = direct_context.llm_calls
            assert [
                item async for item in direct_instance.on_group_message(native_wake)
            ] == []
            assert native_wake.request_llm_calls == 0
            assert direct_context.llm_calls == calls_before_wake
            assert getattr(native_wake, plugin._ENGAGEMENT_PENDING_ATTR)
            native_wake.result = FakeResult("你好呀。")
            native_wake._has_send_oper = True
            await direct_instance.decorate_sticker_result(native_wake)
            await direct_instance.after_message_sent(native_wake)
            assert direct_instance.group_context.engagement_status(
                native_wake.unified_msg_origin,
                now=time.monotonic(),
                enabled=True,
                timeout_seconds=300,
            )[0]

            # Adapter-flattened mentions carry raw IDs; keep the native prompt
            # on its display-name-only representation.
            private_id_wake = FakeEvent(
                message_str="@偷摸零(123456789) 看看",
                components=[_At("synthetic-bot"), _At("123456789", "偷摸零"), _Plain("看看")],
                is_at_or_wake_command=True,
            )
            assert [
                item async for item in direct_instance.on_group_message(private_id_wake)
            ] == []
            assert private_id_wake.message_str == "@偷摸零 看看"
            assert "123456789" not in private_id_wake.message_str
            # A slash command and a self message never reach the classifier.
            command_event = FakeEvent(
                message_str="/yuuk1 status",
                is_wake=True,
            )
            self_event = FakeEvent(
                message_str="\u5927\u80a5\u9c7c\u5728\u5417",
                is_wake=True,
                sender_id="synthetic-bot",
            )
            calls_before_exclusions = context.llm_calls
            async for _ in instance.on_group_message(command_event):
                raise AssertionError("commands must not be yielded to the LLM")
            instance.group_context.clear()
            async for _ in instance.on_group_message(self_event):
                raise AssertionError("self messages must not be yielded to the LLM")
            assert context.llm_calls == calls_before_exclusions
            assert instance.group_context.recent(
                self_event.unified_msg_origin,
                now=time.monotonic(),
            ) == ()

            denied_event = FakeEvent(group_id="54321")
            assert not observer_filter.filter(denied_event, {})
            assert not instance._is_allowed_context(denied_event)
            message = GroupMessage(
                timestamp=1,
                sender="群友1",
                text="前文含敏感测试标记",
                mentions_jingjing=False,
                at_bot=False,
                member_key="member_" + "a" * 64,
                received_monotonic=1,
            )
            current_group_message = GroupMessage(
                timestamp=2,
                sender="奶龙鉴赏家",
                text="当前消息内容",
                mentions_jingjing=False,
                at_bot=False,
                member_key="member_" + "b" * 64,
                received_monotonic=2,
            )
            event_with_context = FakeEvent(
                attributes={
                    plugin._FREE_TALK_CONTEXT_ATTR: (message,),
                    plugin._CURRENT_GROUP_MESSAGE_ATTR: current_group_message,
                },
            )

            class FakeToolSet:
                def __init__(self):
                    self.tools = {"jingjing_sticker", "web_search"}

                def remove_tool(self, name):
                    self.tools.discard(name)

            tool_set = FakeToolSet()
            request = SimpleNamespace(
                system_prompt="Persona-owned stable prompt",
                extra_user_content_parts=[],
                func_tool=tool_set,
            )
            # Exercise the hidden-tool behavior independently of committed
            # production assets; the asset-present case is covered below.
            instance.stickers = StickerCatalog({})
            await instance.customize_request(event_with_context, request)
            assert "前文含敏感测试标记" not in request.system_prompt
            assert len(request.extra_user_content_parts) == 1
            assert request.extra_user_content_parts[0]._no_save
            assert "当前群消息发送者：[奶龙鉴赏家]" in request.extra_user_content_parts[0].text
            assert "[群友1] 前文含敏感测试标记" in request.extra_user_content_parts[0].text
            assert "[奶龙鉴赏家] 当前消息内容" in request.extra_user_content_parts[0].text
            assert "synthetic-user" not in request.extra_user_content_parts[0].text
            assert "synthetic-bot" not in request.extra_user_content_parts[0].text
            assert tool_set.tools == {"web_search"}
            assert set(event_with_context.extras) == {plugin.PERSONA_ERROR_EXTRA_KEY}
            assert "前文含敏感测试标记" not in repr(event_with_context.extras)

            context.send_error = True
            with TemporaryDirectory() as directory:
                sticker_root = Path(directory) / "stickers"
                image_path = sticker_root / "happy" / "private-name.png"
                image_path.parent.mkdir(parents=True)
                PillowImage.new("RGB", (3, 2), color=(64, 128, 192)).save(image_path)
                instance.sticker_root = sticker_root
                instance.stickers = StickerCatalog(
                    {"happy": (image_path.resolve(),)},
                    history_size=instance.settings.sticker_repeat_window,
                )

                class VisibleToolSet:
                    def __init__(self):
                        self.tools = {"jingjing_sticker", "web_search"}

                    def remove_tool(self, name):
                        self.tools.discard(name)

                visible_tools = VisibleToolSet()
                enabled_request = SimpleNamespace(
                    system_prompt="",
                    extra_user_content_parts=[],
                    func_tool=visible_tools,
                )
                await instance.customize_request(FakeEvent(), enabled_request)
                assert visible_tools.tools == {"jingjing_sticker", "web_search"}

                # The tool receives only an allowlisted category. The selected
                # local path stays on the event and never enters tool output.
                tool_event = FakeEvent()
                llm_calls_before_tool = context.llm_calls
                tool_reply = await instance.jingjing_sticker_tool(tool_event, "happy")
                assert str(image_path) not in tool_reply
                assert getattr(tool_event, plugin._STICKER_SELECTION_ATTR)["path"] == str(
                    image_path.resolve()
                )
                second_tool_reply = await instance.jingjing_sticker_tool(
                    tool_event, "happy"
                )
                assert "已经选择过" in second_tool_reply
                assert str(image_path) not in repr(tool_event.extras)
                assert context.llm_calls == llm_calls_before_tool

                invalid_event = FakeEvent()
                invalid_reply = await instance.jingjing_sticker_tool(
                    invalid_event, "../../outside"
                )
                assert str(image_path) not in invalid_reply
                assert getattr(invalid_event, plugin._STICKER_SELECTION_ATTR, None) is None

                # A failed optional image send leaves generated text untouched.
                original_text = _Plain("这是保底文字")
                result = SimpleNamespace(chain=[original_text])
                image_event = FakeEvent(
                    attributes={
                        plugin._STICKER_SELECTION_ATTR: {
                            "path": str(image_path),
                            "category": "happy",
                        },
                        plugin._ENGAGEMENT_PENDING_ATTR: True,
                    },
                    result=result,
                )
                image_event._has_send_oper = True
                await instance.decorate_sticker_result(image_event)
                assert result.chain == [original_text]
                assert getattr(image_event, plugin._PENDING_STICKER_ATTR) == str(
                    image_path
                )
                assert str(image_path) not in repr(image_event.extras)
                await instance.after_message_sent(image_event)
                assert result.chain == [original_text]
                assert len(bot_reply_records) == 1
                sticker_failure_logs = [
                    message
                    for _level, message in log_records
                    if "sticker_send_failed" in message
                ]
                assert sticker_failure_logs
                assert all(str(image_path) not in message for message in sticker_failure_logs)
                assert all("exception_type=" in message for message in sticker_failure_logs)
                assert all("synthetic-user" not in message for message in sticker_failure_logs)
                assert all("12345" not in message for message in sticker_failure_logs)
                assert all("这是保底文字" not in message for message in sticker_failure_logs)

                corrupt_path = sticker_root / "happy" / "corrupt.png"
                corrupt_path.write_bytes(b"\x89PNG\r\n\x1a\ncorrupt")
                corrupt_result = SimpleNamespace(chain=[_Plain("损坏图片时仍保留这句文字")])
                corrupt_event = FakeEvent(
                    attributes={
                        plugin._STICKER_SELECTION_ATTR: {
                            "path": str(corrupt_path),
                            "category": "happy",
                        }
                    },
                    result=corrupt_result,
                )
                await instance.decorate_sticker_result(corrupt_event)
                assert corrupt_result.chain[0].text == "损坏图片时仍保留这句文字"
                assert getattr(corrupt_event, plugin._PENDING_STICKER_ATTR, None) is None

                empty_failed_result = SimpleNamespace(chain=[])
                empty_failed_event = FakeEvent(
                    attributes={
                        plugin._STICKER_SELECTION_ATTR: {
                            "path": str(image_path),
                            "category": "happy",
                        }
                    },
                    result=empty_failed_result,
                )
                await instance.decorate_sticker_result(empty_failed_event)
                assert [part.text for part in empty_failed_result.chain] == [
                    plugin._STICKER_SEND_FALLBACK_TEXT
                ]

                # A future text-and-sticker reply keeps the order text, more
                # text, sticker while using one completed LLM result.
                context.send_error = False
                context.sent_messages.clear()
                bot_reply_records.clear()
                combined_event = FakeEvent(
                    attributes={
                        plugin._STICKER_SELECTION_ATTR: {
                            "path": str(image_path),
                            "category": "happy",
                        },
                        plugin._ENGAGEMENT_PENDING_ATTR: True,
                    },
                    result=FakeResult(
                        "干嘛，突然叫这么大声。\n我又没跑。\n找鲸鲸什么事？"
                    ),
                )
                combined_event._has_send_oper = True
                await instance.decorate_sticker_result(combined_event)
                assert combined_event.result.chain[0].text == "干嘛，突然叫这么大声。"
                await instance.after_message_sent(combined_event)
                assert len(context.sent_messages) == 3
                assert [chain[0].text for chain in context.sent_messages[:2]] == [
                    "我又没跑。",
                    "找鲸鲸什么事？",
                ]
                assert context.sent_messages[2][0].path == str(image_path)
                assert len(bot_reply_records) == 1

                # An empty final text result uses the same selected asset as an
                # image-only reply and sends exactly once.
                context.sent_messages.clear()
                bot_reply_records.clear()
                image_only_result = SimpleNamespace(chain=[])
                image_only_event = FakeEvent(
                    attributes={
                        plugin._STICKER_SELECTION_ATTR: {
                            "path": str(image_path),
                            "category": "happy",
                        },
                        plugin._ENGAGEMENT_PENDING_ATTR: True,
                    },
                    result=image_only_result,
                )
                await instance.decorate_sticker_result(image_only_event)
                assert image_only_result.chain == []
                assert len(context.sent_messages) == 1
                assert context.sent_messages[0][0].path == str(image_path)
                await instance.after_message_sent(image_only_event)
                assert len(context.sent_messages) == 1
                assert len(bot_reply_records) == 1
            await instance.terminate()
            await disabled_instance.terminate()
            await identity_only_instance.terminate()

        asyncio.run(_exercise_plugin_hooks())

        client_registry: dict[str, object] = {}
        adapter = types.SimpleNamespace(
            bot=types.SimpleNamespace(_wsr_api_clients=client_registry)
        )

        class OneBotContext:
            def get_config(self):
                return {
                    "platform": [
                        {
                            "id": "renamed-napcat",
                            "type": "aiocqhttp",
                            "enable": True,
                            "ws_reverse_port": 6199,
                        }
                    ]
                }

            def get_platform_inst(self, platform_id):
                assert platform_id == "renamed-napcat"
                return adapter

        context = OneBotContext()
        self.assertFalse(plugin._onebot_clients_connected(context))
        client_registry["opaque-id"] = object()
        self.assertTrue(plugin._onebot_clients_connected(context))
        client_registry.clear()
        self.assertFalse(plugin._onebot_clients_connected(context))


if __name__ == "__main__":
    unittest.main()
