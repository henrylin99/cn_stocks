#!/usr/bin/env python3
"""
中国股票分析系统主程序
提供命令行接口进行股票分析
"""

import argparse
import sys
import os
from datetime import datetime
import json

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analyzer import StockAnalyzer
from engine import BatchAnalysisEngine, ProgressReporter
from database import AnalysisDatabase
from visualization import ChartPlotter
from strategy import StrategyFactory

def setup_database():
    """初始化数据库表"""
    print("正在初始化数据库表...")
    try:
        with AnalysisDatabase() as db:
            if db.create_tables():
                print("✓ 数据库表初始化成功")
            else:
                print("✗ 数据库表初始化失败")
                return False
        return True
    except Exception as e:
        print(f"✗ 数据库初始化错误: {e}")
        return False

def analyze_single_stock(args):
    """单股票分析"""
    print(f"正在分析股票: {args.stock_code}")
    
    if hasattr(args, 'strategy') and args.strategy and args.strategy.lower() != 'all':
        # 单策略模式
        print(f"使用策略: {args.strategy}")
        print(f"分析天数: {args.days}")
        
        try:
            with StockAnalyzer() as analyzer:
                result = analyzer.analyze_single_stock(
                    ts_code=args.stock_code,
                    strategy_name=args.strategy,
                    days=args.days
                )
                
                if result['success']:
                    analysis = result['analysis_result']
                    print(f"\n--- 分析结果 ---")
                    print(f"股票代码: {args.stock_code}")
                    print(f"策略名称: {args.strategy}")
                    print(f"交易信号: {analysis['signal']}")
                    print(f"置信度: {analysis['confidence']:.1%}")
                    print(f"数据点数: {result['data_points']}")
                    
                    print(f"\n--- 分析原因 ---")
                    for i, reason in enumerate(analysis['reasons'][:5], 1):
                        print(f"{i}. {reason}")
                    
                    print(f"\n--- 关键指标 ---")
                    for key, value in list(analysis['indicators'].items())[:8]:
                        if isinstance(value, float):
                            print(f"{key}: {value:.2f}")
                        else:
                            print(f"{key}: {value}")
                    
                    # 保存到数据库
                    if args.save_db:
                        try:
                            with AnalysisDatabase() as db:
                                from strategy import Signal, AnalysisResult
                                analysis_result = AnalysisResult(
                                    signal=Signal(analysis['signal']),
                                    confidence=analysis['confidence'],
                                    reasons=analysis['reasons'],
                                    indicators=analysis['indicators'],
                                    timestamp=analysis['timestamp']
                                )
                                
                                analysis_id = db.save_analysis_result(
                                    ts_code=args.stock_code,
                                    strategy_name=args.strategy,
                                    analysis_result=analysis_result
                                )
                                
                                if analysis_id > 0:
                                    print(f"✓ 结果已保存到数据库 (ID: {analysis_id})")
                                else:
                                    print("✗ 保存到数据库失败")
                        except Exception as e:
                            print(f"✗ 数据库保存错误: {e}")
                    
                    # 生成图表
                    if args.show_chart or args.chart_path:
                        print("\n正在生成图表...")
                        try:
                            plotter = ChartPlotter()
                            fig = plotter.create_stock_analysis_chart(
                                ts_code=args.stock_code,
                                strategy_names=[args.strategy],
                                days=args.days,
                                save_path=args.chart_path
                            )
                            
                            if args.show_chart and not args.chart_path:
                                from visualization import show_chart_in_browser
                                show_chart_in_browser(fig)
                            
                            print("✓ 图表生成完成")
                        except Exception as e:
                            print(f"✗ 图表生成失败: {e}")
                            print("提示: 需要安装 plotly: pip install plotly")
                else:
                    print(f"✗ 分析失败: {result['error']}")
        except Exception as e:
            print(f"✗ 执行错误: {e}")
    else:
        # 多策略模式（默认）
        print("使用所有可用策略进行综合分析")
        print(f"分析天数: {args.days}")
        
        try:
            with StockAnalyzer() as analyzer:
                result = analyzer.analyze_multi_strategy(
                    ts_code=args.stock_code,
                    days=args.days
                )
                
                if result['success']:
                    print(f"\n=== 综合分析结果 ===")
                    print(f"股票代码: {args.stock_code}")
                    print(f"数据点数: {result['data_points']}")
                    print(f"成功策略: {result['summary']['successful_strategies']}/{result['summary']['total_strategies']}")
                    
                    summary = result['summary']
                    print(f"\n--- 策略投票结果 ---")
                    signal_dist = summary['signal_distribution']
                    print(f"买入: {signal_dist['买入']} 票")
                    print(f"卖出: {signal_dist['卖出']} 票")
                    print(f"观望: {signal_dist['观望']} 票")
                    
                    print(f"\n--- 综合推荐 ---")
                    print(f"主要信号: {summary['main_signal']}")
                    print(f"一致性: {summary['consensus_score']:.1%}")
                    print(f"推荐: {summary['recommendation']}")
                    
                    print(f"\n=== 各策略详细结果 ===")
                    for strategy_name, strategy_result in result['strategies'].items():
                        if strategy_result['success']:
                            signal_emoji = {'买入': '📈', '卖出': '📉', '观望': '⏸️'}
                            emoji = signal_emoji.get(strategy_result['signal'], '❓')
                            
                            print(f"\n{emoji} {strategy_name}")
                            print(f"   信号: {strategy_result['signal']}")
                            print(f"   置信度: {strategy_result['confidence']:.1%}")
                            print(f"   原因: {' | '.join(strategy_result['reasons'][:3])}")
                        else:
                            print(f"\n❌ {strategy_name}")
                            print(f"   错误: {strategy_result['error']}")
                    
                    # 生成图表（多策略）
                    if args.show_chart or args.chart_path:
                        print("\n正在生成综合图表...")
                        try:
                            plotter = ChartPlotter()
                            successful_strategies = [name for name, res in result['strategies'].items() if res['success']]
                            fig = plotter.create_stock_analysis_chart(
                                ts_code=args.stock_code,
                                strategy_names=successful_strategies,
                                days=args.days,
                                save_path=args.chart_path
                            )
                            
                            if args.show_chart and not args.chart_path:
                                from visualization import show_chart_in_browser
                                show_chart_in_browser(fig)
                            
                            print("✓ 综合图表生成完成")
                        except Exception as e:
                            print(f"✗ 图表生成失败: {e}")
                            print("提示: 需要安装 plotly: pip install plotly")
                else:
                    print(f"✗ 多策略分析失败: {result['error']}")
        except Exception as e:
            print(f"✗ 执行错误: {e}")

