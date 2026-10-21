"""Telegram sign-up for people who are not the owner.

Two proofs are tested separately: who a person is (a Mini App or Login Widget
signature) and what the panel may ask the backend to do on their behalf (a
short-lived actor assertion). An identity proof must never become an owner
session.
"""
import hashlib
import hmac
import importlib
import json
import time
import unittest
from urllib.parse import urlencode

from videl.utils.telegram_auth import (AuthError, public_user, sign_actor,
                                       verify_actor, verify_init_data,
                                       verify_login_widget)

TOKEN = "123456:test-token"
SECRET = "offline-test-secret"


def mini_app(user_id=7, *, token=TOKEN, auth_date=None, tamper=None):
    fields = {"auth_date": str(int(time.time()) if auth_date is None else auth_date),
              "query_id": "AAH-test",
              "user": json.dumps({"id": user_id, "first_name": "Ada",
                                  "last_name": "Lovelace", "username": "ada"})}
    if tamper:
        fields.update(tamper)
    check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), "sha256").digest()
    fields["hash"] = hmac.new(secret, check.encode(), "sha256").hexdigest()
    return urlencode(fields)


class InitDataTests(unittest.TestCase):
    def test_a_valid_launch_returns_the_user(self):
        user = verify_init_data(mini_app(), TOKEN)
        self.assertEqual(user["id"], 7)
        self.assertEqual(user["first_name"], "Ada")

    def test_a_tampered_field_is_refused(self):
        # Sign first, then change the value: the point is that the signature
        # covers what was actually sent.
        payload = mini_app().replace("query_id=AAH-test", "query_id=forged")
        with self.assertRaises(AuthError):
            verify_init_data(payload, TOKEN)

    def test_a_wrong_token_is_refused(self):
        with self.assertRaises(AuthError):
            verify_init_data(mini_app(), "999999:other")

    def test_an_old_launch_is_refused(self):
        with self.assertRaises(AuthError):
            verify_init_data(mini_app(auth_date=int(time.time()) - 90000), TOKEN)

    def test_a_duplicate_field_is_refused(self):
        payload = mini_app() + "&auth_date=1"
        with self.assertRaises(AuthError):
            verify_init_data(payload, TOKEN)

    def test_the_public_record_keeps_only_safe_fields(self):
        user = public_user({"id": 7, "first_name": "Ada", "last_name": "Lovelace",
                            "username": "ada", "photo_url": "https://example.com/a.jpg",
                            "phone_number": "never"})
        self.assertEqual(user["name"], "Ada Lovelace")
        self.assertNotIn("phone_number", user)
        self.assertEqual(user["id"], 7)


class LoginWidgetTests(unittest.TestCase):
    def payload(self, **extra):
        fields = {"id": "7", "first_name": "Ada", "auth_date": str(int(time.time()))}
        fields.update(extra)
        check = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
        secret = hashlib.sha256(TOKEN.encode()).digest()
        fields["hash"] = hmac.new(secret, check.encode(), "sha256").hexdigest()
        return fields

    def test_a_valid_widget_answer_returns_the_user(self):
        user = verify_login_widget(self.payload(), TOKEN)
        self.assertEqual(user["id"], "7")

    def test_a_tampered_widget_answer_is_refused(self):
        data = self.payload()
        data["first_name"] = "Grace"
        with self.assertRaises(AuthError):
            verify_login_widget(data, TOKEN)


class ActorAssertionTests(unittest.TestCase):
    def test_a_signed_actor_round_trips(self):
        assertion = sign_actor(501, SECRET)
        self.assertEqual(verify_actor(assertion["actor"], assertion["expires"],
                                      assertion["signature"], SECRET), 501)

    def test_an_expired_or_forged_assertion_is_refused(self):
        assertion = sign_actor(501, SECRET, expires=int(time.time()) - 120)
        with self.assertRaises(AuthError):
            verify_actor(assertion["actor"], assertion["expires"],
                         assertion["signature"], SECRET)
        good = sign_actor(501, SECRET)
        with self.assertRaises(AuthError):
            verify_actor(502, good["expires"], good["signature"], SECRET)
        with self.assertRaises(AuthError):
            verify_actor(good["actor"], good["expires"], "0" * 64, SECRET)


class IdentityRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = importlib.import_module("videl.__main__")
        cls.client = cls.api._flask.test_client()

    def test_the_route_accepts_a_verified_player(self):
        from unittest.mock import patch
        with patch.multiple(self.api.config, BOT_TOKEN=TOKEN, WEBAPP_SECRET=SECRET):
            response = self.client.post("/internal/identity",
                                        headers={"X-Videl-Internal": SECRET},
                                        json={"init_data": mini_app()})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["player"]["id"], 7)
            self.assertNotIn("phone_number", response.get_json()["player"])

    def test_a_forged_launch_is_a_401(self):
        from unittest.mock import patch
        with patch.multiple(self.api.config, BOT_TOKEN=TOKEN, WEBAPP_SECRET=SECRET):
            response = self.client.post("/internal/identity",
                                        headers={"X-Videl-Internal": SECRET},
                                        json={"init_data": mini_app().replace(
                                            "query_id=AAH-test", "query_id=forged")})
            self.assertEqual(response.status_code, 401)

    def test_the_identity_route_requires_the_internal_secret(self):
        response = self.client.post("/internal/identity", json={"init_data": mini_app()})
        self.assertEqual(response.status_code, 403)

    def test_identity_does_not_grant_the_owner_console(self):
        from unittest.mock import patch
        with patch.multiple(self.api.config, BOT_TOKEN=TOKEN, WEBAPP_SECRET=SECRET):
            response = self.client.post("/internal/auth",
                                        headers={"X-Videl-Internal": SECRET},
                                        json={"init_data": mini_app(user_id=7)})
            self.assertEqual(response.status_code, 403, "a verified player is still not the owner")


if __name__ == "__main__":
    unittest.main()
