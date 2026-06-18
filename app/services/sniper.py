import logging
import time
from web3 import AsyncWeb3
from app.config import settings

logger = logging.getLogger(__name__)

FEE_PERCENTAGE = 0.5  # 0.5 درصد کارمزد ربات

# ذخیره کانکشن‌های Web3 برای جلوگیری از ساخت مجدد و افزایش سرعت
_web3_providers = {}

def get_web3_provider(network_name: str) -> AsyncWeb3:
    if network_name not in _web3_providers:
        rpc_url = settings.NETWORKS[network_name]["rpc"]
        _web3_providers[network_name] = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc_url))
    return _web3_providers[network_name]

# ABI کامل‌تر برای تعویض اتریوم (یا کوین اصلی شبکه مثل BNB) با توکن و گرفتن خروجی
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
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [{"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    }
]

async def calculate_fee(amount_in_wei: int) -> int:
    """محاسبه کارمزد بر اساس درصد تعیین شده"""
    return int(amount_in_wei * (FEE_PERCENTAGE / 100))

async def execute_dex_swap(user_private_key: str, network_name: str, token_out: str, amount_in_wei: int, slippage_tolerance: float = 5.0):
    """
    اجرای تراکنش خرید در شبکه‌های مختلف (اتریوم، BSC، آربیتروم و غیره)
    با پشتیبانی از تمام کیف‌پول‌های استاندارد EVM (تراست والت، متامسک و ...)
    """
    try:
        if network_name not in settings.NETWORKS:
            raise ValueError(f"شبکه {network_name} پشتیبانی نمی‌شود.")
            
        network_config = settings.NETWORKS[network_name]
        
        # استفاده از کانکشن ذخیره شده برای سرعت بالا
        w3 = get_web3_provider(network_name)
        
        # 1. بازیابی حساب کاربری از کلید خصوصی
        account = w3.eth.account.from_key(user_private_key)
        user_address = account.address
        logger.info(f"شروع عملیات اسنایپ در شبکه {network_name} برای کاربر: {user_address}")

        # 2. محاسبه کارمزد شبکه و کارمزد سیستم
        fee_amount = await calculate_fee(amount_in_wei)
        amount_after_fee = amount_in_wei - fee_amount
        
        # دریافت نانس و مشخصات بلاک برای محاسبه EIP-1559
        nonce = await w3.eth.get_transaction_count(user_address, 'pending')
        latest_block = await w3.eth.get_block('latest')
        base_fee = latest_block.get('baseFeePerGas', 0)
        
        # محاسبه فی برای شبکه‌های با پشتیبانی از EIP-1559
        if base_fee > 0:
            max_priority_fee = await w3.eth.max_priority_fee
            max_fee_per_gas = int(base_fee * 1.5) + max_priority_fee
            gas_price_estimate = max_fee_per_gas
        else:
            # Fallback برای شبکه‌های بدون EIP-1559 (مثل بعضی نودهای BSC)
            gas_price_estimate = int(await w3.eth.gas_price * 1.1)

        chain_id = await w3.eth.chain_id

        # 3. آماده‌سازی تراکنش اصلی Swap
        router_address = w3.to_checksum_address(network_config["router"])
        router_contract = w3.eth.contract(address=router_address, abi=DEX_ROUTER_ABI)
        
        token_in_checksum = w3.to_checksum_address(network_config["weth"])
        token_out_checksum = w3.to_checksum_address(token_out)
        
        # محاسبه AmountOutMin برای جلوگیری از حملات ساندویچی (MEV)
        path = [token_in_checksum, token_out_checksum]
        try:
            amounts_out = await router_contract.functions.getAmountsOut(amount_after_fee, path).call()
            expected_output = amounts_out[1]
            amount_out_min = int(expected_output * (1 - (slippage_tolerance / 100)))
            logger.info(f"مقدار خروجی مورد انتظار: {expected_output}, حداقل دریافتی (Slippage {slippage_tolerance}%): {amount_out_min}")
        except Exception as e:
            logger.warning(f"عدم امکان دریافت قیمت از استخر نقدینگی: {e}")
            amount_out_min = 0 # Fallback فقط در صورت خطا
        
        deadline = int(time.time()) + 60 # کاهش زمان انقضا به 1 دقیقه برای اسنایپ
        
        # ساختن دیتای تراکنش فراخوانی کانترکت
        swap_func = router_contract.functions.swapExactETHForTokens(
            amount_out_min, 
            path,
            user_address,
            deadline
        )
        
        # پارامترهای پایه تراکنش
        tx_params = {
            'from': user_address,
            'value': amount_after_fee,
            'nonce': nonce,
            'chainId': chain_id
        }
        
        if base_fee > 0:
            tx_params['maxFeePerGas'] = max_fee_per_gas
            tx_params['maxPriorityFeePerGas'] = max_priority_fee
        else:
            tx_params['gasPrice'] = gas_price_estimate

        # محاسبه دقیق گس مصرفی به جای عدد ثابت
        try:
            estimated_gas = await swap_func.estimate_gas(tx_params)
            tx_params['gas'] = int(estimated_gas * 1.2) # 20% حاشیه امنیت
        except Exception as e:
            logger.warning(f"خطا در تخمین گس، استفاده از مقدار پیش‌فرض: {e}")
            tx_params['gas'] = 300000
        
        swap_tx = await swap_func.build_transaction(tx_params)

        # بررسی موجودی کیف پول کاربر برای اطمینان از پرداخت گس
        balance = await w3.eth.get_balance(user_address)
        total_cost = amount_in_wei + (swap_tx['gas'] * gas_price_estimate)
        if balance < total_cost:
            raise ValueError(f"موجودی کافی نیست! موجودی: {w3.from_wei(balance, 'ether')} | نیاز: {w3.from_wei(total_cost, 'ether')}")

        # 4. امضا و ارسال تراکنش اصلی اسنایپ
        signed_swap_tx = w3.eth.account.sign_transaction(swap_tx, private_key=user_private_key)
        swap_tx_hash = await w3.eth.send_raw_transaction(signed_swap_tx.raw_transaction)
        logger.info(f"🚀 تراکنش خرید با موفقیت در شبکه {network_name} ارسال شد: {swap_tx_hash.hex()}")
        
        nonce += 1 # آپدیت نانس برای تراکنش بعدی

        # 5. ساخت و ارسال تراکنش کارمزد ربات پس از موفقیت اسنایپ
        fee_tx_hash_hex = None
        if fee_amount > 0 and settings.SYSTEM_WALLET_ADDRESS != "0x0000000000000000000000000000000000000000":
            fee_tx = {
                'to': settings.SYSTEM_WALLET_ADDRESS,
                'value': fee_amount,
                'gas': 21000,
                'nonce': nonce,
                'chainId': chain_id
            }
            if base_fee > 0:
                fee_tx['maxFeePerGas'] = max_fee_per_gas
                fee_tx['maxPriorityFeePerGas'] = max_priority_fee
            else:
                fee_tx['gasPrice'] = gas_price_estimate
            # اگر موجودی کاربر بعد از اسنایپ برای ارسال کارمزد کافی بود
            try:
                signed_fee_tx = w3.eth.account.sign_transaction(fee_tx, private_key=user_private_key)
                fee_tx_hash = await w3.eth.send_raw_transaction(signed_fee_tx.raw_transaction)
                fee_tx_hash_hex = fee_tx_hash.hex()
                logger.info(f"✅ تراکنش کارمزد ارسال شد: {fee_tx_hash_hex}")
            except Exception as fee_e:
                logger.error(f"⚠️ خرید موفق بود اما تراکنش کارمزد شکست خورد: {fee_e}")

        return {
            "status": "success",
            "network": network_name,
            "fee_tx_hash": fee_tx_hash_hex,
            "swap_tx_hash": swap_tx_hash.hex(),
            "fee_deducted": fee_amount
        }

    except Exception as e:
        logger.error(f"❌ خطا در اجرای اسنایپ: {e}")
        return {
            "status": "error",
            "error_msg": str(e)
        }
