"""One task-reentrant lock and acknowledged session token per voice chat.

Reentrancy lets command transitions call the shared player without deadlocking.
Tokens fence stream-end work observed before a newer playback was acknowledged.
"""
import asyncio
from dataclasses import dataclass
import time
from weakref import WeakValueDictionary


class ChatLock:
    def __init__(self):
        self._lock=asyncio.Lock()
        self._owner=None
        self._depth=0

    async def __aenter__(self):
        task=asyncio.current_task()
        if self._owner is not task:
            await self._lock.acquire()
            self._owner=task
        self._depth+=1
        return self

    async def __aexit__(self,*exc):
        self._depth-=1
        if self._depth==0:
            self._owner=None
            self._lock.release()


_locks=WeakValueDictionary()


def lock(chat_id):
    item=_locks.get(chat_id)
    if item is None:
        item=ChatLock()
        _locks[chat_id]=item
    return item


@dataclass(eq=False)
class Session:
    song:dict
    started:float
    ending:bool=False


sessions={}


def acknowledged(chat_id,song):
    token=Session(song,time.monotonic())
    sessions[chat_id]=token
    return token


def forget(chat_id):
    sessions.pop(chat_id,None)