def analyze_batch_stocks(args):
    """批量股票分析"""
    print("开始批量股票分析")
    
    # 如果没有指定策略或者指定了all，则使用所有策略
    if not hasattr(args, 'strategies') or not args.strategies or (hasattr(args, 'strategies') and 'all' in [s.lower() for s in args.strategies]):
        from strategy import StrategyFactory
        strategies = StrategyFactory.get_available_strategies()
        print("使用所有可用策略进行综合分析")
    else:
        strategies = args.strategies
        print(f"使用指定策略: {strategies}")
    
    print(f"策略数量: {len(strategies)}")
    print(f"股票数量: {args.limit}")
    print(f"分析天数: {args.days}")
    print(f"并发数: {args.workers}")
    
    try:
        # 初始化引擎
        engine = BatchAnalysisEngine(max_workers=args.workers)
        
        # 设置进度报告器
        progress_reporter = ProgressReporter(update_interval=5)
        
        # 运行批量分析
        result = engine.run_batch_analysis(
            strategy_names=strategies,
            limit=args.limit,
            days=args.days,
            batch_name=args.batch_name,
            save_to_db=args.save_db,
            progress_callback=progress_reporter
        )
        
        if result['success']:
            summary = result['summary']
            print(f"\n=== 批量分析完成 ===")
            print(f"处理股票: {summary['total_stocks']} 只")
            print(f"成功分析: {summary['successful_stocks']} 只")
            print(f"失败分析: {summary['failed_stocks']} 只")
            print(f"分析耗时: {summary['analysis_duration']:.1f} 秒")
            
            if args.save_db:
                print(f"数据库保存: 成功 {summary['db_save_success']}, 失败 {summary['db_save_failed']}")
                print(f"批次ID: {summary['batch_id']}")
            
            # 显示策略汇总
            print(f"\n--- 策略汇总 ---")
            for strategy_name, strategy_data in summary['strategy_summary'].items():
                print(f"\n{strategy_name}:")
                print(f"  成功: {strategy_data['success']} / {strategy_data['total']}")
                print(f"  信号分布: 买入 {strategy_data['signals']['买入']}, "
                      f"卖出 {strategy_data['signals']['卖出']}, "
                      f"观望 {strategy_data['signals']['观望']}")
                avg_conf = strategy_data['avg_confidence']
                print(f"  平均置信度: 买入 {avg_conf['买入']:.1%}, "
                      f"卖出 {avg_conf['卖出']:.1%}, "
                      f"观望 {avg_conf['观望']:.1%}")
            
            # 显示综合推荐（多策略模式）
            if len(strategies) > 1:
                print(f"\n--- 多策略综合推荐 (前{args.top_limit}只) ---")
                consensus_recommendations = engine.get_consensus_recommendations(
                    result['results'], limit=args.top_limit
                )
                
                for i, rec in enumerate(consensus_recommendations, 1):
                    signal_emoji = {'买入': '📈', '卖出': '📉', '观望': '⏸️'}
                    emoji = signal_emoji.get(rec['main_signal'], '❓')
                    
                    print(f"{i:2d}. {emoji} {rec['ts_code']} - {rec['main_signal']}")
                    print(f"     一致性: {rec['consensus_score']:.1%} "
                          f"({rec['signal_distribution']['买入']}买/{rec['signal_distribution']['卖出']}卖/{rec['signal_distribution']['观望']}观望)")
                    print(f"     推荐: {rec['recommendation']}")
            
            # 显示顶级信号
            if args.show_top_signals:
                print(f"\n--- 置信度最高的买入信号 (前{args.top_limit}只) ---")
                top_buy_signals = engine.get_top_signals(
                    result['results'], '买入', limit=args.top_limit
                )
                
                for i, signal in enumerate(top_buy_signals, 1):
                    reasons = ' | '.join(signal['reasons'][:3])  # 只显示前3个原因
                    print(f"{i:2d}. {signal['ts_code']} - "
                          f"{signal['confidence']:.1%} - {reasons}")
                
                print(f"\n--- 置信度最高的卖出信号 (前{args.top_limit}只) ---")
                top_sell_signals = engine.get_top_signals(
                    result['results'], '卖出', limit=args.top_limit
                )
                
                for i, signal in enumerate(top_sell_signals, 1):
                    reasons = ' | '.join(signal['reasons'][:3])  # 只显示前3个原因
                    print(f"{i:2d}. {signal['ts_code']} - "
                          f"{signal['confidence']:.1%} - {reasons}")
            
            # 导出结果
            if args.export_excel:
                print(f"\n正在导出结果到 Excel...")
                if engine.export_results_to_excel(result['results'], args.export_excel):
                    print(f"✓ 结果已导出到: {args.export_excel}")
                else:
                    print("✗ Excel 导出失败")
        
        else:
            print(f"✗ 批量分析失败: {result.get('error', '未知错误')}")
    
    except Exception as e:
        print(f"✗ 批量分析异常: {e}")

