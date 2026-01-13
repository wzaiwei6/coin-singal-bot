# 🎯 插针反弹策略 - 完整使用指南

## 📁 文件清单

```
select-coin-2/
├── spike_strategy_config.py         # ⚙️  策略配置（所有参数）
├── spike_strategy_backtest.py       # 🚀 回测主程序
├── spike_strategy_quick_test.py     # 🧪 快速测试（少量币种）
├── spike_strategy_optimizer.py      # 🔧 参数优化工具
├── spike_strategy_visualize.py      # 📊 结果可视化
├── spike_strategy_README.md         # 📖 详细策略说明
└── SPIKE_STRATEGY_GUIDE.md          # 📋 本文档（快速指南）
```

---

## 🚀 三步快速上手

### 第一步：快速测试（验证代码能跑）

```bash
cd /Users/wang/PythonProjects/xingda/xbx_coin_part_2/select-coin-2/

python spike_strategy_quick_test.py
```

选择 `1. 快速回测`，会测试 BTC、ETH、SOL、DOGE、BNB 五个币种。

**预期结果**：
- ✅ 如果看到交易记录和回测报告 → 成功！进入第二步
- ❌ 如果没有交易信号 → 参数太严格，见下方"调参指南"

---

### 第二步：参数优化（找到最优参数）

```bash
python spike_strategy_optimizer.py
```

会自动测试多种参数组合，找出最优参数。

**输出**：
- 终端显示最优参数
- 保存 CSV 文件：`backtest_results/spike_strategy/optimization_results_XXXXXXXX.csv`

**下一步**：
1. 查看最优参数
2. 更新到 `spike_strategy_config.py`
3. 进入第三步

---

### 第三步：完整回测（所有币种）

```bash
python spike_strategy_backtest.py
```

会回测所有币种（可能需要5-30分钟，取决于币种数量）。

**输出**：
- 终端显示完整回测报告
- 保存交易明细：`backtest_results/spike_strategy/插针反弹策略_V1.0_XXXXXXXX.csv`

---

### 第四步：可视化分析

```bash
python spike_strategy_visualize.py backtest_results/spike_strategy/插针反弹策略_V1.0_XXXXXXXX.csv
```

**输出**：生成 5 张图表
1. 📈 权益曲线
2. 💰 盈亏分布
3. 🎯 多空胜率对比
4. 🚪 平仓原因分布
5. 🏆 最佳币种排名

---

## ⚙️ 快速调参指南

所有参数在 `spike_strategy_config.py` 中修改。

### 🔴 问题：没有交易信号

**原因**：过滤条件太严格

**解决方法**：降低过滤标准

```python
# 在 spike_strategy_config.py 中修改：

ATR_MULTIPLIER = 1.5         # 从 2.0 降到 1.5（更宽松）
VOLUME_MULTIPLIER = 1.5      # 从 2.0 降到 1.5（更宽松）
SHADOW_RATIO = 1.5           # 从 2.0 降到 1.5（更宽松）
```

---

### 🟠 问题：胜率太低（< 30%）

**原因**：止盈太贪，盈亏比太高

**解决方法**：降低盈亏比

```python
RISK_REWARD_RATIO = 1.5      # 从 2.0 降到 1.5（更容易止盈）
```

---

### 🟡 问题：最大回撤太大（> 20%）

**原因**：单笔风险太高

**解决方法**：降低风险

```python
RISK_PER_TRADE = 0.01        # 从 2% 降到 1%（更保守）
MAX_POSITION_SIZE = 0.2      # 从 30% 降到 20%（单币种仓位限制）
```

---

### 🟢 问题：想提高收益（在回撤可控的前提下）

**方法1：提高盈亏比**
```python
RISK_REWARD_RATIO = 2.5      # 从 2.0 提到 2.5（追求更大利润）
```

**方法2：缩短时间止损**
```python
TIME_STOP_BARS = 12          # 从 24 改为 12（快进快出）
```

**方法3：只做多或只做空**
```python
TRADE_DIRECTION = "long_only"   # 如果发现做多表现更好
# 或
TRADE_DIRECTION = "short_only"  # 如果发现做空表现更好
```

---

## 📊 如何评价回测结果

### ✅ 优秀策略的特征

```
ROI > 30%              # 年化收益 > 30%
最大回撤 < 15%          # 回撤控制在 15% 以内
夏普比率 > 1.5         # 风险调整后收益
盈亏比 > 2.0           # 平均盈利是平均亏损的 2 倍以上
胜率 > 35%             # 胜率不需要太高，但要 > 35%
```

