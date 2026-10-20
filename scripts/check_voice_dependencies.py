"""Offline Docker smoke check: exercise lazy PyTgCalls adapter imports.

Never starts a Telegram client or reads real credentials. Importing pytgcalls
alone does not detect adapter/client incompatibilities such as missing RPC errors.
"""
from importlib.metadata import PackageNotFoundError, version


def check_voice_dependencies():
    try:
        version("Pyrogram")
    except PackageNotFoundError:
        pass
    else:
        raise RuntimeError("Remove archived Pyrogram: it conflicts with Kurigram's pyrogram namespace")
    from pyrogram import Client
    from pyrogram.errors import GroupcallForbidden
    from pytgcalls import PyTgCalls

    client = Client("voice-dependency-check", api_id=1, api_hash="0" * 32, in_memory=True)
    calls = PyTgCalls(client)
    assert calls is not None and issubclass(GroupcallForbidden, Exception)
    print(f"Voice adapter constructor OK: Kurigram {version('kurigram')}, "
          f"PyTgCalls {version('py-tgcalls')}, NTgCalls {version('ntgcalls')}")


if __name__ == "__main__":
    check_voice_dependencies()
