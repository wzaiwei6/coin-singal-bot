#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@Author: will
@Date: 2025-11-21
@Description: 插针反弹策略回测主程序
----------------------------------------------------------------------------------------------------

策略逻辑：
1. 检测插针信号（下插针/上插针）
2. 插针K线收盘后，下一根K线开盘入场
3. 严格止损止盈，固定风险资金管理
4. 支持多币种并行回测

执行方式：
    python spike_strategy_backtest.py
"""

import glob
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

warnings.filterwarnings('ignore')

# 导入配置
from spike_strategy_config import *

# ====================================================================================================
# ** 数据结构定义 **
# ====================================================================================================

@dataclass
class Trade:
    """交易记录"""
    symbol: str
    entry_time: datetime
    exit_time: datetime
    direction: str  # 'long' or 'short'
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    size: float  # 仓位（张数或U）
    pnl: float  # 盈亏（U）
    pnl_pct: float  # 盈亏百分比
    exit_reason: str  # 'Stop Loss', 'Take Profit', 'Time Stop'
    commission: float  # 手续费
    
    def __repr__(self):
        direction_symbol = "📈" if self.direction == "long" else "📉"
        pnl_symbol = "✅" if self.pnl > 0 else "❌"
        return (f"{direction_symbol} {self.symbol} | "
                f"入场: {self.entry_price:.4f} → 出场: {self.exit_price:.4f} | "
                f"盈亏: {pnl_symbol} {self.pnl:.2f} U ({self.pnl_pct:.2f}%) | "
                f"原因: {self.exit_reason}")


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    direction: str
    entry_time: datetime
    entry_price: float
    stop_loss: float
    take_profit: float
    size: float
    entry_bar: int  # 入场K线索引
    

@dataclass
class BacktestResult:
    """回测结果"""
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list)
    initial_capital: float = INITIAL_CAPITAL
    final_capital: float = INITIAL_CAPITAL
    
    @property
    def total_trades(self) -> int:
        return len(self.trades)
    
    @property
    def win_trades(self) -> int:
        return len([t for t in self.trades if t.pnl > 0])
    
    @property
    def loss_trades(self) -> int:
        return len([t for t in self.trades if t.pnl <= 0])
    
    @property
    def win_rate(self) -> float:
        return (self.win_trades / self.total_trades * 100) if self.total_trades > 0 else 0
    
    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades)
    
    @property
    def total_commission(self) -> float:
        return sum(t.commission for t in self.trades)
    
    @property
    def roi(self) -> float:
        return (self.total_pnl / self.initial_capital * 100) if self.initial_capital > 0 else 0
    
    @property
    def avg_win(self) -> float:
        wins = [t.pnl for t in self.trades if t.pnl > 0]
        return np.mean(wins) if wins else 0
    
    @property
    def avg_loss(self) -> float:
        losses = [t.pnl for t in self.trades if t.pnl <= 0]
        return np.mean(losses) if losses else 0
    
    @property
    def profit_factor(self) -> float:
        """盈亏比（平均盈利/平均亏损）"""
        return abs(self.avg_win / self.avg_loss) if self.avg_loss != 0 else 0
    
    @property
    def max_drawdown(self) -> float:
        """最大回撤"""
        if not self.equity_curve:
            return 0
        equity = [e[1] for e in self.equity_curve]
        peak = equity[0]
        max_dd = 0
        for e in equity:
            if e > peak:
                peak = e
            dd = (peak - e) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd * 100
    
    def summary(self) -> str:
        """生成回测摘要"""
        return f"""
{'='*80}
                        📊 插针反弹策略回测报告
{'='*80}

【资金概况】
  初始资金: {self.initial_capital:,.2f} U
  最终资金: {self.final_capital:,.2f} U
  总收益:   {self.total_pnl:,.2f} U ({self.roi:+.2f}%)
  总手续费: {self.total_commission:,.2f} U

