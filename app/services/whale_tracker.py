import asyncio
import json
import logging
import websockets
from web3 import AsyncWeb3
from app.config import settings

logger = logging.getLogger(__name__)

# مقدار دهی اولیه Web3 با استفاده از AsyncWeb3 در نسخه 6 به بالا
w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(settings.EVM_RPC_URL))

# مقدار نهنگ به اتریوم (به عنوان مثال 50 اتریوم)
WHALE_THRESHOLD_ETH = 50

async def analyze_block(block_hash: str):
    """آنالیز تراکنش‌های یک بلاک برای پیدا کردن نهنگ‌ها"""
    for attempt in range(3):
        try:
            # گرفتن اطلاعات کامل بلاک به همراه تراکنش‌ها
            block = await w3.eth.get_block(block_hash, full_transactions=True)
            
            if block is None:
                raise Exception(f"Block {block_hash} not found")
            
            for tx in block.transactions:
                # مقدار تراکنش بر حسب Wei است، به Ether تبدیل می‌کنیم
                value_in_eth = w3.from_wei(tx.get('value', 0), 'ether')
                
                if value_in_eth >= WHALE_THRESHOLD_ETH:
                    # یک نهنگ پیدا شد!
                    from_addr = tx.get('from', 'Unknown')
                    to_addr = tx.get('to', 'Contract Creation')
                    tx_hash = tx['hash'].hex()
                    
                    logger.info(f"🚨 🐳 نهنگ پیدا شد! 🚨")
                    logger.info(f"مبلغ: {value_in_eth} ETH")
                    logger.info(f"از: {from_addr}")
                    logger.info(f"به: {to_addr}")
                    logger.info(f"هش تراکنش: {tx_hash}")
                    
                    # TODO: ارسال پیام از طریق ربات تلگرام
                    
            break # موفقیت آمیز بود، خروج از حلقه تلاش مجدد
        except Exception as e:
            if "not found" in str(e).lower() and attempt < 2:
                # نود HTTP هنوز سینک نشده است، صبر می‌کنیم
                await asyncio.sleep(2)
            else:
                logger.error(f"خطا در پردازش بلاک {block_hash}: {e}")
                break

async def start_whale_tracker():
    """اتصال به وب‌سوکت بلاکچین و شنود بلاک‌های جدید"""
    wss_url = settings.EVM_WSS_URL
    logger.info(f"Connecting to WebSocket: {wss_url}")
    
    subscribe_msg = json.dumps({
        "id": 1,
        "jsonrpc": "2.0",
        "method": "eth_subscribe",
        "params": ["newHeads"]
    })

    while True:
        try:
            async with websockets.connect(wss_url) as ws:
                logger.info("✅ متصل شد! ارسال درخواست شنود بلاک‌های جدید...")
                await ws.send(subscribe_msg)
                response = await ws.recv()
                logger.info(f"پاسخ عضویت: {response}")

                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    
                    if 'method' in data and data['method'] == 'eth_subscription':
                        block_hash = data['params']['result']['hash']
                        block_number = int(data['params']['result']['number'], 16)
                        logger.info(f"📦 بلاک جدید دریافت شد: {block_number}")
                        
                        # اجرای آنالیز در پس‌زمینه بدون بلاک کردن شنود وب‌سوکت
                        asyncio.create_task(analyze_block(block_hash))
                        
        except websockets.ConnectionClosed:
            logger.warning("ارتباط وب‌سوکت قطع شد! تلاش مجدد تا 5 ثانیه دیگر...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"خطای غیرمنتظره در ردیاب نهنگ: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_whale_tracker())
