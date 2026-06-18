import asyncio
import json
import logging
import websockets
from web3 import AsyncWeb3
from app.config import settings

logger = logging.getLogger(__name__)

w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(settings.EVM_RPC_URL))

# در حالت Mempool، ما دیگر به کل یک بلاک نگاه نمی‌کنیم بلکه فقط تراکنش را اسکن می‌کنیم
WHALE_THRESHOLD_ETH = 50

async def analyze_pending_transaction(tx_hash: str):
    """آنالیز سریع تراکنش تایید نشده (Pending) برای شکار نهنگ‌ها در ممپول"""
    try:
        # در ممپول ممکن است تراکنش در صدم ثانیه ناپدید شود یا در دسترس نباشد
        tx = await w3.eth.get_transaction(tx_hash)
        
        if tx:
            # بررسی اینکه آیا تراکنش دارای ارز اصلی شبکه (ETH/BNB/...) است
            value_in_eth = w3.from_wei(tx.get('value', 0), 'ether')
            
            if value_in_eth >= WHALE_THRESHOLD_ETH:
                from_addr = tx.get('from', 'Unknown')
                to_addr = tx.get('to', 'Contract Creation')
                
                logger.warning(f"⚡ [MEMPOOL ALERT] حرکت نهنگ قبل از ثبت در بلاک! ⚡")
                logger.info(f"مبلغ: {value_in_eth} ETH (Pending)")
                logger.info(f"از: {from_addr}")
                logger.info(f"به: {to_addr}")
                logger.info(f"هش تراکنش: {tx_hash}")
                
                # TODO: اگر این آدرس یک قرارداد Token بود، فورا دستور Snipe صادر شود!
                # await execute_dex_swap(...)
                
    except Exception as e:
        # خطای TransactionNotFound در ممپول بسیار طبیعی است زیرا تراکنش مدام در حال جابجایی است
        if "not found" not in str(e).lower():
            pass # برای جلوگیری از اسپم لاگ‌ها در ممپول، فقط خطاهای حیاتی را لاگ می‌کنیم

async def start_mempool_sniper():
    """اتصال به وب‌سوکت برای شنود تراکنش‌های تایید نشده شبکه (Mempool)"""
    wss_url = settings.EVM_WSS_URL
    logger.info(f"Connecting to Mempool WebSocket: {wss_url}")
    
    # استفاده از newPendingTransactions برای خواندن استخر ماینرها
    subscribe_msg = json.dumps({
        "id": 1,
        "jsonrpc": "2.0",
        "method": "eth_subscribe",
        "params": ["newPendingTransactions"]
    })

    while True:
        try:
            async with websockets.connect(wss_url) as ws:
                logger.info("✅ متصل شد! در حال اسکن استخر ماینرها (Mempool)...")
                await ws.send(subscribe_msg)
                response = await ws.recv()
                logger.info(f"پاسخ عضویت در ممپول: {response}")

                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    
                    if 'method' in data and data['method'] == 'eth_subscription':
                        # خروجی این سابسکریپشن فقط هش تراکنش است
                        tx_hash = data['params']['result']
                        
                        # آنالیز تراکنش به صورت موازی با سرعت نور
                        asyncio.create_task(analyze_pending_transaction(tx_hash))
                        
        except websockets.ConnectionClosed:
            logger.warning("ارتباط ممپول قطع شد! تلاش مجدد...")
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"خطا در ممپول اسنایپر: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_mempool_sniper())
