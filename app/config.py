from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BOT_TOKEN: str = ""
    WEBHOOK_URL: str = ""
    WEBHOOK_PATH: str = "/webhook"
    DATABASE_URL: str = ""
    REDIS_URL: str = ""
    EVM_RPC_URL: str = "https://cloudflare-eth.com"
    EVM_WSS_URL: str = "wss://ethereum-rpc.publicnode.com"
    
    # لیست شبکه‌های پشتیبانی شده با RPC، WSS و Router مخصوص به خودشان
    NETWORKS: dict = {
        "ethereum": {
            "rpc": "https://cloudflare-eth.com",
            "wss": "wss://ethereum-rpc.publicnode.com",
            "router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", # Uniswap V2
            "weth": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
        },
        "bsc": {
            "rpc": "https://bsc-dataseed.binance.org/",
            "wss": "wss://bsc-rpc.publicnode.com",
            "router": "0x10ED43C718714eb63d5aA57B78B54704E256024E", # PancakeSwap
            "weth": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c" # WBNB
        },
        "arbitrum": {
            "rpc": "https://arb1.arbitrum.io/rpc",
            "wss": "wss://arbitrum-one.publicnode.com",
            "router": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506", # SushiSwap Arbitrum
            "weth": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"
        }
    }
    
    SYSTEM_WALLET_ADDRESS: str = "0x0000000000000000000000000000000000000000" # جایگزین با آدرس واقعی شما

    class Config:
        env_file = ".env"

settings = Settings()
