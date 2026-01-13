# 🚀 快速启动指南

## ✅ 测试已通过

所有模块测试已通过，系统运行正常！

---

## 📝 使用步骤

### 1. 安装依赖（如果还没安装）

```bash
cd /Users/wang/PythonProjects/coin-singal-bot/macd_vol_signal_bot
pip install -r requirements.txt
```

### 2. 配置文件已就绪

你的 `config.yaml` 已配置：
- ✅ 监控币种: BTCUSDT, ETHUSDT, SOLUSDT, DOGEUSDT
- ✅ 监控周期: 1h
- ✅ 企业微信 Webhook: 已配置（你已更新为新的key）
- ⚠️  LLM 分析: 已启用，但需要配置 API Key

### 3. 配置 LLM（可选）

如果要使用 AI 分析功能，请配置以下环境变量之一：

**使用 OpenAI:**
```bash
export OPENAI_API_KEY="sk-your-api-key"
```

**使用 DeepSeek:**
```bash
export DEEPSEEK_API_KEY="sk-your-api-key"
```

或者在 `config.yaml` 中直接配置：
```yaml
llm:
  enabled: true
  provider: openai  # 或 deepseek
  api_key: "sk-your-api-key"
```

如果不想使用 LLM，可以在 `config.yaml` 中禁用：
```yaml
llm:
  enabled: false
```

### 4. 启动机器人

**方式 1: 直接运行**
```bash
cd /Users/wang/PythonProjects/coin-singal-bot/macd_vol_signal_bot
python main.py
```

**方式 2: 使用启动脚本**
```bash
cd /Users/wang/PythonProjects/coin-singal-bot/macd_vol_signal_bot
./run.sh
```

---

## 🔍 测试结果

刚刚运行的测试验证了：
- ✅ 所有模块导入成功
- ✅ Signal 数据结构正常
- ✅ 企业微信消息格式化正常
- ✅ 去重管理器工作正常（120分钟冷却期）
- ✅ 配置文件加载成功
- ✅ MACD 指标计算正确
- ✅ ATR 波动率计算正确

---

## 📊 运行示例

启动后，你会看到类似这样的输出：

```
============================================================
🚀 MACD 波动率信号机器人启动
============================================================

✅ 配置文件加载成功

📊 监控配置:
   币种: BTCUSDT, ETHUSDT, SOLUSDT, DOGEUSDT
   周期: 1h
   轮询间隔: 300秒
   冷却时间: 120分钟

正在连接交易所 binanceusdm... (尝试 1/3)
✅ 成功连接到 binanceusdm

✅ 初始化完成，开始监控...

############################################################
# 第 1 轮扫描
############################################################

🔍 检查 BTCUSDT 1h...
🔍 检查 ETHUSDT 1h...
...
```

当检测到信号时，会自动推送到企业微信。

---

## ⚠️ 重要提示

1. **不会自动下单**：这个机器人只发送信号提醒，不会进行任何交易操作
2. **信号仅供参考**：所有信号仅供学习和参考，不构成投资建议
3. **冷却机制**：同一币种、同一方向的信号在120分钟内只会发送一次
4. **LLM 降级**：即使 LLM 调用失败，核心信号功能仍会正常工作

---

## 🎯 下一步建议

1. **先小规模测试**：可以先只监控1-2个币种
2. **观察信号质量**：运行一段时间后，根据信号准确性调整参数
3. **结合实际经验**：将信号与自己的分析结合使用

---

## 🆘 如果遇到问题

### 网络连接问题
如果无法连接到 Binance，设置代理：
```bash
export MACD_VOL_USE_PROXY=true
export MACD_VOL_PROXY_URL=http://127.0.0.1:7890
```

### LLM 调用失败
不用担心，核心功能不受影响。可以：
- 检查 API Key 是否正确
- 或者直接禁用 LLM（在 config.yaml 中设置 `llm.enabled: false`）

### 企业微信推送失败
- 检查 webhook_url 是否正确
- 确认机器人配置正确

---

## 🎉 准备就绪！

现在你可以运行 `python main.py` 启动机器人了！
