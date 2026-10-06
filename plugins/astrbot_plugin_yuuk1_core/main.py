"""Yuuk1-QQBot project policy and commands for AstrBot."""

from __future__ import annotations

import os
import re
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star

from .logic import (
    CoreSettings,
    TwoLevelRateLimiter,
    is_configured_admin,
    is_qq_context_allowed,
    normalize_config,
)

PLUGIN_NAME = "astrbot_plugin_yuuk1_core"
PLUGIN_VERSION = "0.1.0"
# AstrBot v4.28.2 reads this event extra when converting provider exceptions to chat replies.
PERSONA_ERROR_EXTRA_KEY = "persona_custom_error_message"
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)((?:authorization|api[_-]?key|token)[\"']?\s*[:=]\s*)"
    r"(?:bearer\s+)?[\"']?[^\s,\"'}]+"
)
_ACTIVE_SETTINGS: CoreSettings | None = None


class Yuuk1CommandAllowlistFilter(filter.CustomFilter):
    """Apply the configured group gate before AstrBot expands an empty command group."""

    def filter(self, event: AstrMessageEvent, cfg: AstrBotConfig) -> bool:
        del cfg
        if event.get_platform_name() != "aiocqhttp":
            return True
        return _ACTIVE_SETTINGS is not None and is_qq_context_allowed(
            event.get_group_id(),
            _ACTIVE_SETTINGS.allowed_groups,
            _ACTIVE_SETTINGS.allow_private_chat,
        )


class Yuuk1CorePlugin(Star):
    """Small Star plugin that delegates chat, providers, and history to AstrBot."""

    def __init__(self, context: Context, config: AstrBotConfig) -> None:
        global _ACTIVE_SETTINGS
        super().__init__(context)
        self.settings: CoreSettings = normalize_config(config)
        _ACTIVE_SETTINGS = self.settings
        self.rate_limiter = TwoLevelRateLimiter(
            self.settings.user_rate_limit_window,
            self.settings.user_rate_limit_requests,
            self.settings.rate_limit_window,
            self.settings.rate_limit_requests,
        )

    async def initialize(self) -> None:
        """Expose an unambiguous post-initialization signal for runtime checks."""
        logger.info("Yuuk1 Core ready")

    @staticmethod
    def _is_qq(event: AstrMessageEvent) -> bool:
        return event.get_platform_name() == "aiocqhttp"

    def _is_allowed_context(self, event: AstrMessageEvent) -> bool:
        if not self._is_qq(event):
            return False
        return is_qq_context_allowed(
            event.get_group_id(),
            self.settings.allowed_groups,
            self.settings.allow_private_chat,
        )

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        return is_configured_admin(event.get_sender_id(), self.settings.admin_users)

    @filter.on_waiting_llm_request()
    async def guard_qq_request(self, event: AstrMessageEvent) -> None:
        """Apply QQ policy before provider selection and auxiliary model work."""
        if not self._is_qq(event):
            return

        group_id = event.get_group_id()
        try:
            if not self._is_allowed_context(event):
                logger.debug("Yuuk1 skipped LLM request from a disabled QQ context.")
                event.stop_event()
                return

            if self.settings.rate_limit_enabled:
                allowed, retry_after = self.rate_limiter.allow(
                    event.get_sender_id(), group_id
                )
                if not allowed:
                    event.stop_event()
                    logger.debug(
                        "Yuuk1 rate limit reached; retry_after=%.1fs.",
                        retry_after,
                    )
                    return

        except Exception:
            # A guard failure must never permit an unapproved QQ request.
            event.stop_event()
            if group_id or self.settings.allow_private_chat:
                try:
                    await event.send(
                        event.plain_result("Bot 暂时无法处理这条请求，请稍后再试。")
                    )
                except Exception:
                    logger.warning("Could not send the Yuuk1 policy error notice.")
            logger.error("Yuuk1 failed while checking a pending LLM request.")

    @filter.on_llm_request()
    async def customize_request(
        self,
        event: AstrMessageEvent,
        req: ProviderRequest,
    ) -> None:
        """Append stable persona context and mask provider exceptions for QQ users."""
        if not self._is_qq(event):
            return
        if not self._is_allowed_context(event):
            event.stop_event()
            return
        try:
            event.set_extra(
                PERSONA_ERROR_EXTRA_KEY,
                "AI 目前暂时无法响应，请稍后再试。",
            )
            persona_parts = [f"你的名字是 {self.settings.bot_name}。"]
            if self.settings.system_prompt:
                persona_parts.append(self.settings.system_prompt)
            addition = "\n\n".join(persona_parts)
            existing = (req.system_prompt or "").rstrip()
            req.system_prompt = f"{existing}\n\n{addition}" if existing else addition
        except Exception:
            event.stop_event()
            logger.error("Yuuk1 failed while preparing the request policy.")
            try:
                await event.send(
                    event.plain_result("Bot 暂时无法处理这条请求，请稍后再试。")
                )
            except Exception:
                logger.warning("Could not send the Yuuk1 request error notice.")

    @filter.custom_filter(Yuuk1CommandAllowlistFilter)
    @filter.command_group("yuuk1")
    def yuuk1(self) -> None:
        """Namespace for Yuuk1 project commands."""
        pass

    @yuuk1.command("help")
    async def help_command(self, event: AstrMessageEvent):
        """Show commands provided by Yuuk1 Core."""
        if not self._is_allowed_context(event):
            event.stop_event()
            return
        yield event.plain_result(
            "Yuuk1-QQBot 命令：\n"
            "/yuuk1 help - 显示帮助\n"
            "/yuuk1 status - 查看运行状态（管理员）\n"
            "/yuuk1 reset - 清理当前会话上下文（管理员）"
        )

    @yuuk1.command("status")
    async def status_command(self, event: AstrMessageEvent):
        """Show safe runtime information without probing or exposing provider secrets."""
        if not self._is_allowed_context(event):
            event.stop_event()
            return
        if not self._is_admin(event):
            yield event.plain_result("此命令仅限项目管理员使用。")
            return

        group_id = event.get_group_id() or "私聊"
        provider_line = "当前 Provider：不可用或未配置"
        try:
            provider = await self.context.get_using_provider_async(
                umo=event.unified_msg_origin
            )
            if provider is not None:
                provider_line = "当前 Provider：已加载"
        except Exception:
            logger.error("Yuuk1 could not inspect the active provider.")

        yield event.plain_result(
            "Yuuk1 Core 状态：\n"
            f"插件版本：{PLUGIN_VERSION}\n"
            f"当前群：{group_id}\n"
            f"{provider_line}（仅检查加载状态，未发起 API 请求）\n"
            "AstrBot Runtime：运行中\n"
            f"请求限流：{'启用' if self.settings.rate_limit_enabled else '关闭'}"
        )

    @yuuk1.command("reset")
    async def reset_command(self, event: AstrMessageEvent):
        """Delete the current AstrBot conversation through its manager API."""
        if not self._is_allowed_context(event):
            event.stop_event()
            return
        if not self._is_admin(event):
            yield event.plain_result("此命令仅限项目管理员使用。")
            return

        try:
            await self.context.conversation_manager.delete_conversation(
                event.unified_msg_origin
            )
        except Exception:
            logger.error("Yuuk1 could not reset the current conversation.")
            yield event.plain_result("清理会话失败，请稍后重试或查看 AstrBot 日志。")
            return
        yield event.plain_result("当前会话上下文已清理。")

    @filter.on_plugin_error()
    async def handle_plugin_error(
        self,
        event: AstrMessageEvent,
        plugin_name: str,
        handler_name: str,
        error: Any,
        traceback_text: str,
    ) -> None:
        """Keep plugin traces in AstrBot logs and return only a generic QQ message."""
        if plugin_name != PLUGIN_NAME:
            return
        safe_traceback = traceback_text or repr(error)
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if api_key:
            safe_traceback = safe_traceback.replace(api_key, "[REDACTED]")
        safe_traceback = _SECRET_ASSIGNMENT_RE.sub(r"\1[REDACTED]", safe_traceback)
        logger.error(
            "Yuuk1 plugin handler %s failed. Sanitized traceback follows:\n%s",
            handler_name,
            safe_traceback,
        )
        event.stop_event()
        if self._is_allowed_context(event):
            try:
                await event.send(
                    event.plain_result(
                        "Bot 暂时遇到问题，请稍后重试；管理员可查看 AstrBot 日志。"
                    )
                )
            except Exception:
                logger.warning("Could not send the Yuuk1 plugin-error notice.")

    async def terminate(self) -> None:
        """AstrBot calls this during plugin unload; discard in-memory rate buckets."""
        global _ACTIVE_SETTINGS
        if _ACTIVE_SETTINGS is self.settings:
            _ACTIVE_SETTINGS = None
        self.rate_limiter = TwoLevelRateLimiter(
            self.settings.user_rate_limit_window,
            self.settings.user_rate_limit_requests,
            self.settings.rate_limit_window,
            self.settings.rate_limit_requests,
        )
