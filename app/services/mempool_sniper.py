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
ERC20_TRANSFER_SIGNATURE = "0xa9059cbb"
WORKER_COUNT = 5

async def analyze_pending_transaction(tx_hash: str):
    """آنالیز سریع تراکنش تایید نشده (Pending) برای شکار نهنگ‌ها در ممپول"""
    try:
        # در ممپول ممکن است تراکنش در صدم ثانیه ناپدید شود یا در دسترس نباشد
        tx = await w3.eth.get_transaction(tx_hash)
        
        if tx:
            from_addr = tx.get('from', 'Unknown')
            to_addr = tx.get('to', 'Contract Creation')
            tx_input = tx.get('input', '0x')
            if hasattr(tx_input, 'hex'):
                tx_input = '0x' + tx_input.hex()
            elif isinstance(tx_input, bytes):
                tx_input = '0x' + tx_input.hex()
            
            # بررسی اینکه آیا تراکنش دارای ارز اصلی شبکه (ETH/BNB/...) است
            value_in_eth = w3.from_wei(tx.get('value', 0), 'ether')
            
            if value_in_eth >= WHALE_THRESHOLD_ETH:
                logger.warning(f"⚡ [MEMPOOL ALERT] حرکت نهنگ (ارز اصلی) قبل از ثبت در بلاک! ⚡")
                logger.info(f"مبلغ: {value_in_eth} ETH/BNB (Pending)")
                logger.info(f"از: {from_addr}")
                logger.info(f"به: {to_addr}")
                logger.info(f"هش تراکنش: {tx_hash}")
                
            # بررسی انتقال توکن‌های ERC20
            elif str(tx_input).startswith(ERC20_TRANSFER_SIGNATURE) and len(str(tx_input)) >= 138:
                # استخراج آدرس گیرنده و مقدار از دیتا
                recipient = "0x" + str(tx_input)[34:74]
                amount_hex = str(tx_input)[74:138]
                amount_int = int(amount_hex, 16)
                
                # برای سادگی، فعلا مقدار خام رو لاگ می‌کنیم. 
                # (برای محاسبه دقیق به دسیمال کانترکت نیاز داریم اما برای ممپول با سرعت بالا نمی‌صرفه)
                if amount_int > 0:
                    logger.warning(f"⚡ [MEMPOOL ALERT] حرکت نهنگ (ERC20 Token) قبل از ثبت در بلاک! ⚡")
                    logger.info(f"مقدار خام توکن: {amount_int} (Pending)")
                    logger.info(f"کانترکت توکن: {to_addr}")
                    logger.info(f"فرستنده: {from_addr} -> گیرنده: {recipient}")
                    logger.info(f"هش تراکنش: {tx_hash}")

                # TODO: اگر این آدرس یک قرارداد Token بود، فورا دستور Snipe صادر شود!
                # await execute_dex_swap(...)
                
    except Exception as e:
        # خطای TransactionNotFound در ممپول بسیار طبیعی است زیرا تراکنش مدام در حال جابجایی است
        if "not found" not in str(e).lower():
            pass # برای جلوگیری از اسپم لاگ‌ها در ممپول، فقط خطاهای حیاتی را لاگ می‌کنیم

async def worker(queue: asyncio.Queue):
    """ورکر برای پردازش تراکنش‌های ممپول از داخل صف"""
    while True:
        tx_hash = await queue.get()
        try:
            await analyze_pending_transaction(tx_hash)
        except Exception as e:
            logger.error(f"خطا در ورکر ممپول: {e}")
        finally:
            queue.task_done()

async def start_mempool_sniper():
    """اتصال به وب‌سوکت برای شنود تراکنش‌های تایید نشده شبکه (Mempool)"""
    wss_url = settings.EVM_WSS_URL
    logger.info(f"Connecting to Mempool WebSocket: {wss_url}")
    
    # ساخت صف برای تراکنش‌ها جهت جلوگیری از نشت حافظه (OOM)
    queue = asyncio.Queue(maxsize=2000)
    
    # راه‌اندازی ورکرها
    workers = []
    for _ in range(WORKER_COUNT):
        task = asyncio.create_task(worker(queue))
        workers.append(task)
        
    # استفاده از newPendingTransactions برای خواندن استخر ماینرها
    subscribe_msg = json.dumps({
        "id": 1,
        "jsonrpc": "2.0",
        "method": "eth_subscribe",
        "params": ["newPendingTransactions"]
    })

    try:
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
                            tx_hash = data['params']['result']
                            
                            # اضافه کردن به صف به جای ساخت Task جدید برای هر تراکنش
                            if not queue.full():
                                queue.put_nowait(tx_hash)
                            else:
                                logger.warning("Mempool queue is full! Dropping transaction.")
                            
            except websockets.ConnectionClosed:
                logger.warning("ارتباط ممپول قطع شد! تلاش مجدد...")
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"خطا در ممپول اسنایپر: {e}")
                await asyncio.sleep(2)
    finally:
        # متوقف کردن ورکرها در صورت خروج
        for task in workers:
            task.cancel()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_mempool_sniper())
