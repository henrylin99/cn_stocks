import baostock as bs
import pandas as pd
from utils.db_utils import DatabaseUtils
import time
from datetime import datetime

# 连接到MySQL数据库
conn, cursor = DatabaseUtils.connect_to_mysql()

# 创建表结构
cursor.execute('''
    CREATE TABLE IF NOT EXISTS `stock_15min_history` (
      `ts_code` varchar(20) NOT NULL COMMENT '股票代码',
      `timestamp` datetime NOT NULL COMMENT '交易时间',
      `open` decimal(10,4) DEFAULT NULL COMMENT '开盘价',
      `high` decimal(10,4) DEFAULT NULL COMMENT '最高价',
      `low` decimal(10,4) DEFAULT NULL COMMENT '最低价',
      `close` decimal(10,4) DEFAULT NULL COMMENT '收盘价',
      `volume` bigint DEFAULT NULL COMMENT '成交量 （手）',
      `amount` decimal(20,4) DEFAULT NULL COMMENT '成交额 （千元）',
      PRIMARY KEY (`ts_code`,`timestamp`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股票60分钟线行情数据表';
''')

def get_15min_stock_data_bs(stock_code, start_date, end_date):
    """
    使用Baostock获取股票15分钟线数据
    :param stock_code: 股票代码，如 'sh.600519'
    :param start_date: 开始日期，格式 'YYYY-MM-DD'
    :param end_date: 结束日期，格式 'YYYY-MM-DD'
    :return: DataFrame包含60分钟线数据
    """
    # 获取60分钟线数据
    rs = bs.query_history_k_data_plus(stock_code,
                                      "date,time,code,open,high,low,close,volume,amount",
                                      start_date=start_date, end_date=end_date,
                                      frequency="15", adjustflag="3")

    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())

    df = pd.DataFrame(data_list, columns=rs.fields)
    return df


def main():
    try:
        # 获取沪深300股票列表
        lg = bs.login()

        rs = bs.query_hs300_stocks()
        hs300_stocks = []
        while (rs.error_code == '0') & rs.next():
            hs300_stocks.append(rs.get_row_data())
        result = pd.DataFrame(hs300_stocks, columns=rs.fields)

        batch_size = 10
        data_list = []

        for i in range(0, len(result), batch_size):
            batch_stock_list = result.iloc[i:i + batch_size]
            for index, stock in batch_stock_list.iterrows():
                bs_code = stock['code']  # 直接使用返回的code，格式已经是sh.600000
                
                # 获取60分钟数据
                print(bs_code)
                df = get_15min_stock_data_bs(bs_code, '2025-06-28', '2025-08-31')
                if df is not None and not df.empty:
                    data_list.append(df)

            # 合并当前批次的数据
            if data_list:
                combined_data = pd.concat(data_list, ignore_index=True)
                # time.sleep(0.05)  # 避免请求过于频繁

                # 插入数据
                for index, row in combined_data.iterrows():
                    try:
                        # 将时间字符串转换为datetime对象
                        time_str = row['time'][:14]  # 取YYYYMMDDHHMMSS部分
                        
                        # 检查时间字符串格式并打印
                        # print(f"Processing time string: {time_str}")
                        
                        # 解析完整的日期时间字符串
                        year = time_str[:4]
                        month = time_str[4:6]
                        day = time_str[6:8]
                        hour = time_str[8:10]
                        minute = time_str[10:12]
                        second = time_str[12:14]
                        
                        # 构建datetime字符串
                        datetime_str = f"{year}-{month}-{day} {hour}:{minute}:{second}"
                        timestamp = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
                        # print(f"Generated datetime: {timestamp}")
                        
                        cursor.execute('''
                        INSERT IGNORE INTO stock_15min_history (ts_code, timestamp, open, high, low, close, volume, amount)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                        ''', (row['code'], timestamp, row['open'], row['high'], row['low'], 
                              row['close'], row['volume'], row['amount']))
                        
                    except Exception as e:
                        print(f"Error processing row: {row}")
                        print(f"Error details: {e}")
                        continue

                # 提交事务
                conn.commit()

                # 清空当前批次的数据列表，为下一个批次做准备
                data_list.clear()

    except Exception as e:
        print(f"程序执行出错: {e}")
        print("Error details:", e.args)  # 打印更详细的错误信息
    finally:
        # 关闭数据库连接
        cursor.close()
        conn.close()
        bs.logout()

if __name__ == "__main__":
    main()
