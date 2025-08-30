-- 简化版数据库表创建脚本

-- 1. 分析结果主表
CREATE TABLE IF NOT EXISTS `stock_analysis_results` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
  `ts_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
  `strategy_name` VARCHAR(100) NOT NULL COMMENT '策略名称',
  `signal` ENUM('买入', '卖出', '观望') NOT NULL COMMENT '交易信号',
  `confidence` DECIMAL(5,4) NOT NULL DEFAULT 0.0000 COMMENT '信号置信度(0-1)',
  `analysis_timestamp` DATETIME NOT NULL COMMENT '分析时间',
  `data_start_time` DATETIME DEFAULT NULL COMMENT '数据开始时间',
  `data_end_time` DATETIME DEFAULT NULL COMMENT '数据结束时间',
  `data_points` INT DEFAULT 0 COMMENT '分析数据点数',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  
  INDEX `idx_ts_code_strategy` (`ts_code`, `strategy_name`),
  INDEX `idx_analysis_timestamp` (`analysis_timestamp`),
  INDEX `idx_signal` (`signal`),
  INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票分析结果主表';

-- 2. 分析原因表
CREATE TABLE IF NOT EXISTS `stock_analysis_reasons` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
  `analysis_id` BIGINT NOT NULL COMMENT '分析结果ID',
  `reason_text` TEXT NOT NULL COMMENT '原因描述',
  `reason_order` TINYINT NOT NULL DEFAULT 1 COMMENT '原因排序',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  
  INDEX `idx_analysis_id` (`analysis_id`),
  INDEX `idx_analysis_id_order` (`analysis_id`, `reason_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票分析原因表';

-- 3. 技术指标值表
CREATE TABLE IF NOT EXISTS `stock_analysis_indicators` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
  `analysis_id` BIGINT NOT NULL COMMENT '分析结果ID',
  `indicator_name` VARCHAR(50) NOT NULL COMMENT '指标名称',
  `indicator_value` DECIMAL(20,8) DEFAULT NULL COMMENT '指标数值',
  `indicator_text` VARCHAR(255) DEFAULT NULL COMMENT '指标文本值',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  
  INDEX `idx_analysis_id` (`analysis_id`),
  INDEX `idx_indicator_name` (`indicator_name`),
  UNIQUE KEY `uk_analysis_indicator` (`analysis_id`, `indicator_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票分析技术指标表';

-- 4. 分析任务批次表
CREATE TABLE IF NOT EXISTS `analysis_batches` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
  `batch_name` VARCHAR(100) DEFAULT NULL COMMENT '批次名称',
  `strategy_names` TEXT NOT NULL COMMENT '使用的策略列表(JSON)',
  `total_stocks` INT NOT NULL DEFAULT 0 COMMENT '总股票数',
  `successful_count` INT NOT NULL DEFAULT 0 COMMENT '成功分析数',
  `failed_count` INT NOT NULL DEFAULT 0 COMMENT '失败分析数',
  `start_time` DATETIME NOT NULL COMMENT '开始时间',
  `end_time` DATETIME DEFAULT NULL COMMENT '结束时间',
  `duration_seconds` DECIMAL(10,2) DEFAULT NULL COMMENT '耗时(秒)',
  `status` ENUM('running', 'completed', 'failed') DEFAULT 'running' COMMENT '状态',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  
  INDEX `idx_start_time` (`start_time`),
  INDEX `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='分析任务批次表';

-- 5. 批次结果关联表
CREATE TABLE IF NOT EXISTS `batch_analysis_results` (
  `batch_id` BIGINT NOT NULL COMMENT '批次ID',
  `analysis_id` BIGINT NOT NULL COMMENT '分析结果ID',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  
  PRIMARY KEY (`batch_id`, `analysis_id`),
  INDEX `idx_batch_id` (`batch_id`),
  INDEX `idx_analysis_id` (`analysis_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='批次分析结果关联表';