from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.user import User
from app.models.settings import WalletSettings
from app.bot.handlers.user_menu import is_user_vip

router = Router()

class SettingsState(StatesGroup):
    waiting_for_auto_snipe_token = State()
    waiting_for_buy_amount = State()
    waiting_for_slippage = State()

def get_settings_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 تنظیم توکن Auto-Snipe", callback_data="set_auto_snipe")],
            [InlineKeyboardButton(text="💰 تنظیم حجم خرید", callback_data="set_buy_amount")],
            [InlineKeyboardButton(text="⚙️ تنظیم Slippage", callback_data="set_slippage")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu_home")]
        ]
    )

@router.callback_query(F.data == "menu_settings")
async def show_settings(callback: CallbackQuery):
    if not await is_user_vip(callback.from_user.id):
        await callback.answer("❌ دسترسی محدود! این بخش فقط برای کاربران VIP فعال است.", show_alert=True)
        return
        
    async with AsyncSessionLocal() as session:
        query = select(User).where(User.telegram_id == callback.from_user.id)
        user = (await session.execute(query)).scalars().first()
        if not user:
            user = User(telegram_id=callback.from_user.id)
            session.add(user)
            await session.flush()
            
        s_query = select(WalletSettings).where(WalletSettings.user_id == user.id)
        w_settings = (await session.execute(s_query)).scalars().first()
        if not w_settings:
            w_settings = WalletSettings(user_id=user.id)
            session.add(w_settings)
            await session.commit()

        text = f"""
⚙️ *تنظیمات اسنایپر*

آدرس توکن Auto-Snipe: `{w_settings.auto_snipe or 'تنظیم نشده'}`
حجم خرید (ETH/BNB): `{w_settings.buy_amount_eth}`
میزان Slippage: `{w_settings.default_slippage}%`

یکی از موارد زیر را برای تغییر انتخاب کنید:
"""
        await callback.message.edit_text(text, reply_markup=get_settings_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "set_auto_snipe")
async def ask_auto_snipe(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🎯 لطفاً آدرس کانترکت توکن هدف برای خرید خودکار (Auto-Snipe) را ارسال کنید:")
    await state.set_state(SettingsState.waiting_for_auto_snipe_token)
    await callback.answer()

@router.message(SettingsState.waiting_for_auto_snipe_token)
async def process_auto_snipe(message: Message, state: FSMContext):
    token = message.text.strip()
    async with AsyncSessionLocal() as session:
        query = select(User).where(User.telegram_id == message.from_user.id)
        user = (await session.execute(query)).scalars().first()
        if not user:
            user = User(telegram_id=message.from_user.id)
            session.add(user)
            await session.flush()
            
        s_query = select(WalletSettings).where(WalletSettings.user_id == user.id)
        w_settings = (await session.execute(s_query)).scalars().first()
        if not w_settings:
            w_settings = WalletSettings(user_id=user.id)
            session.add(w_settings)
            
        w_settings.auto_snipe = token
        await session.commit()
        
    await message.answer("✅ آدرس توکن Auto-Snipe با موفقیت تنظیم شد.")
    await state.clear()

@router.callback_query(F.data == "set_buy_amount")
async def ask_buy_amount(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("💰 لطفاً حجم خرید (به صورت اعشاری مثلا 0.01) را ارسال کنید:")
    await state.set_state(SettingsState.waiting_for_buy_amount)
    await callback.answer()

@router.message(SettingsState.waiting_for_buy_amount)
async def process_buy_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        async with AsyncSessionLocal() as session:
            query = select(User).where(User.telegram_id == message.from_user.id)
            user = (await session.execute(query)).scalars().first()
            if not user:
                user = User(telegram_id=message.from_user.id)
                session.add(user)
                await session.flush()
                
            s_query = select(WalletSettings).where(WalletSettings.user_id == user.id)
            w_settings = (await session.execute(s_query)).scalars().first()
            if not w_settings:
                w_settings = WalletSettings(user_id=user.id)
                session.add(w_settings)
                
            w_settings.buy_amount_eth = amount
            await session.commit()
            
        await message.answer("✅ حجم خرید با موفقیت تنظیم شد.")
    except ValueError:
        await message.answer("❌ مقدار نامعتبر است. لطفاً یک عدد ارسال کنید.")
    finally:
        await state.clear()

@router.callback_query(F.data == "set_slippage")
async def ask_slippage(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("⚙️ لطفاً درصد اسلیپیج (مثلا 5.0) را ارسال کنید:")
    await state.set_state(SettingsState.waiting_for_slippage)
    await callback.answer()

@router.message(SettingsState.waiting_for_slippage)
async def process_slippage(message: Message, state: FSMContext):
    try:
        slippage = float(message.text.strip())
        async with AsyncSessionLocal() as session:
            query = select(User).where(User.telegram_id == message.from_user.id)
            user = (await session.execute(query)).scalars().first()
            if not user:
                user = User(telegram_id=message.from_user.id)
                session.add(user)
                await session.flush()
                
            s_query = select(WalletSettings).where(WalletSettings.user_id == user.id)
            w_settings = (await session.execute(s_query)).scalars().first()
            if not w_settings:
                w_settings = WalletSettings(user_id=user.id)
                session.add(w_settings)
                
            w_settings.default_slippage = slippage
            await session.commit()
            
        await message.answer("✅ اسلیپیج با موفقیت تنظیم شد.")
    except ValueError:
        await message.answer("❌ مقدار نامعتبر است. لطفاً یک عدد ارسال کنید.")
    finally:
        await state.clear()
