# MACD 波动率信号机器人

基于 **MACD 动能变化 + 波动率(ATR)** 的加密货币交易信号提醒系统。

## 📋 功能特性

- ✅ **纯后端系统**：不自动下单，仅提供信号提醒
- ✅ **模块化架构**：清晰的代码结构，易于维护和扩展
- ✅ **多维度分析**：MACD动能 + ATR波动率 + 价格关键位
- ✅ **智能置信度**：基于多个指标计算信号可靠性
- ✅ **风险评估**：HIGH/MID/LOW 三档风险等级
- ✅ **信号去重**：可配置冷却时间，避免刷屏
- ✅ **AI 分析**：集成 OpenAI/DeepSeek，提供自然语言解释（可选）
- ✅ **企业微信推送**：实时 Markdown 格式通知

## 🏗️ 项目结构

```
macd_vol_signal_bot/
├── config.yaml              # 全局配置文件
├── main.py                  # 程序入口
├── models.py                # Signal 数据结构
├── market/
│   └── binance.py           # Binance 行情接入
├── indicators/
│   ├── macd.py              # MACD 指标计算
│   └── volatility.py        # ATR 波动率计算
├── strategy/
│   └── macd_vol.py          # 核心策略逻辑
├── dedup/
│   └── dedup.py             # 信号去重管理
├── notifier/
│   └── wecom.py             # 企业微信推送
└── llm/
    └── analyzer.py          # LLM 分析模块
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.10+
- 依赖库：ccxt, pandas, numpy, requests, pyyaml, openai

### 2. 安装依赖

```bash
cd macd_vol_signal_bot
pip install -r requirements.txt
```

### 3. 配置文件

编辑 `config.yaml`，配置以下关键项：

```yaml
# 监控交易对
symbols:
  - BTCUSDT
  - ETHUSDT

# 监控时间周期
timeframes:
  - 1h

# 企业微信推送
wecom:
  enabled: true
  webhook_url: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY

# LLM分析（可选）
llm:
  enabled: true
  provider: openai  # 或 deepseek
  api_key: ""  # 留空则从环境变量读取
```

### 4. 运行程序

```bash
python main.py
```

## 📊 策略说明

### 信号生成条件

**做空(SELL)信号：**
1. MACD hist 连续下降 ≥ 2 根
2. hist 当前 < 0 或明显回落
3. ATR分位数在 [0.2, 0.8] 区间（过滤极端波动）

**做多(BUY)信号：**
1. MACD hist 连续上升 ≥ 2 根
2. hist 当前 > 0 或明显抬升
3. ATR分位数在 [0.2, 0.8] 区间

### 置信度计算

基于以下维度加权计算（0~1）：
- MACD 动能一致性 (30%)
- 波动率健康度 (30%)
- 价格距关键位距离 (20%)
- 成交量配合度 (20%)

### 风险等级

- **HIGH**：ATR分位数 > 0.8（极高波动）
- **MID**：ATR分位数 0.3~0.8（正常波动）
- **LOW**：ATR分位数 < 0.3（极低波动）

## ⚙️ 环境变量配置

| 变量名 | 说明 | 示例 |
|:---|:---|:---|
| `MACD_VOL_USE_PROXY` | 是否使用代理 | true/false |
| `MACD_VOL_PROXY_URL` | 代理地址 | http://127.0.0.1:7890 |
| `OPENAI_API_KEY` | OpenAI API密钥 | sk-... |
| `DEEPSEEK_API_KEY` | DeepSeek API密钥 | sk-... |

### 设置示例

```bash
# 启用代理
export MACD_VOL_USE_PROXY=true
export MACD_VOL_PROXY_URL=http://127.0.0.1:7890

# 配置 LLM
export OPENAI_API_KEY=sk-your-api-key

# 运行程序
python main.py
```

## 📱 消息推送格式

企业微信 Markdown 消息示例：

```
【信号】BTCUSDT 1h — 🔴 做空信号
价格: 45230.50
时间: 2026-01-12 14:30:00

置信度: 72%
风险等级: MID
建议: WATCH

