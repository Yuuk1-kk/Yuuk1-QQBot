from __future__ import annotations

import unittest

from plugins.astrbot_plugin_yuuk1_core.logic import (
    SlidingWindowRateLimiter,
    TwoLevelRateLimiter,
    classify_owner_identity,
    is_configured_admin,
    is_configured_owner,
    is_group_allowed,
    is_qq_context_allowed,
    normalize_config,
    normalize_ids,
    normalize_owner_id,
)


class NormalizeIdsTests(unittest.TestCase):
    def test_list_and_delimited_values_normalize_to_string_ids(self) -> None:
        self.assertEqual(
            normalize_ids([12345, " 67890 ", "", None]), {"12345", "67890"}
        )
        self.assertEqual(
            normalize_ids("12345, 67890;\n13579"), {"12345", "67890", "13579"}
        )

    def test_invalid_and_boolean_values_are_ignored(self) -> None:
        self.assertEqual(normalize_ids([True, {}, "abc", -1]), set())
        self.assertEqual(normalize_ids(None), set())


class AccessPolicyTests(unittest.TestCase):
    def test_empty_allowlist_fails_closed_for_groups_and_private_chat(self) -> None:
        self.assertFalse(is_group_allowed("12345", frozenset()))
        self.assertFalse(is_group_allowed("", frozenset()))
        self.assertFalse(is_qq_context_allowed("", frozenset(), False))

    def test_private_chat_requires_explicit_opt_in(self) -> None:
        self.assertTrue(is_qq_context_allowed("", frozenset(), True))
        self.assertFalse(is_qq_context_allowed("54321", frozenset({"12345"}), True))

    def test_allowlist_and_admin_checks_compare_normalized_ids(self) -> None:
        self.assertTrue(is_group_allowed("12345", frozenset({"12345"})))
        self.assertFalse(is_group_allowed("54321", frozenset({"12345"})))
        self.assertTrue(is_configured_admin(12345, frozenset({"12345"})))
        self.assertFalse(is_configured_admin("54321", frozenset({"12345"})))


class OwnerIdentityTests(unittest.TestCase):
    def test_owner_requires_trusted_qq_platform_and_matching_sender_id(self) -> None:
        self.assertTrue(is_configured_owner("aiocqhttp", "900000001", "900000001"))
        self.assertTrue(is_configured_owner("aiocqhttp", 900000001, "900000001"))
        self.assertFalse(is_configured_owner("aiocqhttp", "900000002", "900000001"))
        self.assertFalse(is_configured_owner("webchat", "900000001", "900000001"))

    def test_owner_config_is_a_decimal_string_and_empty_disables_identity(self) -> None:
        self.assertEqual(normalize_owner_id(" 900000001 "), "900000001")
        self.assertEqual(normalize_owner_id(900000001), "")
        self.assertEqual(normalize_owner_id(""), "")
        self.assertEqual(normalize_owner_id("name"), "")
        self.assertEqual(normalize_owner_id("９０００００００１"), "")
        self.assertFalse(is_configured_owner("aiocqhttp", "900000001", ""))

    def test_owner_identity_states_fail_closed(self) -> None:
        self.assertEqual(
            classify_owner_identity("aiocqhttp", "900000001", "900000001"),
            "verified_owner",
        )
        self.assertEqual(
            classify_owner_identity("aiocqhttp", "900000002", "900000001"),
            "verified_non_owner",
        )
        self.assertEqual(
            classify_owner_identity("aiocqhttp", "900000002", ""),
            "unconfigured",
        )
        self.assertEqual(
            classify_owner_identity("webchat", "900000001", "900000001"),
            "unavailable",
        )
        self.assertEqual(
            classify_owner_identity("aiocqhttp", "not-an-id", "900000001"),
            "unavailable",
        )

    def test_owner_binding_does_not_change_admin_authorization(self) -> None:
        settings = normalize_config(
            {"owner_qq_id": "900000001", "admin_users": ["900000002"]}
        )
        self.assertEqual(settings.owner_qq_id, "900000001")
        self.assertFalse(is_configured_admin("900000001", settings.admin_users))
        self.assertTrue(is_configured_admin("900000002", settings.admin_users))


