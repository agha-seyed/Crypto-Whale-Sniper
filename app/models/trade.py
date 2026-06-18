from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.sql import func
from app.models.base import Base

class TradeLog(Base):
    __tablename__ = "trade_logs"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    tx_hash = Column(String, unique=True, index=True, nullable=False)
    network = Column(String, nullable=False)
    token_in = Column(String, nullable=False)
    token_out = Column(String, nullable=False)
    amount_in = Column(Float, nullable=False)
    amount_out = Column(Float, nullable=True)
    status = Column(String, nullable=False)  # pending, success, failed
    error_msg = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<TradeLog(tx_hash={self.tx_hash}, status={self.status})>"
