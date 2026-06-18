from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.user import User
from app.core.security import encrypt_private_key
from app.bot.handlers.user_menu import get_home_keyboard, is_user_vip

router = Router()

class WalletState(StatesGroup):
    waiting_for_private_key = State()

@router.callback_query(F.data == "menu_wallet")
async def process_wallet_menu(callback: CallbackQuery, state: FSMContext):
    if not await is_user_vip(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود! این بخش فقط برای کاربران VIP فعال است.", show_alert=True)
        return
        
    text = """
💼 *کیف پول من*

جهت اتصال کیف پول، لطفاً کلید خصوصی (Private Key) خود را ارسال کنید.
⚠️ *توجه:* ربات در همان لحظه پیام شما را پاک کرده و کلید شما را به صورت امن (Encrypted) ذخیره می‌کند.
"""
    await callback.message.edit_text(text, parse_mode="Markdown")
    await state.set_state(WalletState.waiting_for_private_key)

@router.message(WalletState.waiting_for_private_key)
async def process_private_key_input(message: Message, state: FSMContext):
    private_key = message.text.strip()
    
    # رمزنگاری کلید
    encrypted_key = encrypt_private_key(private_key)
    
    # ذخیره در دیتابیس
    async with AsyncSessionLocal() as session:
        query = select(User).where(User.telegram_id == message.from_user.id)
        result = await session.execute(query)
        user = result.scalars().first()
        
        if user:
            user.encrypted_private_key = encrypted_key
        else:
            user = User(telegram_id=message.from_user.id, encrypted_private_key=encrypted_key)
            session.add(user)
        
        await session.commit()
        
    # پاک کردن پیام حاوی کلید برای امنیت بیشتر
    try:
        await message.delete()
    except Exception:
        pass 
        
    await message.answer("✅ کلید خصوصی شما با موفقیت و به صورت امن ذخیره شد.", reply_markup=get_home_keyboard())
    await state.clear()
