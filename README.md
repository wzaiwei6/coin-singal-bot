# Coin CTA Signal Bots

本项目包含两个加密货币信号监控机器人，用于捕捉市场中的特定交易信号并推送到 Telegram 或企业微信。

## 1. 插针信号机器人 (`spike_signal_bot.py`)

监控市场中的“插针”行为，捕捉潜在的反转信号。

### 核心逻辑
- **影线显著**：监控长上影线（看跌）或长下影线（看涨），要求影线长度至少是实体的 2.0 倍。
- **振幅极端**：要求当前 K 线振幅至少是 ATR（平均真实波幅）的 2.0 倍。
- **放量**：要求当前成交量至少是过去平均成交量的 2.0 倍。
- **去重机制**：同一根 K 线只会报警一次。

### 监控配置
- **默认币种**：BTC, ETH, SOL, DOGE, FIL, BNB, WLD, XRP, ZEC, LINK, LTC
- **默认周期**：3m, 15m, 1h
- **轮询间隔**：5分钟

---

## 2. MACD 信号机器人 (`macd_signal_bot.py`)

监控 MACD 指标的多周期共振信号。

### 核心逻辑
- **多头信号**：MACD 柱连续两根增长，且 DIF 和 DEA 均向上增长。
- **空头信号**：MACD 柱连续两根减少，且 DIF 和 DEA 均向下减少。
- **多周期共振**：必须 **3m, 5m, 15m, 1h** 四个周期**同时**满足相同方向的信号才会报警。
- **去重机制**：5分钟内相同方向的信号不重复发送。

### 监控配置
- **MACD 参数**：(12, 26, 9)
- **默认币种**：BTC, ETH, SOL 等
- **轮询间隔**：3分钟

---

## 部署与使用

### 环境要求
- Python 3.8+
- 依赖库：`ccxt`, `pandas`, `numpy`, `requests`

### 快速开始

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **运行机器人**
   
   **方式一：直接运行（推荐服务器部署）**
   不需要代理，直接连接交易所 API。
   ```bash
   # 运行插针机器人
   python spike_signal_bot.py

   # 运行 MACD 机器人
   python macd_signal_bot.py
   ```

   **方式二：使用启动脚本**
   自动管理虚拟环境和依赖。
   ```bash
   ./run.sh
   ```

### 环境变量配置（可选）

如果需要修改默认配置，可以通过环境变量进行设置：

| 变量名 | 描述 | 默认值 |
| :--- | :--- | :--- |
| `SPIKE_WECHAT_WEBHOOK_URL` | 插针机器人企业微信 Webhook | (内置默认地址) |
| `MACD_WECHAT_WEBHOOK_URL` | MACD 机器人企业微信 Webhook | (内置默认地址) |
| `SPIKE_USE_PROXY` | 是否使用代理 (true/false) | false |
| `SPIKE_PROXY_URL` | 代理地址 | http://127.0.0.1:7890 |

### 消息推送
- **企业微信**：默认启用，通过 Webhook 推送 Markdown 格式消息。
- **Telegram**：支持，需在代码中配置 Token 和 Chat ID。

## 状态管理
机器人会自动在当前目录下生成 `.json` 状态文件，用于记录已发送的信号，防止重启后重复报警。
- `.spike_state.json`
- `.macd_state.json`


