"""Runtime capability checks for the pinned Kurigram Telegram client.

Kurigram includes Bot API methods, Bot API-shaped fields and MTProto-only
methods. Keep those surfaces distinct: in particular, Richgram HTML is not a
native Rich Message, and an MTProto user-only method is not bot-session support.
Unknown signatures fail closed. This module never starts a user session, exports
a managed-bot token, or enables an account-automation feature.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass


@dataclass(frozen=True)
class TelegramCapabilities:
    ephemeral_replies: bool
    message_drafts: bool
    native_rich_messages_mtproto: bool
    business_connection_send: bool
    business_connection_updates: bool
    kurigram_business_profile_automation: bool
    direct_message_topics: bool
    guest_mode: bool
    join_request_queries_mtproto_user_only: bool
    join_request_queries_bot_session: bool
    managed_bot_methods_present: bool
    managed_bot_token_export_present: bool
    bot_to_bot_dispatch_enabled: bool


def supports_parameter(client, method_name: str, parameter: str) -> bool:
    method = getattr(client, method_name, None)
    if not callable(method):
        return False
    try:
        return parameter in inspect.signature(method).parameters
    except (TypeError, ValueError):
        # Unknown signatures are not evidence of support.
        return False


def _method(client, name: str) -> bool:
    return callable(getattr(client, name, None))


def capabilities(client) -> TelegramCapabilities:
    """Report methods exposed by this client without claiming every auth scope.

    Kurigram's get_chat_join_requests wraps MTProto GetChatInviteImporters and is
    documented for user sessions. Videl's command bot is a bot-token session, so
    that method must not be treated as a bot-capable query. No bot-session query
    adapter is currently implemented.
    """
    return TelegramCapabilities(
        ephemeral_replies=supports_parameter(client, "send_message", "ephemeral_message_parameters"),
        message_drafts=(supports_parameter(client, "send_message_draft", "draft_id")
                        and supports_parameter(client, "send_message_draft", "text")),
        native_rich_messages_mtproto=_method(client, "send_rich_message"),
        business_connection_send=supports_parameter(client, "send_message", "business_connection_id"),
        business_connection_updates=_method(client, "on_business_connection") and _method(client, "get_business_connection"),
        # Editing the bot's own profile is not the same thing as editing a linked
        # Business account profile; Kurigram currently exposes no latter adapter.
        kurigram_business_profile_automation=False,
        direct_message_topics=supports_parameter(client, "send_message", "direct_messages_topic_id"),
        guest_mode=_method(client, "on_guest_message") and _method(client, "answer_guest_query"),
        join_request_queries_mtproto_user_only=_method(client, "get_chat_join_requests"),
        join_request_queries_bot_session=False,
        managed_bot_methods_present=_method(client, "get_owned_bots") and _method(client, "create_bot"),
        # Existence is reported for risk review only. Callers must never persist
        # the value; Videl has no managed-bot token export or storage path.
        managed_bot_token_export_present=_method(client, "get_managed_bot_token"),
        # Bot API 10.3 allows sendMessage to a bot username only when both
        # bots have enabled bot-to-bot communication. Kurigram's generic
        # send_message(chat_id: int | str, ...) shape cannot prove either
        # account setting or express consent. Videl therefore exposes no
        # dispatcher and must not infer permission from method presence.
        bot_to_bot_dispatch_enabled=False,
    )
