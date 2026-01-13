#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信号去重和冷却管理模块（升级版）
- 支持基于 K 线数量的冷却
- 支持关键位打破冷却机制
"""
import json
import os
from datetime import datetime
from typing import Optional, Dict, List


class DedupManager:
    """信号去重管理器（升级版）"""
    
    def __init__(self, state_file: str, cooldown_bars: int = 2, break_on_key_level: bool = True):
        """
        初始化去重管理器
        
        Args:
            state_file: 状态文件路径
            cooldown_bars: 冷却 K 线数量
            break_on_key_level: 是否允许关键位打破冷却
        """
        self.state_file = state_file
        self.cooldown_bars = cooldown_bars
        self.break_on_key_level = break_on_key_level
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """加载状态文件"""
        if not os.path.exists(self.state_file):
            return {
                "signals": {},           # 普通信号记录
                "key_levels": {}         # 关键位触发记录
            }
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
                # 确保新格式
                if "signals" not in state:
                    state = {"signals": state, "key_levels": {}}
                return state
        except Exception as e:
            print(f"⚠️  加载状态文件失败: {e}")
            return {"signals": {}, "key_levels": {}}
    
    def _save_state(self) -> None:
        """保存状态文件"""
        try:
            # 确保目录存在
            state_dir = os.path.dirname(self.state_file)
            if state_dir and not os.path.exists(state_dir):
                os.makedirs(state_dir, exist_ok=True)
            
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  保存状态文件失败: {e}")
    
    def _get_key(self, symbol: str, timeframe: str, direction: str) -> str:
        """生成状态键"""
        return f"{symbol}_{timeframe}_{direction}"
    
    def is_in_cooldown(self, symbol: str, timeframe: str, direction: str, 
                       current_bar_time: int) -> tuple[bool, int]:
        """
        检查是否在冷却期内（基于 K 线数量）
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            direction: 方向（BUY/SELL）
            current_bar_time: 当前 K 线时间戳（毫秒）
            
        Returns:
            (是否在冷却期, 已经过去的 K 线数)
        """
        key = self._get_key(symbol, timeframe, direction)
        
        if key not in self.state["signals"]:
            return False, 0
        
        last_bar_time = self.state["signals"][key].get("bar_time")
        if not last_bar_time:
            return False, 0
        
        # 计算 K 线间隔数
        bars_passed = self._calculate_bars_between(
            last_bar_time, current_bar_time, timeframe
        )
        
        in_cooldown = bars_passed < self.cooldown_bars
        
        if in_cooldown:
            remaining_bars = self.cooldown_bars - bars_passed
            print(f"⏰ {symbol} {timeframe} {direction} 在冷却期内，还需等待 {remaining_bars} 根 K 线")
        
        return in_cooldown, bars_passed
    
    def _calculate_bars_between(self, bar_time1: int, bar_time2: int, timeframe: str) -> int:
        """
        计算两个时间戳之间相隔多少根 K 线
        
        Args:
            bar_time1: 第一个时间戳（毫秒）
            bar_time2: 第二个时间戳（毫秒）
            timeframe: 时间周期
            
        Returns:
            相隔的 K 线数量
        """
        # 时间周期转换为毫秒
        timeframe_ms = {
            "1m": 60 * 1000,
            "3m": 3 * 60 * 1000,
            "5m": 5 * 60 * 1000,
            "15m": 15 * 60 * 1000,
            "30m": 30 * 60 * 1000,
            "1h": 60 * 60 * 1000,
            "2h": 2 * 60 * 60 * 1000,
            "4h": 4 * 60 * 60 * 1000,
            "1d": 24 * 60 * 60 * 1000,
        }.get(timeframe, 60 * 60 * 1000)  # 默认 1h
        
        time_diff = abs(bar_time2 - bar_time1)
        bars = int(time_diff / timeframe_ms)
        
        return bars
    
    def check_key_level_trigger(self, symbol: str, timeframe: str, direction: str,
                                current_price: float, key_levels: Dict) -> Optional[Dict]:
        """
        检查是否触发关键位事件（可打破冷却）
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            direction: 信号方向
            current_price: 当前价格
            key_levels: 关键位字典 {"support": [...], "resistance": [...], "invalid": ...}
            
        Returns:
            如果触发关键位，返回事件信息字典，否则返回 None
        """
        if not self.break_on_key_level:
            return None
        
        # SELL 信号：检查是否跌破支撑或失效位
        if direction == "SELL":
            # 检查支撑位
            for support in key_levels.get("support", []):
                if self._is_level_triggered(symbol, timeframe, direction, support, "support"):
                    continue  # 已经触发过
                
                if current_price <= support:
                    # 首次跌破支撑
                    self._mark_level_triggered(symbol, timeframe, direction, support, "support")
                    return {
                        "type": "support_break",
                        "level": support,
                        "message": f"价格已跌破关键支撑 {support:.2f}"
                    }
            
            # 检查失效位
            invalid = key_levels.get("invalid")
            if invalid:
                if self._is_level_triggered(symbol, timeframe, direction, invalid, "invalid"):
                    pass  # 已触发
                elif current_price >= invalid:
                    # 触及失效位（反向突破）
                    self._mark_level_triggered(symbol, timeframe, direction, invalid, "invalid")
                    return {
                        "type": "invalid_break",
                        "level": invalid,
                        "message": f"价格突破失效位 {invalid:.2f}，SELL 信号失效"
                    }
        
        # BUY 信号：检查是否突破阻力或失效位
        elif direction == "BUY":
            # 检查阻力位
            for resistance in key_levels.get("resistance", []):
                if self._is_level_triggered(symbol, timeframe, direction, resistance, "resistance"):
                    continue
                
                if current_price >= resistance:
                    # 首次突破阻力
                    self._mark_level_triggered(symbol, timeframe, direction, resistance, "resistance")
                    return {
                        "type": "resistance_break",
                        "level": resistance,
                        "message": f"价格已突破关键阻力 {resistance:.2f}"
                    }
            
            # 检查失效位
            invalid = key_levels.get("invalid")
            if invalid:
                if self._is_level_triggered(symbol, timeframe, direction, invalid, "invalid"):
                    pass
                elif current_price <= invalid:
                    # 触及失效位（反向跌破）
                    self._mark_level_triggered(symbol, timeframe, direction, invalid, "invalid")
                    return {
                        "type": "invalid_break",
                        "level": invalid,
                        "message": f"价格跌破失效位 {invalid:.2f}，BUY 信号失效"
                    }
        
        return None
    
    def _is_level_triggered(self, symbol: str, timeframe: str, direction: str, 
                           level: float, level_type: str) -> bool:
        """检查关键位是否已经触发过"""
        key = f"{symbol}_{timeframe}_{direction}_{level_type}_{level:.2f}"
        return key in self.state["key_levels"]
    
    def _mark_level_triggered(self, symbol: str, timeframe: str, direction: str,
                             level: float, level_type: str) -> None:
        """标记关键位已触发"""
        key = f"{symbol}_{timeframe}_{direction}_{level_type}_{level:.2f}"
        self.state["key_levels"][key] = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "type": level_type
        }
        self._save_state()
    
    def record_signal(self, symbol: str, timeframe: str, direction: str, 
                     price: float, bar_time: int) -> None:
        """
        记录已发送的信号
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            direction: 方向
            price: 信号价格
            bar_time: K 线时间戳（毫秒）
        """
        key = self._get_key(symbol, timeframe, direction)
        
        self.state["signals"][key] = {
            "bar_time": bar_time,
            "price": price,
            "timestamp": datetime.now().isoformat(),
            "count": self.state["signals"].get(key, {}).get("count", 0) + 1
        }
        
        self._save_state()
        print(f"✅ 记录信号: {symbol} {timeframe} {direction} @ {price}")
    
    def cleanup_expired(self, max_age_hours: int = 24) -> int:
        """
        清理过期的记录
        
        Args:
            max_age_hours: 最大保留时长（小时）
            
        Returns:
            int: 清理的记录数
        """
        now = datetime.now()
        expired_keys = []
        
        # 清理信号记录
        for key, info in self.state["signals"].items():
            timestamp_str = info.get("timestamp")
            if not timestamp_str:
                expired_keys.append(key)
                continue
            
            try:
                last_time = datetime.fromisoformat(timestamp_str)
                age_hours = (now - last_time).total_seconds() / 3600
                
                if age_hours > max_age_hours:
                    expired_keys.append(key)
            except Exception:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.state["signals"][key]
        
        # 清理关键位记录
        expired_level_keys = []
        for key, info in self.state["key_levels"].items():
            timestamp_str = info.get("timestamp")
            if not timestamp_str:
                expired_level_keys.append(key)
                continue
            
            try:
                last_time = datetime.fromisoformat(timestamp_str)
                age_hours = (now - last_time).total_seconds() / 3600
                
                if age_hours > max_age_hours:
                    expired_level_keys.append(key)
            except Exception:
                expired_level_keys.append(key)
        
        for key in expired_level_keys:
            del self.state["key_levels"][key]
        
        total_cleaned = len(expired_keys) + len(expired_level_keys)
        
        if total_cleaned > 0:
            self._save_state()
            print(f"🧹 清理了 {total_cleaned} 条过期记录")
        
        return total_cleaned
    
    def get_statistics(self) -> Dict:
        """
        获取统计信息
        
        Returns:
            dict: 统计数据
        """
        total_signals = sum(info.get("count", 0) for info in self.state["signals"].values())
        
        return {
            "total_signal_keys": len(self.state["signals"]),
            "total_signals": total_signals,
            "total_key_level_triggers": len(self.state["key_levels"]),
            "cooldown_bars": self.cooldown_bars,
            "break_on_key_level": self.break_on_key_level
        }
