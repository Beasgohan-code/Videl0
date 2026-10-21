"""The signed actor assertion the panel attaches to public requests.

The panel already proves who it is with an HttpOnly cookie. This assertion
carries that proof one hop further, so a request that reaches the backend
without passing through the panel's own route cannot name an arbitrary user.
"""
from flask import request

from videl.utils.telegram_auth import AuthError, verify_actor


class ActorError(ValueError):
    def __init__(self, message, status=401):
        super().__init__(message)
        self.status = status


def require_actor(secret):
    try:
        return verify_actor(request.headers.get("X-Videl-Actor"),
                            request.headers.get("X-Videl-Actor-Exp"),
                            request.headers.get("X-Videl-Actor-Sig"), secret)
    except AuthError as error:
        raise ActorError(str(error)) from None
