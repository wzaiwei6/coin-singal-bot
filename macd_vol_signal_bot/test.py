#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MACD 波动率信号机器人 - 测试脚本

快速测试模块功能，不需要实际连接交易所
"""
import sys
from pathlib import Path

# 添加项目路径到 Python 路径
project_dir = Path(__file__).parent
parent_dir = project_dir.parent
sys.path.insert(0, str(parent_dir))

print("\n" + "="*60)
print("🧪 MACD 波动率信号机器人 - 模块测试")
print("="*60 + "\n")

# 测试 1: 导入所有模块
print("📦 测试 1: 导入所有模块...")
try:
    from macd_vol_signal_bot.models import Signal
    from macd_vol_signal_bot.market.binance import build_exchange, fetch_klines
    from macd_vol_signal_bot.indicators.macd import calculate_macd
    from macd_vol_signal_bot.indicators.volatility import calculate_atr
    from macd_vol_signal_bot.strategy.macd_vol import generate_signal
    from macd_vol_signal_bot.dedup.dedup import DedupManager
    from macd_vol_signal_bot.notifier.wecom import send_signal, format_signal_message
    from macd_vol_signal_bot.llm.analyzer import analyze_signal
    print("✅ 所有模块导入成功\n")
except Exception as e:
    print(f"❌ 模块导入失败: {e}\n")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 2: 创建 Signal 对象
print("📦 测试 2: 创建 Signal 对象...")
try:
    from datetime import datetime
    
    signal = Signal(
        symbol="BTCUSDT",
        timeframe="1h",
        direction="SELL",
        price=45000.0,
        timestamp=datetime.now(),
        confidence=0.75,
        risk_level="MID",
        suggestion="WATCH",
        reasons=["测试原因1", "测试原因2"],
        key_levels={"support": [44000, 44500], "resistance": [45500, 46000], "invalid": 45500},
        macd_hist=-12.5,
        macd_dif=-8.2,
        macd_dea=4.3,
        atr=180.0,
        atr_pct=0.4,
        atr_quantile=0.55
    )
    print(f"✅ Signal 对象创建成功: {signal.symbol} {signal.direction}\n")
except Exception as e:
    print(f"❌ Signal 创建失败: {e}\n")
    sys.exit(1)

# 测试 3: 格式化消息
print("📦 测试 3: 格式化企业微信消息...")
try:
    message = format_signal_message(signal, llm_analysis="这是一个测试分析")
    print("✅ 消息格式化成功")
    print(f"消息预览（前200字符）：\n{message[:200]}...\n")
except Exception as e:
    print(f"❌ 消息格式化失败: {e}\n")
    sys.exit(1)

# 测试 4: 去重管理器
print("📦 测试 4: 去重管理器...")
try:
    import tempfile
    temp_file = tempfile.mktemp(suffix=".json")
    
    dedup = DedupManager(temp_file, cooldown_minutes=120)
    
    # 检查是否重复（第一次应该不重复）
    is_dup = dedup.is_duplicate("BTCUSDT", "1h", "SELL")
    print(f"   首次检查是否重复: {is_dup}")
    
    # 记录信号
    dedup.record_signal("BTCUSDT", "1h", "SELL", 45000.0)
    
    # 再次检查（应该重复）
    is_dup = dedup.is_duplicate("BTCUSDT", "1h", "SELL")
    print(f"   二次检查是否重复: {is_dup}")
    
    # 获取统计信息
    stats = dedup.get_statistics()
    print(f"   统计信息: {stats}")
    
    print("✅ 去重管理器测试成功\n")
except Exception as e:
    print(f"❌ 去重管理器测试失败: {e}\n")
    sys.exit(1)

# 测试 5: 加载配置文件
print("📦 测试 5: 加载配置文件...")
try:
    import yaml
    
    config_file = project_dir / "config.yaml"
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    print(f"   监控币种: {config.get('symbols', [])}")
    print(f"   监控周期: {config.get('timeframes', [])}")
    print(f"   企业微信: {'已启用' if config.get('wecom', {}).get('enabled') else '已禁用'}")
    print(f"   LLM分析: {'已启用' if config.get('llm', {}).get('enabled') else '已禁用'}")
    print("✅ 配置文件加载成功\n")
except Exception as e:
    print(f"❌ 配置文件加载失败: {e}\n")
    sys.exit(1)

# 测试 6: MACD 指标计算
print("📦 测试 6: MACD 指标计算...")
try:
    import pandas as pd
    import numpy as np
    
    # 创建模拟数据
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='1h')
    close_prices = 45000 + np.cumsum(np.random.randn(100) * 100)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'close': close_prices
    })
    
    # 计算 MACD
    df_with_macd = calculate_macd(df)
    
    print(f"   数据行数: {len(df_with_macd)}")
    print(f"   最后一根K线:")
    print(f"     DIF: {df_with_macd.iloc[-1]['dif']:.4f}")
    print(f"     DEA: {df_with_macd.iloc[-1]['dea']:.4f}")
    print(f"     MACD柱: {df_with_macd.iloc[-1]['macd_hist']:.4f}")
    print("✅ MACD 指标计算成功\n")
except Exception as e:
    print(f"❌ MACD 指标计算失败: {e}\n")
    sys.exit(1)

# 测试 7: ATR 波动率计算
print("📦 测试 7: ATR 波动率计算...")
try:
    # 添加高低价数据
    df['high'] = df['close'] * 1.01
    df['low'] = df['close'] * 0.99
    
    # 计算 ATR
    df_with_atr = calculate_atr(df)
    
    print(f"   最后一根K线:")
    print(f"     ATR: {df_with_atr.iloc[-1]['atr']:.4f}")
    print(f"     ATR%: {df_with_atr.iloc[-1]['atr_pct']:.4f}%")
    print(f"     ATR分位: {df_with_atr.iloc[-1]['atr_quantile']:.4f}")
    print("✅ ATR 波动率计算成功\n")
except Exception as e:
    print(f"❌ ATR 波动率计算失败: {e}\n")
    sys.exit(1)

print("="*60)
print("✅ 所有测试通过！项目模块功能正常")
print("="*60 + "\n")

print("💡 下一步:")
print("   1. 配置 config.yaml 中的企业微信 Webhook URL")
print("   2. 如需使用 LLM，配置 API Key")
print("   3. 运行 python main.py 启动机器人\n")
