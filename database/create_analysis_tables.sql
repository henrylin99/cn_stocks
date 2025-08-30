-- 股票分析结果数据表
-- 存储策略分析的结果

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
  
  -- 索引
  INDEX `idx_ts_code_strategy` (`ts_code`, `strategy_name`),
  INDEX `idx_analysis_timestamp` (`analysis_timestamp`),
  INDEX `idx_signal` (`signal`),
  INDEX `idx_created_at` (`created_at`),
  
  -- 复合索引用于查询优化
  INDEX `idx_ts_code_timestamp` (`ts_code`, `analysis_timestamp`),
  INDEX `idx_strategy_signal_timestamp` (`strategy_name`, `signal`, `analysis_timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股票分析结果主表';

-- 2. 分析原因表
CREATE TABLE IF NOT EXISTS `stock_analysis_reasons` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
  `analysis_id` BIGINT NOT NULL COMMENT '分析结果ID',
  `reason_text` TEXT NOT NULL COMMENT '原因描述',
  `reason_order` TINYINT NOT NULL DEFAULT 1 COMMENT '原因排序',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  
  -- 外键约束
  FOREIGN KEY (`analysis_id`) REFERENCES `stock_analysis_results`(`id`) ON DELETE CASCADE,
  
  -- 索引
  INDEX `idx_analysis_id` (`analysis_id`),
  INDEX `idx_analysis_id_order` (`analysis_id`, `reason_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股票分析原因表';

-- 3. 技术指标值表
CREATE TABLE IF NOT EXISTS `stock_analysis_indicators` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
  `analysis_id` BIGINT NOT NULL COMMENT '分析结果ID',
  `indicator_name` VARCHAR(50) NOT NULL COMMENT '指标名称',
  `indicator_value` DECIMAL(20,8) DEFAULT NULL COMMENT '指标数值',
  `indicator_text` VARCHAR(255) DEFAULT NULL COMMENT '指标文本值',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  
  -- 外键约束
  FOREIGN KEY (`analysis_id`) REFERENCES `stock_analysis_results`(`id`) ON DELETE CASCADE,
  
  -- 索引
  INDEX `idx_analysis_id` (`analysis_id`),
  INDEX `idx_indicator_name` (`indicator_name`),
  UNIQUE KEY `uk_analysis_indicator` (`analysis_id`, `indicator_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='股票分析技术指标表';

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
  
  -- 索引
  INDEX `idx_start_time` (`start_time`),
  INDEX `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='分析任务批次表';

-- 5. 批次结果关联表
CREATE TABLE IF NOT EXISTS `batch_analysis_results` (
  `batch_id` BIGINT NOT NULL COMMENT '批次ID',
  `analysis_id` BIGINT NOT NULL COMMENT '分析结果ID',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  
  -- 外键约束
  FOREIGN KEY (`batch_id`) REFERENCES `analysis_batches`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`analysis_id`) REFERENCES `stock_analysis_results`(`id`) ON DELETE CASCADE,
  
  -- 主键
  PRIMARY KEY (`batch_id`, `analysis_id`),
  
  -- 索引
  INDEX `idx_batch_id` (`batch_id`),
  INDEX `idx_analysis_id` (`analysis_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='批次分析结果关联表';

-- 6. 分析结果汇总视图
CREATE OR REPLACE VIEW `v_analysis_summary` AS
SELECT 
    sar.ts_code,
    sar.strategy_name,
    sar.signal,
    sar.confidence,
    sar.analysis_timestamp,
    sar.data_points,
    GROUP_CONCAT(saar.reason_text ORDER BY saar.reason_order SEPARATOR ' | ') as reasons,
    sar.created_at
FROM stock_analysis_results sar
LEFT JOIN stock_analysis_reasons saar ON sar.id = saar.analysis_id
GROUP BY sar.id, sar.ts_code, sar.strategy_name, sar.signal, sar.confidence, 
         sar.analysis_timestamp, sar.data_points, sar.created_at;

-- 7. 每日分析汇总视图  
CREATE OR REPLACE VIEW `v_daily_analysis_summary` AS
SELECT 
    DATE(analysis_timestamp) as analysis_date,
    strategy_name,
    `signal`,
    COUNT(*) as count,
    AVG(confidence) as avg_confidence,
    MIN(confidence) as min_confidence,
    MAX(confidence) as max_confidence
FROM stock_analysis_results 
GROUP BY DATE(analysis_timestamp), strategy_name, `signal`
ORDER BY analysis_date DESC, strategy_name, `signal`;

-- 8. 股票历史分析视图
CREATE OR REPLACE VIEW `v_stock_history_analysis` AS
SELECT 
    ts_code,
    strategy_name,
    `signal`,
    confidence,
    analysis_timestamp,
    LAG(`signal`) OVER (PARTITION BY ts_code, strategy_name ORDER BY analysis_timestamp) as prev_signal,
    LAG(confidence) OVER (PARTITION BY ts_code, strategy_name ORDER BY analysis_timestamp) as prev_confidence,
    CASE 
        WHEN `signal` != LAG(`signal`) OVER (PARTITION BY ts_code, strategy_name ORDER BY analysis_timestamp) 
        THEN 1 ELSE 0 
    END as signal_changed
FROM stock_analysis_results
ORDER BY ts_code, strategy_name, analysis_timestamp DESC;

-- 清理旧数据的存储过程
DELIMITER //
CREATE PROCEDURE CleanOldAnalysisData(IN days_to_keep INT)
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE batch_id BIGINT;
    DECLARE cur CURSOR FOR 
        SELECT id FROM analysis_batches 
        WHERE start_time < DATE_SUB(NOW(), INTERVAL days_to_keep DAY);
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;
    
    -- 删除旧的分析结果
    DELETE FROM stock_analysis_results 
    WHERE analysis_timestamp < DATE_SUB(NOW(), INTERVAL days_to_keep DAY);
    
    -- 删除旧的批次记录
    OPEN cur;
    read_loop: LOOP
        FETCH cur INTO batch_id;
        IF done THEN
            LEAVE read_loop;
        END IF;
        DELETE FROM analysis_batches WHERE id = batch_id;
    END LOOP;
    CLOSE cur;
    
    -- 优化表
    OPTIMIZE TABLE stock_analysis_results;
    OPTIMIZE TABLE stock_analysis_reasons;
    OPTIMIZE TABLE stock_analysis_indicators;
    OPTIMIZE TABLE analysis_batches;
    
END //
DELIMITER ;

-- 创建定期清理事件 (可选，需要开启事件调度器)
-- CREATE EVENT IF NOT EXISTS clean_old_analysis_data
-- ON SCHEDULE EVERY 1 DAY
-- STARTS TIMESTAMP(CURRENT_DATE + INTERVAL 1 DAY, '02:00:00')
-- DO CALL CleanOldAnalysisData(30);