def query_analysis_results(args):
    """查询分析结果"""
    print("查询分析结果")
    
    try:
        with AnalysisDatabase() as db:
            if args.stock_code:
                # 查询单个股票
                print(f"查询股票: {args.stock_code}")
                result = db.get_latest_analysis(args.stock_code, args.strategy)
                
                if result:
                    print(f"\n最新分析结果:")
                    print(f"股票代码: {result['ts_code']}")
                    print(f"策略名称: {result['strategy_name']}")
                    print(f"交易信号: {result['signal']}")
                    print(f"置信度: {result['confidence']:.1%}")
                    print(f"分析时间: {result['analysis_timestamp']}")
                    print(f"分析原因: {' | '.join(result['reasons'])}")
                else:
                    print("未找到分析结果")
            
            elif args.signal:
                # 查询特定信号
                print(f"查询信号: {args.signal}")
                results = db.get_top_signals(
                    args.signal, 
                    limit=args.limit,
                    strategy_name=args.strategy,
                    days=args.days
                )
                
                if results:
                    print(f"\n置信度最高的 {args.signal} 信号 (前{len(results)}只):")
                    for i, result in enumerate(results, 1):
                        print(f"{i:2d}. {result['ts_code']} - "
                              f"{result['confidence']:.1%} - "
                              f"{result['reasons'] or '无原因'}")
                else:
                    print(f"未找到 {args.signal} 信号")
            
            else:
                # 查询统计信息
                stats = db.get_signal_statistics(
                    strategy_name=args.strategy,
                    days=args.days
                )
                
                if stats:
                    print(f"\n信号统计 (最近{args.days}天):")
                    print(f"总计: {stats['total']} 个信号")
                    print(f"买入: {stats['signals']['买入']} 个 "
                          f"(平均置信度: {stats['avg_confidence']['买入']:.1%})")
                    print(f"卖出: {stats['signals']['卖出']} 个 "
                          f"(平均置信度: {stats['avg_confidence']['卖出']:.1%})")
                    print(f"观望: {stats['signals']['观望']} 个 "
                          f"(平均置信度: {stats['avg_confidence']['观望']:.1%})")
                else:
                    print("未找到统计数据")
    
    except Exception as e:
        print(f"✗ 查询失败: {e}")