【交易统计】
  总交易次数: {self.total_trades}
  盈利次数:   {self.win_trades}
  亏损次数:   {self.loss_trades}
  胜率:       {self.win_rate:.2f}%

【盈亏分析】
  平均盈利:   {self.avg_win:.2f} U
  平均亏损:   {self.avg_loss:.2f} U
  盈亏比:     {self.profit_factor:.2f}:1
  最大回撤:   {self.max_drawdown:.2f}%

【风险指标】
  夏普比率:   {self._sharpe_ratio():.2f}
  收益回撤比: {self._calmar_ratio():.2f}

{'='*80}
"""
    
    def _sharpe_ratio(self) -> float:
        """计算夏普比率（假设无风险利率=0）"""
        if not self.trades:
            return 0
        returns = [t.pnl / self.initial_capital for t in self.trades]
        if len(returns) < 2:
            return 0
        return np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
    
    def _calmar_ratio(self) -> float:
        """计算卡玛比率（年化收益/最大回撤）"""
        if self.max_drawdown == 0:
            return 0
        return self.roi / self.max_drawdown if self.max_drawdown > 0 else 0


# ====================================================================================================
# ** 技术指标计算 **
# ====================================================================================================

def calc_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """计算ATR（Average True Range）"""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period, min_periods=period).mean()
    
    return atr


def calc_zscore(series: pd.Series, window: int = Z_WINDOW) -> pd.Series:
    """计算Z-Score"""
    mean = series.rolling(window, min_periods=window // 2).mean()
    std = series.rolling(window, min_periods=window // 2).std(ddof=0)
    return (series - mean) / std


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """计算所有技术指标"""
    df = df.copy()
    
    # 基础指标
    df["range"] = df["high"] - df["low"]
    df["body"] = (df["close"] - df["open"]).abs().replace(0, 1e-8)
    df["upper_shadow"] = df["high"] - df[["open", "close"]].max(axis=1)
    df["lower_shadow"] = df[["open", "close"]].min(axis=1) - df["low"]
    
    # ATR
    df["atr"] = calc_atr(df, ATR_PERIOD)
    
    # Z-Score
    df["range_z"] = calc_zscore(df["range"], Z_WINDOW)
    df["volume_z"] = calc_zscore(df["volume"], Z_WINDOW)
    
    # 成交量中位数
    df["volume_med"] = df["volume"].rolling(Z_WINDOW, min_periods=Z_WINDOW // 2).median()
    
    return df


# ====================================================================================================
# ** 插针信号检测 **
# ====================================================================================================

def detect_spike(row: pd.Series) -> Optional[str]:
    """
    检测插针信号
    
    Returns:
        "bullish": 下插针（做多信号）
        "bearish": 上插针（做空信号）
        None: 无信号
    """
    # 检查数据有效性
    if pd.isna(row["atr"]) or row["atr"] == 0:
        return None
    
    range_ratio = row["range"] / row["atr"]
    direction = None
    
    # 1. 检测主导影线（下影线 or 上影线）
    if row["lower_shadow"] >= SHADOW_RATIO * row["body"]:
        direction = "bullish"  # 下插针
    elif row["upper_shadow"] >= SHADOW_RATIO * row["body"]:
        direction = "bearish"  # 上插针
    else:
        return None
    
    # 2. 基础过滤：振幅 >= ATR_RATIO * ATR
    if range_ratio < ATR_RATIO:
        return None
    
    # 3. 基础过滤：波动量 Z-score
    if row["range_z"] < RANGE_Z_THRESHOLD:
        return None
    
    # 4. 基础过滤：成交量 Z-score
    if row["volume_z"] < VOLUME_Z_THRESHOLD:
        return None
    
    # 5. 增强过滤：振幅 >= ATR_MULTIPLIER * ATR
    if range_ratio < ATR_MULTIPLIER:
        return None
    
    # 6. 增强过滤：成交量 >= 中位数 × VOLUME_MULTIPLIER
    volume_med = row.get("volume_med", 0)
    if volume_med > 0 and row["volume"] < volume_med * VOLUME_MULTIPLIER:
        return None
    
    return direction


# ====================================================================================================
# ** 回测引擎 **
# ====================================================================================================

class SpikeStrategyBacktest:
    """插针反弹策略回测引擎"""
    
    def __init__(self):
        self.balance = INITIAL_CAPITAL
        self.positions: Dict[str, Position] = {}  # symbol -> Position
        self.result = BacktestResult(initial_capital=INITIAL_CAPITAL)
    
    def run_single_symbol(self, symbol: str, df: pd.DataFrame):
        """回测单个币种"""
        if df is None or len(df) < Z_WINDOW + ATR_PERIOD:
            return
        
        # 计算技术指标
        df = enrich_dataframe(df)
        
        # 逐根K线回测
        for i in range(Z_WINDOW + ATR_PERIOD, len(df)):
            current_time = df.iloc[i]["candle_begin_time"]
            current_bar = df.iloc[i]
            
            # 1. 检查是否有持仓需要处理
            if symbol in self.positions:
                self._check_exit(symbol, i, df)
            
            # 2. 如果没有持仓，检查开仓信号
            if symbol not in self.positions:
                prev_bar = df.iloc[i - 1]  # 前一根K线
                signal = detect_spike(prev_bar)
                
                if signal:
                    self._open_position(symbol, signal, i, df)
            
            # 3. 记录权益曲线
            self.result.equity_curve.append((current_time, self.balance))
    
    def _open_position(self, symbol: str, signal: str, bar_idx: int, df: pd.DataFrame):
        """开仓"""
        prev_bar = df.iloc[bar_idx - 1]  # 信号K线
        entry_bar = df.iloc[bar_idx]     # 入场K线（下一根）
        
        # 交易方向过滤
        if TRADE_DIRECTION == "long_only" and signal == "bearish":
            return
        if TRADE_DIRECTION == "short_only" and signal == "bullish":
            return
        
        direction = "long" if signal == "bullish" else "short"
        entry_price = entry_bar["open"]  # 在开盘价入场
        entry_time = entry_bar["candle_begin_time"]
        
        # 计算止损价格
        stop_loss = self._calc_stop_loss(prev_bar, entry_price, direction)
        
        # 计算止盈价格
        take_profit = self._calc_take_profit(prev_bar, entry_price, stop_loss, direction)
        
        # 检查止损距离是否合理
        if direction == "long":
            sl_distance = entry_price - stop_loss
        else:
            sl_distance = stop_loss - entry_price
        
        if sl_distance <= 0:
            return  # 止损距离无效，放弃交易
        
        # 计算仓位大小（固定风险）
        risk_amount = self.balance * RISK_PER_TRADE
        size = risk_amount / sl_distance  # 张数
        
        # 检查仓位限制
        max_size = self.balance * MAX_POSITION_SIZE / entry_price
        if size > max_size:
            size = max_size
        
        # 检查资金是否充足
        required_margin = size * entry_price / LEVERAGE
        if required_margin > self.balance * 0.9:  # 留10%作为保证金
            return
        
        # 创建持仓
        position = Position(
            symbol=symbol,
            direction=direction,
            entry_time=entry_time,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            size=size,
            entry_bar=bar_idx
        )
        
        self.positions[symbol] = position
    
    def _check_exit(self, symbol: str, bar_idx: int, df: pd.DataFrame):
        """检查平仓条件"""
        position = self.positions[symbol]
        current_bar = df.iloc[bar_idx]
        
        exit_price = None
        exit_reason = None
        
        # 1. 检查止损止盈
        if position.direction == "long":
            if current_bar["low"] <= position.stop_loss:
                exit_price = position.stop_loss
                exit_reason = "Stop Loss"
            elif current_bar["high"] >= position.take_profit:
                exit_price = position.take_profit
                exit_reason = "Take Profit"
        else:  # short
            if current_bar["high"] >= position.stop_loss:
                exit_price = position.stop_loss
                exit_reason = "Stop Loss"
            elif current_bar["low"] <= position.take_profit:
                exit_price = position.take_profit
                exit_reason = "Take Profit"
        
        # 2. 检查时间止损
        if USE_TIME_STOP and exit_price is None:
            bars_held = bar_idx - position.entry_bar
            if bars_held >= TIME_STOP_BARS:
                exit_price = current_bar["close"]
                exit_reason = "Time Stop"
        
        # 3. 如果触发平仓，执行平仓
        if exit_price is not None:
            self._close_position(symbol, exit_price, current_bar["candle_begin_time"], exit_reason)
    
    def _close_position(self, symbol: str, exit_price: float, exit_time: datetime, exit_reason: str):
        """平仓"""
        position = self.positions.pop(symbol)
        
        # 计算盈亏
        if position.direction == "long":
            pnl_raw = (exit_price - position.entry_price) * position.size
        else:
            pnl_raw = (position.entry_price - exit_price) * position.size
        
        # 扣除手续费（双边）
        commission = (position.entry_price * position.size + exit_price * position.size) * COMMISSION_RATE
        pnl_net = pnl_raw - commission
        
        # 更新余额
        self.balance += pnl_net
        
        # 记录交易
        pnl_pct = (pnl_net / (position.entry_price * position.size)) * 100
        
        trade = Trade(
            symbol=symbol,
            entry_time=position.entry_time,
            exit_time=exit_time,
            direction=position.direction,
            entry_price=position.entry_price,
            exit_price=exit_price,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            size=position.size,
            pnl=pnl_net,
            pnl_pct=pnl_pct,
            exit_reason=exit_reason,
            commission=commission
        )
        
        self.result.trades.append(trade)
    
    def _calc_stop_loss(self, signal_bar: pd.Series, entry_price: float, direction: str) -> float:
        """计算止损价格"""
        if STOP_LOSS_TYPE == "extreme":
            # 使用插针极值点
            if direction == "long":
                return signal_bar["low"]  # 下插针的最低点
            else:
                return signal_bar["high"]  # 上插针的最高点
        
        elif STOP_LOSS_TYPE == "atr":
            # 使用ATR倍数
            atr = signal_bar["atr"]
            if direction == "long":
                return entry_price - (atr * STOP_LOSS_ATR_MULTIPLIER)
            else:
                return entry_price + (atr * STOP_LOSS_ATR_MULTIPLIER)
        
        elif STOP_LOSS_TYPE == "percent":
            # 使用固定百分比
            if direction == "long":
                return entry_price * (1 - STOP_LOSS_PERCENT)
            else:
                return entry_price * (1 + STOP_LOSS_PERCENT)
        
        else:
            raise ValueError(f"未知的止损类型: {STOP_LOSS_TYPE}")
    
    def _calc_take_profit(self, signal_bar: pd.Series, entry_price: float, stop_loss: float, direction: str) -> float:
        """计算止盈价格"""
        if TAKE_PROFIT_TYPE == "risk_reward":
            # 固定盈亏比
            if direction == "long":
                risk = entry_price - stop_loss
                return entry_price + (risk * RISK_REWARD_RATIO)
            else:
                risk = stop_loss - entry_price
                return entry_price - (risk * RISK_REWARD_RATIO)
        
        elif TAKE_PROFIT_TYPE == "atr":
            # ATR倍数
            atr = signal_bar["atr"]
            if direction == "long":
                return entry_price + (atr * TAKE_PROFIT_ATR_MULTIPLIER)
            else:
                return entry_price - (atr * TAKE_PROFIT_ATR_MULTIPLIER)
        
        elif TAKE_PROFIT_TYPE == "percent":
            # 固定百分比
            if direction == "long":
                return entry_price * (1 + TAKE_PROFIT_PERCENT)
            else:
                return entry_price * (1 - TAKE_PROFIT_PERCENT)
        
        else:
            raise ValueError(f"未知的止盈类型: {TAKE_PROFIT_TYPE}")
    
    def finalize(self):
        """结束回测，更新最终资金"""
        self.result.final_capital = self.balance


# ====================================================================================================
# ** 数据加载 **
# ====================================================================================================

def load_symbol_data(symbol_file: Path) -> Tuple[str, pd.DataFrame]:
    """
    加载单个币种的数据
    
    Returns:
        (symbol_name, dataframe)
    """
    try:
        # 提取币种名称（例如：BTC-USDT.csv -> BTC-USDT）
        symbol_name = symbol_file.stem
        
        # 读取CSV（跳过第一行广告，尝试多种编码）
        df = None
        for encoding in ['gbk', 'gb18030', 'gb2312', 'utf-8', 'latin1']:
            try:
                df = pd.read_csv(symbol_file, skiprows=1, encoding=encoding)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        
        if df is None:
            raise ValueError("无法识别文件编码")
        
        # 数据清洗
        df = df[['candle_begin_time', 'open', 'high', 'low', 'close', 'volume', 'quote_volume']].copy()
        df['candle_begin_time'] = pd.to_datetime(df['candle_begin_time'])
        
        # 转换数值类型
        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 删除缺失值
        df = df.dropna()
        
        # 时间范围过滤
        df = df[(df['candle_begin_time'] >= start_date) & (df['candle_begin_time'] <= end_date)]
        
        # 最少K线数量过滤
        if len(df) < MIN_KLINE_NUM:
            return symbol_name, None
        
        # 成交额过滤（剔除低流动性币种）
        avg_quote_volume = df['quote_volume'].mean()
        if avg_quote_volume < MIN_VOLUME_USDT:
            return symbol_name, None
        
        return symbol_name, df
    
    except Exception as e:
        print(f"⚠️  加载 {symbol_file.name} 失败: {e}")
        return None, None


def load_all_data() -> Dict[str, pd.DataFrame]:
    """加载所有币种数据"""
    print("📂 正在加载数据...")
    
    all_files = list(data_path.glob("*.csv"))
    print(f"   发现 {len(all_files)} 个数据文件")
    
    data_dict = {}
    skipped = 0
    
    for file in all_files:
        symbol, df = load_symbol_data(file)
        
        if symbol is None or df is None or df.empty:
            skipped += 1
            continue
        
        # 黑名单过滤
        if symbol in BLACK_LIST:
            skipped += 1
            continue
        
        # 稳定币过滤
        if any(stable in symbol for stable in STABLE_SYMBOLS):
            skipped += 1
            continue
        
        data_dict[symbol] = df
    
    print(f"✅ 成功加载 {len(data_dict)} 个币种")
    print(f"⏭️  跳过 {skipped} 个币种（数据不足/黑名单/稳定币）\n")
    
    return data_dict


# ====================================================================================================
# ** 主程序 **
# ====================================================================================================

def main():
    print("="*80)
    print("                  🚀 插针反弹策略回测系统 V1.0")
    print("="*80)
    print(f"策略名称: {backtest_name}")
    print(f"回测时间: {start_date} ~ {end_date}")
    print(f"初始资金: {INITIAL_CAPITAL:,.0f} U")
    print(f"单笔风险: {RISK_PER_TRADE*100:.1f}%")
    print(f"盈亏比:   {RISK_REWARD_RATIO:.1f}:1")
    print(f"交易方向: {TRADE_DIRECTION}")
    print(f"止损策略: {STOP_LOSS_TYPE}")
    print(f"止盈策略: {TAKE_PROFIT_TYPE}")
    print(f"时间止损: {'启用 (' + str(TIME_STOP_BARS) + ' 根K线)' if USE_TIME_STOP else '禁用'}")
    print("="*80 + "\n")
    
    # 1. 加载数据
    data_dict = load_all_data()
    
    if not data_dict:
        print("❌ 没有可用的数据，退出回测")
        return
    
    # 2. 初始化回测引擎
    print("🔧 初始化回测引擎...")
    engine = SpikeStrategyBacktest()
    
    # 3. 运行回测
    print("🚀 开始回测...\n")
    
    total_symbols = len(data_dict)
    for idx, (symbol, df) in enumerate(data_dict.items(), 1):
        print(f"[{idx}/{total_symbols}] 回测 {symbol:20s} | K线数: {len(df):5d}", end="")
        
        try:
            engine.run_single_symbol(symbol, df)
            print(f" | ✅ 完成")
        except Exception as e:
            print(f" | ❌ 错误: {e}")
    
    # 4. 完成回测
    engine.finalize()
    
    # 5. 输出结果
    print("\n" + "="*80)
    print("                        📊 回测完成！")
    print("="*80)
    
    print(engine.result.summary())
    
    # 6. 保存回测结果
    if SAVE_TRADE_DETAILS and engine.result.trades:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 6.1 保存回测汇总
        summary_file = output_path / f"{backtest_name}_{timestamp}_summary.csv"
        summary_data = {
            "指标": [
                "初始资金(U)", "最终资金(U)", "总收益(U)", "收益率(%)", 
                "总手续费(U)", "总交易次数", "盈利次数", "亏损次数", 
                "胜率(%)", "平均盈利(U)", "平均亏损(U)", "盈亏比", 
                "最大回撤(%)", "夏普比率", "收益回撤比"
            ],
            "数值": [
                f"{engine.result.initial_capital:,.2f}",
                f"{engine.result.final_capital:,.2f}",
                f"{engine.result.total_pnl:,.2f}",
                f"{engine.result.roi:+.2f}",
                f"{engine.result.total_commission:,.2f}",
                engine.result.total_trades,
                engine.result.win_trades,
                engine.result.loss_trades,
                f"{engine.result.win_rate:.2f}",
                f"{engine.result.avg_win:.2f}",
                f"{engine.result.avg_loss:.2f}",
                f"{engine.result.profit_factor:.2f}",
                f"{engine.result.max_drawdown:.2f}",
                f"{engine.result._sharpe_ratio():.2f}",
                f"{engine.result._calmar_ratio():.2f}"
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_csv(summary_file, index=False, encoding='utf-8-sig')
        print(f"\n✅ 回测汇总已保存: {summary_file}")
        
        # 6.2 保存交易明细
        trades_file = output_path / f"{backtest_name}_{timestamp}_trades.csv"
        trades_df = pd.DataFrame([
            {
                "币种": t.symbol,
                "方向": t.direction,
                "入场时间": t.entry_time,
                "出场时间": t.exit_time,
                "入场价": t.entry_price,
                "出场价": t.exit_price,
                "止损价": t.stop_loss,
                "止盈价": t.take_profit,
                "仓位": t.size,
                "盈亏(U)": t.pnl,
                "盈亏(%)": t.pnl_pct,
                "手续费": t.commission,
                "平仓原因": t.exit_reason,
            }
            for t in engine.result.trades
        ])
        
        trades_df.to_csv(trades_file, index=False, encoding='utf-8-sig')
        print(f"✅ 交易明细已保存: {trades_file}")
    
    # 7. 显示前10笔交易
    if engine.result.trades:
        print("\n" + "="*80)
        print("                    📋 交易明细（前10笔）")
        print("="*80)
        for trade in engine.result.trades[:10]:
            print(trade)
        
        if len(engine.result.trades) > 10:
            print(f"\n... 还有 {len(engine.result.trades) - 10} 笔交易 ...")
    
    print("\n" + "="*80)
    print("                        ✅ 全部完成！")
    print("="*80)


if __name__ == "__main__":
    main()

