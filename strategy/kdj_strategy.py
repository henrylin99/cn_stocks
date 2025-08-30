"""
KDJ随机指标策略
基于KDJ指标的超买超卖和金叉死叉信号
"""

import pandas as pd
from .base_strategy import BaseStrategy, StrategyFactory, Signal, AnalysisResult
from .base_strategy import calculate_ema, calculate_rsi

@StrategyFactory.register_strategy
class KDJStrategy(BaseStrategy):
    """
    KDJ随机指标策略
    
    策略逻辑:
    1. K线上穿D线且在超卖区时买入
    2. K线下穿D线且在超买区时卖出
    3. 结合J值和RSI确认信号
    """
    
    def __init__(self):
        super().__init__()
        self.timeframe = '15m'
        self.startup_candle_count = 50
        
        # KDJ参数
        self.kdj_period = 9
        self.k_period = 3
        self.d_period = 3
        
        # 超买超卖参数
        self.oversold_threshold = 20
        self.overbought_threshold = 80
        
        # RSI辅助参数
        self.rsi_period = 14
        
        # 成交量参数
        self.volume_factor = 1.2
    
    def get_strategy_name(self) -> str:
        return "KDJ随机指标策略"
    
    def get_strategy_description(self) -> str:
        return "基于KDJ指标的金叉死叉和超买超卖信号"
    
    def calculate_kdj(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """计算KDJ指标"""
        
        # 计算RSV (Raw Stochastic Value)
        low_min = dataframe['low'].rolling(window=self.kdj_period).min()
        high_max = dataframe['high'].rolling(window=self.kdj_period).max()
        
        rsv = (dataframe['close'] - low_min) / (high_max - low_min) * 100
        
        # 计算K值 (K = 2/3 * K_prev + 1/3 * RSV)
        k_values = []
        k_prev = 50  # 初始值
        
        for rsv_val in rsv:
            if pd.isna(rsv_val):
                k_values.append(k_prev)
            else:
                k_current = (2/3) * k_prev + (1/3) * rsv_val
                k_values.append(k_current)
                k_prev = k_current
        
        dataframe['k'] = pd.Series(k_values, index=dataframe.index)
        
        # 计算D值 (D = 2/3 * D_prev + 1/3 * K)
        d_values = []
        d_prev = 50  # 初始值
        
        for k_val in dataframe['k']:
            if pd.isna(k_val):
                d_values.append(d_prev)
            else:
                d_current = (2/3) * d_prev + (1/3) * k_val
                d_values.append(d_current)
                d_prev = d_current
        
        dataframe['d'] = pd.Series(d_values, index=dataframe.index)
        
        # 计算J值 (J = 3K - 2D)
        dataframe['j'] = 3 * dataframe['k'] - 2 * dataframe['d']
        
        return dataframe
    
    def calculate_indicators(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        
        # KDJ指标
        dataframe = self.calculate_kdj(dataframe)
        
        # KDJ信号
        dataframe['k_above_d'] = dataframe['k'] > dataframe['d']
        dataframe['k_below_d'] = dataframe['k'] < dataframe['d']
        
        # 金叉死叉检测
        dataframe['kdj_golden_cross'] = (
            (dataframe['k'] > dataframe['d']) & 
            (dataframe['k'].shift(1) <= dataframe['d'].shift(1))
        )
        dataframe['kdj_death_cross'] = (
            (dataframe['k'] < dataframe['d']) & 
            (dataframe['k'].shift(1) >= dataframe['d'].shift(1))
        )
        
        # 超买超卖区域
        dataframe['kdj_oversold'] = (dataframe['k'] < self.oversold_threshold) & (dataframe['d'] < self.oversold_threshold)
        dataframe['kdj_overbought'] = (dataframe['k'] > self.overbought_threshold) & (dataframe['d'] > self.overbought_threshold)
        
        # J值极值
        dataframe['j_oversold'] = dataframe['j'] < 0
        dataframe['j_overbought'] = dataframe['j'] > 100
        
        # KDJ趋势
        dataframe['kdj_rising'] = (dataframe['k'] > dataframe['k'].shift(1)) & (dataframe['d'] > dataframe['d'].shift(1))
        dataframe['kdj_falling'] = (dataframe['k'] < dataframe['k'].shift(1)) & (dataframe['d'] < dataframe['d'].shift(1))
        
        # RSI辅助
        dataframe['rsi'] = calculate_rsi(dataframe['close'], self.rsi_period)
        
        # 成交量指标
        dataframe['volume_sma'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # 价格趋势
        dataframe['ema_20'] = calculate_ema(dataframe['close'], 20)
        dataframe['price_trend_up'] = dataframe['close'] > dataframe['ema_20']
        
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
            'k': float(last_row.get('k', 50)),
            'd': float(last_row.get('d', 50)),
            'j': float(last_row.get('j', 50)),
            'rsi': float(last_row.get('rsi', 50)),
            'volume_ratio': float(last_row.get('volume_ratio', 1)),
            'close': float(last_row.get('close', 0))
        }
        
        reasons = []
        
        # 买入信号检测
        if last_row.get('kdj_golden_cross', False) and last_row.get('kdj_oversold', False):
            confidence = 0.85
            reasons.append(f"KDJ金叉且超卖(K:{indicators['k']:.1f}, D:{indicators['d']:.1f})")
            
            # 增强信号条件
            if last_row.get('j_oversold', False):
                confidence += 0.1
                reasons.append(f"J值({indicators['j']:.1f})极度超卖")
            
            if indicators['rsi'] < 40:
                confidence += 0.05
                reasons.append(f"RSI({indicators['rsi']:.1f})确认超卖")
            
            if last_row.get('volume_ratio', 1) > self.volume_factor:
                confidence += 0.05
                reasons.append(f"成交量放大({indicators['volume_ratio']:.1f}倍)")
            
            return AnalysisResult(
                signal=Signal.BUY,
                confidence=min(confidence, 1.0),
                reasons=reasons,
                indicators=indicators,
                timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        
        # 一般买入信号
        elif last_row.get('kdj_golden_cross', False):
            confidence = 0.7
            reasons.append(f"KDJ金叉(K:{indicators['k']:.1f}, D:{indicators['d']:.1f})")
            
            if last_row.get('price_trend_up', False):
                confidence += 0.1
                reasons.append("价格趋势向上")
            
            if last_row.get('kdj_rising', False):
                confidence += 0.05
                reasons.append("KDJ整体上升")
            
            return AnalysisResult(
                signal=Signal.BUY,
                confidence=min(confidence, 1.0),
                reasons=reasons,
                indicators=indicators,
                timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        
        # 卖出信号检测
        elif last_row.get('kdj_death_cross', False) and last_row.get('kdj_overbought', False):
            confidence = 0.85
            reasons.append(f"KDJ死叉且超买(K:{indicators['k']:.1f}, D:{indicators['d']:.1f})")
            
            # 增强信号条件
            if last_row.get('j_overbought', False):
                confidence += 0.1
                reasons.append(f"J值({indicators['j']:.1f})极度超买")
            
            if indicators['rsi'] > 60:
                confidence += 0.05
                reasons.append(f"RSI({indicators['rsi']:.1f})确认超买")
            
            if last_row.get('volume_ratio', 1) > self.volume_factor:
                confidence += 0.05
                reasons.append(f"成交量放大({indicators['volume_ratio']:.1f}倍)")
            
            return AnalysisResult(
                signal=Signal.SELL,
                confidence=min(confidence, 1.0),
                reasons=reasons,
                indicators=indicators,
                timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        
        # 一般卖出信号
        elif last_row.get('kdj_death_cross', False):
            confidence = 0.7
            reasons.append(f"KDJ死叉(K:{indicators['k']:.1f}, D:{indicators['d']:.1f})")
            
            if not last_row.get('price_trend_up', True):
                confidence += 0.1
                reasons.append("价格趋势向下")
            
            if last_row.get('kdj_falling', False):
                confidence += 0.05
                reasons.append("KDJ整体下降")
            
            return AnalysisResult(
                signal=Signal.SELL,
                confidence=min(confidence, 1.0),
                reasons=reasons,
                indicators=indicators,
                timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        
        # 持续信号
        elif last_row.get('k_above_d', False) and last_row.get('kdj_rising', False):
            if indicators['k'] > 50 and indicators['d'] > 50:
                reasons = [f"KDJ多头排列(K:{indicators['k']:.1f}>D:{indicators['d']:.1f})", "指标上升中"]
                return AnalysisResult(
                    signal=Signal.BUY,
                    confidence=0.55,
                    reasons=reasons,
                    indicators=indicators,
                    timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                )
        
        elif last_row.get('k_below_d', False) and last_row.get('kdj_falling', False):
            if indicators['k'] < 50 and indicators['d'] < 50:
                reasons = [f"KDJ空头排列(K:{indicators['k']:.1f}<D:{indicators['d']:.1f})", "指标下降中"]
                return AnalysisResult(
                    signal=Signal.SELL,
                    confidence=0.55,
                    reasons=reasons,
                    indicators=indicators,
                    timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                )
        
        # 默认观望
        reasons = [f"KDJ中性(K:{indicators['k']:.1f}, D:{indicators['d']:.1f})，等待交叉信号"]
        return AnalysisResult(
            signal=Signal.HOLD,
            confidence=0.5,
            reasons=reasons,
            indicators=indicators,
            timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        )