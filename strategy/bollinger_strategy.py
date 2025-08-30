"""
布林带策略
基于布林带的均值回归策略
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
class BollingerStrategy(BaseStrategy):
    """
    布林带策略
    
    策略逻辑:
    1. 价格触及下轨时买入
    2. 价格触及上轨时卖出
    3. 结合RSI和成交量确认信号
    """
    
    def __init__(self):
        super().__init__()
        self.timeframe = '15m'
        self.startup_candle_count = 50
        
        # 布林带参数
        self.bb_period = 20
        self.bb_std = 2.0
        
        # RSI参数
        self.rsi_period = 14
        self.rsi_oversold = 35
        self.rsi_overbought = 65
        
        # 成交量参数
        self.volume_factor = 1.2
        
        # 布林带位置参数
        self.bb_lower_threshold = 0.1  # 接近下轨
        self.bb_upper_threshold = 0.9  # 接近上轨
    
    def get_strategy_name(self) -> str:
        return "布林带均值回归策略"
    
    def get_strategy_description(self) -> str:
        return "基于布林带的均值回归，在极端位置寻找反转机会"
    
    def calculate_indicators(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        
        # 布林带
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(
            dataframe['close'], self.bb_period, self.bb_std
        )
        dataframe['bb_upper'] = bb_upper
        dataframe['bb_middle'] = bb_middle
        dataframe['bb_lower'] = bb_lower
        
        # 布林带宽度和位置
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']
        dataframe['bb_percent'] = (dataframe['close'] - dataframe['bb_lower']) / (dataframe['bb_upper'] - dataframe['bb_lower'])
        
        # 布林带突破
        dataframe['price_above_upper'] = dataframe['close'] > dataframe['bb_upper']
        dataframe['price_below_lower'] = dataframe['close'] < dataframe['bb_lower']
        dataframe['price_near_upper'] = dataframe['bb_percent'] > self.bb_upper_threshold
        dataframe['price_near_lower'] = dataframe['bb_percent'] < self.bb_lower_threshold
        
        # 布林带挤压
        dataframe['bb_squeeze'] = dataframe['bb_width'] < dataframe['bb_width'].rolling(20).quantile(0.2)
        dataframe['bb_expansion'] = dataframe['bb_width'] > dataframe['bb_width'].rolling(20).quantile(0.8)
        
        # RSI
        dataframe['rsi'] = calculate_rsi(dataframe['close'], self.rsi_period)
        
        # 价格趋势
        dataframe['price_momentum'] = (dataframe['close'] - dataframe['close'].shift(5)) / dataframe['close'].shift(5)
        
        # 成交量指标
        dataframe['volume_sma'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # EMA趋势
        dataframe['ema_20'] = calculate_ema(dataframe['close'], 20)
        dataframe['price_vs_ema'] = dataframe['close'] / dataframe['ema_20'] - 1
        
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
        
        # 获取最新数据
        last_row = dataframe.iloc[-1]
        prev_row = dataframe.iloc[-2] if len(dataframe) > 1 else last_row
        
        # 提取关键指标
        indicators = {
            'bb_percent': float(last_row.get('bb_percent', 0.5)),
            'bb_width': float(last_row.get('bb_width', 0)),
            'rsi': float(last_row.get('rsi', 50)),
            'volume_ratio': float(last_row.get('volume_ratio', 1)),
            'close': float(last_row.get('close', 0)),
            'bb_upper': float(last_row.get('bb_upper', 0)),
            'bb_lower': float(last_row.get('bb_lower', 0)),
            'bb_middle': float(last_row.get('bb_middle', 0))
        }
        
        reasons = []
        
        # 买入信号检测 - 价格接近或突破下轨
        if (last_row.get('price_near_lower', False) or last_row.get('price_below_lower', False)):
            confidence = 0.75
            reasons.append(f"价格接近布林带下轨(位置:{indicators['bb_percent']:.1%})")
            
            # 增强信号条件
            if last_row.get('rsi', 50) < self.rsi_oversold:
                confidence += 0.1
                reasons.append(f"RSI({indicators['rsi']:.1f})超卖确认")
            
            if indicators['rsi'] > prev_row.get('rsi', 50):
                confidence += 0.05
                reasons.append("RSI开始回升")
            
            if last_row.get('volume_ratio', 1) > self.volume_factor:
                confidence += 0.05
                reasons.append(f"成交量放大({indicators['volume_ratio']:.1f}倍)")
            
            if last_row.get('bb_squeeze', False):
                confidence += 0.05
                reasons.append("布林带收窄，突破在即")
            
            return AnalysisResult(
                signal=Signal.BUY,
                confidence=min(confidence, 1.0),
                reasons=reasons,
                indicators=indicators,
                timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        
        # 卖出信号检测 - 价格接近或突破上轨
        elif (last_row.get('price_near_upper', False) or last_row.get('price_above_upper', False)):
            confidence = 0.75
            reasons.append(f"价格接近布林带上轨(位置:{indicators['bb_percent']:.1%})")
            
            # 增强信号条件
            if last_row.get('rsi', 50) > self.rsi_overbought:
                confidence += 0.1
                reasons.append(f"RSI({indicators['rsi']:.1f})超买确认")
            
            if indicators['rsi'] < prev_row.get('rsi', 50):
                confidence += 0.05
                reasons.append("RSI开始回落")
            
            if last_row.get('volume_ratio', 1) > self.volume_factor:
                confidence += 0.05
                reasons.append(f"成交量放大({indicators['volume_ratio']:.1f}倍)")
            
            if last_row.get('bb_expansion', False):
                confidence += 0.05
                reasons.append("布林带扩张，压力增大")
            
            return AnalysisResult(
                signal=Signal.SELL,
                confidence=min(confidence, 1.0),
                reasons=reasons,
                indicators=indicators,
                timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        
        # 中轨支撑/阻力
        elif abs(indicators['bb_percent'] - 0.5) < 0.1:  # 接近中轨
            if last_row.get('price_vs_ema', 0) > 0 and indicators['rsi'] > 50:
                reasons = ["价格在中轨附近", "趋势偏多", f"RSI({indicators['rsi']:.1f})中性偏强"]
                return AnalysisResult(
                    signal=Signal.BUY,
                    confidence=0.5,
                    reasons=reasons,
                    indicators=indicators,
                    timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                )
            elif last_row.get('price_vs_ema', 0) < 0 and indicators['rsi'] < 50:
                reasons = ["价格在中轨附近", "趋势偏空", f"RSI({indicators['rsi']:.1f})中性偏弱"]
                return AnalysisResult(
                    signal=Signal.SELL,
                    confidence=0.5,
                    reasons=reasons,
                    indicators=indicators,
                    timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                )
        
        # 默认观望
        reasons = [f"价格在布林带中部({indicators['bb_percent']:.1%})，无明确信号"]
        return AnalysisResult(
            signal=Signal.HOLD,
            confidence=0.5,
            reasons=reasons,
            indicators=indicators,
            timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        )