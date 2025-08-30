"""
ADX趋势强度策略
基于ADX指标识别和跟随强趋势的策略
适配新的分析系统
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
from .base_strategy import BaseStrategy, StrategyFactory, Signal, AnalysisResult
from .base_strategy import (
    calculate_sma, calculate_ema, calculate_rsi, 
    calculate_bollinger_bands, calculate_macd, calculate_atr, calculate_adx
)

@StrategyFactory.register_strategy
class ADXTrendStrategy(BaseStrategy):
    """
    ADX趋势强度策略
    
    策略逻辑:
    1. 使用ADX识别趋势强度
    2. 使用DI+和DI-确定趋势方向  
    3. 当ADX上升且DI+>DI-时买入
    4. 当ADX下降或DI->DI+时卖出
    5. 结合其他指标过滤假信号
    """
    
    def __init__(self):
        super().__init__()
        self.timeframe = '15m'
        self.startup_candle_count = 100
        
        # ADX参数
        self.adx_period = 14
        self.adx_threshold_strong = 30
        self.adx_threshold_weak = 20
        
        # DI差值参数
        self.di_diff_threshold = 5.0
        
        # ADX趋势参数
        self.adx_slope_periods = 5
        self.adx_min_slope = 1.5
        
        # 确认指标参数
        self.ema_fast = 12
        self.ema_slow = 30
        self.rsi_period = 14
        self.rsi_buy_threshold = 50
        self.rsi_sell_threshold = 75
        
        # MACD参数
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        
        # 成交量参数
        self.volume_factor = 1.6
        
        # ATR参数
        self.atr_period = 14
    
    def get_strategy_name(self) -> str:
        return "ADX趋势强度策略"
    
    def get_strategy_description(self) -> str:
        return "基于ADX指标识别和跟随强趋势，结合多个技术指标确认信号"
    
    def calculate_indicators(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        
        # ADX指标组
        adx, di_plus, di_minus = calculate_adx(
            dataframe['high'], dataframe['low'], dataframe['close'], self.adx_period
        )
        dataframe['adx'] = adx
        dataframe['di_plus'] = di_plus  
        dataframe['di_minus'] = di_minus
        
        # DI差值和比率
        dataframe['di_diff'] = dataframe['di_plus'] - dataframe['di_minus']
        dataframe['di_ratio'] = dataframe['di_plus'] / (dataframe['di_minus'] + 0.001)
        
        # ADX趋势和斜率
        dataframe['adx_slope'] = (dataframe['adx'] - dataframe['adx'].shift(self.adx_slope_periods)) / self.adx_slope_periods
        dataframe['adx_rising'] = dataframe['adx_slope'] > self.adx_min_slope
        dataframe['adx_falling'] = dataframe['adx_slope'] < -self.adx_min_slope
        
        # ADX强度分类
        dataframe['adx_very_strong'] = dataframe['adx'] > 50
        dataframe['adx_strong'] = (dataframe['adx'] > self.adx_threshold_strong) & (dataframe['adx'] <= 50)
        dataframe['adx_moderate'] = (dataframe['adx'] > 25) & (dataframe['adx'] <= self.adx_threshold_strong)
        dataframe['adx_weak'] = dataframe['adx'] <= self.adx_threshold_weak
        
        # 趋势方向
        dataframe['bullish_trend'] = (dataframe['di_plus'] > dataframe['di_minus']) & (dataframe['di_diff'] > self.di_diff_threshold)
        dataframe['bearish_trend'] = (dataframe['di_minus'] > dataframe['di_plus']) & (dataframe['di_diff'] < -self.di_diff_threshold)
        
        # EMA趋势确认
        dataframe['ema_fast'] = calculate_ema(dataframe['close'], self.ema_fast)
        dataframe['ema_slow'] = calculate_ema(dataframe['close'], self.ema_slow)
        dataframe['ema_trend_up'] = dataframe['ema_fast'] > dataframe['ema_slow']
        dataframe['price_above_ema_fast'] = dataframe['close'] > dataframe['ema_fast']
        
        # RSI
        dataframe['rsi'] = calculate_rsi(dataframe['close'], self.rsi_period)
        
        # MACD
        macd_line, signal_line, histogram = calculate_macd(
            dataframe['close'], self.macd_fast, self.macd_slow, self.macd_signal
        )
        dataframe['macd'] = macd_line
        dataframe['macd_signal'] = signal_line  
        dataframe['macd_hist'] = histogram
        dataframe['macd_bullish'] = dataframe['macd'] > dataframe['macd_signal']
        
        # ATR
        dataframe['atr'] = calculate_atr(dataframe['high'], dataframe['low'], dataframe['close'], self.atr_period)
        dataframe['atr_percent'] = dataframe['atr'] / dataframe['close']
        
        # 成交量指标
        dataframe['volume_sma'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # 布林带
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(dataframe['close'], 20, 2.0)
        dataframe['bb_upper'] = bb_upper
        dataframe['bb_middle'] = bb_middle
        dataframe['bb_lower'] = bb_lower
        dataframe['bb_percent'] = (dataframe['close'] - dataframe['bb_lower']) / (dataframe['bb_upper'] - dataframe['bb_lower'])
        
        # 价格动量
        dataframe['price_momentum'] = (dataframe['close'] - dataframe['close'].shift(5)) / dataframe['close'].shift(5)
        
        # 趋势综合评分
        trend_score = 0
        trend_score += np.where(dataframe['bullish_trend'], 2, 0)  # ADX方向
        trend_score += np.where(dataframe['adx_strong'] | dataframe['adx_very_strong'], 2, 0)  # ADX强度
        trend_score += np.where(dataframe['adx_rising'], 1, 0)  # ADX上升
        trend_score += np.where(dataframe['ema_trend_up'], 1, 0)  # EMA趋势
        trend_score += np.where(dataframe['price_above_ema_fast'], 1, 0)  # 价格位置
        trend_score += np.where(dataframe['macd_bullish'], 1, 0)  # MACD
        
        dataframe['trend_score'] = trend_score
        
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
        
        # 获取最新一行数据
        last_row = dataframe.iloc[-1]
        
        # 提取关键指标
        indicators = {
            'adx': float(last_row.get('adx', 0)),
            'di_plus': float(last_row.get('di_plus', 0)),
            'di_minus': float(last_row.get('di_minus', 0)),
            'di_diff': float(last_row.get('di_diff', 0)),
            'adx_slope': float(last_row.get('adx_slope', 0)),
            'rsi': float(last_row.get('rsi', 50)),
            'ema_fast': float(last_row.get('ema_fast', 0)),
            'ema_slow': float(last_row.get('ema_slow', 0)),
            'macd': float(last_row.get('macd', 0)),
            'macd_signal': float(last_row.get('macd_signal', 0)),
            'trend_score': float(last_row.get('trend_score', 0)),
            'close': float(last_row.get('close', 0)),
            'volume_ratio': float(last_row.get('volume_ratio', 1))
        }
        
        # 买入条件检查
        buy_conditions = []
        buy_reasons = []
        
        # 主要ADX信号
        if last_row.get('bullish_trend', False):
            buy_conditions.append(True)
            buy_reasons.append("DI+大于DI-，牛市趋势")
        else:
            buy_conditions.append(False)
            
        if last_row.get('adx', 0) > self.adx_threshold_strong:
            buy_conditions.append(True) 
            buy_reasons.append(f"ADX({indicators['adx']:.1f})强度足够")
        else:
            buy_conditions.append(False)
            
        if last_row.get('adx_rising', False):
            buy_conditions.append(True)
            buy_reasons.append("ADX上升趋势")
        else:
            buy_conditions.append(False)
            
        # 趋势确认
        if last_row.get('ema_trend_up', False):
            buy_conditions.append(True)
            buy_reasons.append("EMA趋势向上")
        else:
            buy_conditions.append(False)
            
        if last_row.get('price_above_ema_fast', False):
            buy_conditions.append(True)
            buy_reasons.append("价格在快EMA之上")
        else:
            buy_conditions.append(False)
            
        # RSI确认
        rsi = last_row.get('rsi', 50)
        if self.rsi_buy_threshold < rsi < 80:
            buy_conditions.append(True)
            buy_reasons.append(f"RSI({rsi:.1f})在合理区间")
        else:
            buy_conditions.append(False)
            
        # MACD确认
        if last_row.get('macd_bullish', False):
            buy_conditions.append(True)
            buy_reasons.append("MACD多头信号")
        else:
            buy_conditions.append(False)
            
        # 成交量确认
        volume_ratio = last_row.get('volume_ratio', 1)
        if volume_ratio > self.volume_factor:
            buy_conditions.append(True)
            buy_reasons.append(f"成交量放大({volume_ratio:.1f}倍)")
        else:
            buy_conditions.append(False)
            
        # 趋势评分
        trend_score = last_row.get('trend_score', 0)
        if trend_score >= 6:
            buy_conditions.append(True)
            buy_reasons.append(f"趋势评分高({trend_score}分)")
        else:
            buy_conditions.append(False)
        
        # 卖出条件检查
        sell_conditions = []
        sell_reasons = []
        
        if last_row.get('bearish_trend', False):
            sell_conditions.append(True)
            sell_reasons.append("DI-大于DI+，熊市趋势")
            
        if last_row.get('adx', 0) < self.adx_threshold_weak:
            sell_conditions.append(True)
            sell_reasons.append(f"ADX({indicators['adx']:.1f})弱化")
            
        if last_row.get('adx_falling', False):
            sell_conditions.append(True)
            sell_reasons.append("ADX下降趋势")
            
        if not last_row.get('ema_trend_up', True):
            sell_conditions.append(True)
            sell_reasons.append("EMA趋势转向")
            
        if rsi > self.rsi_sell_threshold:
            sell_conditions.append(True)
            sell_reasons.append(f"RSI({rsi:.1f})超买")
            
        if not last_row.get('macd_bullish', True):
            sell_conditions.append(True)
            sell_reasons.append("MACD死叉")
            
        if trend_score <= 3:
            sell_conditions.append(True)
            sell_reasons.append(f"趋势评分下降({trend_score}分)")
        
        # 决策逻辑
        buy_score = sum(buy_conditions) / len(buy_conditions) if buy_conditions else 0
        sell_score = sum(sell_conditions) / len(sell_conditions) if sell_conditions else 0
        
        if buy_score >= 0.7:  # 70%以上买入条件满足
            signal = Signal.BUY
            confidence = buy_score
            reasons = buy_reasons
        elif sell_score >= 0.4:  # 40%以上卖出条件满足
            signal = Signal.SELL
            confidence = sell_score 
            reasons = sell_reasons
        else:
            signal = Signal.HOLD
            confidence = 0.5
            reasons = ["买卖信号不明确，建议观望"]
        
        return AnalysisResult(
            signal=signal,
            confidence=confidence,
            reasons=reasons,
            indicators=indicators,
            timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        )