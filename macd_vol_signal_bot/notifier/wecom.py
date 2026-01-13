#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信推送模块
"""
import requests
from typing import Optional, Dict
from models import Signal


def format_signal_message(signal: Signal, llm_analysis: Optional[str] = None) -> str:
    """
    格式化信号为Markdown消息
    
    Args:
        signal: 信号对象
        llm_analysis: LLM分析结果（可选）
        
    Returns:
        str: 格式化的Markdown消息
    """
    # 方向标识
    direction_emoji = "🔴" if signal.direction == "SELL" else "🟢"
    direction_text = "做空信号" if signal.direction == "SELL" else "做多信号"
    
    # 构建消息
    lines = [
        f"【信号】{signal.symbol} {signal.timeframe} — {direction_emoji} {direction_text}",
        f"价格: {signal.price:.4f}",
        f"时间: {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"置信度: {signal.confidence * 100:.0f}%",
        f"风险等级: {signal.risk_level}",
        f"建议: {signal.suggestion}",
        "",
        "原因:"
    ]
    
    # 添加原因列表
    for i, reason in enumerate(signal.reasons, 1):
        lines.append(f"{i}. {reason}")
    
    # 添加关键位信息
    lines.append("")
    lines.append("关键位:")
    
    if signal.key_levels.get("support"):
        support_str = ", ".join([f"{s:.4f}" for s in signal.key_levels["support"]])
        lines.append(f"- 支撑: {support_str}")
    
    if signal.key_levels.get("resistance"):
        resistance_str = ", ".join([f"{r:.4f}" for r in signal.key_levels["resistance"]])
        lines.append(f"- 阻力: {resistance_str}")
    
    if signal.key_levels.get("invalid"):
        lines.append(f"- 失效: {signal.key_levels['invalid']:.4f}")
    
    # 添加指标详情
    if signal.macd_hist is not None:
        lines.append("")
        lines.append("指标详情:")
        lines.append(f"- MACD柱: {signal.macd_hist:.4f}")
        lines.append(f"- DIF: {signal.macd_dif:.4f}")
        lines.append(f"- DEA: {signal.macd_dea:.4f}")
        lines.append(f"- ATR: {signal.atr:.4f} ({signal.atr_pct:.2f}%)")
        lines.append(f"- ATR分位: {signal.atr_quantile:.2f}")
    
    # 添加LLM分析
    if llm_analysis:
        lines.append("")
        lines.append("【AI 分析】")
        lines.append(llm_analysis)
    
    # 添加免责声明
    lines.append("")
    lines.append("⚠️ 免责声明: 仅供学习与参考，不构成投资建议")
    
    return "\n".join(lines)


def format_key_level_message(signal: Signal, key_level_event: Dict) -> str:
    """
    格式化关键位触达确认消息
    
    Args:
        signal: 信号对象
        key_level_event: 关键位事件 {"type": "support_break", "level": 900.0, "message": "..."}
        
    Returns:
        str: 格式化的Markdown消息
    """
    direction_emoji = "🔴" if signal.direction == "SELL" else "🟢"
    direction_text = "SELL" if signal.direction == "SELL" else "BUY"
    
    event_type = key_level_event.get("type", "unknown")
    level = key_level_event.get("level", 0)
    message = key_level_event.get("message", "关键位触达")
    
    # 根据事件类型选择标题
    if event_type == "invalid_break":
        title = "⚠️ 信号失效提醒"
        action_text = f"此前 {direction_text} 观点已失效"
    else:
        title = "🚨 关键位触达确认"
        action_text = f"此前 {direction_text} 观点得到进一步确认"
    
    lines = [
        title,
        f"{signal.symbol} {signal.timeframe} — {direction_emoji} {direction_text}",
        "",
        message,
        action_text,
        "",
        f"当前价格: {signal.price:.4f}",
        f"风险等级: {signal.risk_level}",
        "",
        "风险提示: 波动率较高，注意回撤",
        "",
        "⚠️ 免责声明: 仅供学习与参考，不构成投资建议"
    ]
    
    return "\n".join(lines)


def send_signal(signal: Signal, webhook_url: str, llm_analysis: Optional[str] = None, 
                retry_times: int = 3) -> bool:
    """
    发送信号到企业微信
    
    Args:
        signal: 信号对象
        webhook_url: 企业微信Webhook URL
        llm_analysis: LLM分析结果（可选）
        retry_times: 重试次数
        
    Returns:
        bool: 发送是否成功
    """
    if not webhook_url:
        print("⚠️  未配置企业微信Webhook URL")
        return False
    
    # 格式化消息
    message = format_signal_message(signal, llm_analysis)
    
    # 构建请求payload
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": message
        }
    }
    
    # 重试发送
    for attempt in range(retry_times):
        try:
            print(f"📤 发送企业微信消息 (尝试 {attempt + 1}/{retry_times})...")
            response = requests.post(webhook_url, json=payload, timeout=10)
            result = response.json()
            
            if result.get("errcode") == 0:
                print(f"✅ 企业微信消息发送成功")
                print(f"📊 {signal.symbol} {signal.timeframe} {signal.direction} @ {signal.price}")
                return True
            else:
                error_msg = result.get("errmsg", "未知错误")
                print(f"⚠️  企业微信发送失败: {error_msg}")
                
                # 如果是配置错误，不需要重试
                if "invalid webhook url" in error_msg.lower():
                    print("❌ Webhook URL 配置错误，请检查配置文件")
                    return False
        
        except requests.exceptions.Timeout:
            print(f"⚠️  请求超时 (尝试 {attempt + 1}/{retry_times})")
            if attempt < retry_times - 1:
                import time
                time.sleep(2)
        
        except Exception as e:
            print(f"⚠️  企业微信发送异常: {e}")
            if attempt < retry_times - 1:
                import time
                time.sleep(2)
    
    print("❌ 企业微信消息发送失败")
    return False


def send_text_message(text: str, webhook_url: str) -> bool:
    """
    发送纯文本消息到企业微信
    
    Args:
        text: 文本内容
        webhook_url: 企业微信Webhook URL
        
    Returns:
        bool: 发送是否成功
    """
    if not webhook_url:
        return False
    
    payload = {
        "msgtype": "text",
        "text": {
            "content": text
        }
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        result = response.json()
        return result.get("errcode") == 0
    except Exception as e:
        print(f"⚠️  发送文本消息失败: {e}")
        return False


def send_startup_notification(webhook_url: str, config: dict) -> None:
    """
    发送启动通知
    
    Args:
        webhook_url: 企业微信Webhook URL
        config: 配置信息
    """
    symbols = config.get("symbols", [])
    timeframes = config.get("timeframes", [])
    
    message = (
        f"🚀 MACD波动率信号机器人启动成功\n\n"
        f"监控币种: {', '.join(symbols)}\n"
        f"监控周期: {', '.join(timeframes)}\n"
        f"轮询间隔: {config.get('runtime', {}).get('poll_interval', 300)}秒\n"
        f"冷却时间: {config.get('signal', {}).get('cooldown_minutes', 120)}分钟"
    )
    
    send_text_message(message, webhook_url)
