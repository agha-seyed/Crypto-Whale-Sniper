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
ERC20_TRANSFER_SIGNATURE = "0xa9059cbb"
WORKER_COUNT = 3

async def analyze_block(block_hash: str):
    """آنالیز تراکنش‌های یک بلاک برای پیدا کردن نهنگ‌ها"""
    for attempt in range(3):
        try:
            # گرفتن اطلاعات کامل بلاک به همراه تراکنش‌ها
            block = await w3.eth.get_block(block_hash, full_transactions=True)
            
            if block is None:
                raise Exception(f"Block {block_hash} not found")
            
            for tx in block.transactions:
                from_addr = tx.get('from', 'Unknown')
                to_addr = tx.get('to', 'Contract Creation')
                
                # بررسی هش (چون گاهی به صورت HexBytes برمی‌گردد)
                tx_hash = tx.get('hash')
                if hasattr(tx_hash, 'hex'):
                    tx_hash_str = tx_hash.hex()
                elif isinstance(tx_hash, bytes):
                    tx_hash_str = tx_hash.hex()
                else:
                    tx_hash_str = str(tx_hash)

                tx_input = tx.get('input', '0x')
                if hasattr(tx_input, 'hex'):
                    tx_input = '0x' + tx_input.hex()
                elif isinstance(tx_input, bytes):
                    tx_input = '0x' + tx_input.hex()

                # مقدار تراکنش بر حسب Wei است، به Ether تبدیل می‌کنیم
                value_in_eth = w3.from_wei(tx.get('value', 0), 'ether')
                
                if value_in_eth >= WHALE_THRESHOLD_ETH:
                    # یک نهنگ پیدا شد!
                    logger.info(f"🚨 🐳 نهنگ (ارز اصلی) پیدا شد! 🚨")
                    logger.info(f"مبلغ: {value_in_eth} ETH/BNB")
                    logger.info(f"از: {from_addr}")
                    logger.info(f"به: {to_addr}")
                    logger.info(f"هش تراکنش: {tx_hash_str}")
                    
                    # TODO: ارسال پیام از طریق ربات تلگرام
                
                # بررسی انتقال توکن‌های ERC20
                elif str(tx_input).startswith(ERC20_TRANSFER_SIGNATURE) and len(str(tx_input)) >= 138:
                    # استخراج آدرس گیرنده و مقدار از دیتا
                    recipient = "0x" + str(tx_input)[34:74]
                    amount_hex = str(tx_input)[74:138]
                    amount_int = int(amount_hex, 16)
                    
                    if amount_int > 0:
                        logger.info(f"🚨 🐳 نهنگ (ERC20 Token) پیدا شد! 🚨")
                        logger.info(f"مقدار خام توکن: {amount_int}")
                        logger.info(f"کانترکت توکن: {to_addr}")
                        logger.info(f"فرستنده: {from_addr} -> گیرنده: {recipient}")
                        logger.info(f"هش تراکنش: {tx_hash_str}")
                    
            break # موفقیت آمیز بود، خروج از حلقه تلاش مجدد
        except Exception as e:
            if "not found" in str(e).lower() and attempt < 2:
                # نود HTTP هنوز سینک نشده است، صبر می‌کنیم
                await asyncio.sleep(2)
            else:
                logger.error(f"خطا در پردازش بلاک {block_hash}: {e}")
                break

async def worker(queue: asyncio.Queue):
    """ورکر برای پردازش بلاک‌ها از داخل صف"""
    while True:
        block_hash = await queue.get()
        try:
            await analyze_block(block_hash)
        except Exception as e:
            logger.error(f"خطا در ورکر نهنگ‌یاب: {e}")
        finally:
            queue.task_done()

async def start_whale_tracker():
    """اتصال به وب‌سوکت بلاکچین و شنود بلاک‌های جدید"""
    wss_url = settings.EVM_WSS_URL
    logger.info(f"Connecting to WebSocket: {wss_url}")
    
    # ساخت صف برای جلوگیری از ساخت بیش از حد Task و مدیریت منابع
    queue = asyncio.Queue(maxsize=100)
    
    # راه‌اندازی ورکرها
    workers = []
    for _ in range(WORKER_COUNT):
        task = asyncio.create_task(worker(queue))
        workers.append(task)
        
    subscribe_msg = json.dumps({
        "id": 1,
        "jsonrpc": "2.0",
        "method": "eth_subscribe",
        "params": ["newHeads"]
    })

    try:
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
                            
                            # اضافه کردن بلاک به صف
                            if not queue.full():
                                queue.put_nowait(block_hash)
                            else:
                                logger.warning("Block queue is full! Dropping block.")
                            
            except websockets.ConnectionClosed:
                logger.warning("ارتباط وب‌سوکت قطع شد! تلاش مجدد تا 5 ثانیه دیگر...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"خطای غیرمنتظره در ردیاب نهنگ: {e}")
                await asyncio.sleep(5)
    finally:
        for task in workers:
            task.cancel()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_whale_tracker())
