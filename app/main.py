import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from app.config import settings
from app.bot.handlers import user_menu, payment

# تنظیم لاگر برای مشاهده خطاهای احتمالی
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ساخت نمونه ربات و دیسپچر
bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode="MarkdownV2"))
dp = Dispatcher()

# اضافه کردن هندلرها به دیسپچر
dp.include_router(user_menu.router)
dp.include_router(payment.router)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """مدیریت چرخه حیات برنامه FastAPI"""
    # زمان روشن شدن: تنظیم وب‌هوک تلگرام
    url = f"{settings.WEBHOOK_URL}{settings.WEBHOOK_PATH}"
    logger.info(f"Setting webhook to: {url}")
    # این خط در صورتی که توکن تنظیم نشده باشد ممکن است خطا دهد، بنابراین فعلا لاگ میکنیم
    if settings.BOT_TOKEN:
        await bot.set_webhook(
            url=url,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True
        )
    yield
    # زمان خاموش شدن: حذف وب‌هوک و بستن نشست‌ها
    if settings.BOT_TOKEN:
        logger.info("Removing webhook")
        await bot.delete_webhook()
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

@app.post(settings.WEBHOOK_PATH)
async def bot_webhook(update: dict):
    """دریافت آپدیت‌ها از تلگرام و ارسال به aiogram"""
    telegram_update = types.Update(**update)
    await dp.feed_update(bot=bot, update=telegram_update)
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Crypto Trading & Whale Tracker Bot is running!"}
