import unittest

from videl.utils.telegram_features import capabilities, supports_parameter


class TelegramCapabilityTests(unittest.TestCase):
    class Current:
        def send_message(self, chat_id, text, *, ephemeral_message_parameters=None,
                         business_connection_id=None, direct_messages_topic_id=None):
            pass

        async def send_message_draft(self, chat_id, draft_id, text=""):
            pass

        async def send_rich_message(self, *args, **kwargs):
            pass

        async def get_chat_join_requests(self, *args, **kwargs):
            pass

        async def on_guest_message(self, *args, **kwargs):
            pass

        async def answer_guest_query(self, *args, **kwargs):
            pass

        async def on_business_connection(self, *args, **kwargs):
            pass

        async def get_business_connection(self, *args, **kwargs):
            pass

        async def get_owned_bots(self, *args, **kwargs):
            pass

        async def create_bot(self, *args, **kwargs):
            pass

        async def get_managed_bot_token(self, *args, **kwargs):
            pass

    def test_capabilities_are_reported_by_surface_and_auth_scope(self):
        found = capabilities(self.Current())
        self.assertTrue(found.ephemeral_replies)
        self.assertTrue(found.message_drafts)
        self.assertTrue(found.native_rich_messages_mtproto)
        self.assertTrue(found.business_connection_send)
        self.assertTrue(found.business_connection_updates)
        self.assertFalse(found.kurigram_business_profile_automation)
        self.assertTrue(found.direct_message_topics)
        self.assertTrue(found.guest_mode)
        self.assertTrue(found.join_request_queries_mtproto_user_only)
        self.assertFalse(found.join_request_queries_bot_session)
        self.assertTrue(found.managed_bot_methods_present)
        self.assertTrue(found.managed_bot_token_export_present)
        self.assertFalse(found.bot_to_bot_dispatch_enabled)

    def test_pinned_kurigram_2_2_26_has_the_expected_boundaries(self):
        from pyrogram import Client

        found = capabilities(Client)
        self.assertTrue(found.ephemeral_replies)
        self.assertTrue(found.message_drafts)
        self.assertTrue(found.native_rich_messages_mtproto)
        self.assertTrue(found.business_connection_send)
        self.assertTrue(found.business_connection_updates)
        self.assertFalse(found.kurigram_business_profile_automation)
        self.assertTrue(found.direct_message_topics)
        self.assertTrue(found.guest_mode)
        self.assertTrue(found.join_request_queries_mtproto_user_only)
        # Kurigram documents this query as user-session MTProto, not bot-session support.
        self.assertFalse(found.join_request_queries_bot_session)
        self.assertTrue(found.managed_bot_methods_present)
        self.assertTrue(found.managed_bot_token_export_present)
        self.assertFalse(found.bot_to_bot_dispatch_enabled)

    def test_old_or_ambiguous_clients_fail_closed(self):
        class Legacy:
            def send_message(self, chat_id, text):
                pass

        class Ambiguous:
            def send_message(self, **kwargs):
                pass

        self.assertFalse(capabilities(Legacy()).ephemeral_replies)
        self.assertFalse(capabilities(Legacy()).message_drafts)
        self.assertFalse(capabilities(Legacy()).native_rich_messages_mtproto)
        self.assertFalse(supports_parameter(Ambiguous(), "send_message", "ephemeral_message_parameters"))

    def test_richgram_html_is_not_mislabeled_as_native_rich_message_support(self):
        class RichgramOnly:
            async def send_message(self, chat_id, text, *, parse_mode=None):
                pass

        found = capabilities(RichgramOnly())
        self.assertFalse(found.native_rich_messages_mtproto)
        self.assertFalse(found.ephemeral_replies)
        self.assertFalse(found.join_request_queries_bot_session)
        self.assertFalse(found.kurigram_business_profile_automation)


if __name__ == "__main__":
    unittest.main()
