# 时间序列根因分析技能

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
- `根因分析`, `RCA`, `root cause analysis`, `故障定位`
- `时间序列`, `time series`, `预测`, `prediction`
- `异常检测`, `anomaly detection`, `故障预测`
- `指标分析`, `metrics analysis`, `性能分析`
- `趋势分析`, `trend analysis`, `容量规划`

### 1.2 适用条件
- 系统指标异常检测
- 性能瓶颈分析
- 容量规划预测
- 趋势分析
- 异常根因定位

### 1.3 核心能力
- ✅ 时间序列数据生成
- ✅ 数据清洗与预处理
- ✅ Prophet 时间序列预测
- ✅ 异常检测与根因分析
- ✅ 可视化报告生成

---

## 2. 技术原理

### 2.1 时间序列预测

**Prophet** 是 Facebook 开发的时间序列预测工具，适用于：
- 具有趋势和季节性的数据
- 有多个季节性的数据
- 有重要节假日效应的数据
- 缺失数据和异常值

**核心组件**：
```
y(t) = g(t) + s(t) + h(t) + εt

其中:
- g(t): 趋势项（增长或下降）
- s(t): 季节性项（周期性变化）
- h(t): 节假日效应
- εt: 误差项
```

### 2.2 异常检测原理

**基于预测的异常检测**：
1. 使用历史数据训练 Prophet 模型
2. 预测未来的正常范围
3. 如果实际值超出预测范围，则认为是异常
4. 分析异常点，定位根因

**异常判定标准**：
```
实际值 > 预测上限 或 实际值 < 预测下限
    ↓
异常点
    ↓
分析异常特征
    ↓
定位根因
```

### 2.3 根因分析流程

```
时间序列数据
    ↓
数据清洗与预处理
    ↓
Prophet 模型训练
    ↓
预测正常范围
    ↓
检测异常点
    ↓
分析异常特征
    ↓
定位根因
    ↓
生成报告
```

---

## 3. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 数据收集                                           │
│  - 收集时间序列数据                                        │
│  - 或生成模拟数据                                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 数据清洗                                           │
│  - 处理缺失值                                              │
│  - 处理异常值                                              │
│  - 数据标准化                                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 模型训练                                           │
│  - 使用 Prophet 训练时间序列模型                            │
│  - 调整模型参数                                            │
│  - 保存训练好的模型                                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 异常检测                                           │
│  - 预测未来值                                              │
│  - 检测异常点                                              │
│  - 分析异常特征                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 根因分析                                           │
│  - 分析异常原因                                            │
│  - 定位根因                                                │
│  - 生成分析报告                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 工具调用

### 4.1 数据生成

**脚本路径**: `time_sequence_prediction/data_generator.py`

**功能**: 生成模拟的时间序列数据

**参数**:
- `num_samples`: 样本数量
- `num_features`: 特征数量
- `anomaly_ratio`: 异常比例

**调用方式**:
```python
from pathlib import Path
import subprocess

ts_pred_dir = Path(__file__).parent.parent.parent / "time_sequence_prediction"
script_path = ts_pred_dir / "data_generator.py"

result = subprocess.run(
    ["python3", str(script_path)],
    cwd=str(ts_pred_dir),
    capture_output=True,
    text=True
)

print(result.stdout)
```

**输出**:
- 文件: `data/raw_data.parquet`
- 内容: 模拟的时间序列数据

### 4.2 数据清洗

**脚本路径**: `time_sequence_prediction/data_cleaner.py`

**功能**: 清洗和预处理时间序列数据

**调用方式**:
```python
script_path = ts_pred_dir / "data_cleaner.py"

result = subprocess.run(
    ["python3", str(script_path)],
    cwd=str(ts_pred_dir),
    capture_output=True,
    text=True
)

print(result.stdout)
```

**输出**:
- 文件: `data/cleaned_data.parquet`
- 内容: 清洗后的数据

### 4.3 模型训练

**脚本路径**: `time_sequence_prediction/model_trainer.py`

**功能**: 训练 Prophet 时间序列模型

**参数**:
- `seasonality_mode`: 季节性模式（multiplicative/additive）
- `changepoint_prior_scale`: 变化点先验尺度
- `seasonality_prior_scale`: 季节性先验尺度

**调用方式**:
```python
script_path = ts_pred_dir / "model_trainer.py"

result = subprocess.run(
    ["python3", str(script_path)],
    cwd=str(ts_pred_dir),
    capture_output=True,
    text=True
)

print(result.stdout)
```

**输出**:
- 文件: `models/prophet_model.pkl`
- 内容: 训练好的 Prophet 模型

### 4.4 预测与分析

**脚本路径**: `time_sequence_prediction/predictor.py`

**功能**: 使用训练好的模型进行预测和异常检测

**参数**:
- `periods`: 预测周期数
- `freq`: 预测频率（D/H/M）

