# 中国股票分析系统

基于多策略技术指标的股票分析系统，支持6种策略综合分析、批量处理、结果可视化和数据持久化。

## 功能特性

- 🔍 **多策略综合分析**: 支持6种技术分析策略的综合分析和投票推荐
- 📊 **批量处理**: 支持1000只股票的并行批量分析
- 💾 **数据持久化**: 分析结果自动保存到MySQL数据库
- 📈 **可视化图表**: 交互式K线图表，显示买卖信号和技术指标
- 🖥️ **命令行接口**: 完整的CLI工具，支持各种操作
- 📤 **结果导出**: 支持Excel格式数据导出
- 🎯 **智能推荐**: 基于多策略投票的综合推荐系统
- 🌐 **Web界面**: 直观的网页dashboard展示批量分析结果

## 支持的策略

系统目前支持6种主流技术分析策略：

1. **ADXTrendStrategy** - ADX趋势强度策略
2. **MACDStrategy** - MACD金叉死叉策略
3. **RSIStrategy** - RSI超买超卖策略
4. **BollingerStrategy** - 布林带均值回归策略
5. **MACrossoverStrategy** - 移动平均线交叉策略
6. **KDJStrategy** - KDJ随机指标策略

## 系统架构

```
cn_stocks/
├── analyzer/           # 分析器模块
├── database/          # 数据库操作
├── engine/            # 批量分析引擎
├── strategy/          # 策略模块 (6种策略)
├── tools/            # 数据拉取工具
├── visualization/    # 图表可视化
├── web/              # Web界面
│   ├── templates/    # HTML模板
│   └── static/       # 静态文件
├── main.py           # 主程序入口
├── web_app.py        # Web服务入口
└── requirements.txt  # 依赖包
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置数据库

修改 `core/db_utils.py` 中的数据库连接信息：

```python
_host = 'localhost'
_user = 'root'
_password = 'root'
_database = 'stock_cursor'
```

### 3. 初始化数据库

```bash
python main.py init-db
```

### 4. 拉取股票数据

```bash
python tools/fetch_15min_data.py --start-date 2025-07-01 --end-date 2025-08-31 --limit 100
```

## 使用示例

### 查看可用功能

```bash
# 查看所有可用策略
python main.py list-strategies

# 查看前20只可用股票
python main.py list-stocks --limit 20
```

### 单股票多策略综合分析（推荐）

```bash
# 使用所有6种策略进行综合分析
python main.py analyze --stock-code 300024.SZ --show-chart

# 输出示例：
# === 综合分析结果 ===
# 策略投票结果：
# 买入: 1 票, 卖出: 1 票, 观望: 4 票
# 
# 综合推荐: 倾向观望 - 4/6策略支持(平均置信度50.0%)
# 一致性: 66.7%
#
# 各策略详细结果：
# 📉 ADXTrendStrategy - 卖出 (100.0%) - ADX弱化
# 📈 MACDStrategy - 买入 (60.0%) - MACD在信号线上方
# ...
```

### 单策略分析

```bash
# 使用单个策略分析
python main.py analyze --stock-code 300024.SZ --strategy MACDStrategy --show-chart
```

### 批量多策略综合分析（推荐）

```bash
# 批量分析100只股票，使用所有策略
python main.py batch --limit 100 --show-top-signals --save-db

# 输出示例：
# --- 策略汇总 ---
# ADXTrendStrategy: 成功: 95/100, 信号分布: 买入 20, 卖出 35, 观望 40
# MACDStrategy: 成功: 98/100, 信号分布: 买入 25, 卖出 18, 观望 55
# ...
#
# --- 多策略综合推荐 (前10只) ---
# 1. 📈 300059.SZ - 买入
#    一致性: 83.3% (5买/0卖/1观望)
#    推荐: 强烈买入 - 5/6策略一致(平均置信度85.2%)
```

### 单策略批量分析

```bash
# 批量分析，使用指定策略
python main.py batch --limit 100 --strategies ADXTrendStrategy MACDStrategy --save-db

# 使用单个策略
python main.py batch --limit 100 --strategies MACDStrategy --show-top-signals
```

### 查询分析结果

```bash
# 查询买入信号
python main.py query --signal 买入 --limit 20

# 查询单只股票历史
python main.py query --stock-code 300024.SZ --strategy ADXTrendStrategy

# 查看信号统计
python main.py query --days 7
```

### 数据导出和清理

```bash
# 导出最近7天的分析数据
python main.py export --output-file results.xlsx --days 7

# 清理30天前的旧数据
python main.py clean --days-to-keep 30
```

### Web界面使用

```bash
# 启动Web服务
python web_app.py

