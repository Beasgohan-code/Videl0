"""Internal group-manager API for group administrators.

Owner routes keep their own gate. Nothing here can reach a backup import, a
recording toggle, or another group: the scope is enforced in
``videl/utils/group_view.py`` and the actor is proved by a signed assertion.
"""
from datetime import datetime

from flask import jsonify, request

from videl.api.actor import ActorError, require_actor
from videl.utils import manager
from videl.utils.chat_admins import my_groups
from videl.utils.db import get_db
from videl.utils.group_view import ViewError


def _answer(error):
    payload = {"ok": False, "error": str(error)}
    if getattr(error, "conflict", False):
        payload["conflict"] = True
        payload["revision"] = getattr(error, "revision", None)
    return jsonify(payload), getattr(error, "status", 400)


def register_manager_routes(app, authorized, api, secret):
    def actor():
        return require_actor(secret() if callable(secret) else secret)

    @app.route("/internal/manager/groups", methods=["GET"])
    def manager_groups():
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            user = actor()
            refresh = request.args.get("refresh") in {"1", "true", "yes"}
            groups = my_groups(get_db(), api, user, refresh=refresh)
            return jsonify({"ok": True, "groups": groups,
                            "refreshed": refresh and not groups})
        except ActorError as error:
            return _answer(error)
        except Exception:
            return jsonify({"ok": False, "error": "Your groups could not be read"}), 503

    @app.route("/internal/manager/chat/<int(signed=True):chat_id>", methods=["GET", "POST"])
    def manager_chat(chat_id):
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            user = actor()
            if request.method == "GET":
                return jsonify(manager.describe(get_db(), api, chat_id, user))
            if request.content_length and request.content_length > 20000:
                raise ViewError("That request is too large", 413)
            body = request.get_json(silent=True)
            if not isinstance(body, dict) or not body.get("action"):
                raise ViewError("An action is required")
            return jsonify(manager.act(get_db(), api, chat_id, user, body))
        except (ViewError, ActorError) as error:
            return _answer(error)
        except Exception:
            return jsonify({"ok": False, "error": "That change was not confirmed; refresh before retrying"}), 503

    @app.route("/internal/manager/chat/<int(signed=True):chat_id>/audit", methods=["GET"])
    def manager_audit(chat_id):
        if not authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 403
        try:
            user = actor()
            before = request.args.get("before") or None
            limit = min(80, max(5, int(request.args.get("limit", "40"))))
            kind = request.args.get("kind") or None
            query = request.args.get("q", "")[:60]
            raw_actor = request.args.get("actor")
            actor_filter = int(raw_actor) if raw_actor and raw_actor.isdigit() and len(raw_actor) <= 20 else None
            raw_from = request.args.get("from")
            raw_through = request.args.get("through")
            date_from = datetime.fromisoformat(raw_from.replace("Z", "+00:00")) if raw_from else None
            date_through = datetime.fromisoformat(raw_through.replace("Z", "+00:00")) if raw_through else None
            return jsonify(manager.history(get_db(), api, chat_id, user,
                                           limit=limit, before=before, kind=kind,
                                           query=query, actor_filter=actor_filter,
                                           date_from=date_from, date_through=date_through))
        except (ViewError, ActorError) as error:
            return _answer(error)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Use a numeric limit"}), 400
        except Exception:
            return jsonify({"ok": False, "error": "History is unavailable"}), 503
