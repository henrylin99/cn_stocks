"""
RSI策略
基于相对强弱指标的超买超卖策略
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
class RSIStrategy(BaseStrategy):
    """
    RSI策略
    
    策略逻辑:
    1. RSI < 30 时买入 (超卖)
    2. RSI > 70 时卖出 (超买)
    3. 结合趋势和成交量确认
    """
    
    def __init__(self):
        super().__init__()
        self.timeframe = '15m'
        self.startup_candle_count = 50
        
        # RSI参数
        self.rsi_period = 14
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.rsi_middle = 50
        
        # 趋势确认参数
        self.ema_fast = 20
        self.ema_slow = 50
        
        # 成交量参数
        self.volume_factor = 1.3
    
    def get_strategy_name(self) -> str:
        return "RSI超买超卖策略"
    
    def get_strategy_description(self) -> str:
        return "基于RSI指标识别超买超卖区域，寻找反转机会"
    
    def calculate_indicators(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        
        # RSI
        dataframe['rsi'] = calculate_rsi(dataframe['close'], self.rsi_period)
        
        # RSI区域判断
        dataframe['rsi_oversold'] = dataframe['rsi'] < self.rsi_oversold
        dataframe['rsi_overbought'] = dataframe['rsi'] > self.rsi_overbought
        dataframe['rsi_neutral'] = (dataframe['rsi'] >= self.rsi_oversold) & (dataframe['rsi'] <= self.rsi_overbought)
        
        # RSI趋势
        dataframe['rsi_rising'] = dataframe['rsi'] > dataframe['rsi'].shift(1)
        dataframe['rsi_falling'] = dataframe['rsi'] < dataframe['rsi'].shift(1)
        
        # RSI背离检测
        dataframe['price_higher'] = dataframe['close'] > dataframe['close'].shift(5)
        dataframe['price_lower'] = dataframe['close'] < dataframe['close'].shift(5)
        dataframe['rsi_higher'] = dataframe['rsi'] > dataframe['rsi'].shift(5)
        dataframe['rsi_lower'] = dataframe['rsi'] < dataframe['rsi'].shift(5)
        
        # 看涨背离：价格创新低但RSI没有创新低
        dataframe['bullish_divergence'] = (
            dataframe['price_lower'] & ~dataframe['rsi_lower']
        )
        
        # 看跌背离：价格创新高但RSI没有创新高
        dataframe['bearish_divergence'] = (
            dataframe['price_higher'] & ~dataframe['rsi_higher']
        )
        
        # EMA趋势确认
        dataframe['ema_fast'] = calculate_ema(dataframe['close'], self.ema_fast)
        dataframe['ema_slow'] = calculate_ema(dataframe['close'], self.ema_slow)
        dataframe['ema_trend_up'] = dataframe['ema_fast'] > dataframe['ema_slow']
        dataframe['price_above_ema'] = dataframe['close'] > dataframe['ema_fast']
        
        # 成交量指标
        dataframe['volume_sma'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        dataframe['high_volume'] = dataframe['volume_ratio'] > self.volume_factor
        
        # MACD辅助
        macd_line, signal_line, histogram = calculate_macd(dataframe['close'])
        dataframe['macd'] = macd_line
        dataframe['macd_signal'] = signal_line
        dataframe['macd_bullish'] = dataframe['macd'] > dataframe['macd_signal']
        
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
            'rsi': float(last_row.get('rsi', 50)),
            'rsi_prev': float(prev_row.get('rsi', 50)),
            'close': float(last_row.get('close', 0)),
            'volume_ratio': float(last_row.get('volume_ratio', 1)),
            'ema_fast': float(last_row.get('ema_fast', 0)),
            'ema_slow': float(last_row.get('ema_slow', 0))
        }
        
        reasons = []
        
        # 买入信号检测
        if last_row.get('rsi_oversold', False):
            confidence = 0.7
            reasons.append(f"RSI({indicators['rsi']:.1f})超卖")
            
            # 增强信号条件
            if last_row.get('rsi_rising', False):
                confidence += 0.1
                reasons.append("RSI开始回升")
            
            if last_row.get('bullish_divergence', False):
                confidence += 0.15
                reasons.append("看涨背离")
            
            if last_row.get('ema_trend_up', False):
                confidence += 0.05
                reasons.append("主趋势向上")
            
            if last_row.get('high_volume', False):
                confidence += 0.05
                reasons.append("成交量放大")
                
            if last_row.get('macd_bullish', False):
                confidence += 0.05
                reasons.append("MACD支持")
            
            return AnalysisResult(
                signal=Signal.BUY,
                confidence=min(confidence, 1.0),
                reasons=reasons,
                indicators=indicators,
                timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        
        # 卖出信号检测
        elif last_row.get('rsi_overbought', False):
            confidence = 0.7
            reasons.append(f"RSI({indicators['rsi']:.1f})超买")
            
            # 增强信号条件
            if last_row.get('rsi_falling', False):
                confidence += 0.1
                reasons.append("RSI开始回落")
            
            if last_row.get('bearish_divergence', False):
                confidence += 0.15
                reasons.append("看跌背离")
            
            if not last_row.get('ema_trend_up', True):
                confidence += 0.05
                reasons.append("主趋势向下")
            
            if last_row.get('high_volume', False):
                confidence += 0.05
                reasons.append("成交量放大")
                
            if not last_row.get('macd_bullish', True):
                confidence += 0.05
                reasons.append("MACD转弱")
            
            return AnalysisResult(
                signal=Signal.SELL,
                confidence=min(confidence, 1.0),
                reasons=reasons,
                indicators=indicators,
                timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        
        # RSI中性区域的趋势跟随
        elif indicators['rsi'] > self.rsi_middle and last_row.get('ema_trend_up', False):
            if last_row.get('price_above_ema', False) and last_row.get('rsi_rising', False):
                reasons = [f"RSI({indicators['rsi']:.1f})中性偏强", "趋势向上", "价格强势"]
                return AnalysisResult(
                    signal=Signal.BUY,
                    confidence=0.55,
                    reasons=reasons,
                    indicators=indicators,
                    timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                )
        
        elif indicators['rsi'] < self.rsi_middle and not last_row.get('ema_trend_up', True):
            if not last_row.get('price_above_ema', True) and last_row.get('rsi_falling', False):
                reasons = [f"RSI({indicators['rsi']:.1f})中性偏弱", "趋势向下", "价格疲弱"]
                return AnalysisResult(
                    signal=Signal.SELL,
                    confidence=0.55,
                    reasons=reasons,
                    indicators=indicators,
                    timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                )
        
        # 默认观望
        reasons = [f"RSI({indicators['rsi']:.1f})中性区域，等待明确信号"]
        return AnalysisResult(
            signal=Signal.HOLD,
            confidence=0.5,
            reasons=reasons,
            indicators=indicators,
            timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        )