def export_data(args):
    """导出数据"""
    print(f"导出数据到: {args.output_file}")
    
    try:
        with AnalysisDatabase() as db:
            if db.export_to_excel(
                args.output_file, 
                strategy_name=args.strategy,
                days=args.days
            ):
                print("✓ 数据导出成功")
            else:
                print("✗ 数据导出失败")
    except Exception as e:
        print(f"✗ 导出错误: {e}")

def clean_old_data(args):
    """清理旧数据"""
    print(f"清理 {args.days_to_keep} 天前的旧数据...")
    
    try:
        with AnalysisDatabase() as db:
            if db.clear_old_analysis(args.days_to_keep):
                print("✓ 旧数据清理完成")
            else:
                print("✗ 旧数据清理失败")
    except Exception as e:
        print(f"✗ 清理错误: {e}")

def list_strategies(args):
    """列出所有可用策略"""
    print("可用策略:")
    strategies = StrategyFactory.get_available_strategies()
    
    if strategies:
        for i, strategy in enumerate(strategies, 1):
            try:
                instance = StrategyFactory.create_strategy(strategy)
                description = instance.get_strategy_description()
                print(f"{i}. {strategy}")
                print(f"   描述: {description}")
            except Exception as e:
                print(f"{i}. {strategy}")
                print(f"   描述: 加载失败 ({e})")
    else:
        print("未找到可用策略")

