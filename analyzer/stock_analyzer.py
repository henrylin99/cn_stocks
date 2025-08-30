"""
股票分析器
单股票和批量分析的核心模块
"""

import pandas as pd
import sys
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.db_utils import DatabaseUtils
from strategy import StrategyFactory, Signal, AnalysisResult
from database import AnalysisDatabase

class StockAnalyzer:
    """股票分析器类"""
    
    def __init__(self):
        self.conn, self.cursor = DatabaseUtils.connect_to_mysql()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
    
    def convert_stock_code_format(self, ts_code: str) -> str:
        """
        转换股票代码格式
        tushare格式 -> baostock格式: 000001.SZ -> sz.000001, 600000.SH -> sh.600000
        baostock格式保持不变: sz.000001, sh.600000
        """
        if not ts_code or '.' not in ts_code:
            return ts_code
            
        parts = ts_code.split('.')
        if len(parts) != 2:
            return ts_code
            
        part1, part2 = parts
        
        # 如果已经是baostock格式，直接返回
        if part1.lower() in ['sz', 'sh'] and len(part2) == 6 and part2.isdigit():
            return ts_code.lower()
        
        # tushare格式转换为baostock格式
        if part2.upper() in ['SZ', 'SH'] and len(part1) == 6 and part1.isdigit():
            if part2.upper() == 'SZ':
                return f"sz.{part1}"
            elif part2.upper() == 'SH':
                return f"sh.{part1}"
        
        return ts_code
    
    def get_stock_data(self, ts_code: str, days: int = 30) -> pd.DataFrame:
        """
        从数据库获取股票15分钟历史数据
        Args:
            ts_code: 股票代码 (如: 000001.SZ)
            days: 获取最近多少天的数据，默认30天
        Returns:
            包含OHLCV数据的DataFrame
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # 首先尝试使用原始格式查询
            query = """
            SELECT timestamp, ts_code, open, high, low, close, volume, amount
            FROM stock_15min_history 
            WHERE ts_code = %s 
            AND timestamp >= %s 
            AND timestamp <= %s
            ORDER BY timestamp ASC
            """
            
            self.cursor.execute(query, (ts_code, start_date, end_date))
            results = self.cursor.fetchall()
            
            # 如果原始格式没有数据，尝试转换后的格式
            if not results:
                db_ts_code = self.convert_stock_code_format(ts_code)
                if db_ts_code != ts_code:
                    self.cursor.execute(query, (db_ts_code, start_date, end_date))
                    results = self.cursor.fetchall()
            
            if not results:
                return pd.DataFrame()
            
            # 创建DataFrame
            columns = ['timestamp', 'ts_code', 'open', 'high', 'low', 'close', 'volume', 'amount']
            df = pd.DataFrame(results, columns=columns)
            
            # 数据类型转换
            numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 时间戳处理
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # 删除无效数据
            df = df.dropna(subset=['close']).reset_index(drop=True)
            
            return df
            
        except Exception as e:
            print(f"获取股票数据失败 [{ts_code}]: {e}")
            return pd.DataFrame()
    
    def validate_stock_code(self, ts_code: str) -> bool:
        """
        验证股票代码是否有效
        支持两种格式: 
        - tushare格式: 000001.SZ, 600000.SH
        - baostock格式: sz.000001, sh.600000
        """
        if not ts_code or len(ts_code.strip()) == 0:
            return False
        
        # 基本格式验证
        if '.' not in ts_code:
            return False
        
        parts = ts_code.split('.')
        if len(parts) != 2:
            return False
        
        part1, part2 = parts
        
        # tushare格式: 000001.SZ
        if part2.upper() in ['SZ', 'SH']:
            if len(part1) == 6 and part1.isdigit():
                return True
        
        # baostock格式: sh.600000  
        if part1.lower() in ['sz', 'sh']:
            if len(part2) == 6 and part2.isdigit():
                return True
        
        return False
    
    def analyze_single_stock(self, ts_code: str, strategy_name: str = 'ADXTrendStrategy', 
                           days: int = 30) -> Dict:
        """
        单股票分析
        Args:
            ts_code: 股票代码
            strategy_name: 策略名称，默认ADX策略
            days: 分析天数，默认30天
        Returns:
            分析结果字典
        """
        result = {
            'ts_code': ts_code,
            'strategy_name': strategy_name,
            'success': False,
            'error': None,
            'analysis_result': None,
            'data_points': 0,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        try:
            # 验证股票代码
            if not self.validate_stock_code(ts_code):
                result['error'] = "无效的股票代码格式"
                return result
            
            # 获取股票数据
            df = self.get_stock_data(ts_code, days)
            
            if df.empty:
                result['error'] = f"未获取到股票 {ts_code} 的数据。请检查股票代码是否正确或该股票是否有历史数据"
                return result
            
            result['data_points'] = len(df)
            
            # 创建策略实例
            try:
                strategy = StrategyFactory.create_strategy(strategy_name)
            except ValueError as e:
                result['error'] = str(e)
                return result
            
            # 执行分析
            analysis_result = strategy.analyze(df)
            result['analysis_result'] = {
                'signal': analysis_result.signal.value,
                'confidence': analysis_result.confidence,
                'reasons': analysis_result.reasons,
                'indicators': analysis_result.indicators,
                'timestamp': analysis_result.timestamp
            }
            result['success'] = True
            
        except Exception as e:
            result['error'] = f"分析过程异常: {str(e)}"
        
        return result
    
    def analyze_multi_strategy(self, ts_code: str, strategy_names: Optional[List[str]] = None, 
                             days: int = 30) -> Dict:
        """
        多策略分析单只股票
        Args:
            ts_code: 股票代码
            strategy_names: 策略名称列表，如果为None则使用所有可用策略
            days: 分析天数，默认30天
        Returns:
            包含所有策略分析结果的字典
        """
        result = {
            'ts_code': ts_code,
            'success': False,
            'error': None,
            'data_points': 0,
            'strategies': {},
            'summary': {},
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        try:
            # 验证股票代码
            if not self.validate_stock_code(ts_code):
                result['error'] = "无效的股票代码格式"
                return result
            
            # 获取股票数据
            df = self.get_stock_data(ts_code, days)
            
            if df.empty:
                result['error'] = f"未获取到股票 {ts_code} 的数据。请检查股票代码是否正确或该股票是否有历史数据"
                return result
            
            result['data_points'] = len(df)
            
            # 如果没有指定策略，使用所有可用策略
            if strategy_names is None:
                strategy_names = StrategyFactory.get_available_strategies()
            
            # 对每个策略进行分析
            successful_strategies = 0
            signal_counts = {'买入': 0, '卖出': 0, '观望': 0}
            confidence_sum = {'买入': 0.0, '卖出': 0.0, '观望': 0.0}
            all_reasons = []
            
            for strategy_name in strategy_names:
                try:
                    strategy = StrategyFactory.create_strategy(strategy_name)
                    analysis_result = strategy.analyze(df)
                    
                    strategy_result = {
                        'success': True,
                        'signal': analysis_result.signal.value,
                        'confidence': analysis_result.confidence,
                        'reasons': analysis_result.reasons,
                        'indicators': analysis_result.indicators,
                        'timestamp': analysis_result.timestamp,
                        'strategy_description': strategy.get_strategy_description()
                    }
                    
                    result['strategies'][strategy_name] = strategy_result
                    successful_strategies += 1
                    
                    # 统计信号
                    signal = analysis_result.signal.value
                    signal_counts[signal] += 1
                    confidence_sum[signal] += analysis_result.confidence
                    all_reasons.extend(analysis_result.reasons)
                    
                except Exception as e:
                    result['strategies'][strategy_name] = {
                        'success': False,
                        'error': f"策略分析失败: {str(e)}"
                    }
            
            # 生成综合分析结果
            if successful_strategies > 0:
                # 计算平均置信度
                avg_confidence = {}
                for signal, count in signal_counts.items():
                    if count > 0:
                        avg_confidence[signal] = confidence_sum[signal] / count
                    else:
                        avg_confidence[signal] = 0.0
                
                # 确定主要信号（票数最多的信号）
                main_signal = max(signal_counts, key=signal_counts.get)
                
                # 计算一致性得分
                total_signals = sum(signal_counts.values())
                consensus_score = signal_counts[main_signal] / total_signals if total_signals > 0 else 0
                
                result['summary'] = {
                    'total_strategies': len(strategy_names),
                    'successful_strategies': successful_strategies,
                    'failed_strategies': len(strategy_names) - successful_strategies,
                    'signal_distribution': signal_counts,
                    'average_confidence': avg_confidence,
                    'main_signal': main_signal,
                    'consensus_score': consensus_score,
                    'recommendation': self._generate_recommendation(signal_counts, avg_confidence, consensus_score)
                }
                
                result['success'] = True
            else:
                result['error'] = "所有策略分析均失败"
                
        except Exception as e:
            result['error'] = f"多策略分析异常: {str(e)}"
        
        return result
    
    def _generate_recommendation(self, signal_counts: Dict, avg_confidence: Dict, consensus_score: float) -> str:
        """生成综合推荐"""
        main_signal = max(signal_counts, key=signal_counts.get)
        main_count = signal_counts[main_signal]
        total_count = sum(signal_counts.values())
        
        if consensus_score >= 0.7:  # 70%以上一致性
            confidence_desc = f"平均置信度{avg_confidence[main_signal]:.1%}"
            return f"强烈{main_signal} - {main_count}/{total_count}策略一致({confidence_desc})"
        elif consensus_score >= 0.5:  # 50%-70%一致性
            confidence_desc = f"平均置信度{avg_confidence[main_signal]:.1%}"
            return f"倾向{main_signal} - {main_count}/{total_count}策略支持({confidence_desc})"
        else:  # 低于50%一致性
            return f"信号分歧较大 - 建议观望或进一步分析"
    
    def get_top_volume_stocks(self, limit: int = 1000) -> List[str]:
        """
        获取成交量最高的股票列表
        """
        try:
            query = """
            SELECT ts_code FROM highest_trading_volume 
            ORDER BY avg_amount DESC 
            LIMIT %s
            """
            self.cursor.execute(query, (limit,))
            results = self.cursor.fetchall()
            return [row[0] for row in results]
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            return []
    
    def analyze_batch_stocks(self, stock_list: Optional[List[str]] = None,
                           strategy_names: Optional[List[str]] = None,
                           limit: int = 1000, days: int = 30) -> List[Dict]:
        """
        批量股票分析
        Args:
            stock_list: 股票代码列表，如果为None则从highest_trading_volume表获取
            strategy_names: 策略名称列表，默认使用ADX策略
            limit: 分析股票数量限制
            days: 分析天数
        Returns:
            分析结果列表
        """
        if stock_list is None:
            stock_list = self.get_top_volume_stocks(limit)
        
        if strategy_names is None:
            strategy_names = ['ADXTrendStrategy']
        
        results = []
        total_stocks = len(stock_list)
        
        print(f"开始批量分析 {total_stocks} 只股票")
        print(f"使用策略: {', '.join(strategy_names)}")
        
        for i, ts_code in enumerate(stock_list):
            print(f"进度: {i+1}/{total_stocks} - 分析股票: {ts_code}")
            
            stock_result = {
                'ts_code': ts_code,
                'strategies': {},
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 对每个策略进行分析
            for strategy_name in strategy_names:
                analysis = self.analyze_single_stock(ts_code, strategy_name, days)
                stock_result['strategies'][strategy_name] = analysis
            
            results.append(stock_result)
            
            # 每分析10只股票打印一次进度
            if (i + 1) % 10 == 0:
                print(f"已完成 {i+1}/{total_stocks} 只股票的分析")
        
        print("批量分析完成！")
        return results
    
    def get_signal_summary(self, analysis_results: List[Dict]) -> Dict:
        """
        获取分析结果汇总
        """
        summary = {
            'total_stocks': len(analysis_results),
            'successful_analysis': 0,
            'failed_analysis': 0,
            'signal_distribution': {'买入': 0, '卖出': 0, '观望': 0},
            'strategy_summary': {}
        }
        
        for stock_result in analysis_results:
            has_success = False
            for strategy_name, analysis in stock_result['strategies'].items():
                if strategy_name not in summary['strategy_summary']:
                    summary['strategy_summary'][strategy_name] = {
                        'total': 0, 'success': 0, 'failed': 0,
                        'signals': {'买入': 0, '卖出': 0, '观望': 0}
                    }
                
                summary['strategy_summary'][strategy_name]['total'] += 1
                
                if analysis['success']:
                    has_success = True
                    summary['strategy_summary'][strategy_name]['success'] += 1
                    signal = analysis['analysis_result']['signal']
                    summary['strategy_summary'][strategy_name]['signals'][signal] += 1
                    summary['signal_distribution'][signal] += 1
                else:
                    summary['strategy_summary'][strategy_name]['failed'] += 1
            
            if has_success:
                summary['successful_analysis'] += 1
            else:
                summary['failed_analysis'] += 1
        
        return summary
    
    def format_analysis_result(self, result: Dict) -> str:
        """
        格式化分析结果为可读字符串
        """
        if not result['success']:
            return f"❌ {result['ts_code']}: 分析失败 - {result.get('error', '未知错误')}"
        
        analysis = result['analysis_result']
        signal_emoji = {'买入': '🔵', '卖出': '🔴', '观望': '⚪'}
        signal = analysis['signal']
        confidence = analysis['confidence']
        
        main_reasons = analysis['reasons'][:3] if len(analysis['reasons']) > 3 else analysis['reasons']
        reasons_str = ' | '.join(main_reasons)
        
        return (f"{signal_emoji.get(signal, '⚪')} {result['ts_code']}: "
                f"{signal} (置信度: {confidence:.1%}) - {reasons_str}")

class BatchAnalysisManager:
    """批量分析管理器"""
    
    def __init__(self):
        pass
    
    def run_daily_analysis(self, strategies: List[str] = None, 
                          limit: int = 1000, days: int = 30) -> Dict:
        """
        运行每日分析任务
        """
        if strategies is None:
            strategies = ['ADXTrendStrategy']
        
        start_time = datetime.now()
        
        with StockAnalyzer() as analyzer:
            # 执行批量分析
            results = analyzer.analyze_batch_stocks(
                strategy_names=strategies,
                limit=limit,
                days=days
            )
            
            # 获取汇总信息
            summary = analyzer.get_signal_summary(results)
            
            # 保存结果到数据库（稍后实现）
            # self.save_analysis_results(results)
            
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        summary['analysis_duration'] = f"{duration:.1f}秒"
        summary['start_time'] = start_time.strftime('%Y-%m-%d %H:%M:%S')
        summary['end_time'] = end_time.strftime('%Y-%m-%d %H:%M:%S')
        
        return {
            'summary': summary,
            'detailed_results': results
        }