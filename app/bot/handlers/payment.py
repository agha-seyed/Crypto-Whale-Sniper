from aiogram import Router, F, Bot
from aiogram.types import Message, PreCheckoutQuery, LabeledPrice, CallbackQuery
from app.core.db import AsyncSessionLocal
from app.models.user import User
from sqlalchemy.future import select
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = Router()

VIP_PRICE_STARS = 500  # قیمت اکانت VIP به واحد استارز تلگرام (مثلاً 500 Stars)

async def send_vip_invoice(message: Message, bot: Bot):
    """ارسال فاکتور خرید اکانت VIP با ستاره‌های تلگرام"""
    prices = [LabeledPrice(label="اشتراک VIP یک ماهه", amount=VIP_PRICE_STARS)]
    
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="ارتقا به حساب VIP 🌟",
        description="با حساب VIP به قابلیت اسنایپ پیشرفته، مانیتورینگ نهنگ‌ها با سرعت بالا و معاملات بدون محدودیت دسترسی خواهید داشت.",
        payload="vip_1_month_payload",
        provider_token="",  # برای Telegram Stars این مقدار باید خالی باشد
        currency="XTR",     # کد ارز برای Telegram Stars
        prices=prices,
        start_parameter="buy_vip"
    )

@router.callback_query(F.data == "buy_vip")
async def process_buy_vip_button(callback: CallbackQuery, bot: Bot):
    """هندل کردن دکمه خرید VIP از منو"""
    await callback.answer()
    await send_vip_invoice(callback.message, bot)

@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    """
    بررسی نهایی قبل از کسر مبلغ از کاربر.
    در اینجا بررسی می‌کنیم که آیتم موجود باشد و خطایی وجود نداشته باشد.
    """
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """عملیات پس از پرداخت موفقیت آمیز استارز تلگرام"""
    user_id = message.from_user.id
    payment_info = message.successful_payment
    
    logger.info(f"💰 پرداخت موفق! کاربر {user_id} مبلغ {payment_info.total_amount} {payment_info.currency} پرداخت کرد.")

    try:
        # ارتقا سطح کاربری در دیتابیس
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.telegram_id == user_id))
            user = result.scalar_one_or_none()
            
            if user:
                user.is_vip = True
                # تاریخ انقضا 30 روز دیگر
                user.vip_until = datetime.utcnow() + timedelta(days=30)
                await session.commit()
                
                await message.answer("🎉 پرداخت شما با موفقیت انجام شد! حساب شما به VIP ارتقا یافت. 🌟")
            else:
                await message.answer("⚠️ پرداخت تایید شد اما اطلاعات کاربری شما در دیتابیس یافت نشد. به پشتیبانی پیام دهید.")
    except Exception as e:
        logger.error(f"خطا در بروزرسانی دیتابیس پس از پرداخت: {e}")
        await message.answer("⚠️ خطای سیستمی رخ داد. لطفاً به پشتیبانی پیام دهید.")
