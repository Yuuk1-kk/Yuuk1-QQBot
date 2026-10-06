from __future__ import annotations

import unittest

from plugins.astrbot_plugin_yuuk1_core.logic import (
    SlidingWindowRateLimiter,
    is_configured_admin,
    is_group_allowed,
    normalize_config,
    normalize_ids,
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
    def test_empty_allowlist_fails_closed_for_groups_but_not_private_chat(self) -> None:
        self.assertFalse(is_group_allowed("12345", frozenset()))
        self.assertTrue(is_group_allowed("", frozenset()))

    def test_allowlist_and_admin_checks_compare_normalized_ids(self) -> None:
        self.assertTrue(is_group_allowed("12345", frozenset({"12345"})))
        self.assertFalse(is_group_allowed("54321", frozenset({"12345"})))
        self.assertTrue(is_configured_admin(12345, frozenset({"12345"})))
        self.assertFalse(is_configured_admin("54321", frozenset({"12345"})))


class ConfigNormalizationTests(unittest.TestCase):
    def test_defaults_are_safe_and_usable(self) -> None:
        settings = normalize_config({})
        self.assertEqual(settings.bot_name, "Yuuk1")
        self.assertEqual(settings.allowed_groups, frozenset())
        self.assertTrue(settings.rate_limit_enabled)
        self.assertEqual(settings.rate_limit_window, 60)
        self.assertEqual(settings.rate_limit_requests, 5)

    def test_malformed_values_fall_back_and_limits_are_bounded(self) -> None:
        settings = normalize_config(
            {
                "bot_name": "  ",
                "allowed_groups": "12345,67890",
                "admin_users": [12345, True],
                "system_prompt": None,
                "rate_limit_enabled": "false",
                "rate_limit_window": -4,
                "rate_limit_requests": 99_999,
            }
        )
        self.assertEqual(settings.bot_name, "Yuuk1")
        self.assertEqual(settings.allowed_groups, frozenset({"12345", "67890"}))
        self.assertEqual(settings.admin_users, frozenset({"12345"}))
        self.assertEqual(settings.system_prompt, "")
        self.assertFalse(settings.rate_limit_enabled)
        self.assertEqual(settings.rate_limit_window, 1)
        self.assertEqual(settings.rate_limit_requests, 10_000)


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


if __name__ == "__main__":
    unittest.main()