class ConfigNormalizationTests(unittest.TestCase):
    def test_defaults_are_safe_and_usable(self) -> None:
        settings = normalize_config({})
        self.assertEqual(settings.bot_name, "鲸鲸")
        self.assertEqual(settings.allowed_groups, frozenset())
        self.assertFalse(settings.allow_private_chat)
        self.assertEqual(settings.owner_qq_id, "")
        self.assertTrue(settings.rate_limit_enabled)
        self.assertEqual(settings.rate_limit_window, 60)
        self.assertEqual(settings.rate_limit_requests, 30)
        self.assertEqual(settings.user_rate_limit_window, 60)
        self.assertEqual(settings.user_rate_limit_requests, 8)
        self.assertFalse(settings.free_talk_enabled)
        self.assertTrue(settings.engagement_enabled)
        self.assertEqual(settings.engagement_timeout_seconds, 300)
        self.assertEqual(settings.free_talk_min_interval_seconds, 0)
        self.assertEqual(settings.free_talk_decision_interval_seconds, 0)
        self.assertEqual(settings.free_talk_probability, 0.35)
        self.assertEqual(settings.free_talk_nickname_probability, 1.0)
        self.assertEqual(settings.free_talk_context_messages, 20)
        self.assertEqual(settings.free_talk_context_ttl_seconds, 900)
        self.assertEqual(settings.free_talk_min_recent_messages, 2)
        self.assertTrue(settings.multi_message_enabled)
        self.assertEqual(settings.multi_message_max_parts, 3)
        self.assertEqual(settings.multi_message_min_chars_to_split, 20)
        self.assertFalse(settings.stickers_enabled)
        self.assertEqual(settings.sticker_send_mode, "image")
        self.assertFalse(settings.sticker_diagnostics_enabled)
        self.assertFalse(settings.owner_identity_diagnostics_enabled)
        self.assertEqual(settings.sticker_repeat_window, 4)
        self.assertFalse(settings.idle_speak_enabled)
        self.assertEqual(settings.idle_threshold_seconds, 1800)
        self.assertEqual(settings.idle_check_interval_seconds, 300)
        self.assertEqual(settings.idle_probability, 0.1)
        self.assertEqual(settings.idle_min_interval_seconds, 21600)
        self.assertEqual(settings.idle_active_start_hour, 9)
        self.assertEqual(settings.idle_active_end_hour, 23)

    def test_new_feature_values_are_bounded_and_malformed_values_fall_back(self) -> None:
        settings = normalize_config(
            {
                "free_talk_enabled": "true",
                "engagement_enabled": "false",
                "engagement_timeout_seconds": 999_999,
                "free_talk_min_interval_seconds": 999_999,
                "free_talk_decision_interval_seconds": 0,
                "free_talk_probability": 4,
                "free_talk_nickname_probability": "nan",
                "multi_message_enabled": "false",
                "multi_message_max_parts": 4,
                "multi_message_min_chars_to_split": -1,
                "free_talk_context_messages": 0,
                "free_talk_context_ttl_seconds": -1,
                "free_talk_min_recent_messages": 1000,
                "stickers_enabled": "yes",
                "sticker_send_mode": "qq_custom",
                "sticker_diagnostics_enabled": "true",
                "owner_identity_diagnostics_enabled": "true",
                "sticker_repeat_window": 100,
                "idle_speak_enabled": True,
                "idle_threshold_seconds": 999_999,
                "idle_check_interval_seconds": "bad",
                "idle_probability": -1,
                "idle_min_interval_seconds": 0,
                "idle_active_start_hour": 24,
                "idle_active_end_hour": -2,
            }
        )
        self.assertTrue(settings.free_talk_enabled)
        self.assertFalse(settings.engagement_enabled)
        self.assertEqual(settings.engagement_timeout_seconds, 86_400)
        self.assertEqual(settings.free_talk_min_interval_seconds, 86_400)
        self.assertEqual(settings.free_talk_decision_interval_seconds, 0)
        self.assertEqual(settings.free_talk_probability, 1.0)
        self.assertEqual(settings.free_talk_nickname_probability, 1.0)
        self.assertEqual(settings.free_talk_context_messages, 1)
        self.assertEqual(settings.free_talk_context_ttl_seconds, 1)
        self.assertEqual(settings.free_talk_min_recent_messages, 100)
        self.assertFalse(settings.multi_message_enabled)
        self.assertEqual(settings.multi_message_max_parts, 3)
        self.assertEqual(settings.multi_message_min_chars_to_split, 1)
        self.assertTrue(settings.stickers_enabled)
        self.assertEqual(settings.sticker_send_mode, "qq_custom")
        self.assertTrue(settings.sticker_diagnostics_enabled)
        self.assertTrue(settings.owner_identity_diagnostics_enabled)
        self.assertEqual(settings.sticker_repeat_window, 5)
        self.assertTrue(settings.idle_speak_enabled)
        self.assertEqual(settings.idle_threshold_seconds, 604_800)
        self.assertEqual(settings.idle_check_interval_seconds, 300)
        self.assertEqual(settings.idle_probability, 0.0)
        self.assertEqual(settings.idle_min_interval_seconds, 1)
        self.assertEqual(settings.idle_active_start_hour, 23)
        self.assertEqual(settings.idle_active_end_hour, 0)

    def test_malformed_values_fall_back_and_limits_are_bounded(self) -> None:
        settings = normalize_config(
            {
                "bot_name": "  ",
                "allowed_groups": "12345,67890",
                "allow_private_chat": "invalid",
                "admin_users": [12345, True],
                "system_prompt": None,
                "rate_limit_enabled": "false",
                "rate_limit_window": -4,
                "rate_limit_requests": 99_999,
                "user_rate_limit_window": 0,
                "user_rate_limit_requests": 99_999,
            }
        )
        self.assertEqual(settings.bot_name, "鲸鲸")
        self.assertEqual(settings.allowed_groups, frozenset({"12345", "67890"}))
        self.assertFalse(settings.allow_private_chat)
        self.assertEqual(settings.admin_users, frozenset({"12345"}))
        self.assertEqual(settings.system_prompt, "")
        self.assertFalse(settings.rate_limit_enabled)
        self.assertEqual(settings.rate_limit_window, 1)
        self.assertEqual(settings.rate_limit_requests, 10_000)
        self.assertEqual(settings.user_rate_limit_window, 1)
        self.assertEqual(settings.user_rate_limit_requests, 10_000)

    def test_unsupported_or_non_string_sticker_send_mode_falls_back(self) -> None:
        self.assertEqual(
            normalize_config({"sticker_send_mode": "other"}).sticker_send_mode,
            "image",
        )
        self.assertEqual(
            normalize_config({"sticker_send_mode": ["qq_custom"]}).sticker_send_mode,
            "image",
        )

    def test_private_chat_can_be_enabled_explicitly(self) -> None:
        self.assertTrue(normalize_config({"allow_private_chat": True}).allow_private_chat)


