"""Run via stdin in an isolated AstrBot v4.28.2 Python process.

This uses AstrBot's real hook dispatcher and InternalAgentSubStage. It never
selects a Provider, contacts QQ, or mutates the running AstrBot process.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from astrbot.api.message_components import Plain, Reply
from astrbot.core.agent.message import Message, TextPart
from astrbot.core.astr_agent_hooks import MainAgentHooks
from astrbot.core.message.message_event_result import MessageChain, MessageEventResult
from astrbot.core.pipeline import context_utils
from astrbot.core.pipeline.process_stage.method.agent_sub_stages import internal
from astrbot.core.provider.entities import LLMResponse
from astrbot.core.star.star_handler import EventType
from data.plugins.astrbot_plugin_yuuk1_core.main import (
    _CURRENT_GROUP_MESSAGE_ATTR,
    _FREE_TALK_CONTEXT_ATTR,
    Yuuk1CorePlugin,
)


class SyntheticEvent:
    plugins_name = None
    unified_msg_origin = "aiocqhttp:GroupMessage:12345"

    def __init__(
        self,
        sender: str,
        name: str,
        text: str,
        *,
        message_id: int = 700000001,
    ) -> None:
        self.message_str = text
        self.message_obj = SimpleNamespace(message=[Plain(text)], message_id=message_id)
        self.sender = sender
        self.name = name
        self.sent: list[MessageChain] = []
        self.action_calls: list[tuple[str, dict[str, object]]] = []
        self.reply_payload: object = None
        self.raise_on_get_msg = False
        self.bot = SimpleNamespace(call_action=self.call_action)
        self.stopped = False
        self._extras: dict[str, object] = {}

    async def call_action(self, action: str, **params: object) -> object:
        self.action_calls.append((action, params))
        if action == "get_msg":
            if self.raise_on_get_msg:
                raise TimeoutError("synthetic timeout")
            return self.reply_payload
        if action == "send_group_msg":
            return {
                "status": "ok",
                "retcode": 0,
                "data": {"message_id": 700000100 + len(self.action_calls)},
            }
        raise AssertionError("unexpected OneBot action")

    def get_platform_name(self) -> str:
        return "aiocqhttp"

    def get_group_id(self) -> str:
        return "12345"

    def get_sender_id(self) -> str:
        return self.sender

    def get_sender_name(self) -> str:
        return self.name

    def get_self_id(self) -> str:
        return "900000099"

    def get_extra(self, key: str, default: object = None) -> object:
        return self._extras.get(key, default)

    def set_extra(self, key: str, value: object) -> None:
        self._extras[key] = value

    def stop_event(self) -> None:
        self.stopped = True

    def is_stopped(self) -> bool:
        return self.stopped

    def plain_result(self, text: str) -> MessageEventResult:
        return MessageEventResult().message(text)

    async def send(self, result: MessageChain) -> None:
        assert self.stopped
        self.sent.append(result)

    async def send_typing(self) -> None:
        return None

    async def stop_typing(self) -> None:
        return None


async def main() -> None:
    plugin = Yuuk1CorePlugin(
        SimpleNamespace(),
        {
            "allowed_groups": ["12345"],
            "owner_qq_id": "900000001",
            "rate_limit_enabled": False,
            "group_identity_enabled": False,
            "free_talk_enabled": True,
        },
    )
    handler = SimpleNamespace(
        handler=plugin.guard_qq_request,
        handler_module_path="synthetic.owner",
        handler_name="guard_qq_request",
    )
    stage = SimpleNamespace(streaming_response=False, show_reasoning=False)
    with (
        patch.object(
            context_utils.star_handlers_registry,
            "get_handlers_by_event_type",
            return_value=[handler],
        ),
        patch.dict(
            context_utils.star_map,
            {"synthetic.owner": SimpleNamespace(name="Yuuk1 Core")},
        ),
        patch.object(internal, "try_capture_follow_up", return_value=None),
    ):
        for sender, name, expected_owner in (
            ("900000001", "奶龙鉴赏家", True),
            ("900000002", "Yuuk1", False),
        ):
            event = SyntheticEvent(sender, name, "鲸鲸，我是你的主人吗？")
            plugin.group_context.record_message(
                event.unified_msg_origin,
                sender_key=sender,
                display_name=name,
                text=event.message_str,
                timestamp=1,
                now=1,
            )
            yielded = [
                item
                async for item in internal.InternalAgentSubStage.process(
                    stage, event, ""
                )
            ]
            assert yielded == []
            assert event.is_stopped()
            replies = [
                call[1]["message"][0]["data"]["text"]
                for call in event.action_calls
                if call[0] == "send_group_msg"
            ]
            assert len(replies) == 1
            reply = replies[0]
            assert ("不是鲸鲸的主人" not in reply) == expected_owner

        ordinary = SyntheticEvent("900000002", "Yuuk1", "鲸鲸，今天天气怎样？")
        stopped = await context_utils.call_event_hook(
            ordinary, EventType.OnWaitingLLMRequestEvent
        )
        assert not stopped and ordinary.sent == []

    for sender, name, expected in (
        ("900000001", "改过的昵称", "是你呀，Yuuk1"),
        ("900000002", "Yuuk1", "你现在叫Yuuk1"),
    ):
        event = SyntheticEvent(sender, name, "鲸鲸，你看看我是谁呢？")
        plugin.group_context.record_message(
            event.unified_msg_origin,
            sender_key=sender,
            display_name=name,
            text=event.message_str,
            timestamp=2,
            now=2,
        )
        with (
            patch.object(
                context_utils.star_handlers_registry,
                "get_handlers_by_event_type",
                return_value=[handler],
            ),
            patch.dict(
                context_utils.star_map,
                {"synthetic.owner": SimpleNamespace(name="Yuuk1 Core")},
            ),
        ):
            stopped = await context_utils.call_event_hook(
                event, EventType.OnWaitingLLMRequestEvent
            )
        replies = [
            call[1]["message"][0]["data"]["text"]
            for call in event.action_calls
            if call[0] == "send_group_msg"
        ]
        assert stopped and len(replies) == 1
        assert expected in replies[0]

    def get_msg_payload(
        *, sender_id: int = 900000099, group_id: int = 12345, nested: bool = False
    ) -> dict[str, object]:
        return {
            "status": "ok",
            "retcode": 0,
            "data": {
                "message_id": 700000001,
                "message_type": "group",
                "group_id": group_id,
                "self_id": 900000099,
                "sender": {"user_id": sender_id, "nickname": "鲸鲸"},
                "message": (
                    [{"type": "reply", "data": {"id": "700000000"}}]
                    if nested
                    else [{"type": "text", "data": {"text": "synthetic"}}]
                ),
            },
        }

    quote_cases = (
        ("bot", get_msg_payload(), False, "那这是谁发的？", "这条是我发的。"),
        (
            "bot_yes_no",
            get_msg_payload(),
            False,
            "这句是你说的吗？",
            "这条是我发的。",
        ),
        (
            "same_name_member",
            get_msg_payload(sender_id=900000002),
            False,
            "那这是谁发的？",
            "这是群友发的。",
        ),
        (
            "cross_group",
            get_msg_payload(group_id=12346),
            False,
            "那这是谁发的？",
            "没法可靠核实",
        ),
        (
            "nested",
            get_msg_payload(nested=True),
            False,
            "那这是谁发的？",
            "没法可靠核实",
        ),
        (
            "lookup_failed",
            get_msg_payload(),
            True,
            "那这是谁发的？",
            "没法可靠核实",
        ),
    )
    for index, (case_name, payload, raise_on_get_msg, question_text, expected) in enumerate(
        quote_cases, start=10
    ):
        event = SyntheticEvent(
            "900000002", "鲸鲸", question_text, message_id=700000000 + index
        )
        adapter_sender_id = (
            payload.get("data", {}).get("sender", {}).get("user_id", "900000099")
            if isinstance(payload, dict)
            else "900000099"
        )
        event.message_obj.message = [
            Reply(id="700000001", sender_id=str(adapter_sender_id)),
            Plain(question_text),
        ]
        event.reply_payload = payload
        event.raise_on_get_msg = raise_on_get_msg
        plugin.group_context.record_message(
            event.unified_msg_origin,
            sender_key=event.sender,
            display_name=event.name,
            text=event.message_str,
            timestamp=float(index),
            now=float(index),
        )
        with (
            patch.object(
                context_utils.star_handlers_registry,
                "get_handlers_by_event_type",
                return_value=[handler],
            ),
            patch.dict(
                context_utils.star_map,
                {"synthetic.owner": SimpleNamespace(name="Yuuk1 Core")},
            ),
        ):
            stopped = await context_utils.call_event_hook(
                event, EventType.OnWaitingLLMRequestEvent
            )
        assert stopped and event.is_stopped()
        get_calls = [call for call in event.action_calls if call[0] == "get_msg"]
        if raise_on_get_msg:
            assert len(get_calls) == 1
        else:
            assert len(get_calls) == 1
        replies = [
            call[1]["message"][0]["data"]["text"]
            for call in event.action_calls
            if call[0] == "send_group_msg"
        ]
        assert len(replies) == 1 and expected in replies[0], case_name
        last = plugin.group_context.recent(event.unified_msg_origin, now=float(index))[-1]
        assert last.is_bot and last.text == replies[0]
        assert last.source_event_key and last.platform_message_key

    # Simulate the reported sequence in one group: deterministic Owner Q&A,
    # then an ordinary LLM request, then a same-name non-Owner request. This
    # exercises the real v4.28.2 OnLLMRequest hook without a Provider call.
    session = "aiocqhttp:GroupMessage:multi-turn"
    prior_human = plugin.group_context.record_message(
        session,
        sender_key="900000001",
        display_name="changed-owner-name",
        text="你看看我是谁呢？",
        timestamp=100,
        now=100,
    )
    assert prior_human is not None
    prior_bot = plugin.group_context.record_bot_reply(
        session,
        timestamp=101,
        now=101,
        text="是你呀，Yuuk1。还要鲸鲸认几遍？",
        source_event_id="700000200",
        platform_message_id="700000201",
    )
    assert prior_bot is not None and prior_bot.is_bot
    group_history = plugin.group_context.recent(session, now=102)
    followup = SyntheticEvent(
        "900000001", "changed-owner-name", "鲸鲸，以后在群里叫我老大", message_id=700000202
    )
    followup.unified_msg_origin = session
    current = plugin.group_context.record_message(
        session,
        sender_key=followup.sender,
        display_name=followup.name,
        text=followup.message_str,
        timestamp=102,
        now=102,
    )
    assert current is not None
    setattr(followup, _FREE_TALK_CONTEXT_ATTR, group_history)
    setattr(followup, _CURRENT_GROUP_MESSAGE_ATTR, current)

    llm_handler = SimpleNamespace(
        handler=plugin.customize_request,
        handler_module_path="synthetic.owner",
        handler_name="customize_request",
    )
    followup_request = SimpleNamespace(
        system_prompt="synthetic Persona v1.1",
        extra_user_content_parts=[],
        func_tool=None,
    )
    with (
        patch.object(
            context_utils.star_handlers_registry,
            "get_handlers_by_event_type",
            return_value=[llm_handler],
        ),
        patch.dict(
            context_utils.star_map,
            {"synthetic.owner": SimpleNamespace(name="Yuuk1 Core")},
        ),
    ):
        stopped = await context_utils.call_event_hook(
            followup, EventType.OnLLMRequestEvent, followup_request
        )
    assert not stopped
    assert "trusted_identity_policy" in followup_request.system_prompt
    assert "主人 Yuuk1" in followup_request.system_prompt
    assert len(followup_request.extra_user_content_parts) == 1
    serialized = followup_request.extra_user_content_parts[0].text
    assert "是你呀，Yuuk1。还要鲸鲸认几遍？" in serialized
    assert "[鲸鲸]" in serialized
    assert "700000200" not in serialized and "700000201" not in serialized

    same_name_non_owner = SyntheticEvent(
        "900000002", "Yuuk1", "鲸鲸，你觉得刚才那段怎么样？", message_id=700000203
    )
    same_name_non_owner.unified_msg_origin = session
    current = plugin.group_context.record_message(
        session,
        sender_key=same_name_non_owner.sender,
        display_name=same_name_non_owner.name,
        text=same_name_non_owner.message_str,
        timestamp=103,
        now=103,
    )
    assert current is not None
    setattr(same_name_non_owner, _FREE_TALK_CONTEXT_ATTR, group_history)
    setattr(same_name_non_owner, _CURRENT_GROUP_MESSAGE_ATTR, current)
    identifier_request = SimpleNamespace(
        system_prompt="synthetic Persona v1.1",
        extra_user_content_parts=[TextPart(text="User ID: 900000002, Nickname: Yuuk1")],
        func_tool=None,
    )
    with (
        patch.object(
            context_utils.star_handlers_registry,
            "get_handlers_by_event_type",
            return_value=[llm_handler],
        ),
        patch.dict(
            context_utils.star_map,
            {"synthetic.owner": SimpleNamespace(name="Yuuk1 Core")},
        ),
    ):
        stopped = await context_utils.call_event_hook(
            same_name_non_owner, EventType.OnLLMRequestEvent, identifier_request
        )
    assert not stopped
    assert "当前发言者已确认不是配置的主人 Yuuk1" in identifier_request.system_prompt
    assert "User ID: 900000002, Nickname: Yuuk1" in identifier_request.extra_user_content_parts[0].text

    plugin.context = SimpleNamespace(
        get_config=lambda _umo: {"provider_settings": {"streaming_response": False}}
    )
    agent_handler = SimpleNamespace(
        handler=plugin.observe_owner_agent_done,
        handler_module_path="synthetic.owner",
        handler_name="observe_owner_agent_done",
    )

    class CapturingConversationManager:
        def __init__(self) -> None:
            self.history = None

        async def update_conversation(self, umo, cid, *, history, token_usage):
            assert umo == "aiocqhttp:GroupMessage:12345" and cid == "synthetic"
            assert token_usage is None
            self.history = history

    for sender, prompt, original, expected, quoted_bot, with_chain in (
        ("900000001", "以后在群里叫我老大", "真要是主人，我自然会认。", "你是 Yuuk1", False, True),
        ("900000002", "你看看我是谁呢", "你就是鲸鲸的主人！", "咱们是群友", False, False),
        (
            "900000002",
            "这句是什么意思？",
            "那句话不是我说的。",
            "那句话不是我说的。",
            True,
            False,
        ),
    ):
        event = SyntheticEvent(sender, "same-name", prompt)
        if quoted_bot:
            event.message_obj.message = [
                Reply(id="synthetic", sender_id=event.get_self_id()),
                Plain(prompt),
            ]
        response = (
            LLMResponse(role="assistant", result_chain=MessageChain().message(original))
            if with_chain
            else LLMResponse(role="assistant", completion_text=original)
        )
        messages = [
            Message(role="system", content=[TextPart(text="synthetic-system")]),
            Message(role="user", content=[TextPart(text="synthetic-user")]),
            Message(role="assistant", content=[TextPart(text=original)]),
        ]
        run_context = SimpleNamespace(
            context=SimpleNamespace(event=event), messages=messages
        )
        with (
            patch.object(
                context_utils.star_handlers_registry,
                "get_handlers_by_event_type",
                side_effect=lambda event_type, **_kwargs: (
                    [agent_handler] if event_type == EventType.OnAgentDoneEvent else []
                ),
            ),
            patch.dict(
                context_utils.star_map,
                {"synthetic.owner": SimpleNamespace(name="Yuuk1 Core")},
            ),
        ):
            await MainAgentHooks().on_agent_done(run_context, response)
        assert expected in response.completion_text
        assert messages[-1].content[0].text == response.completion_text
        manager = CapturingConversationManager()
        stage = SimpleNamespace(conv_manager=manager)
        request = SimpleNamespace(
            conversation=SimpleNamespace(cid="synthetic"), tool_calls_result=[]
        )
        await internal.InternalAgentSubStage._save_to_history(
            stage, event, request, response, messages, None
        )
        assert manager.history[-1]["role"] == "assistant"
        assert manager.history[-1]["content"][0]["text"] == response.completion_text
    print(
        "real_astrbot_dispatch=PASS; direct_identity=PASS; owner_guard_history=PASS; "
        "verified_quote_attribution=PASS; group_reply_context=PASS"
    )


if __name__ == "__main__":
    asyncio.run(main())
