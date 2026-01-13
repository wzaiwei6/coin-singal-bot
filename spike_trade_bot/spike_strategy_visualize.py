#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@Author: will
@Date: 2025-11-21
@Description: 插针策略回测结果可视化
----------------------------------------------------------------------------------------------------

生成权益曲线、胜率分析、盈亏分布等图表

执行方式：
    python spike_strategy_visualize.py <交易记录CSV文件路径>
"""

import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def plot_equity_curve(trades_df: pd.DataFrame, output_path: Path):
    """绘制权益曲线"""
    trades_df = trades_df.sort_values('出场时间')
    trades_df['累计盈亏'] = trades_df['盈亏(U)'].cumsum()
    
    fig, ax = plt.subplots(figsize=(14, 6))
    
    ax.plot(trades_df['出场时间'], trades_df['累计盈亏'], 
            linewidth=2, color='#2E86DE', label='权益曲线')
    ax.axhline(y=0, color='red', linestyle='--', linewidth=1, alpha=0.5, label='初始资金')
    ax.fill_between(trades_df['出场时间'], 0, trades_df['累计盈亏'], 
                     where=trades_df['累计盈亏'] >= 0, alpha=0.3, color='green', label='盈利区域')
    ax.fill_between(trades_df['出场时间'], 0, trades_df['累计盈亏'], 
                     where=trades_df['累计盈亏'] < 0, alpha=0.3, color='red', label='亏损区域')
    
    ax.set_xlabel('时间', fontsize=12)
    ax.set_ylabel('累计盈亏 (U)', fontsize=12)
    ax.set_title('📈 插针策略权益曲线', fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path / 'equity_curve.png', dpi=150, bbox_inches='tight')
    print(f"✅ 权益曲线已保存: {output_path / 'equity_curve.png'}")
    plt.close()


def plot_pnl_distribution(trades_df: pd.DataFrame, output_path: Path):
    """绘制盈亏分布"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # 盈亏直方图
    ax1.hist(trades_df['盈亏(U)'], bins=50, color='#3498db', edgecolor='black', alpha=0.7)
    ax1.axvline(x=0, color='red', linestyle='--', linewidth=2)
    ax1.set_xlabel('单笔盈亏 (U)', fontsize=12)
    ax1.set_ylabel('交易次数', fontsize=12)
    ax1.set_title('💰 盈亏分布', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    
    # 盈亏百分比分布
    ax2.hist(trades_df['盈亏(%)'], bins=50, color='#e74c3c', edgecolor='black', alpha=0.7)
    ax2.axvline(x=0, color='red', linestyle='--', linewidth=2)
    ax2.set_xlabel('盈亏百分比 (%)', fontsize=12)
    ax2.set_ylabel('交易次数', fontsize=12)
    ax2.set_title('📊 盈亏百分比分布', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path / 'pnl_distribution.png', dpi=150, bbox_inches='tight')
    print(f"✅ 盈亏分布已保存: {output_path / 'pnl_distribution.png'}")
    plt.close()


def plot_win_rate_by_direction(trades_df: pd.DataFrame, output_path: Path):
    """按方向统计胜率"""
    direction_stats = trades_df.groupby('方向').apply(
        lambda x: pd.Series({
            '总交易': len(x),
            '盈利次数': (x['盈亏(U)'] > 0).sum(),
            '胜率': (x['盈亏(U)'] > 0).sum() / len(x) * 100 if len(x) > 0 else 0
        })
    )
    
    fig, ax = plt.subplots(figsize=(8, 6))
    
    direction_stats['胜率'].plot(kind='bar', ax=ax, color=['#27ae60', '#e74c3c'], 
                                  edgecolor='black', linewidth=1.5, alpha=0.8)
    
    ax.set_xlabel('交易方向', fontsize=12)
    ax.set_ylabel('胜率 (%)', fontsize=12)
    ax.set_title('🎯 多空胜率对比', fontsize=14, fontweight='bold')
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)
    ax.grid(True, alpha=0.3, axis='y')
    
    # 在柱子上显示数值
    for i, (idx, row) in enumerate(direction_stats.iterrows()):
        ax.text(i, row['胜率'] + 2, f"{row['胜率']:.1f}%\n({int(row['盈利次数'])}/{int(row['总交易'])})", 
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path / 'win_rate_by_direction.png', dpi=150, bbox_inches='tight')
    print(f"✅ 多空胜率对比已保存: {output_path / 'win_rate_by_direction.png'}")
    plt.close()


