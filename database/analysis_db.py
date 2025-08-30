"""
分析结果数据库操作类
负责分析结果的存储、查询和管理
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pandas as pd
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.db_utils import DatabaseUtils
from strategy import AnalysisResult, Signal

class AnalysisDatabase:
    """分析结果数据库操作类"""
    
    def __init__(self):
        self.conn, self.cursor = DatabaseUtils.connect_to_mysql()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
    
    def create_tables(self) -> bool:
        """
        创建分析结果相关表
        """
        try:
            # 读取SQL文件
            sql_file_path = os.path.join(
                os.path.dirname(__file__), 
                'create_tables_simple.sql'
            )
            
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # 分割SQL语句并执行
            # 处理多行语句和注释
            import re
            
            # 移除纯注释行和空行
            lines = [line for line in sql_content.split('\n') 
                    if line.strip() and not line.strip().startswith('--')]
            clean_content = '\n'.join(lines)
            
            # 按分号分割语句，但保留DELIMITER块
            statements = []
            current_stmt = ""
            in_delimiter_block = False
            
            for line in clean_content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('DELIMITER'):
                    if 'DELIMITER //' in line:
                        in_delimiter_block = True
                    elif 'DELIMITER ;' in line:
                        in_delimiter_block = False
                        if current_stmt.strip():
                            statements.append(current_stmt.strip())
                            current_stmt = ""
                    continue
                
                current_stmt += line + '\n'
                
                if not in_delimiter_block and line.endswith(';'):
                    statements.append(current_stmt.strip())
                    current_stmt = ""
            
            if current_stmt.strip():
                statements.append(current_stmt.strip())
            
            # 执行每个语句
            for sql in statements:
                if sql and not sql.startswith('--'):
                    try:
                        self.cursor.execute(sql)
                    except Exception as e:
                        print(f"执行SQL语句失败: {e}")
                        print(f"语句: {sql[:100]}...")
                        # 继续执行其他语句
            
            self.conn.commit()
            print("数据库表创建成功")
            return True
            
        except Exception as e:
            print(f"创建数据库表失败: {e}")
            self.conn.rollback()
            return False
    
    def create_batch(self, strategy_names: List[str], total_stocks: int,
                    batch_name: Optional[str] = None) -> int:
        """
        创建分析批次记录
        """
        try:
            sql = """
            INSERT INTO analysis_batches 
            (batch_name, strategy_names, total_stocks, start_time, status)
            VALUES (%s, %s, %s, %s, 'running')
            """
            
            self.cursor.execute(sql, (
                batch_name or f"批次_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                json.dumps(strategy_names, ensure_ascii=False),
                total_stocks,
                datetime.now()
            ))
            
            batch_id = self.cursor.lastrowid
            self.conn.commit()
            return batch_id
            
        except Exception as e:
            print(f"创建批次记录失败: {e}")
            self.conn.rollback()
            return 0
    
    def update_batch_status(self, batch_id: int, status: str, 
                           successful_count: int = 0, failed_count: int = 0) -> bool:
        """
        更新批次状态
        """
        try:
            end_time = datetime.now()
            sql = """
            UPDATE analysis_batches 
            SET status = %s, successful_count = %s, failed_count = %s,
                end_time = %s,
                duration_seconds = TIMESTAMPDIFF(MICROSECOND, start_time, %s) / 1000000
            WHERE id = %s
            """
            
            self.cursor.execute(sql, (
                status, successful_count, failed_count, 
                end_time, end_time, batch_id
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"更新批次状态失败: {e}")
            self.conn.rollback()
            return False
    
    def save_analysis_result(self, ts_code: str, strategy_name: str,
                           analysis_result: AnalysisResult,
                           batch_id: Optional[int] = None,
                           data_start_time: Optional[datetime] = None,
                           data_end_time: Optional[datetime] = None,
                           data_points: int = 0) -> int:
        """
        保存单个分析结果
        """
        try:
            # 插入主结果记录
            sql = """
            INSERT INTO stock_analysis_results 
            (ts_code, strategy_name, `signal`, confidence, analysis_timestamp,
             data_start_time, data_end_time, data_points)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            # 处理confidence中的NaN值
            import math
            confidence_value = analysis_result.confidence
            if math.isnan(confidence_value) or math.isinf(confidence_value):
                confidence_value = 0.0  # 将NaN/Inf设为0
            
            self.cursor.execute(sql, (
                ts_code,
                strategy_name,
                analysis_result.signal.value,
                confidence_value,
                datetime.strptime(analysis_result.timestamp, '%Y-%m-%d %H:%M:%S'),
                data_start_time,
                data_end_time,
                data_points
            ))
            
            analysis_id = self.cursor.lastrowid
            
            # 插入原因记录
            if analysis_result.reasons:
                reason_sql = """
                INSERT INTO stock_analysis_reasons 
                (analysis_id, reason_text, reason_order)
                VALUES (%s, %s, %s)
                """
                
                for i, reason in enumerate(analysis_result.reasons):
                    self.cursor.execute(reason_sql, (analysis_id, reason, i + 1))
            
            # 插入指标记录
            if analysis_result.indicators:
                indicator_sql = """
                INSERT INTO stock_analysis_indicators 
                (analysis_id, indicator_name, indicator_value, indicator_text)
                VALUES (%s, %s, %s, %s)
                """
                
                for name, value in analysis_result.indicators.items():
                    if isinstance(value, (int, float)):
                        # 处理NaN值，转换为NULL
                        import math
                        if math.isnan(value) or math.isinf(value):
                            self.cursor.execute(indicator_sql, (analysis_id, name, None, f"NaN/Inf_{value}"))
                        else:
                            self.cursor.execute(indicator_sql, (analysis_id, name, value, None))
                    else:
                        self.cursor.execute(indicator_sql, (analysis_id, name, None, str(value)))
            
            # 关联到批次
            if batch_id:
                batch_sql = """
                INSERT INTO batch_analysis_results (batch_id, analysis_id)
                VALUES (%s, %s)
                """
                self.cursor.execute(batch_sql, (batch_id, analysis_id))
            
            self.conn.commit()
            return analysis_id
            
        except Exception as e:
            print(f"保存分析结果失败 [{ts_code}]: {e}")
            self.conn.rollback()
            return 0
    
    def get_latest_analysis(self, ts_code: str, strategy_name: str) -> Optional[Dict]:
        """
        获取最新的分析结果
        """
        try:
            sql = """
            SELECT sar.*, 
                   GROUP_CONCAT(saar.reason_text ORDER BY saar.reason_order SEPARATOR '|') as reasons
            FROM stock_analysis_results sar
            LEFT JOIN stock_analysis_reasons saar ON sar.id = saar.analysis_id
            WHERE sar.ts_code = %s AND sar.strategy_name = %s
            GROUP BY sar.id
            ORDER BY sar.analysis_timestamp DESC
            LIMIT 1
            """
            
            self.cursor.execute(sql, (ts_code, strategy_name))
            result = self.cursor.fetchone()
            
            if not result:
                return None
            
            # 获取指标数据
            indicator_sql = """
            SELECT indicator_name, indicator_value, indicator_text
            FROM stock_analysis_indicators
            WHERE analysis_id = %s
            """
            self.cursor.execute(indicator_sql, (result[0],))
            indicators = {}
            for row in self.cursor.fetchall():
                name, value, text = row
                indicators[name] = value if value is not None else text
            
            return {
                'id': result[0],
                'ts_code': result[1],
                'strategy_name': result[2],
                'signal': result[3],
                'confidence': float(result[4]),
                'analysis_timestamp': result[5],
                'data_start_time': result[6],
                'data_end_time': result[7],
                'data_points': result[8],
                'created_at': result[9],
                'updated_at': result[10],
                'reasons': result[11].split('|') if result[11] else [],
                'indicators': indicators
            }
            
        except Exception as e:
            print(f"获取最新分析结果失败 [{ts_code}]: {e}")
            return None
    
    def get_analysis_history(self, ts_code: str, strategy_name: str, 
                           days: int = 30) -> List[Dict]:
        """
        获取历史分析结果
        """
        try:
            sql = """
            SELECT * FROM v_analysis_summary
            WHERE ts_code = %s AND strategy_name = %s
            AND analysis_timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY analysis_timestamp DESC
            """
            
            self.cursor.execute(sql, (ts_code, strategy_name, days))
            results = self.cursor.fetchall()
            
            columns = [desc[0] for desc in self.cursor.description]
            return [dict(zip(columns, row)) for row in results]
            
        except Exception as e:
            print(f"获取历史分析结果失败: {e}")
            return []
    
    def get_signal_statistics(self, strategy_name: str = None, 
                            days: int = 7) -> Dict:
        """
        获取信号统计
        """
        try:
            base_sql = """
            SELECT `signal`, COUNT(*) as count, AVG(confidence) as avg_confidence
            FROM stock_analysis_results
            WHERE analysis_timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)
            """
            
            params = [days]
            if strategy_name:
                base_sql += " AND strategy_name = %s"
                params.append(strategy_name)
            
            base_sql += " GROUP BY `signal`"
            
            self.cursor.execute(base_sql, params)
            results = self.cursor.fetchall()
            
            stats = {
                'total': 0,
                'signals': {'买入': 0, '卖出': 0, '观望': 0},
                'avg_confidence': {'买入': 0.0, '卖出': 0.0, '观望': 0.0}
            }
            
            for signal, count, avg_conf in results:
                stats['signals'][signal] = count
                stats['avg_confidence'][signal] = float(avg_conf)
                stats['total'] += count
            
            return stats
            
        except Exception as e:
            print(f"获取信号统计失败: {e}")
            return {}
    
    def get_top_signals(self, signal_type: str, limit: int = 20,
                       strategy_name: str = None, days: int = 1) -> List[Dict]:
        """
        获取置信度最高的信号
        """
        try:
            base_sql = """
            SELECT ts_code, strategy_name, `signal`, confidence, analysis_timestamp,
                   (SELECT GROUP_CONCAT(reason_text ORDER BY reason_order SEPARATOR ' | ') 
                    FROM stock_analysis_reasons WHERE analysis_id = sar.id) as reasons
            FROM stock_analysis_results sar
            WHERE `signal` = %s
            AND analysis_timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)
            """
            
            params = [signal_type, days]
            if strategy_name:
                base_sql += " AND strategy_name = %s"
                params.append(strategy_name)
            
            base_sql += " ORDER BY confidence DESC, analysis_timestamp DESC LIMIT %s"
            params.append(limit)
            
            self.cursor.execute(base_sql, params)
            results = self.cursor.fetchall()
            
            columns = ['ts_code', 'strategy_name', 'signal', 'confidence', 
                      'analysis_timestamp', 'reasons']
            return [dict(zip(columns, row)) for row in results]
            
        except Exception as e:
            print(f"获取顶级信号失败: {e}")
            return []
    
    def clear_old_analysis(self, days_to_keep: int = 30) -> bool:
        """
        清理旧的分析数据
        """
        try:
            self.cursor.execute("CALL CleanOldAnalysisData(%s)", (days_to_keep,))
            self.conn.commit()
            print(f"已清理{days_to_keep}天前的分析数据")
            return True
            
        except Exception as e:
            print(f"清理旧数据失败: {e}")
            self.conn.rollback()
            return False
    
    def get_batch_results(self, batch_id: int) -> Dict:
        """
        获取批次分析结果
        """
        try:
            # 获取批次信息
            batch_sql = """
            SELECT * FROM analysis_batches WHERE id = %s
            """
            self.cursor.execute(batch_sql, (batch_id,))
            batch_info = self.cursor.fetchone()
            
            if not batch_info:
                return {}
            
            # 获取批次结果
            results_sql = """
            SELECT vs.* FROM v_analysis_summary vs
            INNER JOIN batch_analysis_results bar ON vs.ts_code = bar.analysis_id
            WHERE bar.batch_id = %s
            ORDER BY vs.confidence DESC
            """
            self.cursor.execute(results_sql, (batch_id,))
            results = self.cursor.fetchall()
            
            columns = [desc[0] for desc in self.cursor.description]
            detailed_results = [dict(zip(columns, row)) for row in results]
            
            return {
                'batch_info': dict(zip([
                    'id', 'batch_name', 'strategy_names', 'total_stocks',
                    'successful_count', 'failed_count', 'start_time', 'end_time',
                    'duration_seconds', 'status', 'created_at'
                ], batch_info)),
                'results': detailed_results
            }
            
        except Exception as e:
            print(f"获取批次结果失败: {e}")
            return {}
    
    def export_to_excel(self, file_path: str, strategy_name: str = None,
                       days: int = 1) -> bool:
        """
        导出分析结果到Excel
        """
        try:
            base_sql = """
            SELECT ts_code as '股票代码', strategy_name as '策略名称', 
                   `signal` as '信号', confidence as '置信度',
                   analysis_timestamp as '分析时间', 
                   (SELECT GROUP_CONCAT(reason_text ORDER BY reason_order SEPARATOR ' | ') 
                    FROM stock_analysis_reasons sar2 WHERE sar2.analysis_id = sar.id) as '原因'
            FROM stock_analysis_results sar
            WHERE analysis_timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)
            """
            
            params = [days]
            if strategy_name:
                base_sql += " AND strategy_name = %s"
                params.append(strategy_name)
            
            base_sql += " ORDER BY confidence DESC, analysis_timestamp DESC"
            
            df = pd.read_sql(base_sql, self.conn, params=params)
            df.to_excel(file_path, index=False)
            print(f"分析结果已导出到: {file_path}")
            return True
            
        except Exception as e:
            print(f"导出Excel失败: {e}")
            return False