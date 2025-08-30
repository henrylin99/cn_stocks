"""
MACD策略
基于MACD指标的金叉死叉信号
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
from .base_strategy import BaseStrategy, StrategyFactory, Signal, AnalysisResult
from .base_strategy import (
    calculate_sma, calculate_ema, calculate_rsi, 
    calculate_bollinger_bands, calculate_macd, calculate_atr
)

@StrategyFactory.register_strategy
class MACDStrategy(BaseStrategy):
    """
    MACD策略
    
    策略逻辑:
    1. MACD金叉时买入
    2. MACD死叉时卖出
    3. 结合成交量和RSI过滤信号
    """
    
    def __init__(self):
        super().__init__()
        self.timeframe = '15m'
        self.startup_candle_count = 50
        
        # MACD参数
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        
        # RSI参数
        self.rsi_period = 14
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        
        # 成交量参数
        self.volume_factor = 1.2
    
    def get_strategy_name(self) -> str:
        return "MACD金叉死叉策略"
    
    def get_strategy_description(self) -> str:
        return "基于MACD指标的金叉死叉信号，结合RSI和成交量确认"
    
    def calculate_indicators(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        
        # MACD
        macd_line, signal_line, histogram = calculate_macd(
            dataframe['close'], self.macd_fast, self.macd_slow, self.macd_signal
        )
        dataframe['macd'] = macd_line
        dataframe['macd_signal'] = signal_line
        dataframe['macd_hist'] = histogram
        
        # MACD信号
        dataframe['macd_above_signal'] = dataframe['macd'] > dataframe['macd_signal']
        dataframe['macd_below_signal'] = dataframe['macd'] < dataframe['macd_signal']
        
        # 金叉死叉检测
        dataframe['macd_golden_cross'] = (
            (dataframe['macd'] > dataframe['macd_signal']) & 
            (dataframe['macd'].shift(1) <= dataframe['macd_signal'].shift(1))
        )
        dataframe['macd_death_cross'] = (
            (dataframe['macd'] < dataframe['macd_signal']) & 
            (dataframe['macd'].shift(1) >= dataframe['macd_signal'].shift(1))
        )
        
        # MACD直方图趋势
        dataframe['macd_hist_rising'] = dataframe['macd_hist'] > dataframe['macd_hist'].shift(1)
        dataframe['macd_hist_falling'] = dataframe['macd_hist'] < dataframe['macd_hist'].shift(1)
        
        # RSI
        dataframe['rsi'] = calculate_rsi(dataframe['close'], self.rsi_period)
        
        # 成交量指标
        dataframe['volume_sma'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # EMA趋势
        dataframe['ema_fast'] = calculate_ema(dataframe['close'], 12)
        dataframe['ema_slow'] = calculate_ema(dataframe['close'], 26)
        dataframe['ema_trend_up'] = dataframe['ema_fast'] > dataframe['ema_slow']
        
        return dataframe
    
    def generate_signal(self, dataframe: pd.DataFrame) -> AnalysisResult:
        """生成交易信号"""
        
        if len(dataframe) == 0:
            return AnalysisResult(
                signal=Signal.HOLD,
                confidence=0.0,
                reasons=["数据不足"],
                indicators={},
                timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        
        # 获取最新几行数据用于分析
        last_row = dataframe.iloc[-1]
        prev_row = dataframe.iloc[-2] if len(dataframe) > 1 else last_row
        
        # 提取关键指标
        indicators = {
            'macd': float(last_row.get('macd', 0)),
            'macd_signal': float(last_row.get('macd_signal', 0)),
            'macd_hist': float(last_row.get('macd_hist', 0)),
            'rsi': float(last_row.get('rsi', 50)),
            'volume_ratio': float(last_row.get('volume_ratio', 1)),
            'close': float(last_row.get('close', 0))
        }
        
        reasons = []
        
        # 买入信号检测
        if last_row.get('macd_golden_cross', False):
            confidence = 0.8
            
            # 增强信号条件
            if last_row.get('macd_hist_rising', False):
                confidence += 0.1
                reasons.append("MACD直方图上升")
            
            if indicators['rsi'] < self.rsi_overbought:
                confidence += 0.05
                reasons.append(f"RSI({indicators['rsi']:.1f})未超买")
            
            if last_row.get('volume_ratio', 1) > self.volume_factor:
                confidence += 0.05
                reasons.append(f"成交量放大({last_row.get('volume_ratio', 1):.1f}倍)")
            
            reasons.insert(0, "MACD金叉")
            
            return AnalysisResult(
                signal=Signal.BUY,
                confidence=min(confidence, 1.0),
                reasons=reasons,
                indicators=indicators,
                timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        
        # 卖出信号检测
        elif last_row.get('macd_death_cross', False):
            confidence = 0.8
            
            # 增强信号条件
            if last_row.get('macd_hist_falling', False):
                confidence += 0.1
                reasons.append("MACD直方图下降")
            
            if indicators['rsi'] > self.rsi_oversold:
                confidence += 0.05
                reasons.append(f"RSI({indicators['rsi']:.1f})未超卖")
            
            if last_row.get('volume_ratio', 1) > self.volume_factor:
                confidence += 0.05
                reasons.append(f"成交量放大({last_row.get('volume_ratio', 1):.1f}倍)")
            
            reasons.insert(0, "MACD死叉")
            
            return AnalysisResult(
                signal=Signal.SELL,
                confidence=min(confidence, 1.0),
                reasons=reasons,
                indicators=indicators,
                timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        
        # 持续趋势信号
        elif last_row.get('macd_above_signal', False) and last_row.get('ema_trend_up', False):
            if indicators['rsi'] < self.rsi_overbought:
                reasons = ["MACD在信号线上方", "趋势向上", f"RSI({indicators['rsi']:.1f})合理"]
                return AnalysisResult(
                    signal=Signal.BUY,
                    confidence=0.6,
                    reasons=reasons,
                    indicators=indicators,
                    timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                )
        
        elif last_row.get('macd_below_signal', False) and not last_row.get('ema_trend_up', True):
            if indicators['rsi'] > self.rsi_oversold:
                reasons = ["MACD在信号线下方", "趋势向下", f"RSI({indicators['rsi']:.1f})合理"]
                return AnalysisResult(
                    signal=Signal.SELL,
                    confidence=0.6,
                    reasons=reasons,
                    indicators=indicators,
                    timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                )
        
        # 默认观望
        reasons = ["MACD信号不明确"]
        return AnalysisResult(
            signal=Signal.HOLD,
            confidence=0.5,
            reasons=reasons,
            indicators=indicators,
            timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        )