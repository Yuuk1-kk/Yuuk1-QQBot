from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from plugins.astrbot_plugin_yuuk1_core.reply_attribution import (
    ReplyOrigin,
    classify_get_msg_result,
    fetch_reply_origin,
    recognize_reply_sender_question,
    send_group_text_with_receipt,
)


@dataclass
class Plain:
    text: str


@dataclass
class At:
    qq: str


@dataclass
class Reply:
    id: str
    sender_id: str = ""


@dataclass
class Forward:
    content: str


def _payload(
    *,
    sender_id: str = "900000099",
    group_id: str = "900000123",
    message_id: str = "700000001",
    message_type: str = "group",
    message: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "status": "ok",
        "retcode": 0,
        "data": {
            "message_id": int(message_id),
            "message_type": message_type,
            "group_id": int(group_id),
            "self_id": 900000099,
            "sender": {"user_id": int(sender_id), "nickname": "鲸鲸"},
            "message": message or [{"type": "text", "data": {"text": "合成内容"}}],
        },
    }


@pytest.mark.parametrize(
    "text",
    [
        "那这是谁发的？",
        "这是谁发的",
        "那句话是谁发的。",
        "这句是谁说的？",
        "这句是你说的吗？",
        "这条是你发的吗",
        "这是不是你刚才说的？",
    ],
)
def test_recognizes_only_short_source_question_attached_to_one_reply(text: str) -> None:
    result = recognize_reply_sender_question(
        [Reply("700000001", "900000099"), Plain(text)],
        self_id="900000099",
    )
    assert result is not None
    assert result.message_id == "700000001"
    assert result.adapter_sender_id == "900000099"


@pytest.mark.parametrize(
    "components",
    [
        [Plain("那这是谁发的？")],
        [Reply("700000001"), Plain("这段历史讲了什么？")],
        [Reply("700000001"), Reply("700000002"), Plain("这是谁发的？")],
        [Reply("700000001"), At("900000002"), Plain("这是谁发的？")],
        [Reply("700000001"), Forward("nested"), Plain("这是谁发的？")],
    ],
)
def test_ambiguous_or_unstructured_requests_are_not_intercepted(
    components: list[object],
) -> None:
    assert (
        recognize_reply_sender_question(components, self_id="900000099") is None
    )


def test_reply_without_id_is_recognized_but_cannot_be_verified() -> None:
    result = recognize_reply_sender_question(
        [Reply("", ""), Plain("那这是谁发的？")],
        self_id="900000099",
    )
    assert result is not None
    assert result.message_id == ""


@pytest.mark.parametrize(
    ("payload", "sender", "expected"),
    [
        (_payload(), "900000099", ReplyOrigin.VERIFIED_BOT),
        (_payload(sender_id="900000002"), "900000002", ReplyOrigin.VERIFIED_MEMBER),
    ],
)
def test_get_msg_proves_bot_or_member_by_numeric_sender_id(
    payload: dict[str, object], sender: str, expected: ReplyOrigin
) -> None:
    result, reason = classify_get_msg_result(
        payload,
        requested_message_id="700000001",
        current_group_id="900000123",
        current_self_id="900000099",
        adapter_sender_id=sender,
    )
    assert result is expected
    assert reason == "verified"


@pytest.mark.parametrize(
    ("changes", "adapter_sender", "reason"),
    [
        ({"data": {"message_id": 700000002}}, "900000099", "message_id_mismatch"),
        ({"data": {"group_id": 900000124}}, "900000099", "group_mismatch_or_missing"),
        ({"data": {"group_id": None}}, "900000099", "group_mismatch_or_missing"),
        ({"data": {"message_type": "private"}}, "900000099", "not_group_message"),
        ({"data": {"sender": {"user_id": None}}}, "", "sender_missing"),
    ],
)
def test_inconsistent_platform_metadata_is_unknown(
    changes: dict[str, object], adapter_sender: str, reason: str
) -> None:
    payload = _payload()
    data = payload["data"]
    assert isinstance(data, dict)
    data.update(changes.get("data", {}))
    result, actual_reason = classify_get_msg_result(
        payload,
        requested_message_id="700000001",
        current_group_id="900000123",
        current_self_id="900000099",
        adapter_sender_id=adapter_sender,
    )
    assert result is ReplyOrigin.UNKNOWN
    assert actual_reason == reason


