"""
@Author: will
@Date: 2025-11-21
@Description: 插针反弹策略配置文件
----------------------------------------------------------------------------------------------------

基于插针信号的交易策略：
1. 下插针 → 开多，赚反弹收益
2. 上插针 → 开空，赚回落收益

策略特点：
- 捕捉极端波动后的反弹/回落
- 严格止损止盈
- 固定风险资金管理
"""

from pathlib import Path

# ====================================================================================================
# ** 数据配置 **
# ====================================================================================================
# 合约数据路径（1小时K线）
# 修改为实际的数据路径
data_path = Path(r'/Users/wang/PythonProjects/xingda/data/coin-binance-swap-candle-csv-1h-2025-11-12/')

# 回测时间范围
start_date = '2021-01-01'
end_date = '2099-01-01'

# ====================================================================================================
# ** 插针检测参数（与 spike_signal_bot.py 保持一致）**
# ====================================================================================================
ATR_PERIOD = 14                 # ATR周期
SHADOW_RATIO = 2.0              # 主导影线 >= 2.0 × 实体
ATR_RATIO = 1.1                 # 振幅 >= 1.1 × ATR（基础过滤）
ATR_MULTIPLIER = 1.5            # 振幅 >= 1.5 × ATR（增强过滤）
RANGE_Z_THRESHOLD = 0.0         # 波动量 Z-score 阈值
VOLUME_Z_THRESHOLD = 0.5        # 成交量 Z-score 阈值
VOLUME_MULTIPLIER = 1.5         # 成交量 >= 中位数 × 2.0
Z_WINDOW = 120                  # Z-score 计算窗口（120根K线）

# ====================================================================================================
# ** 交易策略参数 **
# ====================================================================================================
# 资金管理
INITIAL_CAPITAL = 100000        # 初始资金（U）
RISK_PER_TRADE = 0.02          # 单笔风险比例（2%）
MAX_POSITION_SIZE = 0.3        # 单币种最大仓位（30%）
COMMISSION_RATE = 0.0004       # 手续费（万四，包含滑点）
LEVERAGE = 1                   # 杠杆倍数（建议1倍，稳健）

# 止损止盈策略
STOP_LOSS_TYPE = "extreme"     # 止损类型：
                               # - "extreme": 使用插针极值点（最低点/最高点）
                               # - "atr": 使用ATR倍数止损
                               # - "percent": 使用固定百分比止损

STOP_LOSS_ATR_MULTIPLIER = 1.5 # ATR止损倍数（当 STOP_LOSS_TYPE="atr" 时使用）
STOP_LOSS_PERCENT = 0.01       # 固定百分比止损（当 STOP_LOSS_TYPE="percent" 时使用）

TAKE_PROFIT_TYPE = "risk_reward"  # 止盈类型：
                                  # - "risk_reward": 固定盈亏比
                                  # - "atr": ATR倍数止盈
                                  # - "percent": 固定百分比止盈

RISK_REWARD_RATIO = 3        # 盈亏比（当 TAKE_PROFIT_TYPE="risk_reward" 时使用）
TAKE_PROFIT_ATR_MULTIPLIER = 3.0  # ATR止盈倍数
TAKE_PROFIT_PERCENT = 0.04     # 固定百分比止盈

# 时间止损
USE_TIME_STOP = True           # 是否启用时间止损
TIME_STOP_BARS = 24            # 持仓超过N根K线强制平仓（24根=24小时=1天）

# 额外过滤条件
MIN_VOLUME_USDT = 1000000      # 最小成交额（100万U，过滤低流动性币种）
MIN_KLINE_NUM = 168            # 最少上市时间（168小时=7天）

# 黑名单（不参与交易的币种）
BLACK_LIST = []  # 例如：['BTC-USDT', 'ETH-USDT']

# ====================================================================================================
# ** 策略模式 **
# ====================================================================================================
# 交易方向：
# - "both": 做多+做空（双向交易）
# - "long_only": 仅做多（下插针）
# - "short_only": 仅做空（上插针）
TRADE_DIRECTION = "both"

# ====================================================================================================
# ** 回测输出配置 **
# ====================================================================================================
backtest_name = "插针反弹策略_V1.0"
output_path = Path(__file__).parent / "backtest_results"

# 是否生成详细交易记录
SAVE_TRADE_DETAILS = True

# 是否生成权益曲线图
PLOT_EQUITY_CURVE = True

# 稳定币名单（不参与交易）
STABLE_SYMBOLS = ['BKRW', 'USDC', 'USDP', 'TUSD', 'BUSD', 'FDUSD', 'DAI', 'EUR', 'GBP', 'USBP', 'SUSD', 'PAXG', 'AEUR']

# ====================================================================================================
# ** 验证配置 **
# ====================================================================================================
if not data_path.exists():
    print(f'⚠️ 数据路径不存在：{data_path}')
    print(f'💡 请修改 spike_strategy_config.py 中的 data_path 变量')
    print(f'   当前配置：{data_path}')
else:
    print(f"✅ 配置加载成功")
    print(f"📂 数据路径: {data_path}")
    print(f"💰 初始资金: {INITIAL_CAPITAL:,.0f} U")
    print(f"⚠️  单笔风险: {RISK_PER_TRADE*100:.1f}%")
    print(f"🎯 盈亏比: {RISK_REWARD_RATIO:.1f}:1")
    print(f"📊 交易方向: {TRADE_DIRECTION}")

# 确保输出目录存在
output_path.mkdir(parents=True, exist_ok=True)