def list_stocks(args):
    """列出可用股票代码"""
    print("正在查询可用股票...")
    
    try:
        with StockAnalyzer() as analyzer:
            # 获取前50只成交量最高的股票
            stock_list = analyzer.get_top_volume_stocks(args.limit)
            
            if stock_list:
                print(f"\n可用股票代码 (按成交量排序，前{len(stock_list)}只):")
                print("=" * 60)
                
                # 按交易所分类显示
                sh_stocks = [code for code in stock_list if code.endswith('.SH')]
                sz_stocks = [code for code in stock_list if code.endswith('.SZ')]
                
                if sh_stocks:
                    print(f"\n上海证券交易所 ({len(sh_stocks)}只):")
                    for i, code in enumerate(sh_stocks, 1):
                        if i % 5 == 0:
                            print(f"{code}")
                        else:
                            print(f"{code:<15}", end="")
                    if len(sh_stocks) % 5 != 0:
                        print()
                
                if sz_stocks:
                    print(f"\n深圳证券交易所 ({len(sz_stocks)}只):")
                    for i, code in enumerate(sz_stocks, 1):
                        if i % 5 == 0:
                            print(f"{code}")
                        else:
                            print(f"{code:<15}", end="")
                    if len(sz_stocks) % 5 != 0:
                        print()
                
                print(f"\n使用示例:")
                if sh_stocks:
                    print(f"  python main.py analyze --stock-code {sh_stocks[0]} --show-chart")
                if sz_stocks:
                    print(f"  python main.py analyze --stock-code {sz_stocks[0]} --show-chart")
            
            else:
                print("未找到可用股票")
                
    except Exception as e:
        print(f"✗ 查询失败: {e}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='中国股票分析系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 初始化数据库
  python main.py init-db
  
  # 查看可用股票
  python main.py list-stocks --limit 20
  
  # 多策略综合分析（推荐）
  python main.py analyze --stock-code 601138.SH --show-chart
  
  # 单策略分析
  python main.py analyze --stock-code 601138.SH --strategy ADXTrendStrategy --show-chart
  
  # 多策略批量分析（推荐）
  python main.py batch --limit 20 --workers 4 --save-db --show-top-signals
  
  # 单策略批量分析
  python main.py batch --limit 20 --strategies ADXTrendStrategy --workers 4 --save-db
  
  # 查询结果
  python main.py query --signal 买入 --limit 10
  
  # 导出数据
  python main.py export --output results.xlsx --days 7
  
  # 列出策略
  python main.py list-strategies
  
  注意：当前数据库仅包含上海证券交易所股票数据，使用前请先运行 list-stocks 查看可用代码。
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 初始化数据库
    init_parser = subparsers.add_parser('init-db', help='初始化数据库表')
    
    # 单股票分析
    analyze_parser = subparsers.add_parser('analyze', help='单股票分析')
    analyze_parser.add_argument('--stock-code', required=True, help='股票代码 (例: 000001.SZ)')
    analyze_parser.add_argument('--strategy', help='策略名称，不指定则使用所有策略进行综合分析')
    analyze_parser.add_argument('--days', type=int, default=30, help='分析天数')
    analyze_parser.add_argument('--save-db', action='store_true', help='保存结果到数据库')
    analyze_parser.add_argument('--show-chart', action='store_true', help='显示图表')
    analyze_parser.add_argument('--chart-path', help='保存图表路径 (HTML格式)')
    
    # 批量分析
    batch_parser = subparsers.add_parser('batch', help='批量股票分析')
    batch_parser.add_argument('--strategies', nargs='+', help='策略名称列表，不指定则使用所有策略进行综合分析')
    batch_parser.add_argument('--limit', type=int, default=1000, help='分析股票数量')
    batch_parser.add_argument('--days', type=int, default=30, help='分析天数')
    batch_parser.add_argument('--workers', type=int, default=4, help='并发线程数')
    batch_parser.add_argument('--batch-name', help='批次名称')
    batch_parser.add_argument('--save-db', action='store_true', help='保存结果到数据库')
    batch_parser.add_argument('--show-top-signals', action='store_true', help='显示顶级信号')
    batch_parser.add_argument('--top-limit', type=int, default=10, help='顶级信号数量')
    batch_parser.add_argument('--export-excel', help='导出Excel文件路径')
    
    # 查询结果
    query_parser = subparsers.add_parser('query', help='查询分析结果')
    query_parser.add_argument('--stock-code', help='股票代码')
    query_parser.add_argument('--signal', choices=['买入', '卖出', '观望'], help='查询特定信号')
    query_parser.add_argument('--strategy', help='策略名称过滤')
    query_parser.add_argument('--days', type=int, default=7, help='查询天数')
    query_parser.add_argument('--limit', type=int, default=20, help='查询数量限制')
    
    # 导出数据
    export_parser = subparsers.add_parser('export', help='导出分析数据')
    export_parser.add_argument('--output-file', required=True, help='输出Excel文件路径')
    export_parser.add_argument('--strategy', help='策略名称过滤')
    export_parser.add_argument('--days', type=int, default=1, help='导出天数')
    
    # 清理数据
    clean_parser = subparsers.add_parser('clean', help='清理旧数据')
    clean_parser.add_argument('--days-to-keep', type=int, default=30, help='保留天数')
    
    # 列出策略
    list_parser = subparsers.add_parser('list-strategies', help='列出所有可用策略')
    
    # 列出股票
    stocks_parser = subparsers.add_parser('list-stocks', help='列出可用股票代码')
    stocks_parser.add_argument('--limit', type=int, default=50, help='显示股票数量，默认50')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    print(f"中国股票分析系统 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 执行对应命令
    if args.command == 'init-db':
        setup_database()
    elif args.command == 'analyze':
        analyze_single_stock(args)
    elif args.command == 'batch':
        analyze_batch_stocks(args)
    elif args.command == 'query':
        query_analysis_results(args)
    elif args.command == 'export':
        export_data(args)
    elif args.command == 'clean':
        clean_old_data(args)
    elif args.command == 'list-strategies':
        list_strategies(args)
    elif args.command == 'list-stocks':
        list_stocks(args)

if __name__ == "__main__":
    main()