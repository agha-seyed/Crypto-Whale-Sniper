import asyncio
import json
import logging
import websockets
from web3 import AsyncWeb3
from sqlalchemy import select
from decimal import Decimal

from app.config import settings
from app.core.db import AsyncSessionLocal
from app.models.settings import WalletSettings
from app.services.sniper import execute_dex_swap

logger = logging.getLogger(__name__)

WHALE_THRESHOLD_ETH = 50
WORKER_COUNT = 5

ERC20_TRANSFER_ABI = [{
    "constant": False,
    "inputs": [
        {"name": "_to", "type": "address"},
        {"name": "_value", "type": "uint256"}
    ],
    "name": "transfer",
    "outputs": [{"name": "", "type": "bool"}],
    "payable": False,
    "stateMutability": "nonpayable",
    "type": "function"
}]

# Create Web3 providers globally per network
web3_providers = {}
for network, config in settings.NETWORKS.items():
    if config.get("rpc"):
        web3_providers[network] = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(config["rpc"]))

# Helper contract for decoding
dummy_w3 = AsyncWeb3()
erc20_contract = dummy_w3.eth.contract(abi=ERC20_TRANSFER_ABI)

async def trigger_auto_snipe(network_name: str, token_contract: str):
    """جستجوی کاربرانی که این توکن را هدف قرار داده‌اند و اجرای اسنایپ خودکار"""
    async with AsyncSessionLocal() as session:
        # جستجو بر اساس آدرس کانترکت به صورت حساسیت کمتر به حروف بزرگ و کوچک
        query = select(WalletSettings).where(
            WalletSettings.auto_snipe.ilike(token_contract)
        )
        result = await session.execute(query)
        settings_list = result.scalars().all()
        
        for user_settings in settings_list:
            logger.info(f"🎯 Auto-Snipe triggered for user {user_settings.user_id} on token {token_contract}")
            amount_in_wei = web3_providers[network_name].to_wei(Decimal(str(user_settings.buy_amount_eth)), 'ether')
            
            # ایجاد یک task برای اینکه منتظر اجرای اسنایپ نشویم و ورکر ممپول بلاک نشود
            asyncio.create_task(
                execute_dex_swap(
                    user_id=user_settings.user_id,
                    network_name=network_name,
                    token_out=token_contract,
                    amount_in_wei=amount_in_wei,
                    slippage_tolerance=user_settings.default_slippage
                )
            )

async def analyze_pending_transaction(network_name: str, tx_hash: str):
    """آنالیز سریع تراکنش تایید نشده (Pending) برای شکار نهنگ‌ها در ممپول"""
    w3 = web3_providers.get(network_name)
    if not w3:
        return

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
                logger.warning(f"⚡ [MEMPOOL ALERT {network_name.upper()}] حرکت نهنگ (ارز اصلی) قبل از ثبت در بلاک! ⚡")
                logger.info(f"مبلغ: {value_in_eth} ETH/BNB (Pending)")
                logger.info(f"از: {from_addr}")
                logger.info(f"به: {to_addr}")
                logger.info(f"هش تراکنش: {tx_hash}")
                
            # بررسی انتقال توکن‌های ERC20 (متد transfer)
            elif str(tx_input).startswith("0xa9059cbb"):
                # استفاده از دیکدر استاندارد قرارداد هوشمند
                try:
                    func_obj, func_params = erc20_contract.decode_function_input(tx_input)
                    recipient = func_params.get('_to')
                    amount_int = func_params.get('_value')
                except Exception as parse_e:
                    # اگر دیکد نشد، یعنی احتمالاً فرمت transfer نبوده است
                    return
                
                if amount_int > 0:
                    logger.warning(f"⚡ [MEMPOOL ALERT {network_name.upper()}] حرکت نهنگ (ERC20 Token) قبل از ثبت در بلاک! ⚡")
                    logger.info(f"مقدار خام توکن: {amount_int} (Pending)")
                    logger.info(f"کانترکت توکن: {to_addr}")
                    logger.info(f"فرستنده: {from_addr} -> گیرنده: {recipient}")
                    logger.info(f"هش تراکنش: {tx_hash}")

                    # در صورت یافتن نهنگ، اجرای اتو اسنایپ
                    if to_addr and to_addr != 'Contract Creation':
                        await trigger_auto_snipe(network_name, to_addr)

    except Exception as e:
        # خطای TransactionNotFound در ممپول بسیار طبیعی است زیرا تراکنش مدام در حال جابجایی است
        if "not found" not in str(e).lower():
            pass # برای جلوگیری از اسپم لاگ‌ها در ممپول، فقط خطاهای حیاتی را لاگ می‌کنیم

async def worker(network_name: str, queue: asyncio.Queue):
    """ورکر برای پردازش تراکنش‌های ممپول یک شبکه خاص از داخل صف"""
    while True:
        tx_hash = await queue.get()
        try:
            await analyze_pending_transaction(network_name, tx_hash)
        except Exception as e:
            logger.error(f"خطا در ورکر ممپول شبکه {network_name}: {e}")
        finally:
            queue.task_done()

async def monitor_network(network_name: str, config: dict):
    """اسکن ممپول مربوط به یک شبکه خاص"""
    wss_url = config.get("wss")
    if not wss_url:
        return
        
    logger.info(f"Connecting to Mempool WebSocket for {network_name}: {wss_url}")
    
    # ساخت صف برای تراکنش‌ها جهت جلوگیری از نشت حافظه (OOM)
    queue = asyncio.Queue(maxsize=2000)
    
    # راه‌اندازی ورکرها
    workers = []
    for _ in range(WORKER_COUNT):
        task = asyncio.create_task(worker(network_name, queue))
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
                    logger.info(f"✅ متصل شد! در حال اسکن استخر ماینرها (Mempool) شبکه {network_name}...")
                    await ws.send(subscribe_msg)
                    response = await ws.recv()
                    logger.info(f"پاسخ عضویت در ممپول {network_name}: {response}")

                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        
                        if 'method' in data and data['method'] == 'eth_subscription':
                            tx_hash = data['params']['result']
                            
                            # اضافه کردن به صف به جای ساخت Task جدید برای هر تراکنش
                            if not queue.full():
                                queue.put_nowait(tx_hash)
                            else:
                                logger.warning(f"[{network_name.upper()}] Mempool queue is full! Dropping transaction.")
                            
            except websockets.ConnectionClosed:
                logger.warning(f"ارتباط ممپول {network_name} قطع شد! تلاش مجدد...")
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"خطا در ممپول اسنایپر شبکه {network_name}: {e}")
                await asyncio.sleep(2)
    finally:
        # متوقف کردن ورکرها در صورت خروج
        for task in workers:
            task.cancel()

async def start_mempool_sniper():
    """اجرای اسکن ممپول روی تمام شبکه‌ها به صورت همزمان"""
    tasks = []
    for network_name, config in settings.NETWORKS.items():
        if config.get("wss"):
            tasks.append(monitor_network(network_name, config))
            
    if tasks:
        await asyncio.gather(*tasks)
    else:
        logger.error("No WSS configurations found in settings.NETWORKS.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_mempool_sniper())
