from sqlalchemy import Column, BigInteger, String, Boolean, DateTime
from app.models.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    
    # اطلاعات مربوط به سیستم VIP
    is_vip = Column(Boolean, default=False)
    vip_until = Column(DateTime, nullable=True) # برای ذخیره تاریخ انقضا
    
    # اطلاعات کیف پول برای اسنایپر
    wallet_address = Column(String, nullable=True)
    encrypted_private_key = Column(String, nullable=True) # این فیلد حتما باید موقع ذخیره انکریپت شود
    
    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username={self.username}, vip={self.is_vip})>"
