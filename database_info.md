## mysql config
```
host: localhost
port: 3306
user: root
password: root
database_name: stock_cursor 
```

### 15分钟行情表
```
CREATE TABLE `stock_15min_history` (
  `ts_code` varchar(20) NOT NULL COMMENT '股票代码',
  `timestamp` datetime NOT NULL COMMENT '交易时间',
  `open` decimal(10,4) DEFAULT NULL COMMENT '开盘价',
  `high` decimal(10,4) DEFAULT NULL COMMENT '最高价',
  `low` decimal(10,4) DEFAULT NULL COMMENT '最低价',
  `close` decimal(10,4) DEFAULT NULL COMMENT '收盘价',
  `volume` bigint DEFAULT NULL COMMENT '成交量 （手）',
  `amount` decimal(20,4) DEFAULT NULL COMMENT '成交额 （千元）'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='15分钟行情表';
```

### 历史数据日线表
```
CREATE TABLE `stock_daily_history` (
  `ts_code` varchar(20) NOT NULL COMMENT '股票代码',
  `trade_date` date NOT NULL COMMENT '交易日期',
  `open` decimal(10,2) DEFAULT NULL COMMENT '开盘价',
  `high` decimal(10,2) DEFAULT NULL COMMENT '最高价',
  `low` decimal(10,2) DEFAULT NULL COMMENT '最低价',
  `close` decimal(10,2) DEFAULT NULL COMMENT '收盘价',
  `pre_close` decimal(10,2) DEFAULT NULL COMMENT '昨收价【除权价，前复权】',
  `change_c` decimal(10,2) DEFAULT NULL COMMENT '涨跌额',
  `pct_chg` decimal(10,2) DEFAULT NULL COMMENT '涨跌幅 【基于除权后的昨收计算的涨跌幅：（今收-除权昨收）/除权昨收】',
  `vol` bigint DEFAULT NULL COMMENT '成交量 （手）',
  `amount` decimal(20,2) DEFAULT NULL COMMENT '成交额 （千元）',
  PRIMARY KEY (`ts_code`,`trade_date`),
  KEY `code_index` (`ts_code`),
  KEY `idx_stock_daily_history_ts_code_trade_date_close_low` (`ts_code`,`trade_date`,`close`,`low`),
  KEY `idx_stock_daily_history_trade_date_ts_code` (`trade_date`,`ts_code`),
  KEY `idx_stock_daily_history_trade_date_ts_code_close_high` (`trade_date`,`ts_code`,`close`,`high`),
  KEY `idx_stock_daily_history_trade_date_ts_code_close_low` (`trade_date`,`ts_code`,`close`,`low`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股票日线行情历史数据表';
```

### 最近成交量最高的1000只股票
```
CREATE TABLE `highest_trading_volume` (
  `ts_code` varchar(20) NOT NULL COMMENT '股票代码',
  `avg_amount` decimal(23,0) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='最近成交量最高的1000只股票';
```

