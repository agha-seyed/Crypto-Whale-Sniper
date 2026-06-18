from sqlalchemy import Column, BigInteger, String, Float, ForeignKey
from app.models.base import Base

class WalletSettings(Base):
    __tablename__ = "wallet_settings"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), unique=True, nullable=False)
    
    # تنظیمات اسنایپر کاربر
    default_slippage = Column(Float, default=5.0)
    auto_snipe = Column(String, nullable=True) # برای مثال آدرس توکن برای خرید خودکار
    buy_amount_eth = Column(Float, default=0.01) # مقدار پیش‌فرض برای خرید به اتریوم
    
    def __repr__(self):
        return f"<WalletSettings(user_id={self.user_id}, slippage={self.default_slippage})>"
