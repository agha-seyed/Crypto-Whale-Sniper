import asyncio
import logging
from app.core.db import init_models
from app.config import settings

# تنظیم لاگر برای دیدن خروجی‌ها
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info(f"Connecting to database at: {settings.DATABASE_URL}")
    try:
        # فراخوانی تابع ایجاد جداول
        await init_models()
        logger.info("✅ جداول دیتابیس با موفقیت ساخته شدند! هیچ باگی وجود ندارد.")
    except Exception as e:
        logger.error(f"❌ خطا در ساخت جداول دیتابیس: {e}")

if __name__ == "__main__":
    # اجرای تابع ناهمگام
    asyncio.run(main())
