#!/usr/bin/env python3
"""
15分钟股票数据拉取工具
从highest_trading_volume表读取股票代码，然后拉取15分钟历史数据
"""

import baostock as bs
import pandas as pd
import sys
import os
import time
import argparse
from datetime import datetime, timedelta

# 添加路径以便导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from core.db_utils import DatabaseUtils

class DataFetcher:
    def __init__(self):
        self.conn, self.cursor = DatabaseUtils.connect_to_mysql()
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
    
    def clear_15min_data_table(self):
        """
        清空stock_15min_history表的所有数据
        """
        try:
            print("正在清空stock_15min_history表...")
            self.cursor.execute("DELETE FROM stock_15min_history")
            self.conn.commit()
            
            # 获取清空后的记录数确认
            self.cursor.execute("SELECT COUNT(*) FROM stock_15min_history")
            count = self.cursor.fetchone()[0]
            
            if count == 0:
                print("✓ 成功清空stock_15min_history表")
                return True
            else:
                print(f"✗ 表清空可能不完整，仍有{count}条记录")
                return False
                
        except Exception as e:
            print(f"✗ 清空表失败: {e}")
            self.conn.rollback()
            return False
    
    def get_stock_list_from_db(self, limit=None):
        """
        从highest_trading_volume表获取股票列表
        """
        try:
            if limit:
                query = "SELECT ts_code FROM highest_trading_volume ORDER BY avg_amount DESC LIMIT %s"
                self.cursor.execute(query, (limit,))
            else:
                query = "SELECT ts_code FROM highest_trading_volume ORDER BY avg_amount DESC"
                self.cursor.execute(query)
            
            results = self.cursor.fetchall()
            return [row[0] for row in results]
        except Exception as e:
            print(f"从数据库获取股票列表失败: {e}")
            return []
    
    def get_stock_list_from_baostock(self, limit=1000):
        """
        从baostock获取股票列表（沪深全部A股）
        """
        try:
            import baostock as bs
            
            print("从baostock获取全部A股列表...")
            
            # 获取全部A股列表
            rs = bs.query_all_stock(day='2025-08-01')  # 使用一个已知日期
            stock_list = []
            
            while (rs.error_code == '0') & rs.next():
                stock_data = rs.get_row_data()
                code = stock_data[0]  # baostock格式：sh.600000, sz.000001
                
                # 转换为tushare格式用于显示
                if code.startswith('sh.'):
                    ts_code = code.replace('sh.', '') + '.SH'
                elif code.startswith('sz.'):
                    ts_code = code.replace('sz.', '') + '.SZ'
                else:
                    continue
                
                stock_list.append(ts_code)
            
            # 限制数量并返回
            if limit and len(stock_list) > limit:
                stock_list = stock_list[:limit]
                
            print(f"获取到 {len(stock_list)} 只股票（上海：{len([s for s in stock_list if s.endswith('.SH')])}，深圳：{len([s for s in stock_list if s.endswith('.SZ')])}）")
            return stock_list
            
        except Exception as e:
            print(f"从baostock获取股票列表失败: {e}")
            return []
    
    def get_stock_list(self, limit=None, use_baostock=False):
        """
        获取股票列表
        """
        if use_baostock:
            return self.get_stock_list_from_baostock(limit)
        else:
            # 先尝试从数据库获取
            db_stocks = self.get_stock_list_from_db(limit)
            if db_stocks:
                return db_stocks
            
            # 如果数据库为空或股票数量不足，从baostock获取
            print("数据库股票数量不足，从baostock获取...")
            return self.get_stock_list_from_baostock(limit)
    
    def convert_tushare_to_baostock_code(self, ts_code):
        """
        将tushare格式股票代码转换为baostock格式
        例: 000001.SZ -> sz.000001, 600000.SH -> sh.600000
        """
        if '.' not in ts_code:
            return ts_code
            
        code, exchange = ts_code.split('.')
        if exchange.upper() == 'SZ':
            return f"sz.{code}"
        elif exchange.upper() == 'SH':
            return f"sh.{code}"
        else:
            return ts_code
    
    def get_15min_stock_data(self, stock_code, start_date, end_date):
        """
        获取15分钟K线数据
        """
        try:
            bs_code = self.convert_tushare_to_baostock_code(stock_code)
            
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,time,code,open,high,low,close,volume,amount",
                start_date=start_date, 
                end_date=end_date,
                frequency="15", 
                adjustflag="3"
            )
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if data_list:
                df = pd.DataFrame(data_list, columns=rs.fields)
                return df
            return pd.DataFrame()
            
        except Exception as e:
            print(f"获取股票 {stock_code} 数据失败: {e}")
            return pd.DataFrame()
    
    def save_to_database(self, df, stock_code):
        """
        将数据保存到数据库
        """
        if df.empty:
            return 0
            
        saved_count = 0
        for index, row in df.iterrows():
            try:
                # 解析时间字符串
                time_str = str(row['time'])[:14]
                if len(time_str) < 14:
                    continue
                    
                year = time_str[:4]
                month = time_str[4:6]
                day = time_str[6:8]
                hour = time_str[8:10]
                minute = time_str[10:12]
                second = time_str[12:14]
                
                datetime_str = f"{year}-{month}-{day} {hour}:{minute}:{second}"
                timestamp = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
                
                self.cursor.execute('''
                    INSERT IGNORE INTO stock_15min_history 
                    (ts_code, timestamp, open, high, low, close, volume, amount)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    stock_code, timestamp, 
                    float(row['open']) if row['open'] else 0,
                    float(row['high']) if row['high'] else 0,
                    float(row['low']) if row['low'] else 0,
                    float(row['close']) if row['close'] else 0,
                    int(row['volume']) if row['volume'] else 0,
                    float(row['amount']) if row['amount'] else 0
                ))
                saved_count += 1
                
            except Exception as e:
                print(f"保存数据行失败: {e}")
                continue
        
        self.conn.commit()
        return saved_count
    
    def fetch_data_batch(self, stock_list, start_date, end_date, batch_size=10):
        """
        批量获取股票数据
        """
        total_processed = 0
        total_saved = 0
        total_stocks = len(stock_list)
        start_time = datetime.now()
        
        for i in range(0, len(stock_list), batch_size):
            batch_stocks = stock_list[i:i + batch_size]
            batch_num = i//batch_size + 1
            total_batches = (len(stock_list)-1)//batch_size + 1
            
            print(f"📦 批次 {batch_num}/{total_batches} ({len(batch_stocks)}只股票)")
            print("-" * 40)
            
            for stock_code in batch_stocks:
                # 转换股票代码格式用于baostock查询
                bs_code = self.convert_tushare_to_baostock_code(stock_code)
                
                print(f"  📈 {stock_code} ({bs_code}) ... ", end="")
                
                # 获取数据
                df = self.get_15min_stock_data(stock_code, start_date, end_date)
                
                if not df.empty:
                    # 保存到数据库
                    saved_count = self.save_to_database(df, stock_code)
                    total_saved += saved_count
                    print(f"✓ 保存{saved_count}条")
                else:
                    print("❌ 无数据")
                
                total_processed += 1
                
                # 显示总体进度
                progress = (total_processed / total_stocks) * 100
                elapsed = (datetime.now() - start_time).total_seconds()
                if total_processed > 0:
                    avg_time_per_stock = elapsed / total_processed
                    estimated_total = avg_time_per_stock * total_stocks
                    remaining = estimated_total - elapsed
                    print(f"    进度: {total_processed}/{total_stocks} ({progress:.1f}%) "
                          f"预计剩余: {remaining/60:.1f}分钟")
                
                # 避免请求过于频繁
                # time.sleep(0.2)
            
            # 批次间休息
            if i + batch_size < len(stock_list):
                print(f"  ⏸️  批次间休息2秒...")
                # time.sleep(2)
            
            print()
        
        # 最终统计
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("=" * 60)
        print("🎉 数据拉取完成！")
        print("=" * 60)
        print(f"📊 处理股票数: {total_processed}")
        print(f"💾 保存记录数: {total_saved:,}")
        print(f"⏱️  总耗时: {duration/60:.1f} 分钟")
        if total_processed > 0:
            print(f"⚡ 平均每只股票: {duration/total_processed:.1f} 秒")
        print(f"📅 数据时间范围: {start_date} ~ {end_date}")
        
        # 验证数据保存
        try:
            self.cursor.execute("SELECT COUNT(*) FROM stock_15min_history")
            final_count = self.cursor.fetchone()[0]
            print(f"📋 数据库总记录数: {final_count:,}")
        except Exception as e:
            print(f"⚠️  无法验证最终记录数: {e}")

def main():
    parser = argparse.ArgumentParser(description='拉取股票15分钟历史数据')
    parser.add_argument('--start-date', type=str, default='2025-07-01',
                       help='开始日期 (YYYY-MM-DD)，默认2025-07-01')
    parser.add_argument('--end-date', type=str, default='2025-08-31',
                       help='结束日期 (YYYY-MM-DD)，默认2025-08-31')
    parser.add_argument('--limit', type=int, default=1000,
                       help='拉取股票数量限制，默认1000')
    parser.add_argument('--batch-size', type=int, default=10,
                       help='批次大小，默认10')
    parser.add_argument('--clear-table', action='store_true',
                       help='拉取前清空stock_15min_history表')
    parser.add_argument('--skip-clear', action='store_true',
                       help='跳过清空表（默认会清空）')
    
    args = parser.parse_args()
    
    # 验证日期格式
    try:
        datetime.strptime(args.start_date, '%Y-%m-%d')
        datetime.strptime(args.end_date, '%Y-%m-%d')
    except ValueError:
        print("日期格式错误，请使用 YYYY-MM-DD 格式")
        return
    
    # 登录baostock
    try:
        lg = bs.login()
        if lg.error_code != '0':
            print(f"baostock登录失败: {lg.error_msg}")
            return
    except Exception as e:
        print(f"baostock登录异常: {e}")
        return
    
    try:
        with DataFetcher() as fetcher:
            # 清空表（默认行为，除非用户指定跳过）
            if not args.skip_clear:
                print("=" * 60)
                print("🗑️  准备清空现有数据")
                print("=" * 60)
                
                if not fetcher.clear_15min_data_table():
                    print("⚠️  表清空失败，是否继续？(y/N): ", end="")
                    response = input().strip().lower()
                    if response != 'y':
                        print("❌ 用户取消操作")
                        return
                
                print()
            
            # 获取股票列表
            print("=" * 60) 
            print("📊 获取股票列表")
            print("=" * 60)
            
            stock_list = fetcher.get_stock_list(args.limit)
            
            if not stock_list:
                print("❌ 未获取到股票列表")
                return
            
            print(f"✓ 获取到 {len(stock_list)} 只股票")
            print(f"📅 数据时间范围: {args.start_date} 到 {args.end_date}")
            print(f"📦 批次大小: {args.batch_size}")
            print()
            
            # 确认开始拉取
            print("准备开始数据拉取，预计需要较长时间...")
            print("按 Ctrl+C 可随时中断")
            print()
            time.sleep(2)
            
            # 批量拉取数据
            print("=" * 60)
            print("📥 开始拉取数据")
            print("=" * 60)
            
            fetcher.fetch_data_batch(
                stock_list, 
                args.start_date, 
                args.end_date, 
                args.batch_size
            )
            
    except Exception as e:
        print(f"执行过程中发生错误: {e}")
    finally:
        bs.logout()

if __name__ == "__main__":
    main()