### ⚠️ 需要优化的信号

```
ROI < 10%              # 收益太低 → 提高盈亏比或优化过滤条件
最大回撤 > 25%          # 回撤太大 → 降低单笔风险
夏普比率 < 1.0         # 风险收益比不佳 → 优化止损止盈
盈亏比 < 1.5           # 盈亏不对称 → 提高盈亏比
胜率 < 25%             # 胜率太低 → 降低盈亏比或加入趋势过滤
```

---

## 🧪 测试工作流程

### 推荐流程（避免过度拟合）

```
1. 快速测试（验证逻辑）
   ↓
2. 样本内优化（找最优参数）
   - 测试时间：2024年1月-6月
   ↓
3. 样本外验证（验证参数是否过拟合）
   - 测试时间：2024年7月-12月
   - 如果表现差距太大 → 过拟合，重新优化
   ↓
4. 完整回测（全部数据）
   - 测试时间：2021年-2024年
   ↓
5. 小资金实盘验证（最关键！）
   - 用 1000U 跑 1-2 个月
   - 如果表现稳定 → 逐步加大资金
```

---

## 💡 进阶优化方向

### 1️⃣ 加入趋势过滤

在 `spike_strategy_backtest.py` 的 `detect_spike()` 后增加：

```python
# 计算20日均线
ma_20 = df['close'].rolling(20).mean()

# 只在上升趋势中做多
if signal == "bullish" and current_price < ma_20:
    return None

# 只在下降趋势中做空
if signal == "bearish" and current_price > ma_20:
    return None
```

### 2️⃣ 动态止盈（保本止损）

在 `_check_exit()` 中增加：

```python
# 盈利达到1倍风险时，移动止损到成本价
if position.direction == "long":
    profit_distance = current_bar["close"] - position.entry_price
    risk_distance = position.entry_price - position.stop_loss
    
    if profit_distance >= risk_distance:
        position.stop_loss = position.entry_price  # 保本止损
```

### 3️⃣ 多周期确认

```python
# 1小时插针 + 15分钟确认反弹
# 需要加载 15 分钟数据
```

### 4️⃣ 结合资金费率

```python
# 资金费率 > 0.1% 且上插针 → 做空（多头过热）
# 资金费率 < -0.1% 且下插针 → 做多（空头过热）
```

---

## 🐛 常见错误排查

### 错误1：`ModuleNotFoundError: No module named 'pandas'`

**解决方法**：
```bash
pip install pandas numpy matplotlib
```

---

### 错误2：`FileNotFoundError: [Errno 2] No such file or directory`

**原因**：数据路径不正确

**解决方法**：
在 `spike_strategy_config.py` 中检查：
```python
data_path = Path(r'../../data/coin-binance-swap-candle-csv-1h-2025-11-12/')
```

确保路径存在且有 CSV 文件。

---

### 错误3：回测非常慢

**原因**：币种太多或数据太多

**解决方法**：
1. 先用快速测试（只测 5 个币种）
2. 缩短回测时间范围（只测 2024 年）
3. 使用参数优化时自动限制币种数量

---

## 📞 需要帮助？

### 查看详细文档

```bash
# 策略原理、参数详解、优化建议
cat spike_strategy_README.md
```

### 检测插针信号

```bash
python spike_strategy_quick_test.py

# 选择 2. 插针检测测试
```

会显示 BTC 最近的所有插针信号，帮助你理解信号逻辑。

---

## ✅ 检查清单（开始实盘前）

```
□ 回测至少 50+ 个币种
□ 样本外验证表现稳定（ROI 差距 < 20%）
□ 最大回撤可接受（< 15%）
□ 理解了每个参数的作用
□ 小资金测试 1-2 个月
□ 有止损纪律（不抗单）
□ 准备好承受回撤（心理建设）
```

---

## 🎯 总结

| 步骤 | 命令 | 用途 | 时间 |
|-----|------|------|------|
| 1️⃣ | `python spike_strategy_quick_test.py` | 验证代码能跑 | 1分钟 |
| 2️⃣ | `python spike_strategy_optimizer.py` | 找最优参数 | 5-15分钟 |
| 3️⃣ | `python spike_strategy_backtest.py` | 完整回测 | 5-30分钟 |
| 4️⃣ | `python spike_strategy_visualize.py` | 生成图表 | 10秒 |

---

**祝交易顺利！记住：活下来比赚快钱更重要！** 🚀💰

