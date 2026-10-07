from plugins.astrbot_plugin_yuuk1_core.multi_message import split_natural_messages


def test_short_text_stays_a_single_message() -> None:
    assert split_natural_messages("好呀", min_chars=20) == ["好呀"]


def test_natural_paragraphs_split_in_order_and_obey_max_parts() -> None:
    text = "干嘛，突然叫这么大声。\n我又没跑。\n找鲸鲸什么事？"
    assert split_natural_messages(text, max_parts=3) == [
        "干嘛，突然叫这么大声。",
        "我又没跑。",
        "找鲸鲸什么事？",
    ]

    capped = split_natural_messages(
        "第一句说完。\n第二句继续。\n第三句再说。\n第四句收尾。",
        max_parts=3,
    )
    assert len(capped) == 3
    assert capped[0] == "第一句说完。"
    assert capped[1] == "第二句继续。"
    assert "第三句再说。" in capped[2]
    assert "第四句收尾。" in capped[2]


def test_complete_sentences_split_but_markdown_and_urls_stay_whole() -> None:
    assert split_natural_messages(
        "这件事挺有意思。我们接着聊吧！", min_chars=10
    ) == ["这件事挺有意思。", "我们接着聊吧！"]
    code = "看这个示例：\n```python\nprint('hello')\n```\n很简单。"
    assert split_natural_messages(code, min_chars=5) == [code]
    linked = "可以看看 https://example.com/a。然后告诉我想法。"
    assert split_natural_messages(linked, min_chars=10) == [linked]


def test_disabled_or_one_part_limit_never_splits() -> None:
    text = "第一段自然结束。\n第二段自然结束。"
    assert split_natural_messages(text, enabled=False) == [text]
    assert split_natural_messages(text, max_parts=1) == [text]
