import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message
from cachetools import TTLCache

# کش ساده برای ذخیره زمان آخرین پیام کاربر (نگهداری تا 2 ثانیه)
# در محیط‌های مقیاس‌پذیرتر بهتر است از Redis استفاده شود
user_cache = TTLCache(maxsize=10000, ttl=2.0)

class ThrottlingMiddleware(BaseMiddleware):
    """
    میدلور ضد اسپم (Rate Limiting) برای جلوگیری از ارسال پیام‌های پشت سر هم.
    کاربران در هر 2 ثانیه فقط می‌توانند یک پیام/درخواست ارسال کنند.
    """
    RATE_LIMIT = 2.0  # ثانیه

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # اگر آپدیت پیام نبود (مثلا CallbackQuery بود) فعلا اجازه عبور می‌دهیم
        # (می‌توان برای CallbackQuery هم اعمال کرد)
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id
        current_time = time.time()

        last_time = user_cache.get(user_id)
        if last_time is not None:
            if current_time - last_time < self.RATE_LIMIT:
                # پیام اسپم است، دراپ می‌شود (یا می‌توانیم خطا بدهیم)
                return
            
        # آپدیت زمان آخرین پیام
        user_cache[user_id] = current_time
        
        return await handler(event, data)
