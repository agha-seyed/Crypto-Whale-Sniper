from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.models.base import Base
# Import all models here so metadata is collected
from app.models.user import User
from app.models.trade import TradeLog
from app.models.settings import WalletSettings

# ساخت موتور دیتابیس ناهمگام
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False, # برای دیدن کوئری‌های SQL در محیط توسعه این را True کنید
    pool_pre_ping=True
)

# ساخت تولیدکننده سشن (نشست)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def init_models():
    """ایجاد جداول دیتابیس در صورت عدم وجود"""
    async with engine.begin() as conn:
        # در محیط پروداکشن معمولا از Alembic برای مایگریشن استفاده می‌شود
        # اما برای شروع کار، این متد جداول را در صورت نبودن می‌سازد.
        await conn.run_sync(Base.metadata.create_all)

async def get_db_session():
    """وابستگی (Dependency) برای دریافت سشن دیتابیس"""
    async with AsyncSessionLocal() as session:
        yield session
