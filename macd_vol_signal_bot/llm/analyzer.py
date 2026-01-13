#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 分析模块 - 支持 OpenAI 和 DeepSeek
"""
import os
from typing import Optional
from models import Signal


def analyze_signal(signal: Signal, config: dict) -> Optional[str]:
    """
    使用LLM分析交易信号（支持降级）
    
    Args:
        signal: 信号对象
        config: 配置字典
        
    Returns:
        str: LLM分析结果，失败时返回None（不影响主流程）
    """
    llm_config = config.get("llm", {})
    
    # 检查是否启用LLM
    if not llm_config.get("enabled", False):
        return None
    
    try:
        provider = llm_config.get("provider", "openai").lower()
        
        if provider == "openai":
            return _analyze_with_openai(signal, llm_config)
        elif provider == "deepseek":
            return _analyze_with_deepseek(signal, llm_config)
        else:
            print(f"⚠️  不支持的LLM提供商: {provider}")
            return None
    
    except Exception as e:
        # 任何异常都不应该影响主流程
        print(f"⚠️  LLM分析失败（已降级）: {e}")
        return None


def _analyze_with_openai(signal: Signal, llm_config: dict) -> Optional[str]:
    """使用OpenAI进行分析"""
    try:
        from openai import OpenAI
    except ImportError:
        print("⚠️  未安装 openai 库，LLM分析已禁用")
        return None
    
    # 获取API配置
    api_key = llm_config.get("api_key") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  未配置 OPENAI_API_KEY，LLM分析已禁用")
        return None
    
    base_url = llm_config.get("base_url") or None
    model = llm_config.get("model", "gpt-4o-mini")
    timeout = llm_config.get("timeout", 10)
    max_tokens = llm_config.get("max_tokens", 300)
    
    try:
        # 初始化客户端
        if base_url:
            client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        else:
            client = OpenAI(api_key=api_key, timeout=timeout)
        
        # 构建prompt
        prompt = _build_analysis_prompt(signal)
        
        # 调用API
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一位专业的加密货币量化交易分析师，精通技术分析。你的分析必须：1)逻辑严谨，不自相矛盾；2)与给定的信号方向和操作建议保持一致；3)客观评估风险；4)提供具体可执行的建议。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=max_tokens,
            temperature=0.7
        )
        
        analysis = response.choices[0].message.content.strip()
        print(f"✅ OpenAI分析完成")
        return analysis
    
    except Exception as e:
        print(f"⚠️  OpenAI调用失败: {e}")
        return None


def _analyze_with_deepseek(signal: Signal, llm_config: dict) -> Optional[str]:
    """使用DeepSeek进行分析"""
    try:
        from openai import OpenAI
    except ImportError:
        print("⚠️  未安装 openai 库，LLM分析已禁用")
        return None
    
    # 获取API配置
    api_key = llm_config.get("api_key") or os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("⚠️  未配置 DEEPSEEK_API_KEY，LLM分析已禁用")
        return None
    
    base_url = llm_config.get("base_url", "https://api.deepseek.com")
    model = llm_config.get("model", "deepseek-chat")
    timeout = llm_config.get("timeout", 10)
    max_tokens = llm_config.get("max_tokens", 300)
    
    try:
        # 初始化客户端（DeepSeek使用OpenAI兼容接口）
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        
        # 构建prompt
        prompt = _build_analysis_prompt(signal)
        
        # 调用API
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "你是一位专业的加密货币量化交易分析师，精通技术分析。你的分析必须：1)逻辑严谨，不自相矛盾；2)与给定的信号方向和操作建议保持一致；3)客观评估风险；4)提供具体可执行的建议。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=max_tokens,
            temperature=0.7
        )
        
        analysis = response.choices[0].message.content.strip()
        print(f"✅ DeepSeek分析完成")
        return analysis
    
    except Exception as e:
        print(f"⚠️  DeepSeek调用失败: {e}")
        return None


def _build_analysis_prompt(signal: Signal) -> str:
    """构建分析prompt"""
    direction_text = "做空(SELL)" if signal.direction == "SELL" else "做多(BUY)"
    suggestion_text = {
        "SELL": "建议做空",
        "BUY": "建议做多",
        "WATCH": "建议观望"
    }.get(signal.suggestion, "建议观望")
    
    prompt_parts = [
        f"# 交易信号分析",
        f"",
        f"交易对: {signal.symbol}",
        f"周期: {signal.timeframe}",
        f"信号方向: {direction_text}",
        f"操作建议: {suggestion_text}",
        f"当前价格: {signal.price}",
        f"置信度: {signal.confidence * 100:.0f}%",
        f"风险等级: {signal.risk_level}",
        f"",
        f"## 技术指标",
        f"- MACD柱: {signal.macd_hist:.4f}",
        f"- DIF: {signal.macd_dif:.4f}",
        f"- DEA: {signal.macd_dea:.4f}",
        f"- ATR波动率: {signal.atr:.4f} ({signal.atr_pct:.2f}%)",
        f"- ATR分位数: {signal.atr_quantile:.2f} (0=极低波动, 0.5=正常, 1=极高波动)",
        f"",
        f"## 信号原因",
    ]
    
    for i, reason in enumerate(signal.reasons, 1):
        prompt_parts.append(f"{i}. {reason}")
    
    prompt_parts.extend([
        f"",
        f"## 关键价位",
        f"- 支撑位: {', '.join([f'{s:.2f}' for s in signal.key_levels.get('support', [])])}",
        f"- 阻力位: {', '.join([f'{r:.2f}' for r in signal.key_levels.get('resistance', [])])}",
        f"- 失效位: {signal.key_levels.get('invalid', 0):.2f}",
        f"",
        f"---",
        f"",
        f"请作为专业量化交易分析师，基于以上数据提供分析:",
        f"",
        f"1. **市场状态判断**: 当前趋势和动能特征",
        f"2. **信号可靠性**: 评估{direction_text}信号的有效性",
        f"3. **风险提示**: 主要风险点和注意事项",
        f"4. **操作建议**: 具体的入场、止损、止盈建议",
        f"",
        f"要求:",
        f"- 分析必须与'{direction_text}'方向一致",
        f"- 操作建议必须与'{suggestion_text}'一致",
        f"- 专业、客观、简洁(150-200字)",
        f"- 不要自相矛盾",
    ])
    
    return "\n".join(prompt_parts)
