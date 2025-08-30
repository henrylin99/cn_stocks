#!/usr/bin/env python3
"""
中国股票分析系统 - Web界面
提供批量分析结果的网页展示
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import sys
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import plotly
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import AnalysisDatabase
from analyzer import StockAnalyzer
from engine import BatchAnalysisEngine, ProgressReporter
from strategy import StrategyFactory
from visualization import ChartPlotter

app = Flask(__name__, 
           template_folder='web/templates',
           static_folder='web/static')

class WebAnalysisService:
    """Web分析服务"""
    
    def __init__(self):
        self.batch_engine = None
        self.current_analysis = None
    
    def get_recent_batch_analyses(self, limit: int = 10) -> List[Dict]:
        """获取最近的批量分析结果"""
        try:
            with AnalysisDatabase() as db:
                # 获取最近的批次分析
                query = """
                SELECT ab.id, ab.batch_name, ab.created_at, ab.strategy_names,
                       COUNT(bar.analysis_id) as total_stocks,
                       SUM(CASE WHEN sar.signal = '买入' THEN 1 ELSE 0 END) as buy_signals,
                       SUM(CASE WHEN sar.signal = '卖出' THEN 1 ELSE 0 END) as sell_signals,
                       SUM(CASE WHEN sar.signal = '观望' THEN 1 ELSE 0 END) as hold_signals
                FROM analysis_batches ab
                LEFT JOIN batch_analysis_results bar ON ab.id = bar.batch_id
                LEFT JOIN stock_analysis_results sar ON bar.analysis_id = sar.id
                GROUP BY ab.id, ab.batch_name, ab.created_at, ab.strategy_names
                ORDER BY ab.created_at DESC
                LIMIT %s
                """
                db.cursor.execute(query, (limit,))
                results = db.cursor.fetchall()
                
                batch_list = []
                for row in results:
                    batch_list.append({
                        'batch_id': row[0],
                        'batch_name': row[1] or f"批次-{row[0]}",
                        'created_at': row[2],
                        'strategy_names': json.loads(row[3]) if row[3] else [],
                        'total_stocks': row[4] or 0,
                        'buy_signals': row[5] or 0,
                        'sell_signals': row[6] or 0,
                        'hold_signals': row[7] or 0
                    })
                
                return batch_list
                
        except Exception as e:
            print(f"获取批量分析列表失败: {e}")
            return []
    
    def get_batch_details(self, batch_id: int) -> Dict:
        """获取批次详细结果"""
        try:
            with AnalysisDatabase() as db:
                # 获取批次基本信息
                batch_query = """
                SELECT batch_name, created_at, strategy_names
                FROM analysis_batches 
                WHERE id = %s
                """
                db.cursor.execute(batch_query, (batch_id,))
                batch_info = db.cursor.fetchone()
                
                if not batch_info:
                    return {}
                
                # 获取详细结果 - 不包含指标，因为指标存储在单独的表中需要单独查询
                results_query = """
                SELECT sar.ts_code, sar.strategy_name, sar.signal, sar.confidence,
                       sar.analysis_timestamp
                FROM batch_analysis_results bar
                JOIN stock_analysis_results sar ON bar.analysis_id = sar.id
                WHERE bar.batch_id = %s
                ORDER BY sar.confidence DESC, sar.ts_code
                """
                db.cursor.execute(results_query, (batch_id,))
                results = db.cursor.fetchall()
                
                # 组织数据
                stock_results = {}
                strategy_summary = {}
                
                for row in results:
                    ts_code, strategy_name, signal, confidence, timestamp = row
                    
                    if ts_code not in stock_results:
                        stock_results[ts_code] = {}
                    
                    stock_results[ts_code][strategy_name] = {
                        'signal': signal,
                        'confidence': confidence,
                        'timestamp': timestamp,
                        'indicators': {}  # 暂时设为空，后续可扩展查询指标
                    }
                    
                    # 策略汇总统计
                    if strategy_name not in strategy_summary:
                        strategy_summary[strategy_name] = {
                            'total': 0,
                            'signals': {'买入': 0, '卖出': 0, '观望': 0},
                            'avg_confidence': {'买入': 0, '卖出': 0, '观望': 0},
                            'confidence_sum': {'买入': 0, '卖出': 0, '观望': 0}
                        }
                    
                    strategy_summary[strategy_name]['total'] += 1
                    strategy_summary[strategy_name]['signals'][signal] += 1
                    strategy_summary[strategy_name]['confidence_sum'][signal] += confidence
                
                # 计算平均置信度
                for strategy_data in strategy_summary.values():
                    for signal in ['买入', '卖出', '观望']:
                        if strategy_data['signals'][signal] > 0:
                            strategy_data['avg_confidence'][signal] = \
                                strategy_data['confidence_sum'][signal] / strategy_data['signals'][signal]
                
                return {
                    'batch_id': batch_id,
                    'batch_name': batch_info[0] or f"批次-{batch_id}",
                    'created_at': batch_info[1],
                    'strategy_names': json.loads(batch_info[2]) if batch_info[2] else [],
                    'stock_results': stock_results,
                    'strategy_summary': strategy_summary,
                    'total_stocks': len(stock_results)
                }
                
        except Exception as e:
            print(f"获取批次详情失败: {e}")
            return {}
    
    def run_new_batch_analysis(self, limit: int = 50, strategies: Optional[List[str]] = None) -> Dict:
        """运行新的批量分析"""
        try:
            if strategies is None:
                strategies = StrategyFactory.get_available_strategies()
            
            # 初始化引擎
            engine = BatchAnalysisEngine(max_workers=4)
            
            # 运行分析
            result = engine.run_batch_analysis(
                strategy_names=strategies,
                limit=limit,
                days=30,
                batch_name=f"Web批量分析-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                save_to_db=True,
                progress_callback=None
            )
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

# 全局服务实例
web_service = WebAnalysisService()

# Jinja2 辅助函数
@app.template_global()
def get_consensus_for_stock(strategies):
    """计算单只股票的综合推荐"""
    if not strategies:
        return {'signal': '观望', 'confidence': 0}
    
    signals = [result['signal'] for result in strategies.values()]
    confidences = [result['confidence'] for result in strategies.values()]
    
    # 统计各信号数量
    signal_counts = {
        '买入': signals.count('买入'),
        '卖出': signals.count('卖出'),
        '观望': signals.count('观望')
    }
    
    # 确定综合推荐
    consensus = max(signal_counts.items(), key=lambda x: x[1])[0]
    
    # 计算平均置信度
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    return {
        'signal': consensus,
        'confidence': avg_confidence
    }

@app.template_global()
def get_strategy_agreement(strategies):
    """计算策略一致性百分比"""
    if not strategies:
        return 0
    
    signals = [result['signal'] for result in strategies.values()]
    if not signals:
        return 0
    
    # 找到最多的信号类型
    signal_counts = {}
    for signal in signals:
        signal_counts[signal] = signal_counts.get(signal, 0) + 1
    
    max_count = max(signal_counts.values())
    agreement = (max_count / len(signals)) * 100
    
    return agreement

@app.route('/')
def index():
    """主页"""
    recent_batches = web_service.get_recent_batch_analyses(10)
    available_strategies = StrategyFactory.get_available_strategies()
    
    return render_template('index.html', 
                         recent_batches=recent_batches,
                         available_strategies=available_strategies)

@app.route('/batch/<int:batch_id>')
def batch_details(batch_id):
    """批次详情页"""
    batch_data = web_service.get_batch_details(batch_id)
    
    if not batch_data:
        return "批次不存在", 404
    
    return render_template('batch_details.html', batch=batch_data)

@app.route('/api/run_analysis', methods=['POST'])
def api_run_analysis():
    """API: 运行批量分析"""
    try:
        data = request.get_json()
        limit = data.get('limit', 50)
        strategies = data.get('strategies', None)
        
        result = web_service.run_new_batch_analysis(limit, strategies)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/batch/<int:batch_id>')
def api_batch_details(batch_id):
    """API: 获取批次详情"""
    batch_data = web_service.get_batch_details(batch_id)
    return jsonify(batch_data)

@app.route('/api/recent_batches')
def api_recent_batches():
    """API: 获取最近批次"""
    limit = request.args.get('limit', 10, type=int)
    recent_batches = web_service.get_recent_batch_analyses(limit)
    return jsonify(recent_batches)

@app.route('/api/stock_chart/<string:ts_code>')
def api_stock_chart(ts_code):
    """API: 获取股票图表"""
    try:
        days = request.args.get('days', 30, type=int)
        batch_id = request.args.get('batch_id', type=int)
        
        # 如果提供了批次ID，获取该批次使用的策略
        strategies = None
        if batch_id:
            batch_data = web_service.get_batch_details(batch_id)
            if batch_data:
                strategies = batch_data['strategy_names']
        
        # 如果没有策略信息，使用所有可用策略
        if not strategies:
            strategies = StrategyFactory.get_available_strategies()
        
        # 生成图表
        plotter = ChartPlotter()
        fig = plotter.create_stock_analysis_chart(
            ts_code=ts_code,
            strategy_names=strategies,
            days=days
        )
        
        # 转换为JSON
        chart_json = json.dumps(fig, cls=PlotlyJSONEncoder)
        return jsonify({'success': True, 'chart': chart_json})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/chart/<string:ts_code>')
def stock_chart_page(ts_code):
    """股票图表页面"""
    days = request.args.get('days', 30, type=int)
    batch_id = request.args.get('batch_id', type=int)
    
    # 获取策略信息
    strategies = StrategyFactory.get_available_strategies()
    if batch_id:
        batch_data = web_service.get_batch_details(batch_id)
        if batch_data:
            strategies = batch_data['strategy_names']
    
    return render_template('stock_chart.html', 
                         ts_code=ts_code,
                         days=days,
                         batch_id=batch_id,
                         strategies=strategies)

if __name__ == '__main__':
    print("启动股票分析Web服务...")
    print("访问地址: http://localhost:5002")
    app.run(debug=True, host='0.0.0.0', port=5002)