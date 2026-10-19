from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from typing import Any, Callable, Dict
import logging, time
log=logging.getLogger("videl.mw")

class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[TelegramObject, Dict[str,Any]], Any],
                       event: TelegramObject, data: Dict[str,Any]) -> Any:
        start=time.time()
        try:
            res=await handler(event, data)
            return res
        except Exception as e:
            log.exception(f"Handler error: {e}")
            # try to answer user
            if isinstance(event, Message):
                try: await event.answer(f"⚠️ Error: <code>{e}</code>")
                except: pass
            raise
        finally:
            dur=(time.time()-start)*1000
            if dur>2000:
                log.warning(f"Slow handler {handler} {dur:.0f}ms")
