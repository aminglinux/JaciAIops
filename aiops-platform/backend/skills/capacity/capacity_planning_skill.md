# 容量规划与资源预测技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `容量规划`, `扩容`, `缩容`, `资源预测`
- `水位`, `利用率`, `资源不足`, `资源闲置`
- `大促`, `活动`, `流量预估`, `压测`
- `成本`, `预算`, `资源优化`, `降本增效`

### 1.2 适用条件
- 业务增长需要容量规划
- 大促/活动前容量评估
- 资源利用率低需要缩容
- 成本优化与资源盘点
- K8s HPA/VPA 策略制定

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 确认规划目标                                       │
│  - 业务增长预估                                             │
│  - 大促流量预估                                             │
│  - 成本优化目标                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 当前资源盘点                                       │
│  - 计算资源 (CPU/内存/GPU)                                  │
│  - 存储资源 (磁盘/对象存储)                                 │
│  - 网络资源 (带宽/连接数)                                   │
│  - 中间件资源 (数据库/缓存/MQ)                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 利用率分析                                         │
│  - 峰值/均值/P95 利用率                                     │
│  - 资源瓶颈识别                                             │
│  - 闲置资源识别                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 趋势预测                                           │
│  - 历史趋势分析                                             │
│  - 增长率计算                                               │
│  - 容量预警时间点                                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 提供规划建议                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 K8s 资源盘点

```bash
# 节点资源总览
kubectl top nodes
kubectl get nodes -o wide

# 节点资源详情
kubectl describe nodes | grep -A 5 "Allocated resources"

# Pod 资源请求 vs 实际使用
kubectl top pods -A --sort-by=cpu | head -20
kubectl top pods -A --sort-by=memory | head -20

# 资源请求/限制统计
kubectl get pods -A -o json | python3 -c "
import sys, json
pods = json.load(sys.stdin)['items']
total_cpu_req = total_mem_req = total_cpu_lim = total_mem_lim = 0
for p in pods:
    for c in p['spec']['containers']:
        req = c.get('resources', {}).get('requests', {})
        lim = c.get('resources', {}).get('limits', {})
        total_cpu_req += float(req.get('cpu', '0').replace('m','').replace('n','0.001')) if 'cpu' in req else 0
        total_mem_req += int(req.get('memory', '0').replace('Mi','').replace('Gi','1024').replace('Ki','0.001')) if 'memory' in req else 0
print(f'CPU Request: {total_cpu_req}, Memory Request: {total_mem_req}Mi')
"

# 命名空间资源使用
kubectl top pods -n <namespace> --sort-by=cpu
kubectl top pods -n <namespace> --sort-by=memory

# HPA 状态
kubectl get hpa -A
```

### 3.2 阿里云资源盘点

```bash
# ECS 实例列表
aliyun ecs DescribeInstances --RegionId cn-hangzhou --PageSize 100 | \
  python3 -c "import sys,json; instances=json.load(sys.stdin)['Instances']['Instance']; [print(f\"{i['InstanceId']}: {i['InstanceType']} - {i['Status']}\") for i in instances]"

# RDS 实例列表
aliyun rds DescribeDBInstances --RegionId cn-hangzhou | \
  python3 -c "import sys,json; instances=json.load(sys.stdin)['Items']['DBInstance']; [print(f\"{i['DBInstanceId']}: {i['DBInstanceType']} - {i['DBInstanceStatus']}\") for i in instances]"

# Redis 实例列表
aliyun r-kvstore DescribeInstances --RegionId cn-hangzhou

# SLB 实例列表
aliyun slb DescribeLoadBalancers --RegionId cn-hangzhou

# OSS Bucket 列表
aliyun oss ls

# 费用概览
aliyun bss QueryAccountBalance
aliyun bss QueryAvailableInstances --ProductCode ecs
```

### 3.3 利用率分析