# 浏览器访问: http://localhost:5002
```

**Web界面功能**:
- 📊 **批量分析历史**: 查看所有历史批量分析记录
- 🚀 **在线分析**: 直接在网页上启动新的批量分析
- 📈 **交互图表**: 点击查看每只股票的详细技术分析图表
- 📋 **策略对比**: 对比不同策略的分析结果和一致性
- 🔍 **信号筛选**: 按买入/卖出/观望信号筛选股票
- 📱 **响应式设计**: 支持PC和移动端访问

## 策略详细说明

### 1. ADX趋势强度策略
- **特点**: 识别和跟随强趋势
- **买入**: ADX > 30且上升，DI+ > DI-，结合多指标确认
- **卖出**: ADX下降或DI-转强，趋势反转
- **适用**: 趋势明确的市场

### 2. MACD金叉死叉策略
- **特点**: 基于MACD指标的经典信号
- **买入**: MACD线上穿信号线（金叉）
- **卖出**: MACD线下穿信号线（死叉）
- **适用**: 中长期趋势判断

### 3. RSI超买超卖策略
- **特点**: 识别超买超卖区域的反转机会
- **买入**: RSI < 30（超卖）且开始回升
- **卖出**: RSI > 70（超买）且开始回落
- **适用**: 震荡市场

### 4. 布林带均值回归策略
- **特点**: 基于价格回归中轴的特性
- **买入**: 价格触及下轨，RSI确认超卖
- **卖出**: 价格触及上轨，RSI确认超买
- **适用**: 震荡市场

### 5. 移动平均线交叉策略
- **特点**: 基于快慢均线交叉的趋势跟随
- **买入**: 快线上穿慢线（金叉）
- **卖出**: 快线下穿慢线（死叉）
- **适用**: 趋势市场

### 6. KDJ随机指标策略
- **特点**: 结合超买超卖和交叉信号
- **买入**: K线上穿D线且在超卖区
- **卖出**: K线下穿D线且在超买区
- **适用**: 短期波段操作

## 多策略综合分析优势

1. **降低误判**: 6种策略互相验证，减少单一策略的局限性
2. **提高准确性**: 通过投票机制提供更可靠的信号
3. **一致性评估**: 显示策略间的一致性程度
4. **智能推荐**: 根据一致性和置信度提供分级推荐
5. **风险控制**: 分歧较大时建议观望，避免高风险操作

## 数据库结构

系统使用MySQL存储分析结果：

- `stock_analysis_results`: 分析结果主表
- `stock_analysis_reasons`: 分析原因详情  
- `stock_analysis_indicators`: 技术指标数值
- `analysis_batches`: 批量分析记录
- `batch_analysis_results`: 批次关联表
- `stock_15min_history`: 15分钟K线数据
- `highest_trading_volume`: 高成交量股票列表

## 扩展开发

### 添加新策略

1. 继承 `BaseStrategy` 类
2. 实现必要的方法
3. 使用 `@StrategyFactory.register_strategy` 装饰器注册

```python
@StrategyFactory.register_strategy
class MyCustomStrategy(BaseStrategy):
    def get_strategy_name(self) -> str:
        return "我的自定义策略"
    
    def get_strategy_description(self) -> str:
        return "策略描述"
    
    def calculate_indicators(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        # 计算技术指标
        return dataframe
    
    def generate_signal(self, dataframe: pd.DataFrame) -> AnalysisResult:
        # 生成交易信号
        return AnalysisResult(
            signal=Signal.BUY,  # or SELL, HOLD
            confidence=0.8,
            reasons=["信号原因1", "信号原因2"],
            indicators={"指标1": 值1, "指标2": 值2},
            timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        )
```

### 自定义可视化

```python
from visualization import ChartPlotter

plotter = ChartPlotter()
fig = plotter.create_stock_analysis_chart(
    ts_code='300024.SZ',
    strategy_names=['ADXTrendStrategy', 'MACDStrategy'],
    days=30
)

# 在浏览器中显示
from visualization import show_chart_in_browser
show_chart_in_browser(fig)
```

## 性能优化

- **并行处理**: 批量分析支持多线程并行
- **数据库索引**: 关键字段已创建适当索引  
- **内存管理**: 大批量处理时采用分批加载
- **策略复用**: 同一股票的数据在多策略间复用

## 注意事项

1. **数据同步**: 确保 `highest_trading_volume` 和 `stock_15min_history` 表的股票代码一致
2. **数据质量**: 确保15分钟K线数据的完整性和准确性
3. **策略风险**: 技术分析策略仅供参考，不构成投资建议
4. **系统资源**: 大批量分析时注意CPU和内存使用
5. **数据库维护**: 定期清理旧数据避免表过大

## 故障排除

### 常见问题

1. **股票代码不存在**:
   ```bash
   # 先查看可用股票
   python main.py list-stocks --limit 20
   # 使用显示的股票代码进行分析
   ```

2. **数据不同步**:
   ```bash
   # 重新拉取数据，确保不跳过记录
   python tools/fetch_15min_data.py --clear-table --limit 100
   ```

3. **策略分析失败**:
   - 检查股票是否有足够的历史数据（至少50个数据点）
   - 确认技术指标计算依赖包已正确安装

## 依赖说明

- **pandas/numpy**: 数据处理核心
- **pymysql**: MySQL数据库连接
- **baostock**: 股票数据获取
- **talib**: 技术指标计算
- **plotly**: 交互式图表
- **openpyxl**: Excel文件导出

## 开发路线

- [x] 6种主流技术分析策略
- [x] 多策略综合分析系统
- [x] 智能投票推荐机制
- [ ] 策略权重调整功能
- [ ] 实现策略回测功能
- [x] 开发Web管理界面
- [ ] 增加实时数据支持
- [ ] 集成机器学习模型
- [ ] 添加风险管理模块

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request来改进项目。

## 联系方式

如有问题或建议，请通过Issue联系。