class RateLimiterTests(unittest.TestCase):
    def test_enforces_a_sliding_window_and_expires_old_hits(self) -> None:
        limiter = SlidingWindowRateLimiter(window_seconds=10, request_limit=2)
        self.assertEqual(limiter.allow("group-a", now=0), (True, 0.0))
        self.assertEqual(limiter.allow("group-a", now=1), (True, 0.0))
        allowed, retry_after = limiter.allow("group-a", now=2)
        self.assertFalse(allowed)
        self.assertEqual(retry_after, 8.0)
        self.assertEqual(limiter.allow("group-a", now=10), (True, 0.0))

    def test_scopes_are_isolated_by_group(self) -> None:
        limiter = SlidingWindowRateLimiter(window_seconds=60, request_limit=1)
        self.assertEqual(limiter.allow("group-a", now=5), (True, 0.0))
        self.assertEqual(limiter.allow("group-b", now=5), (True, 0.0))

    def test_new_scopes_prune_expired_old_scopes(self) -> None:
        limiter = SlidingWindowRateLimiter(window_seconds=10, request_limit=1)
        for index in range(257):
            self.assertEqual(limiter.allow(f"user-{index}", now=0), (True, 0.0))
        self.assertEqual(limiter.allow("new-user", now=11), (True, 0.0))
        self.assertEqual(len(limiter._hits), 1)