**调用方式**:
```python
script_path = ts_pred_dir / "predictor.py"

result = subprocess.run(
    ["python3", str(script_path)],
    cwd=str(ts_pred_dir),
    capture_output=True,
    text=True
)

print(result.stdout)
```

**输出**:
- 文件: `reports/prediction_results.csv`
- 文件: `reports/anomaly_detection.csv`
- 内容: 预测结果和异常检测结果

---

## 5. 使用示例

### 5.1 完整流程示例

```python
import subprocess
from pathlib import Path

# 1. 定位时间序列预测目录
ts_pred_dir = Path("/Users/jaci-j/AIops/time_sequence_prediction")

# 2. 生成数据
print("Step 1: 生成时间序列数据...")
result = subprocess.run(
    ["python3", "data_generator.py"],
    cwd=str(ts_pred_dir),
    capture_output=True,
    text=True
)
print(result.stdout)

# 3. 清洗数据
print("\nStep 2: 清洗数据...")
result = subprocess.run(
    ["python3", "data_cleaner.py"],
    cwd=str(ts_pred_dir),
    capture_output=True,
    text=True
)
print(result.stdout)

# 4. 训练模型
print("\nStep 3: 训练模型...")
result = subprocess.run(
    ["python3", "model_trainer.py"],
    cwd=str(ts_pred_dir),
    capture_output=True,
    text=True
)
print(result.stdout)

# 5. 预测与分析
print("\nStep 4: 预测与分析...")
result = subprocess.run(
    ["python3", "predictor.py"],
    cwd=str(ts_pred_dir),
    capture_output=True,
    text=True
)
print(result.stdout)
```

### 5.2 查看结果

```python
import pandas as pd

# 查看预测结果
df_predictions = pd.read_csv(ts_pred_dir / "reports/prediction_results.csv")
print("预测结果:")
print(df_predictions.head())

# 查看异常检测结果
df_anomalies = pd.read_csv(ts_pred_dir / "reports/anomaly_detection.csv")
print("\n异常检测结果:")
print(f"检测到的异常数: {len(df_anomalies)}")
print(df_anomalies.head())
```

### 5.3 实际应用场景

#### 场景 1: CPU 使用率异常检测
```
用户: "分析 CPU 使用率的异常情况"

执行流程:
1. 收集 CPU 使用率时间序列数据
2. 训练 Prophet 模型
3. 预测正常范围
4. 检测异常点
5. 分析异常原因（如进程、服务、任务等）
6. 生成根因分析报告
```

#### 场景 2: 内存使用趋势预测
```
用户: "预测未来一周的内存使用趋势"

执行流程:
1. 收集历史内存使用数据
2. 训练 Prophet 模型
3. 预测未来一周的内存使用
4. 分析趋势（增长/下降）
5. 提供容量规划建议
```

#### 场景 3: 网络流量异常分析
```
用户: "检测网络流量的异常峰值"

执行流程:
1. 收集网络流量时间序列数据
2. 训练 Prophet 模型
3. 检测异常峰值
4. 分析异常原因（如 DDoS 攻击、大流量下载等）
5. 提供应对建议
```

---

## 6. 权限边界

### 6.1 安全的只读操作
- 读取时间序列数据
- 训练模型
- 预测分析
- 生成报告

### 6.2 需要确认的操作
- 生成模拟数据
- 保存模型文件
- 保存分析报告

### 6.3 危险操作禁止执行
- 删除数据文件
- 删除模型文件
- 修改系统配置

---

## 7. 性能指标

### 7.1 模型性能
- 预测准确率: ~85-95%
- 异常检测率: ~80-90%
- 误报率: ~5-10%

### 7.2 资源消耗
- 内存: ~200MB (训练时)
- CPU: 中等
- 磁盘: ~500KB (模型文件)

### 7.3 时间消耗
- 数据生成: ~1秒
- 数据清洗: ~2秒
- 模型训练: ~10-30秒
- 预测分析: ~1秒

---

## 8. 故障排查

### 8.1 常见问题

**问题 1: Prophet 模型训练失败**
```
解决方案:
1. 检查数据格式是否符合要求
2. 确保数据包含 ds 和 y 列
3. 处理缺失值和异常值
```

**问题 2: 预测准确率低**
```
解决方案:
1. 增加训练数据量
2. 调整模型参数（seasonality_mode, changepoint_prior_scale）
3. 添加节假日效应
```

**问题 3: 异常检测误报率高**
```
解决方案:
1. 调整异常判定阈值
2. 增加训练数据量
3. 分析误报原因，优化模型
```

---

## 9. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-07
- 维护者: AIOps Team

### 更新日志

#### v1.0.0 (2025-04-07)
- 初始版本
- 集成 Prophet 时间序列预测功能
- 支持数据生成、清洗、训练、预测完整流程
- 支持异常检测和根因分析