```bash
# ECS CPU 利用率 (CloudMonitor)
aliyun cms QueryMetricList --Project acs_ecs_dashboard \
  --Metric CPUUtilization --Period 86400 \
  --StartTime "$(date -d '7 days ago' +%Y-%m-%d %H:%M:%S)" \
  --EndTime "$(date +%Y-%m-%d %H:%M:%S)"

# ECS 内存利用率
aliyun cms QueryMetricList --Project acs_ecs_dashboard \
  --Metric memory_usedutilization --Period 86400 \
  --StartTime "$(date -d '7 days ago' +%Y-%m-%d %H:%M:%S)"

# RDS CPU 利用率
aliyun cms QueryMetricList --Project acs_rds_dashboard \
  --Metric CpuUsage --Period 86400 \
  --StartTime "$(date -d '7 days ago' +%Y-%m-%d %H:%M:%S)"

# RDS 连接数使用率
aliyun cms QueryMetricList --Project acs_rds_dashboard \
  --Metric ConnectionUsage --Period 86400 \
  --StartTime "$(date -d '7 days ago' +%Y-%m-%d %H:%M:%S)"

# Redis 内存使用率
aliyun cms QueryMetricList --Project acs_kvstore \
  --Metric MemoryUsage --Period 86400 \
  --StartTime "$(date -d '7 days ago' +%Y-%m-%d %H:%M:%S)"
```

### 3.4 趋势预测

```bash
# 30 天磁盘使用趋势
aliyun cms QueryMetricList --Project acs_ecs_dashboard \
  --Metric DiskUsage --Period 86400 \
  --StartTime "$(date -d '30 days ago' +%Y-%m-%d %H:%M:%S)"

# 30 天 QPS 趋势
aliyun cms QueryMetricList --Project acs_slb_dashboard \
  --Metric Qps --Period 86400 \
  --StartTime "$(date -d '30 days ago' +%Y-%m-%d %H:%M:%S)"

# 基于趋势的容量预测 (简单线性回归)
# 使用 Python 脚本:
# python3 predict_capacity.py --metric cpu --days 30 --predict 90
```

---

## 4. 常见问题与解决方案

### 4.1 大促容量评估

**规划步骤**:

| 步骤 | 操作 | 产出 |
|------|------|------|
| 1. 流量预估 | 基于历史大促数据 × 增长系数 | 峰值 QPS/TPS |
| 2. 单机容量 | 压测获取单机极限 | 单机 QPS/TPS |
| 3. 实例数计算 | 峰值 ÷ 单机容量 × 安全系数 | 所需实例数 |
| 4. 依赖评估 | 数据库/缓存/MQ 容量 | 依赖资源需求 |
| 5. 弹性预案 | HPA 策略 + 手动扩容 | 弹性方案 |

### 4.2 资源利用率低

**诊断步骤**:
```bash
# 1. 查看低利用率实例
aliyun ecs DescribeInstances --RegionId cn-hangzhou | \
  python3 -c "import sys,json; instances=json.load(sys.stdin)['Instances']['Instance']; [print(f\"{i['InstanceId']}: {i['InstanceType']}\") for i in instances]"

# 2. 查看历史 CPU 利用率
aliyun cms QueryMetricList --Project acs_ecs_dashboard --Metric CPUUtilization
```

**优化方案**:

| 方案 | 操作 | 节省 |
|------|------|------|
| 降配 | 降低实例规格 | ~30-50% |
| 缩容 | 减少实例数量 | 按比例 |
| 闲置回收 | 释放未使用资源 | 100% |
| 预留实例 | 购买 RI/节省计划 | ~30-60% |
| 竞价实例 | 非核心业务用抢占式 | ~80% |

### 4.3 容量预警

**预警阈值建议**:

| 资源 | 预警阈值 | 危险阈值 |
|------|---------|---------|
| CPU | > 70% | > 85% |
| 内存 | > 75% | > 90% |
| 磁盘 | > 75% | > 85% |
| 数据库连接数 | > 70% | > 85% |
| Redis 内存 | > 70% | > 85% |
| Kafka Lag | > 10000 | > 100000 |
| MQ 堆积 | > 5000 | > 50000 |

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
kubectl top nodes/pods
CloudMonitor 指标查询
资源列表查询
费用查询
```

### 5.2 需要确认的操作
```bash
修改 HPA 策略
调整资源 Request/Limit
实例规格变更
```

### 5.3 危险操作禁止执行
```bash
释放实例 (需变更审批)
降配核心数据库
删除监控/告警配置
```

---

## 6. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
