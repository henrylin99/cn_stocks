"""
策略模块
统一的股票分析策略接口
"""

from .base_strategy import BaseStrategy, StrategyFactory, Signal, AnalysisResult
from .adx_trend_strategy import ADXTrendStrategy
from .macd_strategy import MACDStrategy
from .rsi_strategy import RSIStrategy
from .bollinger_strategy import BollingerStrategy
from .ma_crossover_strategy import MACrossoverStrategy
from .kdj_strategy import KDJStrategy

__all__ = [
    'BaseStrategy',
    'StrategyFactory', 
    'Signal',
    'AnalysisResult',
    'ADXTrendStrategy',
    'MACDStrategy',
    'RSIStrategy',
    'BollingerStrategy',
    'MACrossoverStrategy',
    'KDJStrategy'
]