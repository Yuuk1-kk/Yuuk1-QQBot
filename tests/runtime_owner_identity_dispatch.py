"""Run via stdin in an isolated AstrBot v4.28.2 Python process.

This uses AstrBot's real hook dispatcher and InternalAgentSubStage. It never
selects a Provider, contacts QQ, or mutates the running AstrBot process.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from astrbot.api.message_components import Plain
from astrbot.core.message.message_event_result import MessageChain, MessageEventResult
from astrbot.core.pipeline import context_utils
from astrbot.core.pipeline.process_stage.method.agent_sub_stages import internal
from astrbot.core.star.star_handler import EventType
from data.plugins.astrbot_plugin_yuuk1_core.main import Yuuk1CorePlugin


class SyntheticEvent:
    plugins_name = None
    unified_msg_origin = "aiocqhttp:GroupMessage:12345"

    def __init__(self, sender: str, name: str, text: str) -> None:
        self.message_str = text
        self.message_obj = SimpleNamespace(message=[Plain(text)])
        self.sender = sender
        self.name = name
        self.sent: list[MessageChain] = []
        self.stopped = False
        self._extras: dict[str, object] = {}

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
            yielded = [
                item
                async for item in internal.InternalAgentSubStage.process(
                    stage, event, ""
                )
            ]
            assert yielded == []
            assert event.is_stopped()
            assert len(event.sent) == 1
            reply = event.sent[0].chain[0].text
            assert ("不是鲸鲸的主人" not in reply) == expected_owner

        ordinary = SyntheticEvent("900000002", "Yuuk1", "鲸鲸，今天天气怎样？")
        stopped = await context_utils.call_event_hook(
            ordinary, EventType.OnWaitingLLMRequestEvent
        )
        assert not stopped and ordinary.sent == []
    print(
        "real_astrbot_dispatch=PASS; owner_and_non_owner=single_reply; ordinary_chat=continues"
    )


if __name__ == "__main__":
    asyncio.run(main())
