"""
移动平均线交叉策略
基于快慢均线的金叉死叉信号
"""

import pandas as pd
from .base_strategy import BaseStrategy, StrategyFactory, Signal, AnalysisResult
from .base_strategy import calculate_sma, calculate_ema, calculate_rsi, calculate_macd

@StrategyFactory.register_strategy
class MACrossoverStrategy(BaseStrategy):
    """
    移动平均线交叉策略
    
    策略逻辑:
    1. 快线上穿慢线时买入(金叉)
    2. 快线下穿慢线时卖出(死叉)
    3. 结合成交量和RSI确认
    """
    
    def __init__(self):
        super().__init__()
        self.timeframe = '15m'
        self.startup_candle_count = 60
        
        # 均线参数
        self.ma_fast = 20
        self.ma_slow = 50
        
        # RSI参数
        self.rsi_period = 14
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        
        # 成交量参数
        self.volume_factor = 1.2
    
    def get_strategy_name(self) -> str:
        return "移动平均线交叉策略"
    
    def get_strategy_description(self) -> str:
        return "基于快慢均线的金叉死叉信号，适合趋势跟随"
    
    def calculate_indicators(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        
        # 移动平均线
        dataframe['ma_fast'] = calculate_ema(dataframe['close'], self.ma_fast)
        dataframe['ma_slow'] = calculate_ema(dataframe['close'], self.ma_slow)
        
        # 均线关系
        dataframe['ma_fast_above_slow'] = dataframe['ma_fast'] > dataframe['ma_slow']
        dataframe['ma_gap'] = (dataframe['ma_fast'] - dataframe['ma_slow']) / dataframe['ma_slow']
        
        # 金叉死叉检测
        dataframe['golden_cross'] = (
            (dataframe['ma_fast'] > dataframe['ma_slow']) & 
            (dataframe['ma_fast'].shift(1) <= dataframe['ma_slow'].shift(1))
        )
        dataframe['death_cross'] = (
            (dataframe['ma_fast'] < dataframe['ma_slow']) & 
            (dataframe['ma_fast'].shift(1) >= dataframe['ma_slow'].shift(1))
        )
        
        # 价格与均线关系
        dataframe['price_above_ma_fast'] = dataframe['close'] > dataframe['ma_fast']
        dataframe['price_above_ma_slow'] = dataframe['close'] > dataframe['ma_slow']
        dataframe['price_between_ma'] = (
            (dataframe['close'] > dataframe['ma_fast']) & 
            (dataframe['close'] < dataframe['ma_slow'])
        ) | (
            (dataframe['close'] < dataframe['ma_fast']) & 
            (dataframe['close'] > dataframe['ma_slow'])
        )
        
        # 均线趋势
        dataframe['ma_fast_rising'] = dataframe['ma_fast'] > dataframe['ma_fast'].shift(3)
        dataframe['ma_slow_rising'] = dataframe['ma_slow'] > dataframe['ma_slow'].shift(5)
        
        # RSI
        dataframe['rsi'] = calculate_rsi(dataframe['close'], self.rsi_period)
        
        # 成交量指标
        dataframe['volume_sma'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
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
        
        # 提取关键指标
        indicators = {
            'ma_fast': float(last_row.get('ma_fast', 0)),
            'ma_slow': float(last_row.get('ma_slow', 0)),
            'ma_gap': float(last_row.get('ma_gap', 0)),
            'rsi': float(last_row.get('rsi', 50)),
            'volume_ratio': float(last_row.get('volume_ratio', 1)),
            'close': float(last_row.get('close', 0))
        }
        
        reasons = []
        
        # 买入信号检测 - 金叉
        if last_row.get('golden_cross', False):
            confidence = 0.8
            reasons.append(f"均线金叉(快线{indicators['ma_fast']:.2f}>慢线{indicators['ma_slow']:.2f})")
            
            # 增强信号条件
            if last_row.get('price_above_ma_fast', False):
                confidence += 0.1
                reasons.append("价格在快线上方")
            
            if last_row.get('ma_fast_rising', False):
                confidence += 0.05
                reasons.append("快线上升趋势")
            
            if indicators['rsi'] > 50 and indicators['rsi'] < self.rsi_overbought:
                confidence += 0.05
                reasons.append(f"RSI({indicators['rsi']:.1f})偏强但未超买")
            
            if last_row.get('volume_ratio', 1) > self.volume_factor:
                confidence += 0.05
                reasons.append(f"成交量放大({indicators['volume_ratio']:.1f}倍)")
            
            if last_row.get('macd_bullish', False):
                confidence += 0.05
                reasons.append("MACD支持多头")
            
            return AnalysisResult(
                signal=Signal.BUY,
                confidence=min(confidence, 1.0),
                reasons=reasons,
                indicators=indicators,
                timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        
        # 卖出信号检测 - 死叉
        elif last_row.get('death_cross', False):
            confidence = 0.8
            reasons.append(f"均线死叉(快线{indicators['ma_fast']:.2f}<慢线{indicators['ma_slow']:.2f})")
            
            # 增强信号条件
            if not last_row.get('price_above_ma_fast', True):
                confidence += 0.1
                reasons.append("价格跌破快线")
            
            if not last_row.get('ma_fast_rising', True):
                confidence += 0.05
                reasons.append("快线下降趋势")
            
            if indicators['rsi'] < 50 and indicators['rsi'] > self.rsi_oversold:
                confidence += 0.05
                reasons.append(f"RSI({indicators['rsi']:.1f})偏弱但未超卖")
            
            if last_row.get('volume_ratio', 1) > self.volume_factor:
                confidence += 0.05
                reasons.append(f"成交量放大({indicators['volume_ratio']:.1f}倍)")
            
            if not last_row.get('macd_bullish', True):
                confidence += 0.05
                reasons.append("MACD转为空头")
            
            return AnalysisResult(
                signal=Signal.SELL,
                confidence=min(confidence, 1.0),
                reasons=reasons,
                indicators=indicators,
                timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        
        # 趋势跟随信号
        elif last_row.get('ma_fast_above_slow', False):
            if (last_row.get('price_above_ma_fast', False) and 
                last_row.get('ma_fast_rising', False) and 
                indicators['rsi'] > 50):
                reasons = ["快线在慢线上方", "价格强势", f"RSI({indicators['rsi']:.1f})偏强"]
                return AnalysisResult(
                    signal=Signal.BUY,
                    confidence=0.6,
                    reasons=reasons,
                    indicators=indicators,
                    timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                )
        
        elif not last_row.get('ma_fast_above_slow', True):
            if (not last_row.get('price_above_ma_fast', True) and 
                not last_row.get('ma_fast_rising', True) and 
                indicators['rsi'] < 50):
                reasons = ["快线在慢线下方", "价格疲弱", f"RSI({indicators['rsi']:.1f})偏弱"]
                return AnalysisResult(
                    signal=Signal.SELL,
                    confidence=0.6,
                    reasons=reasons,
                    indicators=indicators,
                    timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                )
        
        # 默认观望
        reasons = ["均线无明确交叉信号，等待机会"]
        return AnalysisResult(
            signal=Signal.HOLD,
            confidence=0.5,
            reasons=reasons,
            indicators=indicators,
            timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        )