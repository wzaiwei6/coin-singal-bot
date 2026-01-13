#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Binance 行情数据接入模块
"""
import os
import time
from typing import Optional, Tuple
import ccxt
import pandas as pd
import requests


def detect_proxy(config: dict) -> Tuple[bool, Optional[str]]:
    """
    自动检测代理设置
    
    Args:
        config: 配置字典
        
    Returns:
        (是否使用代理, 代理URL)
    """
    # 如果配置中明确启用代理
    if config.get("proxy", {}).get("enabled"):
        proxy_url = config["proxy"].get("url", "http://127.0.0.1:7890")
        return True, proxy_url
    
    # 检测环境变量
    use_proxy_env = os.getenv("MACD_VOL_USE_PROXY", "").lower()
    if use_proxy_env == "false":
        return False, None
    if use_proxy_env == "true":
        proxy_url = os.getenv("MACD_VOL_PROXY_URL", "http://127.0.0.1:7890")
        return True, proxy_url
    
    # 检测系统代理环境变量
    for env_var in ["HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"]:
        proxy_url = os.getenv(env_var)
        if proxy_url:
            return True, proxy_url
    
    # 如果设置了自定义代理URL
    custom_proxy = os.getenv("MACD_VOL_PROXY_URL")
    if custom_proxy:
        return True, custom_proxy
    
    # 默认不使用代理（适用于服务器部署）
    return False, None


def build_exchange(config: dict) -> ccxt.Exchange:
    """
    构建交易所对象，支持重试和错误处理
    
    Args:
        config: 配置字典
        
    Returns:
        ccxt.Exchange: 交易所对象
        
    Raises:
        ValueError: 不支持的交易所
        ConnectionError: 无法连接到交易所
    """
    exchange_id = config.get("binance", {}).get("exchange_id", "binanceusdm")
    timeout = config.get("binance", {}).get("timeout", 30000)
    
    # 获取交易所类
    try:
        exchange_class = getattr(ccxt, exchange_id)
    except AttributeError:
        raise ValueError(f"不支持的交易所: {exchange_id}。请检查配置文件中的 binance.exchange_id")
    
    # 配置交易所
    cfg = {
        "enableRateLimit": True,
        "timeout": timeout,
        "options": {"defaultType": "future"},
    }
    
    # 配置代理
    use_proxy, proxy_url = detect_proxy(config)
    if use_proxy and proxy_url:
        cfg["proxies"] = {"http": proxy_url, "https": proxy_url}
        print(f"✅ 使用代理: {proxy_url}")
    else:
        print("⚠️  代理已禁用")
    
    exchange = exchange_class(cfg)
    
    # 重试加载市场数据
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"正在连接交易所 {exchange_id}... (尝试 {attempt + 1}/{max_retries})")
            exchange.load_markets()
            print(f"✅ 成功连接到 {exchange_id}")
            return exchange
        except (ccxt.NetworkError, ccxt.ExchangeError, requests.exceptions.RequestException) as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                print(f"⚠️  连接失败，{wait_time}秒后重试... 错误: {str(e)[:100]}")
                time.sleep(wait_time)
            else:
                error_msg = (
                    f"\n❌ 无法连接到交易所 {exchange_id}\n"
                    f"错误详情: {str(e)}\n\n"
                    f"💡 解决方案：\n"
                    f"1. 检查网络连接\n"
                    f"2. 如果在中国大陆，请设置代理：\n"
                    f"   export MACD_VOL_USE_PROXY=true\n"
                    f"   export MACD_VOL_PROXY_URL=http://127.0.0.1:7890\n"
                    f"3. 或者在 config.yaml 中配置代理\n"
                )
                raise ConnectionError(error_msg) from e


def fetch_klines(exchange: ccxt.Exchange, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
    """
    获取K线数据
    
    Args:
        exchange: 交易所对象
        symbol: 交易对符号，如 "BTCUSDT" 或 "BTC/USDT"
        timeframe: 时间周期，如 "1h", "4h", "1d"
        limit: 获取的K线数量
        
    Returns:
        pd.DataFrame: K线数据，包含 timestamp, open, high, low, close, volume
        
    Raises:
        Exception: 获取数据失败
    """
    # 统一符号格式（支持两种格式）
    if "/" not in symbol:
        # 将 BTCUSDT 转换为 BTC/USDT
        if symbol.endswith("USDT"):
            base = symbol[:-4]
            symbol = f"{base}/USDT"
        else:
            raise ValueError(f"无法解析交易对: {symbol}")
    
    try:
        raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        return df
    except Exception as e:
        print(f"❌ 获取 {symbol} {timeframe} K线数据失败: {e}")
        raise
