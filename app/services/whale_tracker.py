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
WORKER_COUNT = 3

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

web3_providers = {}
for network, config in settings.NETWORKS.items():
    if config.get("rpc"):
        web3_providers[network] = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(config["rpc"]))

dummy_w3 = AsyncWeb3()
erc20_contract = dummy_w3.eth.contract(abi=ERC20_TRANSFER_ABI)

async def trigger_auto_snipe(network_name: str, token_contract: str):
    """جستجوی کاربرانی که این توکن را هدف قرار داده‌اند و اجرای اسنایپ خودکار"""
    async with AsyncSessionLocal() as session:
        query = select(WalletSettings).where(
            WalletSettings.auto_snipe.ilike(token_contract)
        )
        result = await session.execute(query)
        settings_list = result.scalars().all()
        
        for user_settings in settings_list:
            logger.info(f"🎯 Auto-Snipe triggered for user {user_settings.user_id} on token {token_contract}")
            amount_in_wei = web3_providers[network_name].to_wei(Decimal(str(user_settings.buy_amount_eth)), 'ether')
            
            asyncio.create_task(
                execute_dex_swap(
                    user_id=user_settings.user_id,
                    network_name=network_name,
                    token_out=token_contract,
                    amount_in_wei=amount_in_wei,
                    slippage_tolerance=user_settings.default_slippage
                )
            )

async def analyze_block(network_name: str, block_hash: str):
    """آنالیز تراکنش‌های یک بلاک برای پیدا کردن نهنگ‌ها"""
    w3 = web3_providers.get(network_name)
    if not w3:
        return

    for attempt in range(3):
        try:
            block = await w3.eth.get_block(block_hash, full_transactions=True)
            if block is None:
                raise Exception(f"Block {block_hash} not found")
            
            for tx in block.transactions:
                from_addr = tx.get('from', 'Unknown')
                to_addr = tx.get('to', 'Contract Creation')
                
                tx_hash = tx.get('hash')
                tx_hash_str = tx_hash.hex() if hasattr(tx_hash, 'hex') or isinstance(tx_hash, bytes) else str(tx_hash)

                tx_input = tx.get('input', '0x')
                if hasattr(tx_input, 'hex'):
                    tx_input = '0x' + tx_input.hex()
                elif isinstance(tx_input, bytes):
                    tx_input = '0x' + tx_input.hex()

                value_in_eth = w3.from_wei(tx.get('value', 0), 'ether')
                
                if value_in_eth >= WHALE_THRESHOLD_ETH:
                    logger.info(f"🚨 🐳 نهنگ (ارز اصلی {network_name.upper()}) پیدا شد! 🚨")
                    logger.info(f"مبلغ: {value_in_eth} ETH/BNB")
                    logger.info(f"از: {from_addr}")
                    logger.info(f"به: {to_addr}")
                    logger.info(f"هش تراکنش: {tx_hash_str}")
                    
                elif str(tx_input).startswith("0xa9059cbb"):
                    try:
                        func_obj, func_params = erc20_contract.decode_function_input(tx_input)
                        recipient = func_params.get('_to')
                        amount_int = func_params.get('_value')
                    except Exception:
                        continue
                        
                    if amount_int and amount_int > 0:
                        logger.info(f"🚨 🐳 نهنگ (ERC20 Token روی {network_name.upper()}) پیدا شد! 🚨")
                        logger.info(f"مقدار خام توکن: {amount_int}")
                        logger.info(f"کانترکت توکن: {to_addr}")
                        logger.info(f"فرستنده: {from_addr} -> گیرنده: {recipient}")
                        logger.info(f"هش تراکنش: {tx_hash_str}")
                        
                        if to_addr and to_addr != 'Contract Creation':
                            await trigger_auto_snipe(network_name, to_addr)
                    
            break 
        except Exception as e:
            if "not found" in str(e).lower() and attempt < 2:
                await asyncio.sleep(2)
            else:
                logger.error(f"خطا در پردازش بلاک {block_hash} شبکه {network_name}: {e}")
                break

async def worker(network_name: str, queue: asyncio.Queue):
    while True:
        block_hash = await queue.get()
        try:
            await analyze_block(network_name, block_hash)
        except Exception as e:
            logger.error(f"خطا در ورکر نهنگ‌یاب شبکه {network_name}: {e}")
        finally:
            queue.task_done()

async def monitor_network(network_name: str, config: dict):
    wss_url = config.get("wss")
    if not wss_url:
        return

    logger.info(f"Connecting to Whale Tracker WebSocket for {network_name}: {wss_url}")
    
    queue = asyncio.Queue(maxsize=100)
    workers = []
    for _ in range(WORKER_COUNT):
        task = asyncio.create_task(worker(network_name, queue))
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
                    logger.info(f"✅ متصل شد! ارسال درخواست شنود بلاک‌های جدید {network_name}...")
                    await ws.send(subscribe_msg)
                    response = await ws.recv()
                    logger.info(f"پاسخ عضویت {network_name}: {response}")

                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        
                        if 'method' in data and data['method'] == 'eth_subscription':
                            block_hash = data['params']['result']['hash']
                            block_number = int(data['params']['result']['number'], 16)
                            logger.info(f"📦 بلاک جدید دریافت شد روی {network_name.upper()}: {block_number}")
                            
                            if not queue.full():
                                queue.put_nowait(block_hash)
                            else:
                                logger.warning(f"[{network_name.upper()}] Block queue is full! Dropping block.")
                            
            except websockets.ConnectionClosed:
                logger.warning(f"ارتباط وب‌سوکت {network_name} قطع شد! تلاش مجدد...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"خطای غیرمنتظره در ردیاب نهنگ {network_name}: {e}")
                await asyncio.sleep(5)
    finally:
        for task in workers:
            task.cancel()

async def start_whale_tracker():
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
    asyncio.run(start_whale_tracker())