class TwoLevelRateLimiterTests(unittest.TestCase):
    def test_same_user_burst_does_not_exhaust_group(self) -> None:
        limiter = TwoLevelRateLimiter(60, 2, 60, 5)
        self.assertEqual(limiter.allow("user-a", "group-a", now=0), (True, 0.0))
        self.assertEqual(limiter.allow("user-a", "group-a", now=1), (True, 0.0))
        self.assertEqual(limiter.allow("user-a", "group-a", now=2), (False, 58.0))
        self.assertEqual(limiter.allow("user-b", "group-a", now=2), (True, 0.0))
        self.assertEqual(limiter.allow("user-c", "group-a", now=2), (True, 0.0))
        self.assertEqual(limiter.allow("user-d", "group-a", now=2), (True, 0.0))

    def test_group_limit_rejects_different_users_without_charging_user(self) -> None:
        limiter = TwoLevelRateLimiter(60, 3, 60, 2)
        self.assertEqual(limiter.allow("user-a", "group-a", now=0), (True, 0.0))
        self.assertEqual(limiter.allow("user-b", "group-a", now=1), (True, 0.0))
        self.assertEqual(limiter.allow("user-c", "group-a", now=2), (False, 58.0))
        self.assertEqual(limiter.allow("user-c", "group-b", now=2), (True, 0.0))

    def test_user_limit_applies_across_groups_and_private_chat(self) -> None:
        limiter = TwoLevelRateLimiter(60, 2, 60, 10)
        self.assertEqual(limiter.allow("user-a", "group-a", now=0), (True, 0.0))
        self.assertEqual(limiter.allow("user-a", "", now=1), (True, 0.0))
        self.assertEqual(limiter.allow("user-a", "group-b", now=2), (False, 58.0))
        self.assertEqual(limiter.allow("user-b", "group-b", now=2), (True, 0.0))

    def test_user_and_group_windows_expire_independently(self) -> None:
        limiter = TwoLevelRateLimiter(10, 1, 20, 2)
        self.assertEqual(limiter.allow("user-a", "group-a", now=0), (True, 0.0))
        self.assertEqual(limiter.allow("user-a", "group-a", now=1), (False, 9.0))
        self.assertEqual(limiter.allow("user-b", "group-a", now=1), (True, 0.0))
        self.assertEqual(limiter.allow("user-c", "group-a", now=10), (False, 10.0))
        self.assertEqual(limiter.allow("user-a", "group-b", now=10), (True, 0.0))
        self.assertEqual(limiter.allow("user-c", "group-a", now=20), (True, 0.0))

    def test_default_security_limits_allow_five_normal_engaged_turns(self) -> None:
        settings = normalize_config({})
        limiter = TwoLevelRateLimiter(
            settings.user_rate_limit_window,
            settings.user_rate_limit_requests,
            settings.rate_limit_window,
            settings.rate_limit_requests,
        )
        self.assertEqual(settings.user_rate_limit_requests, 8)
        self.assertEqual(settings.rate_limit_requests, 30)
        for index in range(5):
            self.assertTrue(limiter.allow("user-a", "group-a", now=10 + index)[0])

    def test_missing_sender_fails_closed_without_charging_group(self) -> None:
        limiter = TwoLevelRateLimiter(60, 1, 60, 1)
        self.assertEqual(limiter.allow("", "group-a", now=0), (False, 0.0))
        self.assertEqual(limiter.allow("user-a", "group-a", now=0), (True, 0.0))


if __name__ == "__main__":
    unittest.main()
