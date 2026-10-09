"""Pure, synthetic coverage of conservative Owner identity questions."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from plugins.astrbot_plugin_yuuk1_core.owner_identity_reply import (
    identity_reply,
    recognize_identity_question,
)


@dataclass
class Plain:
    text: str


@dataclass
class At:
    qq: str


@dataclass
class Reply:
    sender_id: str


@dataclass
class Forward:
    content: str


def question(text: str, *, group: bool = True, at: bool = False) -> str | None:
    parts = ([At("900000099")] if at else []) + [Plain(text)]
    return recognize_identity_question(parts, self_id="900000099", is_group=group)


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("鲸鲸，我是谁？", "who"),
        ("鲸鲸，我是誰？", "who"),
        ("鲸鲸，你认识我吗？", "know"),
        ("鲸鲸，你还认得我吗？", "know"),
        ("鲸鲸，我是你的主人吗？", "owner"),
        ("鲸鲸，我是不是你的主人？", "owner"),
        ("鲸鲸，我和你是什么关系？", "relationship"),
        ("鲸鲸，我是谁？和你是什么关系？", "who_relationship"),
    ],
)
def test_direct_whitelist(text: str, kind: str) -> None:
    assert question(text) == kind


def test_structured_bot_mention_and_private_message() -> None:
    assert question("我是谁？", at=True) == "who"
    assert question("我是你的主人吗？", at=True) == "owner"
    assert question("我是谁？", group=False) == "who"
    assert question("我是谁？") is None


@pytest.mark.parametrize(
    "text",
    [
        "你是谁？",
        "他是不是你的主人？",
        "我是你的主人",
        "Yuuk1 是你的主人吗？",
        "鲸鲸，我是谁？顺便讲讲昨天的事。",
        "鲸鲸，我是谁？\n别人也这样问过",
        "鲸鲸，“我是谁？”这句话什么意思？",
        "鲸鲸，`我是谁？`",
        "鲸鲸：有人问我是谁？",
        "鲸鲸，我是谁？" + "闲聊" * 40,
    ],
)
def test_discussion_quotes_and_long_text_do_not_match(text: str) -> None:
    assert question(text) is None


def test_reply_forward_other_member_and_ambiguous_mentions_do_not_match() -> None:
    bot_id = "900000099"
    cases = [
        [Reply("900000001"), Plain("鲸鲸，我是谁？")],
        [Forward("我是谁？"), Plain("鲸鲸，我是谁？")],
        [At("900000002"), Plain("我是谁？")],
        [Plain("别人说"), At(bot_id), Plain("我是谁？")],
        [At(bot_id), At(bot_id), Plain("我是谁？")],
        [Plain("我是谁？"), At(bot_id)],
    ]
    for components in cases:
        assert (
            recognize_identity_question(components, self_id=bot_id, is_group=True)
            is None
        )


def test_owner_fact_ignores_current_display_name() -> None:
    for display_name in ("奶龙鉴赏家", "Yuuk1", "任何新名称"):
        assert "Yuuk1" in identity_reply("who", "verified_owner", display_name)
        relation = identity_reply("who_relationship", "verified_owner", display_name)
        assert "主人" in relation and "项目维护者" in relation
        assert display_name not in relation or display_name == "Yuuk1"


def test_non_owner_can_be_called_yuuk1_without_becoming_owner() -> None:
    assert "Yuuk1" in identity_reply("who", "verified_non_owner", "Yuuk1")
    for display_name in ("Yuuk1", "奶龙鉴赏家"):
        denial = identity_reply("owner", "verified_non_owner", display_name)
        assert "不是鲸鲸的主人" in denial
        assert display_name not in denial


def test_unavailable_and_unconfigured_never_claim_owner() -> None:
    for classification in ("unavailable", "unconfigured"):
        assert "不能确定" in identity_reply("owner", classification, "Yuuk1")
        assert "Yuuk1" in identity_reply("who", classification, "Yuuk1")
        assert "不知道" in identity_reply("who", classification, "")