def plot_exit_reason_distribution(trades_df: pd.DataFrame, output_path: Path):
    """平仓原因分布"""
    exit_counts = trades_df['平仓原因'].value_counts()
    
    fig, ax = plt.subplots(figsize=(8, 6))
    
    colors = {'Stop Loss': '#e74c3c', 'Take Profit': '#27ae60', 'Time Stop': '#f39c12'}
    wedges, texts, autotexts = ax.pie(exit_counts, labels=exit_counts.index, autopct='%1.1f%%',
                                        colors=[colors.get(x, '#95a5a6') for x in exit_counts.index],
                                        startangle=90, textprops={'fontsize': 11, 'weight': 'bold'})
    
    ax.set_title('🚪 平仓原因分布', fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path / 'exit_reason_distribution.png', dpi=150, bbox_inches='tight')
    print(f"✅ 平仓原因分布已保存: {output_path / 'exit_reason_distribution.png'}")
    plt.close()


def plot_top_symbols(trades_df: pd.DataFrame, output_path: Path, top_n: int = 10):
    """表现最好的币种"""
    symbol_pnl = trades_df.groupby('币种')['盈亏(U)'].sum().sort_values(ascending=False).head(top_n)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    colors = ['#27ae60' if x >= 0 else '#e74c3c' for x in symbol_pnl.values]
    symbol_pnl.plot(kind='barh', ax=ax, color=colors, edgecolor='black', linewidth=1.5, alpha=0.8)
    
    ax.set_xlabel('累计盈亏 (U)', fontsize=12)
    ax.set_ylabel('币种', fontsize=12)
    ax.set_title(f'🏆 表现最好的 {top_n} 个币种', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout()
    plt.savefig(output_path / 'top_symbols.png', dpi=150, bbox_inches='tight')
    print(f"✅ 最佳币种统计已保存: {output_path / 'top_symbols.png'}")
    plt.close()


def generate_all_plots(csv_file: str):
    """生成所有图表"""
    csv_path = Path(csv_file)
    
    if not csv_path.exists():
        print(f"❌ 文件不存在: {csv_file}")
        return
    
    print(f"📂 读取交易记录: {csv_file}")
    trades_df = pd.read_csv(csv_file, encoding='utf-8-sig')
    
    # 解析时间列
    trades_df['入场时间'] = pd.to_datetime(trades_df['入场时间'])
    trades_df['出场时间'] = pd.to_datetime(trades_df['出场时间'])
    
    # 创建输出目录
    output_dir = csv_path.parent / f"plots_{csv_path.stem}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n🎨 开始生成图表...")
    print(f"📁 输出目录: {output_dir}\n")
    
    # 生成各类图表
    plot_equity_curve(trades_df, output_dir)
    plot_pnl_distribution(trades_df, output_dir)
    plot_win_rate_by_direction(trades_df, output_dir)
    plot_exit_reason_distribution(trades_df, output_dir)
    plot_top_symbols(trades_df, output_dir)
    
    print(f"\n✅ 所有图表生成完成！")
    print(f"📂 查看图表: {output_dir}")


def main():
    if len(sys.argv) < 2:
        print("使用方法: python spike_strategy_visualize.py <交易记录CSV文件>")
        print("示例:   python spike_strategy_visualize.py backtest_results/spike_strategy/插针反弹策略_V1.0_20251121_120000.csv")
        return
    
    csv_file = sys.argv[1]
    generate_all_plots(csv_file)


if __name__ == "__main__":
    main()