def test_missing_group_id_is_unknown_even_when_reply_sender_says_bot() -> None:
    payload = _payload()
    data = payload["data"]
    assert isinstance(data, dict)
    data.pop("group_id")
    result, reason = classify_get_msg_result(
        payload,
        requested_message_id="700000001",
        current_group_id="900000123",
        current_self_id="900000099",
        adapter_sender_id="900000099",
    )
    assert result is ReplyOrigin.UNKNOWN
    assert reason == "group_mismatch_or_missing"


@pytest.mark.parametrize(
    "message",
    [
        [{"type": "reply", "data": {"id": "700000000"}}],
        [{"type": "forward", "data": {"id": "forward-id"}}],
        [{"type": "node", "data": {"content": []}}],
    ],
)
def test_nested_quote_and_forwarded_messages_are_unknown(
    message: list[dict[str, object]],
) -> None:
    result, reason = classify_get_msg_result(
        _payload(message=message),
        requested_message_id="700000001",
        current_group_id="900000123",
        current_self_id="900000099",
        adapter_sender_id="900000099",
    )
    assert result is ReplyOrigin.UNKNOWN
    assert reason == "nested_or_forwarded_message"


def test_get_msg_failure_sender_disagreement_and_missing_fields_fail_closed() -> None:
    cases = [
        (None, "900000099", "invalid_response"),
        ({"status": "failed", "retcode": 1, "data": None}, "900000099", "action_failed"),
        (_payload(sender_id="900000002"), "900000099", "sender_mismatch"),
    ]
    for response, adapter_sender, expected_reason in cases:
        origin, reason = classify_get_msg_result(
            response,
            requested_message_id="700000001",
            current_group_id="900000123",
            current_self_id="900000099",
            adapter_sender_id=adapter_sender,
        )
        assert origin is ReplyOrigin.UNKNOWN
        assert reason == expected_reason


def test_fetch_uses_get_msg_without_logging_or_exposing_ids() -> None:
    async def scenario() -> None:
        calls: list[tuple[str, dict[str, object]]] = []

        async def call_action(action: str, **params: object) -> object:
            calls.append((action, params))
            return _payload()

        origin, reason = await fetch_reply_origin(
            call_action,
            message_id="700000001",
            current_group_id="900000123",
            current_self_id="900000099",
            adapter_sender_id="900000099",
        )
        assert origin is ReplyOrigin.VERIFIED_BOT
        assert reason == "verified"
        assert calls == [
            (
                "get_msg",
                {"message_id": 700000001, "self_id": 900000099},
            )
        ]

    asyncio.run(scenario())


def test_get_msg_exception_is_unknown_without_retry() -> None:
    async def scenario() -> None:
        calls = 0

        async def call_action(_action: str, **_params: object) -> object:
            nonlocal calls
            calls += 1
            raise TimeoutError("synthetic timeout")

        origin, reason = await fetch_reply_origin(
            call_action,
            message_id="700000001",
            current_group_id="900000123",
            current_self_id="900000099",
        )
        assert origin is ReplyOrigin.UNKNOWN
        assert reason == "lookup_failed"
        assert calls == 1

    asyncio.run(scenario())


def test_group_send_requires_onebot_receipt_and_returns_message_id() -> None:
    async def scenario() -> None:
        calls: list[tuple[str, dict[str, object]]] = []

        async def call_action(action: str, **params: object) -> object:
            calls.append((action, params))
            return {"status": "ok", "retcode": 0, "data": {"message_id": 700000003}}

        message_id = await send_group_text_with_receipt(
            call_action,
            group_id="900000123",
            self_id="900000099",
            text="合成回复",
        )
        assert message_id == "700000003"
        assert calls == [
            (
                "send_group_msg",
                {
                    "group_id": 900000123,
                    "self_id": 900000099,
                    "message": [{"type": "text", "data": {"text": "合成回复"}}],
                },
            )
        ]

    asyncio.run(scenario())


def test_group_send_without_receipt_is_not_recordable() -> None:
    async def scenario() -> None:
        calls = 0

        async def call_action(_action: str, **_params: object) -> object:
            nonlocal calls
            calls += 1
            return {"status": "ok", "retcode": 0, "data": {}}

        result = await send_group_text_with_receipt(
            call_action,
            group_id="900000123",
            self_id="900000099",
            text="合成回复",
        )
        assert result is None
        assert calls == 1

    asyncio.run(scenario())
