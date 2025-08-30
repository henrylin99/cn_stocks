"""
策略基类和信号枚举
统一的股票分析策略接口，兼容freqtrade策略结构
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Tuple, Optional
import pandas as pd
import numpy as np
import talib.abstract as ta
from dataclasses import dataclass

class Signal(Enum):
    """交易信号枚举"""
    BUY = "买入"
    SELL = "卖出" 
    HOLD = "观望"

@dataclass
class AnalysisResult:
    """分析结果数据类"""
    signal: Signal
    confidence: float  # 信号置信度 (0-1)
    reasons: list     # 信号原因列表
    indicators: dict  # 相关技术指标值
    timestamp: str    # 分析时间

class BaseStrategy(ABC):
    """
    统一的策略基类
    所有策略需要继承此类并实现相应方法
    """
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.timeframe = '15m'  # 默认15分钟
        self.startup_candle_count = 50  # 启动需要的K线数量
        
    @abstractmethod
    def get_strategy_name(self) -> str:
        """获取策略名称"""
        pass
    
    @abstractmethod 
    def get_strategy_description(self) -> str:
        """获取策略描述"""
        pass
    
    @abstractmethod
    def calculate_indicators(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        计算技术指标
        Args:
            dataframe: 包含OHLCV数据的DataFrame
        Returns:
            添加了技术指标的DataFrame
        """
        pass
    
    @abstractmethod
    def generate_signal(self, dataframe: pd.DataFrame) -> AnalysisResult:
        """
        生成交易信号
        Args:
            dataframe: 包含OHLCV和技术指标的DataFrame
        Returns:
            AnalysisResult对象，包含信号和相关信息
        """
        pass
    
    def validate_data(self, dataframe: pd.DataFrame) -> bool:
        """
        验证数据完整性
        """
        if dataframe is None or dataframe.empty:
            return False
            
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in dataframe.columns]
        
        if missing_columns:
            print(f"缺少必要的数据列: {missing_columns}")
            return False
            
        if len(dataframe) < self.startup_candle_count:
            print(f"数据量不足，需要至少{self.startup_candle_count}条记录")
            return False
            
        return True
    
    def preprocess_data(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        数据预处理
        """
        # 确保数据类型正确
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            if col in dataframe.columns:
                dataframe[col] = pd.to_numeric(dataframe[col], errors='coerce')
        
        # 按时间排序
        if 'timestamp' in dataframe.columns:
            dataframe = dataframe.sort_values('timestamp').reset_index(drop=True)
        
        # 删除无效数据
        dataframe = dataframe.dropna(subset=['close'])
        
        return dataframe
    
    def _clean_nan_values(self, indicators: Dict) -> Dict:
        """清理指标字典中的NaN值"""
        import math
        cleaned_indicators = {}
        
        for key, value in indicators.items():
            if isinstance(value, (int, float)):
                if math.isnan(value) or math.isinf(value):
                    # 将NaN/Inf替换为0或合理的默认值
                    if 'confidence' in key.lower() or 'percent' in key.lower():
                        cleaned_indicators[key] = 0.0
                    elif 'price' in key.lower():
                        cleaned_indicators[key] = 0.0
                    else:
                        cleaned_indicators[key] = 0.0
                else:
                    cleaned_indicators[key] = value
            else:
                cleaned_indicators[key] = value
        
        return cleaned_indicators
    
    def analyze(self, dataframe: pd.DataFrame) -> AnalysisResult:
        """
        主分析方法 - 对外统一接口
        """
        # 数据验证
        if not self.validate_data(dataframe):
            return AnalysisResult(
                signal=Signal.HOLD,
                confidence=0.0,
                reasons=["数据验证失败"],
                indicators={},
                timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        
        try:
            # 数据预处理
            dataframe = self.preprocess_data(dataframe)
            
            # 计算技术指标
            dataframe = self.calculate_indicators(dataframe)
            
            # 生成交易信号
            result = self.generate_signal(dataframe)
            
            # 清理结果中的NaN值
            if result.indicators:
                result.indicators = self._clean_nan_values(result.indicators)
            
            # 检查confidence是否为NaN
            import math
            if math.isnan(result.confidence) or math.isinf(result.confidence):
                result.confidence = 0.0
            
            return result
            
        except Exception as e:
            print(f"策略分析错误 [{self.name}]: {e}")
            return AnalysisResult(
                signal=Signal.HOLD,
                confidence=0.0,
                reasons=[f"分析异常: {str(e)}"],
                indicators={},
                timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            )

class StrategyFactory:
    """策略工厂类"""
    
    _strategies = {}
    
    @classmethod
    def register_strategy(cls, strategy_class):
        """注册策略类"""
        strategy_name = strategy_class.__name__
        cls._strategies[strategy_name] = strategy_class
        return strategy_class
    
    @classmethod
    def create_strategy(cls, strategy_name: str) -> BaseStrategy:
        """创建策略实例"""
        if strategy_name not in cls._strategies:
            raise ValueError(f"未找到策略: {strategy_name}")
        
        strategy_class = cls._strategies[strategy_name]
        return strategy_class()
    
    @classmethod
    def get_available_strategies(cls) -> list:
        """获取所有可用策略"""
        return list(cls._strategies.keys())

# 辅助函数
def calculate_sma(data: pd.Series, period: int) -> pd.Series:
    """简单移动平均"""
    return data.rolling(window=period).mean()

def calculate_ema(data: pd.Series, period: int) -> pd.Series:
    """指数移动平均"""
    return data.ewm(span=period).mean()

def calculate_rsi(data: pd.Series, period: int = 14) -> pd.Series:
    """相对强弱指标"""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_bollinger_bands(data: pd.Series, period: int = 20, std: float = 2.0) -> tuple:
    """布林带"""
    sma = calculate_sma(data, period)
    std_dev = data.rolling(window=period).std()
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    return upper, sma, lower

def calculate_macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """MACD"""
    ema_fast = calculate_ema(data, fast)
    ema_slow = calculate_ema(data, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """平均真实范围"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> tuple:
    """ADX指标"""
    try:
        import talib
        # 使用talib计算ADX
        adx = talib.ADX(high.values, low.values, close.values, timeperiod=period)
        di_plus = talib.PLUS_DI(high.values, low.values, close.values, timeperiod=period)
        di_minus = talib.MINUS_DI(high.values, low.values, close.values, timeperiod=period)
        
        # 转换回pandas Series
        adx_series = pd.Series(adx, index=close.index)
        di_plus_series = pd.Series(di_plus, index=close.index)
        di_minus_series = pd.Series(di_minus, index=close.index)
        
        return adx_series, di_plus_series, di_minus_series
    except Exception:
        # 如果talib不可用，返回空序列
        empty_series = pd.Series([np.nan] * len(close), index=close.index)
        return empty_series, empty_series, empty_series