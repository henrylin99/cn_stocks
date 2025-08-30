"""
批量分析引擎
支持多策略并行分析和结果持久化
"""

import sys
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analyzer import StockAnalyzer
from database import AnalysisDatabase
from strategy import StrategyFactory, AnalysisResult

class BatchAnalysisEngine:
    """批量分析引擎"""
    
    def __init__(self, max_workers: int = 4):
        """
        初始化批量分析引擎
        Args:
            max_workers: 最大并发线程数
        """
        self.max_workers = max_workers
        self.analysis_stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'start_time': None,
            'end_time': None
        }
    
    def analyze_single_stock_multi_strategy(self, ts_code: str, strategy_names: List[str],
                                          days: int = 30) -> Dict:
        """
        单股票多策略分析
        """
        result = {
            'ts_code': ts_code,
            'strategies': {},
            'success': False,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        try:
            with StockAnalyzer() as analyzer:
                # 获取股票数据（只获取一次，避免重复查询）
                df = analyzer.get_stock_data(ts_code, days)
                
                if df.empty:
                    for strategy_name in strategy_names:
                        result['strategies'][strategy_name] = {
                            'success': False,
                            'error': '未获取到股票数据',
                            'analysis_result': None
                        }
                    return result
                
                # 为每个策略进行分析
                has_success = False
                for strategy_name in strategy_names:
                    try:
                        strategy = StrategyFactory.create_strategy(strategy_name)
                        analysis_result = strategy.analyze(df)
                        
                        result['strategies'][strategy_name] = {
                            'success': True,
                            'error': None,
                            'analysis_result': {
                                'signal': analysis_result.signal.value,
                                'confidence': analysis_result.confidence,
                                'reasons': analysis_result.reasons,
                                'indicators': analysis_result.indicators,
                                'timestamp': analysis_result.timestamp
                            },
                            'data_points': len(df),
                            'data_start_time': df['timestamp'].min() if not df.empty else None,
                            'data_end_time': df['timestamp'].max() if not df.empty else None
                        }
                        has_success = True
                        
                    except Exception as e:
                        result['strategies'][strategy_name] = {
                            'success': False,
                            'error': f'策略分析失败: {str(e)}',
                            'analysis_result': None
                        }
                
                result['success'] = has_success
                
        except Exception as e:
            for strategy_name in strategy_names:
                result['strategies'][strategy_name] = {
                    'success': False,
                    'error': f'数据获取失败: {str(e)}',
                    'analysis_result': None
                }
        
        return result
    
    def save_analysis_results_to_db(self, stock_results: List[Dict], 
                                   batch_id: Optional[int] = None) -> Tuple[int, int]:
        """
        保存分析结果到数据库
        Returns:
            (成功数量, 失败数量)
        """
        success_count = 0
        failed_count = 0
        
        try:
            with AnalysisDatabase() as db:
                for stock_result in stock_results:
                    ts_code = stock_result['ts_code']
                    
                    for strategy_name, strategy_result in stock_result['strategies'].items():
                        if strategy_result['success'] and strategy_result['analysis_result']:
                            try:
                                # 重构AnalysisResult对象
                                from strategy import Signal
                                analysis_result = AnalysisResult(
                                    signal=Signal(strategy_result['analysis_result']['signal']),
                                    confidence=strategy_result['analysis_result']['confidence'],
                                    reasons=strategy_result['analysis_result']['reasons'],
                                    indicators=strategy_result['analysis_result']['indicators'],
                                    timestamp=strategy_result['analysis_result']['timestamp']
                                )
                                
                                # 保存到数据库
                                db.save_analysis_result(
                                    ts_code=ts_code,
                                    strategy_name=strategy_name,
                                    analysis_result=analysis_result,
                                    batch_id=batch_id,
                                    data_start_time=strategy_result.get('data_start_time'),
                                    data_end_time=strategy_result.get('data_end_time'),
                                    data_points=strategy_result.get('data_points', 0)
                                )
                                success_count += 1
                            except Exception as e:
                                print(f"保存结果失败 [{ts_code}][{strategy_name}]: {e}")
                                failed_count += 1
                        else:
                            failed_count += 1
            
        except Exception as e:
            print(f"数据库操作失败: {e}")
        
        return success_count, failed_count
    
    def run_batch_analysis(self, stock_list: Optional[List[str]] = None,
                          strategy_names: Optional[List[str]] = None,
                          limit: int = 1000, days: int = 30,
                          batch_name: Optional[str] = None,
                          save_to_db: bool = True,
                          progress_callback: Optional[callable] = None) -> Dict:
        """
        运行批量分析
        """
        # 初始化参数
        if strategy_names is None:
            strategy_names = ['ADXTrendStrategy']
        
        # 获取股票列表
        if stock_list is None:
            with StockAnalyzer() as analyzer:
                stock_list = analyzer.get_top_volume_stocks(limit)
        
        if not stock_list:
            return {
                'success': False,
                'error': '未获取到股票列表',
                'summary': {},
                'results': []
            }
        
        # 初始化统计信息
        self.analysis_stats['start_time'] = datetime.now()
        self.analysis_stats['total_processed'] = 0
        self.analysis_stats['successful'] = 0
        self.analysis_stats['failed'] = 0
        
        total_stocks = len(stock_list)
        print(f"开始批量分析: {total_stocks} 只股票, 策略: {strategy_names}")
        
        # 创建数据库批次记录
        batch_id = None
        if save_to_db:
            try:
                with AnalysisDatabase() as db:
                    db.create_tables()  # 确保表存在
                    batch_id = db.create_batch(strategy_names, total_stocks, batch_name)
                print(f"创建批次记录: {batch_id}")
            except Exception as e:
                print(f"创建批次记录失败: {e}")
        
        # 并行分析
        results = []
        successful_stocks = 0
        failed_stocks = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_stock = {
                executor.submit(
                    self.analyze_single_stock_multi_strategy, 
                    ts_code, strategy_names, days
                ): ts_code for ts_code in stock_list
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_stock):
                ts_code = future_to_stock[future]
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result['success']:
                        successful_stocks += 1
                        self.analysis_stats['successful'] += 1
                    else:
                        failed_stocks += 1
                        self.analysis_stats['failed'] += 1
                    
                    self.analysis_stats['total_processed'] += 1
                    
                    # 进度回调
                    if progress_callback:
                        progress_callback(self.analysis_stats['total_processed'], total_stocks, ts_code)
                    
                    # 每处理10个股票打印进度
                    if self.analysis_stats['total_processed'] % 10 == 0:
                        progress = (self.analysis_stats['total_processed'] / total_stocks) * 100
                        print(f"进度: {self.analysis_stats['total_processed']}/{total_stocks} "
                              f"({progress:.1f}%) - 成功: {successful_stocks}, 失败: {failed_stocks}")
                
                except Exception as e:
                    print(f"处理股票 {ts_code} 时发生异常: {e}")
                    failed_stocks += 1
                    self.analysis_stats['failed'] += 1
                    self.analysis_stats['total_processed'] += 1
        
        self.analysis_stats['end_time'] = datetime.now()
        duration = (self.analysis_stats['end_time'] - self.analysis_stats['start_time']).total_seconds()
        
        print(f"\n批量分析完成!")
        print(f"总计: {total_stocks} 只股票")
        print(f"成功: {successful_stocks} 只")
        print(f"失败: {failed_stocks} 只")
        print(f"耗时: {duration:.1f} 秒")
        
        # 保存结果到数据库
        db_success_count = 0
        db_failed_count = 0
        if save_to_db and results:
            print("正在保存结果到数据库...")
            db_success_count, db_failed_count = self.save_analysis_results_to_db(results, batch_id)
            print(f"数据库保存完成: 成功 {db_success_count}, 失败 {db_failed_count}")
            
            # 更新批次状态
            if batch_id:
                try:
                    with AnalysisDatabase() as db:
                        db.update_batch_status(
                            batch_id, 'completed', 
                            db_success_count, db_failed_count
                        )
                except Exception as e:
                    print(f"更新批次状态失败: {e}")
        
        # 生成汇总统计
        summary = self.generate_summary(results, strategy_names)
        summary.update({
            'analysis_duration': duration,
            'start_time': self.analysis_stats['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': self.analysis_stats['end_time'].strftime('%Y-%m-%d %H:%M:%S'),
            'batch_id': batch_id,
            'db_save_success': db_success_count,
            'db_save_failed': db_failed_count
        })
        
        return {
            'success': True,
            'summary': summary,
            'results': results
        }
    
    def generate_summary(self, results: List[Dict], strategy_names: List[str]) -> Dict:
        """生成分析结果汇总"""
        summary = {
            'total_stocks': len(results),
            'successful_stocks': 0,
            'failed_stocks': 0,
            'strategy_summary': {}
        }
        
        # 初始化策略汇总
        for strategy_name in strategy_names:
            summary['strategy_summary'][strategy_name] = {
                'total': 0,
                'success': 0,
                'failed': 0,
                'signals': {'买入': 0, '卖出': 0, '观望': 0},
                'avg_confidence': {'买入': 0.0, '卖出': 0.0, '观望': 0.0},
                'confidence_scores': {'买入': [], '卖出': [], '观望': []}
            }
        
        # 统计结果
        for stock_result in results:
            has_success = False
            
            for strategy_name, strategy_result in stock_result['strategies'].items():
                if strategy_name not in summary['strategy_summary']:
                    continue
                
                summary['strategy_summary'][strategy_name]['total'] += 1
                
                if strategy_result['success'] and strategy_result['analysis_result']:
                    has_success = True
                    summary['strategy_summary'][strategy_name]['success'] += 1
                    
                    signal = strategy_result['analysis_result']['signal']
                    confidence = strategy_result['analysis_result']['confidence']
                    
                    summary['strategy_summary'][strategy_name]['signals'][signal] += 1
                    summary['strategy_summary'][strategy_name]['confidence_scores'][signal].append(confidence)
                else:
                    summary['strategy_summary'][strategy_name]['failed'] += 1
            
            if has_success:
                summary['successful_stocks'] += 1
            else:
                summary['failed_stocks'] += 1
        
        # 计算平均置信度
        for strategy_name, strategy_data in summary['strategy_summary'].items():
            for signal in ['买入', '卖出', '观望']:
                scores = strategy_data.get('confidence_scores', {}).get(signal, [])
                if scores:
                    strategy_data['avg_confidence'][signal] = sum(scores) / len(scores)
            # 清理临时数据
            if 'confidence_scores' in strategy_data:
                del strategy_data['confidence_scores']
        
        return summary
    
    def get_top_signals(self, results: List[Dict], signal_type: str, 
                       strategy_name: str = None, limit: int = 20) -> List[Dict]:
        """获取置信度最高的信号"""
        signal_results = []
        
        for stock_result in results:
            ts_code = stock_result['ts_code']
            
            for strategy, strategy_result in stock_result['strategies'].items():
                if strategy_name and strategy != strategy_name:
                    continue
                
                if (strategy_result['success'] and 
                    strategy_result['analysis_result'] and
                    strategy_result['analysis_result']['signal'] == signal_type):
                    
                    signal_results.append({
                        'ts_code': ts_code,
                        'strategy_name': strategy,
                        'signal': signal_type,
                        'confidence': strategy_result['analysis_result']['confidence'],
                        'reasons': strategy_result['analysis_result']['reasons'][:3],  # 只显示前3个原因
                        'timestamp': strategy_result['analysis_result']['timestamp']
                    })
        
        # 按置信度排序
        signal_results.sort(key=lambda x: x['confidence'], reverse=True)
        return signal_results[:limit]
    
    def export_results_to_excel(self, results: List[Dict], file_path: str) -> bool:
        """导出结果到Excel"""
        try:
            export_data = []
            
            for stock_result in results:
                ts_code = stock_result['ts_code']
                
                for strategy_name, strategy_result in stock_result['strategies'].items():
                    row = {
                        '股票代码': ts_code,
                        '策略名称': strategy_name,
                        '分析时间': stock_result['timestamp']
                    }
                    
                    if strategy_result['success'] and strategy_result['analysis_result']:
                        analysis = strategy_result['analysis_result']
                        row.update({
                            '信号': analysis['signal'],
                            '置信度': analysis['confidence'],
                            '主要原因': ' | '.join(analysis['reasons'][:3]),
                            '数据点数': strategy_result.get('data_points', 0)
                        })
                    else:
                        row.update({
                            '信号': '失败',
                            '置信度': 0.0,
                            '主要原因': strategy_result.get('error', '未知错误'),
                            '数据点数': 0
                        })
                    
                    export_data.append(row)
            
            df = pd.DataFrame(export_data)
            df.to_excel(file_path, index=False)
            print(f"结果已导出到: {file_path}")
            return True
            
        except Exception as e:
            print(f"导出Excel失败: {e}")
            return False
    
    def get_consensus_recommendations(self, results: List[Dict], limit: int = 20) -> List[Dict]:
        """获取多策略综合推荐"""
        consensus_results = []
        
        for stock_result in results:
            ts_code = stock_result['ts_code']
            strategies = stock_result['strategies']
            
            # 统计各策略信号
            signal_counts = {'买入': 0, '卖出': 0, '观望': 0}
            confidence_sum = {'买入': 0.0, '卖出': 0.0, '观望': 0.0}
            successful_strategies = 0
            
            for strategy_result in strategies.values():
                if strategy_result['success'] and strategy_result['analysis_result']:
                    signal = strategy_result['analysis_result']['signal']
                    confidence = strategy_result['analysis_result']['confidence']
                    
                    signal_counts[signal] += 1
                    confidence_sum[signal] += confidence
                    successful_strategies += 1
            
            if successful_strategies == 0:
                continue
            
            # 确定主要信号
            main_signal = max(signal_counts, key=signal_counts.get)
            main_count = signal_counts[main_signal]
            consensus_score = main_count / successful_strategies if successful_strategies > 0 else 0
            
            # 计算平均置信度
            avg_confidence = {}
            for signal, count in signal_counts.items():
                if count > 0:
                    avg_confidence[signal] = confidence_sum[signal] / count
                else:
                    avg_confidence[signal] = 0.0
            
            # 生成推荐
            if consensus_score >= 0.7:  # 70%以上一致性
                confidence_desc = f"平均置信度{avg_confidence[main_signal]:.1%}"
                recommendation = f"强烈{main_signal} - {main_count}/{successful_strategies}策略一致({confidence_desc})"
            elif consensus_score >= 0.5:  # 50%-70%一致性
                confidence_desc = f"平均置信度{avg_confidence[main_signal]:.1%}"
                recommendation = f"倾向{main_signal} - {main_count}/{successful_strategies}策略支持({confidence_desc})"
            else:  # 低于50%一致性
                recommendation = f"信号分歧较大 - 建议观望或进一步分析"
            
            consensus_results.append({
                'ts_code': ts_code,
                'main_signal': main_signal,
                'consensus_score': consensus_score,
                'signal_distribution': signal_counts,
                'average_confidence': avg_confidence,
                'recommendation': recommendation,
                'successful_strategies': successful_strategies,
                'timestamp': stock_result['timestamp']
            })
        
        # 按一致性得分和主要信号置信度排序
        def sort_key(x):
            # 优先按一致性排序，然后按主要信号的平均置信度排序
            return (x['consensus_score'], x['average_confidence'][x['main_signal']])
        
        consensus_results.sort(key=sort_key, reverse=True)
        return consensus_results[:limit]

class ProgressReporter:
    """进度报告器"""
    
    def __init__(self, update_interval: int = 5):
        self.update_interval = update_interval
        self.last_update_time = 0
    
    def __call__(self, current: int, total: int, current_stock: str):
        """进度回调函数"""
        now = time.time()
        
        if now - self.last_update_time >= self.update_interval:
            progress = (current / total) * 100
            print(f"进度更新: {current}/{total} ({progress:.1f}%) - 当前: {current_stock}")
            self.last_update_time = now