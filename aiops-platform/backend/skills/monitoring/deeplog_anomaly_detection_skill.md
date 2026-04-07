# DeepLog 日志异常检测技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 技术原理](#2-技术原理)
- [3. 诊断流程](#3-诊断流程)
- [4. 工具调用](#4-工具调用)
- [5. 使用示例](#5-使用示例)
- [6. 权限边界](#6-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `日志异常检测`, `日志异常`, `异常日志`, `anomaly detection`
- `DeepLog`, `LSTM`, `日志序列`, `日志模式`
- `日志预测`, `日志分析`, `log analysis`
- `时间序列`, `time series`, `日志模板`

### 1.2 适用条件
- 微服务日志异常检测
- 日志序列模式识别
- 日志异常预测
- 日志模板提取
- 日志根因分析

### 1.3 核心能力
- ✅ 日志数据生成与模拟
- ✅ 日志模板提取（Drain 算法）
- ✅ DeepLog 模型训练
- ✅ 日志异常检测
- ✅ 异常报告生成

---

## 2. 技术原理

### 2.1 DeepLog 模型

**DeepLog** 是一个基于 LSTM 的日志异常检测模型，通过学习日志序列的正常模式来检测异常。

**核心思想**：
1. 将日志事件序列视为时间序列
2. 使用 LSTM 学习日志事件的正常模式
3. 通过预测下一个事件来检测异常
4. 如果实际事件不在预测的 Top-k 个事件中，则认为是异常

**模型结构**：
```
Input: [EventId_1, EventId_2, ..., EventId_10]
         ↓
    Embedding Layer (128维)
         ↓
    LSTM Layer (2层, 128维隐藏层)
         ↓
    Linear Layer (映射到事件空间)
         ↓
    Softmax (输出概率分布)
         ↓
Output: [P(Event_1), P(Event_2), ..., P(Event_n)]
```

### 2.2 日志解析流程

```
原始日志
    ↓
正则表达式提取 (时间戳、级别、服务名、消息)
    ↓
模板提取 (Drain 算法)
    ↓
EventId 映射
    ↓
结构化日志 (CSV)
```

### 2.3 异常检测流程

```
日志序列 [E1, E2, ..., E10]
    ↓
DeepLog 模型预测
    ↓
Top-k 个最可能的事件
    ↓
实际事件是否在 Top-k 中？
    ├─ 是 → 正常
    └─ 否 → 异常
```

---

## 3. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 日志数据准备                                       │
│  - 收集原始日志                                            │
│  - 或生成模拟日志数据                                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 日志解析                                           │
│  - 使用 Drain 算法提取日志模板                              │
│  - 构建 EventId 映射                                       │
│  - 生成结构化日志                                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 模型训练                                           │
│  - 构建滑动窗口序列                                        │
│  - 训练 DeepLog 模型                                       │
│  - 保存训练好的模型                                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 异常检测                                           │
│  - 加载训练好的模型                                        │
│  - 模拟实时日志流                                          │
│  - 预测并检测异常                                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 生成报告                                           │
│  - 异常统计                                                │
│  - 异常事件分布                                            │
│  - 异常详情                                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 工具调用

### 4.1 日志数据生成

**脚本路径**: `time_sequence_prediction/log_analysis/1_generate_data.py`

**功能**: 生成模拟的微服务日志数据

**参数**:
- `target_lines`: 目标日志行数（默认：5000）
- `anomaly_a_prob`: 异常A概率（高并发时段：0.30，正常时段：0.10）
- `anomaly_b_prob`: 异常B概率（高并发时段：0.20，正常时段：0.05）

**调用方式**:
```python
from pathlib import Path
import subprocess

log_analysis_dir = Path(__file__).parent.parent.parent / "time_sequence_prediction" / "log_analysis"
script_path = log_analysis_dir / "1_generate_data.py"

result = subprocess.run(
    ["python3", str(script_path)],
    cwd=str(log_analysis_dir),
    capture_output=True,
    text=True
)

print(result.stdout)
```

**输出**:
- 文件: `data/raw/logs_raw.log`
- 内容: 约 5000 行模拟日志

### 4.2 日志解析

**脚本路径**: `time_sequence_prediction/log_analysis/2_parse_logs.py`

**功能**: 使用 Drain 算法解析日志

**调用方式**:
```python
script_path = log_analysis_dir / "2_parse_logs.py"

result = subprocess.run(
    ["python3", str(script_path)],
    cwd=str(log_analysis_dir),
    capture_output=True,
    text=True
)

print(result.stdout)
```

**输出**:
- 文件: `data/cleaned/logs_structured.csv`
- 列: LineId, EventId, EventTemplate, Timestamp, Level, Service, Message

### 4.3 模型训练

**脚本路径**: `time_sequence_prediction/log_analysis/3_train_model.py`

**功能**: 训练 DeepLog 模型

**参数**:
- `window_size`: 滑动窗口大小（默认：10）
- `embedding_dim`: Embedding 维度（默认：128）
- `hidden_dim`: LSTM 隐藏层维度（默认：128）
- `num_layers`: LSTM 层数（默认：2）
- `num_epochs`: 训练轮数（默认：10）
- `learning_rate`: 学习率（默认：0.001）

**调用方式**:
```python
script_path = log_analysis_dir / "3_train_model.py"

result = subprocess.run(
    ["python3", str(script_path)],
    cwd=str(log_analysis_dir),
    capture_output=True,
    text=True
)

print(result.stdout)
```

**输出**:
- 文件: `models/deeplog_model.pth`
- 文件: `models/deeplog_model_best.pth`

### 4.4 异常检测

**脚本路径**: `time_sequence_prediction/log_analysis/4_predict.py`

**功能**: 使用训练好的模型进行异常检测

**参数**:
- `top_k`: 预测的 Top-k 个事件（默认：1）
- `test_ratio`: 测试数据比例（默认：0.3）

**调用方式**:
```python
script_path = log_analysis_dir / "4_predict.py"

result = subprocess.run(
    ["python3", str(script_path)],
    cwd=str(log_analysis_dir),
    capture_output=True,
    text=True
)

print(result.stdout)
```

**输出**:
- 文件: `reports/anomaly_detection_results.csv`
- 内容: 异常检测结果

---

## 5. 使用示例

### 5.1 完整流程示例

```python
import subprocess
from pathlib import Path

# 1. 定位日志分析目录
log_analysis_dir = Path("/Users/jaci-j/AIops/time_sequence_prediction/log_analysis")

# 2. 生成日志数据
print("Step 1: 生成日志数据...")
result = subprocess.run(
    ["python3", "1_generate_data.py"],
    cwd=str(log_analysis_dir),
    capture_output=True,
    text=True
)
print(result.stdout)

# 3. 解析日志
print("\nStep 2: 解析日志...")
result = subprocess.run(
    ["python3", "2_parse_logs.py"],
    cwd=str(log_analysis_dir),
    capture_output=True,
    text=True
)
print(result.stdout)

# 4. 训练模型
print("\nStep 3: 训练模型...")
result = subprocess.run(
    ["python3", "3_train_model.py"],
    cwd=str(log_analysis_dir),
    capture_output=True,
    text=True
)
print(result.stdout)

# 5. 异常检测
print("\nStep 4: 异常检测...")
result = subprocess.run(
    ["python3", "4_predict.py"],
    cwd=str(log_analysis_dir),
    capture_output=True,
    text=True
)
print(result.stdout)
```

### 5.2 查看结果

```python
import pandas as pd

# 查看结构化日志
df_logs = pd.read_csv(log_analysis_dir / "data/cleaned/logs_structured.csv")
print("日志模板统计:")
print(df_logs['EventId'].value_counts())

# 查看异常检测结果
df_anomalies = pd.read_csv(log_analysis_dir / "reports/anomaly_detection_results.csv")
print("\n异常检测结果:")
print(f"检测到的异常数: {len(df_anomalies)}")
print(df_anomalies.head())
```

### 5.3 实际应用场景

#### 场景 1: 微服务日志异常检测
```
用户: "帮我检测 order-service 的日志异常"

执行流程:
1. 收集 order-service 的日志
2. 解析日志提取模板
3. 训练 DeepLog 模型
4. 检测异常并生成报告
```

#### 场景 2: 日志模式识别
```
用户: "分析日志中的异常模式"

执行流程:
1. 解析日志提取模板
2. 统计模板分布
3. 识别异常模板
4. 生成分析报告
```

#### 场景 3: 日志预测
```
用户: "预测下一个可能出现的日志事件"

执行流程:
1. 加载训练好的模型
2. 输入当前日志序列
3. 预测下一个事件
4. 返回预测结果
```

---

## 6. 权限边界

### 6.1 安全的只读操作
- 读取日志文件
- 解析日志
- 训练模型
- 异常检测

### 6.2 需要确认的操作
- 生成模拟日志数据
- 保存模型文件
- 保存分析报告

### 6.3 危险操作禁止执行
- 删除日志文件
- 修改原始日志
- 删除模型文件

---

## 7. 性能指标

### 7.1 模型性能
- 训练准确率: ~98%
- 验证准确率: ~98%
- 异常检测率: ~3-5%

### 7.2 资源消耗
- 内存: ~500MB (训练时)
- CPU: 中等
- 磁盘: ~1MB (模型文件)

### 7.3 时间消耗
- 日志生成: ~1秒 (5000行)
- 日志解析: ~2秒
- 模型训练: ~30秒 (10 epochs)
- 异常检测: ~1秒 (1500行)

---

## 8. 故障排查

### 8.1 常见问题

**问题 1: 找不到 logparser 库**
```
解决方案: 使用简单的模板提取方法，不依赖 logparser 库
```

**问题 2: 模型准确率低**
```
解决方案:
1. 增加训练数据量
2. 调整模型参数（层数、隐藏层维度）
3. 增加训练轮数
```

**问题 3: 异常检测率为 0**
```
解决方案:
1. 增加 Top-k 值（如从 1 改为 3）
2. 增加测试数据中的异常比例
3. 检查模型是否过拟合
```

---

## 9. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-07
- 维护者: AIOps Team

### 更新日志

#### v1.0.0 (2025-04-07)
- 初始版本
- 集成 DeepLog 日志异常检测功能
- 支持日志生成、解析、训练、检测完整流程
