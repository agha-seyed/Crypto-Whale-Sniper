import logging
import time
from web3 import AsyncWeb3
from app.config import settings

logger = logging.getLogger(__name__)

FEE_PERCENTAGE = 0.5  # 0.5 درصد کارمزد ربات

# ABI حداقلی برای تعویض اتریوم (یا کوین اصلی شبکه مثل BNB) با توکن
DEX_ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function"
    }
]

async def calculate_fee(amount_in_wei: int) -> int:
    """محاسبه کارمزد بر اساس درصد تعیین شده"""
    return (amount_in_wei * int(FEE_PERCENTAGE * 10)) // 1000

async def execute_dex_swap(user_private_key: str, network_name: str, token_out: str, amount_in_wei: int):
    """
    اجرای تراکنش خرید در شبکه‌های مختلف (اتریوم، BSC، آربیتروم و غیره)
    با پشتیبانی از تمام کیف‌پول‌های استاندارد EVM (تراست والت، متامسک و ...)
    """
    try:
        if network_name not in settings.NETWORKS:
            raise ValueError(f"شبکه {network_name} پشتیبانی نمی‌شود.")
            
        network_config = settings.NETWORKS[network_name]
        
        # ساخت یک کانکشن اختصاصی برای این شبکه
        w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(network_config["rpc"]))
        
        # 1. بازیابی حساب کاربری از کلید خصوصی (پشتیبانی از هر ولتی)
        account = w3.eth.account.from_key(user_private_key)
        user_address = account.address
        logger.info(f"شروع عملیات اسنایپ در شبکه {network_name} برای کاربر: {user_address}")

        # 2. محاسبه کارمزد شبکه و کارمزد سیستم (ربات)
        fee_amount = await calculate_fee(amount_in_wei)
        amount_after_fee = amount_in_wei - fee_amount
        
        # دریافت نانس (Nonce) امن و قیمت گاز لحظه‌ای
        nonce = await w3.eth.get_transaction_count(user_address, 'pending')
        gas_price = await w3.eth.gas_price
        current_gas_price = int(gas_price * 1.1)  # 10% افزایش برای سرعت بالاتر

        chain_id = await w3.eth.chain_id

        # 3. ساخت و ارسال تراکنش کارمزد ربات به صورت جداگانه (ارسال به ولت سیستم)
        if fee_amount > 0 and settings.SYSTEM_WALLET_ADDRESS != "0x0000000000000000000000000000000000000000":
            fee_tx = {
                'to': settings.SYSTEM_WALLET_ADDRESS,
                'value': fee_amount,
                'gas': 21000,
                'gasPrice': current_gas_price,
                'nonce': nonce,
                'chainId': chain_id
            }
            # امضا و ارسال تراکنش کارمزد به صورت آفلاین (بالاترین امنیت)
            signed_fee_tx = w3.eth.account.sign_transaction(fee_tx, private_key=user_private_key)
            fee_tx_hash = await w3.eth.send_raw_transaction(signed_fee_tx.raw_transaction)
            logger.info(f"✅ تراکنش کارمزد ارسال شد: {fee_tx_hash.hex()}")
            nonce += 1 # افزایش نانس برای تراکنش بعدی (جلوگیری از تداخل)

        # 4. آماده‌سازی تراکنش اصلی Swap در صرافی شبکه مورد نظر
        router_address = w3.to_checksum_address(network_config["router"])
        router_contract = w3.eth.contract(address=router_address, abi=DEX_ROUTER_ABI)
        
        token_in_checksum = w3.to_checksum_address(network_config["weth"])
        token_out_checksum = w3.to_checksum_address(token_out)
        
        deadline = int(time.time()) + 300 # 5 دقیقه زمان انقضا
        
        # ساختن دیتای تراکنش فراخوانی کانترکت
        swap_func = router_contract.functions.swapExactETHForTokens(
            0, # در یک ربات واقعی حرفه‌ای باید Slippage محاسبه شود
            [token_in_checksum, token_out_checksum],
            user_address,
            deadline
        )
        
        # استفاده از گس ۵۰۰,۰۰۰ برای جلوگیری از ارور Out of Gas در صرافی‌های پیچیده
        swap_tx = await swap_func.build_transaction({
            'from': user_address,
            'value': amount_after_fee,
            'gas': 500000,
            'gasPrice': current_gas_price,
            'nonce': nonce,
            'chainId': chain_id
        })

        # 5. امضا و ارسال تراکنش اصلی
        signed_swap_tx = w3.eth.account.sign_transaction(swap_tx, private_key=user_private_key)
        swap_tx_hash = await w3.eth.send_raw_transaction(signed_swap_tx.raw_transaction)
        logger.info(f"🚀 تراکنش خرید با موفقیت در شبکه {network_name} ارسال شد: {swap_tx_hash.hex()}")

        return {
            "status": "success",
            "network": network_name,
            "fee_tx_hash": fee_tx_hash.hex() if 'fee_tx_hash' in locals() else None,
            "swap_tx_hash": swap_tx_hash.hex(),
            "fee_deducted": fee_amount
        }

    except Exception as e:
        logger.error(f"❌ خطا در اجرای اسنایپ: {e}")
        return {
            "status": "error",
            "error_msg": str(e)
        }
