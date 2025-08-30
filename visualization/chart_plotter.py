"""
股票图表绘制器
使用plotly创建交互式K线图和技术指标图表
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analyzer import StockAnalyzer
from database import AnalysisDatabase
from strategy import StrategyFactory

class ChartPlotter:
    """股票图表绘制器"""
    
    def __init__(self):
        self.colors = {
            'up': '#00ff88',      # 上涨绿色
            'down': '#ff4444',    # 下跌红色
            'buy_signal': '#0066ff',   # 买入信号蓝色
            'sell_signal': '#ff6600',  # 卖出信号橙色
            'hold_signal': '#888888',  # 观望信号灰色
            'volume': '#666666',       # 成交量灰色
            'ma_fast': '#ff00ff',      # 快速均线紫色
            'ma_slow': '#ffff00',      # 慢速均线黄色
            'bb_upper': '#00ffff',     # 布林上轨青色
            'bb_lower': '#00ffff',     # 布林下轨青色
            'bb_middle': '#888888',    # 布林中轨灰色
            'rsi': '#ff8800',          # RSI橙色
            'macd': '#0088ff',         # MACD蓝色
            'macd_signal': '#ff0088',  # MACD信号红色
            'adx': '#00ff00',          # ADX绿色
            'di_plus': '#ff0000',      # DI+红色
            'di_minus': '#0000ff'      # DI-蓝色
        }
    
    def create_kline_chart(self, df: pd.DataFrame, ts_code: str,
                          analysis_results: Optional[Dict] = None,
                          show_volume: bool = True,
                          show_indicators: bool = True,
                          width: int = 1200, height: int = 1000) -> go.Figure:
        """
        创建K线图表
        Args:
            df: 包含OHLCV数据的DataFrame
            ts_code: 股票代码
            analysis_results: 分析结果字典
            show_volume: 是否显示成交量
            show_indicators: 是否显示技术指标
            width: 图表宽度
            height: 图表高度
        """
        if df.empty:
            return self._create_empty_chart("无数据", width, height)
        
        # 计算子图数量
        subplot_count = 1  # K线图
        if show_volume:
            subplot_count += 1
        if show_indicators:
            subplot_count += 2  # RSI和MACD
        
        # 创建子图
        specs = [[{"secondary_y": False}] for _ in range(subplot_count)]
        subplot_titles = [f"{ts_code} K线图"]
        
        if show_volume:
            subplot_titles.append("成交量")
        if show_indicators:
            subplot_titles.extend(["RSI", "MACD"])
        
        # 优化子图高度分配
        if subplot_count == 1:
            row_heights = [1.0]
        elif subplot_count == 2:
            row_heights = [0.7, 0.3]  # K线图占70%，其他30%
        elif subplot_count == 3:
            row_heights = [0.6, 0.2, 0.2]  # K线图占60%，其他各20%
        else:
            row_heights = [0.5] + [0.5/(subplot_count-1)]*(subplot_count-1)
        
        fig = make_subplots(
            rows=subplot_count, cols=1,
            specs=specs,
            subplot_titles=subplot_titles,
            vertical_spacing=0.08,  # 增加子图间距
            row_heights=row_heights
        )
        
        # 添加K线图
        self._add_candlestick(fig, df, row=1)
        
        # 添加交易信号标记
        if analysis_results:
            self._add_signal_markers(fig, df, analysis_results, row=1)
        
        # 添加技术指标到K线图
        if show_indicators:
            self._add_moving_averages(fig, df, row=1)
            self._add_bollinger_bands(fig, df, row=1)
        
        # 添加成交量图
        if show_volume:
            volume_row = 2
            self._add_volume(fig, df, row=volume_row)
        else:
            volume_row = 1
        
        # 添加技术指标子图
        if show_indicators:
            rsi_row = volume_row + 1 if show_volume else 2
            macd_row = rsi_row + 1
            
            self._add_rsi(fig, df, row=rsi_row)
            self._add_macd(fig, df, row=macd_row)
        
        # 设置布局
        fig.update_layout(
            width=width,
            height=height,
            title=f"{ts_code} 股票分析图表",
            xaxis_rangeslider_visible=False,
            showlegend=True,
            template='plotly_white',
            hovermode='x unified',
            margin=dict(l=80, r=80, t=100, b=80),  # 增加边距
            font=dict(size=12, color='black')
        )
        
        # 优化x轴显示 - 减少标签密度，只显示部分时间点
        total_points = len(df)
        if total_points > 50:
            # 如果数据点多，只显示部分标签
            step = max(1, total_points // 20)  # 最多显示20个标签
            tickvals = list(range(0, total_points, step))
            ticktext = [df.index[i] if i < len(df.index) else '' for i in tickvals]
        else:
            step = max(1, total_points // 10)  # 较少数据时显示10个标签
            tickvals = list(range(0, total_points, step))
            ticktext = [df.index[i] if i < len(df.index) else '' for i in tickvals]
        
        # 计算子图总数
        total_subplots = 1  # K线图
        if show_volume:
            total_subplots += 1
        if show_indicators:
            total_subplots += 2  # RSI和MACD
        
        # 更新所有子图的x轴
        for i in range(1, total_subplots + 1):
            fig.update_xaxes(
                type='category',
                tickmode='array',
                tickvals=tickvals,
                ticktext=ticktext,
                tickangle=45,  # 倾斜45度显示
                row=i, col=1
            )
            
            # 只在最底部的子图显示x轴标签
            if i < total_subplots:
                fig.update_xaxes(showticklabels=False, row=i, col=1)
        
        return fig
    
    def _add_candlestick(self, fig: go.Figure, df: pd.DataFrame, row: int):
        """添加K线图"""
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                increasing_line_color=self.colors['up'],
                decreasing_line_color=self.colors['down'],
                name='K线',
                showlegend=False
            ),
            row=row, col=1
        )
    
    def _add_signal_markers(self, fig: go.Figure, df: pd.DataFrame, 
                           analysis_results: Dict, row: int):
        """添加交易信号标记"""
        if not analysis_results:
            return
        
        # 在最后一个K线上添加信号标记
        last_idx = len(df) - 1
        last_price = df.iloc[-1]['close']
        
        signal_colors = {
            '买入': self.colors['buy_signal'],
            '卖出': self.colors['sell_signal'],
            '观望': self.colors['hold_signal']
        }
        
        signal_symbols = {
            '买入': 'triangle-up',
            '卖出': 'triangle-down',
            '观望': 'circle'
        }
        
        # 按信号类型分组，避免重叠
        signal_groups = {'买入': [], '卖出': [], '观望': []}
        
        for strategy_name, result in analysis_results.items():
            if result.get('success') and result.get('analysis_result'):
                signal = result['analysis_result']['signal']
                confidence = result['analysis_result']['confidence']
                signal_groups[signal].append((strategy_name, confidence))
        
        # 为每个信号组创建标记
        for signal, strategies in signal_groups.items():
            if not strategies:
                continue
                
            # 按信号类型调整Y轴位置，避免重叠
            if signal == '买入':
                y_offset = last_price * 1.02  # 上方
            elif signal == '卖出':
                y_offset = last_price * 0.98  # 下方
            else:  # 观望
                y_offset = last_price  # 中间
            
            # 水平偏移，如果同一信号有多个策略
            for i, (strategy_name, confidence) in enumerate(strategies):
                x_offset = last_idx + (i - len(strategies)/2 + 0.5) * 0.3
                
                fig.add_trace(
                    go.Scatter(
                        x=[x_offset],
                        y=[y_offset],
                        mode='markers',
                        marker=dict(
                            symbol=signal_symbols.get(signal, 'circle'),
                            color=signal_colors.get(signal, '#888888'),
                            size=12 + confidence * 8,  # 根据置信度调整大小
                            line=dict(width=2, color='white'),
                            opacity=0.8
                        ),
                        name=f'{strategy_name}: {signal}',
                        hovertemplate=f'<b>{strategy_name}</b><br>' +
                                    f'信号: {signal}<br>' +
                                    f'置信度: {confidence:.1%}<br>' +
                                    '<extra></extra>',
                        showlegend=True
                    ),
                    row=row, col=1
                )
    
    def _add_moving_averages(self, fig: go.Figure, df: pd.DataFrame, row: int):
        """添加移动平均线"""
        if 'ema_fast' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['ema_fast'],
                    line=dict(color=self.colors['ma_fast'], width=1),
                    name='EMA12',
                    opacity=0.7
                ),
                row=row, col=1
            )
        
        if 'ema_slow' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['ema_slow'],
                    line=dict(color=self.colors['ma_slow'], width=1),
                    name='EMA30',
                    opacity=0.7
                ),
                row=row, col=1
            )
    
    def _add_bollinger_bands(self, fig: go.Figure, df: pd.DataFrame, row: int):
        """添加布林带"""
        if all(col in df.columns for col in ['bb_upper', 'bb_middle', 'bb_lower']):
            # 上轨
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['bb_upper'],
                    line=dict(color=self.colors['bb_upper'], width=1, dash='dash'),
                    name='布林上轨',
                    opacity=0.5
                ),
                row=row, col=1
            )
            
            # 中轨
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['bb_middle'],
                    line=dict(color=self.colors['bb_middle'], width=1),
                    name='布林中轨',
                    opacity=0.5
                ),
                row=row, col=1
            )
            
            # 下轨和填充
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['bb_lower'],
                    fill='tonexty',
                    fillcolor='rgba(128,128,128,0.1)',
                    line=dict(color=self.colors['bb_lower'], width=1, dash='dash'),
                    name='布林下轨',
                    opacity=0.5
                ),
                row=row, col=1
            )
    
    def _add_volume(self, fig: go.Figure, df: pd.DataFrame, row: int):
        """添加成交量"""
        colors = [self.colors['up'] if df.iloc[i]['close'] >= df.iloc[i]['open']
                 else self.colors['down'] for i in range(len(df))]
        
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df['volume'],
                marker_color=colors,
                name='成交量',
                opacity=0.6,
                showlegend=False
            ),
            row=row, col=1
        )
        
        fig.update_yaxes(title_text="成交量", row=row, col=1)
    
    def _add_rsi(self, fig: go.Figure, df: pd.DataFrame, row: int):
        """添加RSI指标"""
        if 'rsi' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['rsi'],
                    line=dict(color=self.colors['rsi'], width=2),
                    name='RSI',
                    showlegend=False
                ),
                row=row, col=1
            )
            
            # 添加超买超卖线
            fig.add_hline(y=70, line_dash="dash", line_color="red", 
                         opacity=0.5, row=row, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", 
                         opacity=0.5, row=row, col=1)
            fig.add_hline(y=50, line_dash="dot", line_color="gray", 
                         opacity=0.3, row=row, col=1)
            
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=row, col=1)
    
    def _add_macd(self, fig: go.Figure, df: pd.DataFrame, row: int):
        """添加MACD指标"""
        if all(col in df.columns for col in ['macd', 'macd_signal', 'macd_hist']):
            # MACD线
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['macd'],
                    line=dict(color=self.colors['macd'], width=2),
                    name='MACD',
                    showlegend=False
                ),
                row=row, col=1
            )
            
            # 信号线
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['macd_signal'],
                    line=dict(color=self.colors['macd_signal'], width=2),
                    name='MACD信号',
                    showlegend=False
                ),
                row=row, col=1
            )
            
            # 柱状图
            colors = ['red' if x < 0 else 'green' for x in df['macd_hist']]
            fig.add_trace(
                go.Bar(
                    x=df.index,
                    y=df['macd_hist'],
                    marker_color=colors,
                    name='MACD柱状图',
                    opacity=0.6,
                    showlegend=False
                ),
                row=row, col=1
            )
            
            fig.add_hline(y=0, line_dash="dash", line_color="gray", 
                         opacity=0.5, row=row, col=1)
            fig.update_yaxes(title_text="MACD", row=row, col=1)
    
    def _create_empty_chart(self, message: str, width: int, height: int) -> go.Figure:
        """创建空图表"""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=20, color="gray")
        )
        fig.update_layout(
            width=width,
            height=height,
            title="图表",
            template='plotly_white',
            font=dict(color='black')
        )
        return fig
    
    def create_stock_analysis_chart(self, ts_code: str, strategy_names: Optional[List[str]] = None,
                                  days: int = 30, save_path: Optional[str] = None) -> go.Figure:
        """
        创建股票分析图表（完整流程）
        """
        if strategy_names is None:
            strategy_names = ['ADXTrendStrategy']
        
        try:
            # 获取股票数据
            with StockAnalyzer() as analyzer:
                df = analyzer.get_stock_data(ts_code, days)
                
                if df.empty:
                    return self._create_empty_chart(f"股票 {ts_code} 无数据", 1200, 1000)
                
                # 运行策略分析
                analysis_results = {}
                final_df = df.copy()  # 保存最终用于图表的数据框
                
                for strategy_name in strategy_names:
                    try:
                        strategy = StrategyFactory.create_strategy(strategy_name)
                        df_with_indicators = strategy.calculate_indicators(df.copy())
                        analysis_result = strategy.generate_signal(df_with_indicators)
                        
                        analysis_results[strategy_name] = {
                            'success': True,
                            'analysis_result': {
                                'signal': analysis_result.signal.value,
                                'confidence': analysis_result.confidence,
                                'reasons': analysis_result.reasons,
                                'indicators': analysis_result.indicators
                            }
                        }
                        
                        # 合并指标到最终数据框（避免覆盖）
                        for col in df_with_indicators.columns:
                            if col not in final_df.columns and col not in ['timestamp', 'ts_code', 'open', 'high', 'low', 'close', 'volume', 'amount']:
                                final_df[col] = df_with_indicators[col]
                        
                    except Exception as e:
                        print(f"策略 {strategy_name} 分析失败: {e}")
                        analysis_results[strategy_name] = {
                            'success': False,
                            'error': str(e)
                        }
                
                # 使用包含所有指标的数据框
                df = final_df
                
                # 创建图表
                fig = self.create_kline_chart(
                    df, ts_code, analysis_results,
                    show_volume=True,
                    show_indicators=True
                )
                
                # 保存图表
                if save_path:
                    fig.write_html(save_path)
                    print(f"图表已保存到: {save_path}")
                
                return fig
                
        except Exception as e:
            print(f"创建图表失败: {e}")
            return self._create_empty_chart(f"创建图表失败: {str(e)}", 1200, 1000)
    
    def create_multi_stock_comparison(self, stock_codes: List[str], 
                                    strategy_name: str = 'ADXTrendStrategy',
                                    metric: str = 'confidence') -> go.Figure:
        """
        创建多股票对比图表
        """
        try:
            comparison_data = []
            
            with StockAnalyzer() as analyzer:
                for ts_code in stock_codes:
                    result = analyzer.analyze_single_stock(ts_code, strategy_name)
                    
                    if result['success'] and result['analysis_result']:
                        analysis = result['analysis_result']
                        comparison_data.append({
                            'ts_code': ts_code,
                            'signal': analysis['signal'],
                            'confidence': analysis['confidence'],
                            'rsi': analysis['indicators'].get('rsi', 0),
                            'adx': analysis['indicators'].get('adx', 0)
                        })
            
            if not comparison_data:
                return self._create_empty_chart("无对比数据", 1200, 600)
            
            df_compare = pd.DataFrame(comparison_data)
            
            # 创建对比图表
            fig = go.Figure()
            
            if metric == 'confidence':
                colors = [self.colors['buy_signal'] if signal == '买入' 
                         else self.colors['sell_signal'] if signal == '卖出' 
                         else self.colors['hold_signal'] for signal in df_compare['signal']]
                
                fig.add_trace(
                    go.Bar(
                        x=df_compare['ts_code'],
                        y=df_compare['confidence'],
                        marker_color=colors,
                        text=df_compare['signal'],
                        textposition='auto',
                        name='置信度'
                    )
                )
                
                fig.update_layout(
                    title=f'{strategy_name} 策略置信度对比',
                    yaxis_title='置信度',
                    xaxis_title='股票代码'
                )
            
            fig.update_layout(
                width=1200,
                height=600,
                template='plotly_white',
                showlegend=True,
                font=dict(color='black')
            )
            
            return fig
            
        except Exception as e:
            print(f"创建对比图表失败: {e}")
            return self._create_empty_chart(f"创建对比图表失败: {str(e)}", 1200, 600)

def show_chart_in_browser(fig: go.Figure):
    """在浏览器中显示图表"""
    try:
        fig.show()
    except Exception as e:
        print(f"显示图表失败: {e}")

def save_chart_as_image(fig: go.Figure, file_path: str, 
                       format: str = 'png', width: int = 1200, height: int = 800):
    """保存图表为图片"""
    try:
        fig.write_image(file_path, format=format, width=width, height=height)
        print(f"图表已保存为图片: {file_path}")
    except Exception as e:
        print(f"保存图片失败: {e}")
        print("提示: 需要安装 kaleido: pip install kaleido")