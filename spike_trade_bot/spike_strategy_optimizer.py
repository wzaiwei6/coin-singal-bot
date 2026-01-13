#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@Author: will
@Date: 2025-11-21
@Description: 插针策略参数优化工具
----------------------------------------------------------------------------------------------------

网格搜索最优参数组合：
- 盈亏比（Risk-Reward Ratio）
- 止损类型
- 时间止损周期
- 成交量过滤倍数

执行方式：
    python spike_strategy_optimizer.py
"""

import pandas as pd
from pathlib import Path
from itertools import product
from datetime import datetime
from typing import List, Dict, Tuple

from spike_strategy_backtest import SpikeStrategyBacktest, load_symbol_data
import spike_strategy_config as config

# ====================================================================================================
# ** 参数优化配置 **
# ====================================================================================================

# 要优化的参数范围
PARAM_GRID = {
    "RISK_REWARD_RATIO": [1.5, 2.0, 2.5, 3.0],
    "TIME_STOP_BARS": [12, 24, 48],
    "VOLUME_MULTIPLIER": [1.5, 2.0, 2.5],
    "ATR_MULTIPLIER": [1.5, 2.0, 2.5],
}

# 测试币种（减少币种加快优化速度）
TEST_SYMBOLS = [
    'BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'BNB-USDT',  'DOGE-USDT'
]

# 优化目标（选择一个作为主要优化指标）
OPTIMIZATION_METRIC = "sharpe_ratio"  # 可选: "roi", "sharpe_ratio", "profit_factor", "calmar_ratio"

# 测试时间范围（使用配置文件中的时间范围）
TEST_START_DATE = config.start_date
TEST_END_DATE = config.end_date


# ====================================================================================================
# ** 优化引擎 **
# ====================================================================================================

class ParameterOptimizer:
    """参数优化器"""
    
    def __init__(self):
        self.results: List[Dict] = []
        self.data_dict = self._load_test_data()
    
    def _load_test_data(self) -> Dict[str, pd.DataFrame]:
        """加载测试数据"""
        print("="*80)
        print("                  📂 加载测试数据")
        print("="*80)
        print(f"测试币种: {', '.join(TEST_SYMBOLS)}")
        print(f"测试时间: {TEST_START_DATE} ~ {TEST_END_DATE}\n")
        
        data_dict = {}
        
        for symbol in TEST_SYMBOLS:
            symbol_file = config.data_path / f"{symbol}.csv"
            
            if not symbol_file.exists():
                print(f"⚠️  {symbol:15s} | 文件不存在")
                continue
            
            symbol_name, df = load_symbol_data(symbol_file)
            
            if df is None or df.empty:
                print(f"⚠️  {symbol:15s} | 数据加载失败")
                continue
            
            # 过滤时间范围
            df = df[(df['candle_begin_time'] >= TEST_START_DATE) & 
                    (df['candle_begin_time'] <= TEST_END_DATE)]
            
            if len(df) < 200:
                print(f"⚠️  {symbol:15s} | 数据不足 ({len(df)} 根)")
                continue
            
            data_dict[symbol] = df
            print(f"✅ {symbol:15s} | {len(df):5d} 根K线")
        
        print(f"\n✅ 成功加载 {len(data_dict)} 个币种\n")
        return data_dict
    
    def run_backtest_with_params(self, params: Dict) -> Dict:
        """使用指定参数运行回测"""
        # 临时修改配置
        original_config = {}
        for key, value in params.items():
            if hasattr(config, key):
                original_config[key] = getattr(config, key)
                setattr(config, key, value)
        
        # 重新导入模块以应用新参数（重要！）
        import importlib
        import spike_strategy_backtest
        importlib.reload(spike_strategy_backtest)
        from spike_strategy_backtest import SpikeStrategyBacktest
        
        try:
            # 运行回测
            engine = SpikeStrategyBacktest()
            
            for symbol, df in self.data_dict.items():
                engine.run_single_symbol(symbol, df)
            
            engine.finalize()
            
            # 提取指标
            result = {
                "params": params.copy(),
                "total_trades": engine.result.total_trades,
                "win_rate": engine.result.win_rate,
                "roi": engine.result.roi,
                "max_drawdown": engine.result.max_drawdown,
                "profit_factor": engine.result.profit_factor,
                "sharpe_ratio": engine.result._sharpe_ratio(),
                "calmar_ratio": engine.result._calmar_ratio(),
                "final_capital": engine.result.final_capital,
            }
            
            return result
        
        finally:
            # 恢复原始配置
            for key, value in original_config.items():
                setattr(config, key, value)
    
    def optimize(self):
        """网格搜索优化"""
        print("="*80)
        print("                  🔧 开始参数优化")
        print("="*80)
        print(f"优化目标: {OPTIMIZATION_METRIC}")
        print(f"参数网格:")
        for key, values in PARAM_GRID.items():
            print(f"  - {key}: {values}")
        
        # 生成所有参数组合
        param_names = list(PARAM_GRID.keys())
        param_values = list(PARAM_GRID.values())
        param_combinations = list(product(*param_values))
        
        total_combinations = len(param_combinations)
        print(f"\n总共 {total_combinations} 种参数组合\n")
        print("="*80 + "\n")
        
        # 遍历所有组合
        for idx, combination in enumerate(param_combinations, 1):
            params = dict(zip(param_names, combination))
            
            print(f"[{idx}/{total_combinations}] 测试参数组合:")
            for key, value in params.items():
                print(f"  {key:20s} = {value}")
            
            try:
                result = self.run_backtest_with_params(params)
                self.results.append(result)
                
                print(f"  📊 结果: 交易={result['total_trades']}, "
                      f"胜率={result['win_rate']:.1f}%, "
                      f"ROI={result['roi']:.2f}%, "
                      f"夏普={result['sharpe_ratio']:.2f}")
                print()
                
            except Exception as e:
                print(f"  ❌ 错误: {e}\n")
                continue
        
        print("="*80)
        print("                  ✅ 优化完成！")
        print("="*80 + "\n")
    
    def get_best_params(self) -> Dict:
        """获取最优参数"""
        if not self.results:
            return {}
        
        # 过滤：至少要有一定数量的交易
        valid_results = [r for r in self.results if r['total_trades'] >= 10]
        
        if not valid_results:
            print("⚠️  所有参数组合的交易次数都太少（< 10笔）")
            return {}
        
        # 根据优化目标排序
        if OPTIMIZATION_METRIC == "roi":
            best = max(valid_results, key=lambda x: x['roi'])
        elif OPTIMIZATION_METRIC == "sharpe_ratio":
            best = max(valid_results, key=lambda x: x['sharpe_ratio'])
        elif OPTIMIZATION_METRIC == "profit_factor":
            best = max(valid_results, key=lambda x: x['profit_factor'])
        elif OPTIMIZATION_METRIC == "calmar_ratio":
            best = max(valid_results, key=lambda x: x['calmar_ratio'])
        else:
            best = max(valid_results, key=lambda x: x['roi'])
        
        return best
    
    def save_results(self, output_file: Path):
        """保存所有结果"""
        if not self.results:
            print("⚠️  没有结果可保存")
            return
        
        # 展开参数字典
        rows = []
        for result in self.results:
            row = result['params'].copy()
            row.update({
                k: v for k, v in result.items() if k != 'params'
            })
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        # 按优化目标排序
        df = df.sort_values(OPTIMIZATION_METRIC, ascending=False)
        
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"💾 优化结果已保存: {output_file}")
    
    def print_summary(self):
        """打印优化摘要"""
        if not self.results:
            print("⚠️  没有优化结果")
            return
        
        best = self.get_best_params()
        
        if not best:
            return
        
        print("="*80)
        print("                  🏆 最优参数组合")
        print("="*80)
        print(f"\n优化目标: {OPTIMIZATION_METRIC}\n")
        
        print("【最优参数】")
        for key, value in best['params'].items():
            print(f"  {key:25s} = {value}")
        
        print("\n【回测表现】")
        print(f"  总交易次数: {best['total_trades']}")
        print(f"  胜率:       {best['win_rate']:.2f}%")
        print(f"  总收益率:   {best['roi']:.2f}%")
        print(f"  最大回撤:   {best['max_drawdown']:.2f}%")
        print(f"  盈亏比:     {best['profit_factor']:.2f}")
        print(f"  夏普比率:   {best['sharpe_ratio']:.2f}")
        print(f"  卡玛比率:   {best['calmar_ratio']:.2f}")
        print(f"  最终资金:   {best['final_capital']:,.2f} U")
        
        print("\n" + "="*80)
        
        # 前5名对比
        print("\n" + "="*80)
        print("                  📊 前5名参数对比")
        print("="*80 + "\n")
        
        valid_results = [r for r in self.results if r['total_trades'] >= 10]
        
        if OPTIMIZATION_METRIC == "roi":
            top5 = sorted(valid_results, key=lambda x: x['roi'], reverse=True)[:5]
        elif OPTIMIZATION_METRIC == "sharpe_ratio":
            top5 = sorted(valid_results, key=lambda x: x['sharpe_ratio'], reverse=True)[:5]
        elif OPTIMIZATION_METRIC == "profit_factor":
            top5 = sorted(valid_results, key=lambda x: x['profit_factor'], reverse=True)[:5]
        else:
            top5 = sorted(valid_results, key=lambda x: x['roi'], reverse=True)[:5]
        
        for idx, result in enumerate(top5, 1):
            print(f"第 {idx} 名:")
            print(f"  参数: RR={result['params']['RISK_REWARD_RATIO']}, "
                  f"TimeStop={result['params']['TIME_STOP_BARS']}, "
                  f"VolMul={result['params']['VOLUME_MULTIPLIER']}, "
                  f"ATRMul={result['params']['ATR_MULTIPLIER']}")
            print(f"  表现: ROI={result['roi']:.2f}%, "
                  f"胜率={result['win_rate']:.1f}%, "
                  f"夏普={result['sharpe_ratio']:.2f}, "
                  f"回撤={result['max_drawdown']:.2f}%")
            print()


# ====================================================================================================
# ** 主程序 **
# ====================================================================================================

def main():
    print("\n" + "="*80)
    print("                  🚀 插针策略参数优化器")
    print("="*80)
    print(f"初始资金: {config.INITIAL_CAPITAL:,.0f} U")
    print(f"测试币种数: {len(TEST_SYMBOLS)}")
    print(f"测试时间: {TEST_START_DATE} ~ {TEST_END_DATE}")
    print("="*80 + "\n")
    
    # 创建优化器
    optimizer = ParameterOptimizer()
    
    if not optimizer.data_dict:
        print("❌ 没有可用的测试数据")
        return
    
    # 运行优化
    optimizer.optimize()
    
    # 打印摘要
    optimizer.print_summary()
    
    # 保存结果
    output_file = config.output_path / f"optimization_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    optimizer.save_results(output_file)
    
    print("\n" + "="*80)
    print("                  ✅ 优化完成！")
    print("="*80)
    print("\n💡 下一步:")
    print("  1. 查看优化结果CSV文件，对比不同参数的表现")
    print("  2. 将最优参数更新到 spike_strategy_config.py")
    print("  3. 运行完整回测验证效果")
    print("  4. 小资金实盘验证")


if __name__ == "__main__":
    main()