原因:
1. MACD动能连续下降3根,柱体转弱
2. MACD柱体已转为负值,空头动能增强
3. DIF和DEA同时向下,趋势一致性强

关键位:
- 支撑: 44800.00, 44500.00
- 阻力: 45500.00, 46000.00
- 失效: 45500.00

指标详情:
- MACD柱: -12.5400
- DIF: -8.2300
- DEA: 4.3100
- ATR: 182.45 (0.40%)
- ATR分位: 0.55

【AI 分析】
当前市场处于高位回调阶段，MACD动能转弱且柱体连续下降，
表明空头力量增强。波动率处于正常范围，技术面倾向看空。
建议观望，等待价格突破45500失效位再考虑反向操作。

⚠️ 免责声明: 仅供学习与参考，不构成投资建议
```

## 🔧 高级配置

### 自定义策略参数

编辑 `config.yaml`：

```yaml
strategy:
  macd:
    fast: 12
    slow: 26
    signal: 9
  
  atr:
    period: 14
    low_quantile: 0.2
    high_quantile: 0.8
  
  history_limit: 200

signal:
  cooldown_minutes: 120  # 冷却时间
  max_valid_minutes: 240  # 信号有效期

runtime:
  poll_interval: 300  # 轮询间隔(秒)
```

### LLM 提供商配置

**使用 OpenAI:**
```yaml
llm:
  enabled: true
  provider: openai
  model: gpt-4o-mini
  timeout: 10
```

**使用 DeepSeek:**
```yaml
llm:
  enabled: true
  provider: deepseek
  base_url: https://api.deepseek.com
  model: deepseek-chat
  timeout: 10
```

**禁用 LLM:**
```yaml
llm:
  enabled: false
```

## 📈 运行示例

```bash
$ python main.py

============================================================
🚀 MACD 波动率信号机器人启动
============================================================

✅ 配置文件加载成功: /Users/xxx/macd_vol_signal_bot/config.yaml

📊 监控配置:
   币种: BTCUSDT, ETHUSDT, SOLUSDT
   周期: 1h
   轮询间隔: 300秒
   冷却时间: 120分钟

正在连接交易所 binanceusdm... (尝试 1/3)
✅ 成功连接到 binanceusdm

✅ 初始化完成，开始监控...

############################################################
# 第 1 轮扫描
############################################################

============================================================
⏰ 开始新一轮扫描 - 2026-01-12 14:30:00
============================================================

🔍 检查 BTCUSDT 1h...

============================================================
🎯 检测到信号: BTCUSDT 1h SELL
   价格: 45230.5 | 置信度: 72% | 风险: MID
🤖 调用AI分析...
✅ OpenAI分析完成
📤 发送企业微信消息 (尝试 1/3)...
✅ 企业微信消息发送成功
📊 BTCUSDT 1h SELL @ 45230.5
✅ 记录信号: BTCUSDT 1h SELL @ 45230.5
============================================================

🔍 检查 ETHUSDT 1h...
...

============================================================
✅ 本轮扫描完成
============================================================

💤 休眠 300 秒...
```

## 🛡️ 注意事项

### 禁止事项
❌ 不要自动下单
❌ 不要在生产环境中频繁修改策略参数
❌ 不要完全依赖信号进行交易决策

### 建议
✅ 结合多个时间周期综合判断
✅ 关注置信度和风险等级
✅ 使用少量资金测试策略
✅ 定期回顾信号准确性

## 🐛 故障排除

### 无法连接交易所
```bash
# 启用代理
export MACD_VOL_USE_PROXY=true
export MACD_VOL_PROXY_URL=http://127.0.0.1:7890
```

### LLM 调用失败
```bash
# 检查 API Key
echo $OPENAI_API_KEY

# 或在 config.yaml 中配置
llm:
  api_key: "sk-your-key"
```

### 企业微信推送失败
1. 检查 `webhook_url` 是否正确
2. 确认机器人配置正确
3. 查看返回的错误信息

## 📄 许可证

本项目仅供学习和研究使用。

## ⚠️ 免责声明

本软件仅用于技术研究和学习目的，不构成任何投资建议。
加密货币交易存在高风险，请谨慎决策，风险自负。
