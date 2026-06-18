from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import textwrap

router = Router()

def get_home_keyboard() -> InlineKeyboardMarkup:
    """ساخت دکمه‌های شیشه‌ای منوی اصلی با ظاهر لوکس"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎯 اسنایپر / خرید سریع", callback_data="menu_sniper"),
                InlineKeyboardButton(text="🐳 ردیاب نهنگ‌ها", callback_data="menu_whale")
            ],
            [
                InlineKeyboardButton(text="👑 پنل VIP / ارتقا", callback_data="menu_vip"),
                InlineKeyboardButton(text="💼 کیف پول من", callback_data="menu_wallet")
            ],
            [
                InlineKeyboardButton(text="⚙️ تنظیمات و کارمزدها", callback_data="menu_settings"),
                InlineKeyboardButton(text="ℹ️ درباره ربات (About)", callback_data="menu_about")
            ]
        ]
    )

@router.message(CommandStart())
async def cmd_start(message: Message):
    """هندلر دستور /start"""
    welcome_text = textwrap.dedent("""\
        ⬛ ⬛ ⬛ ⬛ ⬛ ⬛ ⬛ ⬛ ⬛ ⬛
        
        👑 *به سیستم پیشرفته ترید و ردیاب نهنگ خوش آمدید* 👑
        
        🟢 **قدرتمند، سریع، امن**
        
        با استفاده از این ربات، شما می‌توانید:
        🔹 به صورت آنی تراکنش نهنگ‌ها را رصد کنید\\.
        🔹 توکن‌های جدید را قبل از دیگران خریداری کنید \\(Sniper\\)\\.
        🔹 با کمترین کارمزد و بالاترین سرعت معامله کنید\\.
        
        لطفاً از منوی زیر یک گزینه را انتخاب کنید:
        
        ⬛ ⬛ ⬛ ⬛ ⬛ ⬛ ⬛ ⬛ ⬛ ⬛
    """)
    
    await message.answer(
        text=welcome_text,
        reply_markup=get_home_keyboard()
    )

@router.callback_query(F.data == "menu_sniper")
async def process_sniper_menu(callback: CallbackQuery):
    """هندلر کلیک روی دکمه اسنایپر"""
    text = textwrap.dedent("""\
        🎯 *بخش اسنایپر و خرید سریع*
        
        لطفاً آدرس کانترکت توکن مورد نظر خود را ارسال کنید:
        `0x...`
        
        _کارمزد سیستم در این بخش 0\\.5% از حجم معامله می‌باشد\\._
    """)
    await callback.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu_home")]]
    ))

@router.callback_query(F.data == "menu_about")
async def process_about_menu(callback: CallbackQuery, bot):
    """هندلر کلیک روی دکمه درباره ما با ۳ زبان"""
    from aiogram.types import FSInputFile
    import os
    
    text = textwrap.dedent("""\
        🤖 **Crypto Whale Sniper & Tracker**
        > _Developed by: Wirangar Group (گروه ویرانگران)_
        
        🇮🇷 **فارسی:**
        این سیستم قدرتمند توسط **گروه برنامه‌نویسی، هوش مصنوعی و رباتیک ویرانگر** طراحی شده است. از امکانات آن می‌توان به اسنایپر چندشبکه‌ای (Multi-chain)، ردیابی پیشرفته در ممپول، و امنیت سطح نظامی (رمزنگاری کلیدهای خصوصی) اشاره کرد.
        
        🇬🇧 **English:**
        This powerful system is designed by the **Wirangar Group**. Features include multi-chain sniping, advanced mempool tracking, and military-grade private key encryption.
        
        🇮🇹 **Italiano:**
        Questo potente sistema è progettato dal **Gruppo Wirangar**. Le caratteristiche includono il cecchinaggio multi-catena, il tracciamento avanzato della mempool e la crittografia di livello militare.
    """)
    
    photo_path = "assets/logo.jpg"
    
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(photo=photo, caption=text, parse_mode="Markdown")
        await callback.answer()
    else:
        await callback.message.edit_text(text=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu_home")]]
        ))

@router.callback_query(F.data == "menu_vip")
async def process_vip_menu(callback: CallbackQuery):
    """هندلر کلیک روی دکمه پنل VIP"""
    text = textwrap.dedent("""\
        👑 *پنل کاربری VIP*
        
        با تهیه اشتراک VIP به امکانات زیر دسترسی خواهید داشت:
        ✅ فعال‌سازی ردیاب نهنگ با تفکیک توکن‌ها
        ✅ اسنایپ همزمان در چندین شبکه بلاکچین
        ✅ کاهش کارمزد ربات
        
        هزینه اشتراک 30 روزه: 500 ستاره تلگرام ⭐️
    """)
    await callback.message.edit_text(text=text, reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐️ خرید اشتراک (500 Stars)", callback_data="buy_vip")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="menu_home")]
        ]
    ))

@router.callback_query(F.data == "menu_home")
async def process_back_home(callback: CallbackQuery):
    """هندلر دکمه بازگشت به خانه"""
    welcome_text = textwrap.dedent("""\
        👑 *به سیستم پیشرفته ترید و ردیاب نهنگ خوش آمدید* 👑
        
        لطفاً از منوی زیر یک گزینه را انتخاب کنید:
    """)
    await callback.message.edit_text(
        text=welcome_text,
        reply_markup=get_home_keyboard()
    )
