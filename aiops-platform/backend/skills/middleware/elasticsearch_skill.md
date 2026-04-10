# Elasticsearch 集群诊断技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `Elasticsearch`, `ES`, `集群状态RED`, `YELLOW`
- `分片未分配`, `UNASSIGNED`, `Shard`
- `慢查询`, `索引膨胀`, `Mapping 冲突`
- `JVM 堆`, `GC`, `熔断器`, `Circuit Breaker`
- `Rebalance`, `恢复`, `Snapshot`

### 1.2 适用条件
- 集群状态 RED/YELLOW
- 分片未分配
- 搜索/写入性能下降
- JVM 堆内存不足
- 磁盘空间告警

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 环境检测                                           │
│  - 检测 ES 版本与集群信息                                   │
│  - 确定连接方式                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 集群健康检查                                       │
│  - 集群状态 (GREEN/YELLOW/RED)                              │
│  - 节点状态                                                 │
│  - 分片状态                                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 分片分析                                           │
│  - 未分配分片                                               │
│  - 分片迁移/恢复                                            │
│  - 磁盘水位                                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 性能分析                                           │
│  - 慢查询                                                   │
│  - 写入性能                                                 │
│  - JVM 堆/GC                                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 集群健康

```bash
# 集群健康
curl -s http://localhost:9200/_cluster/health?pretty

# 节点状态
curl -s http://localhost:9200/_cat/nodes?v

# 节点详情
curl -s http://localhost:9200/_nodes/stats?pretty

# 集群状态 (含索引级)
curl -s http://localhost:9200/_cluster/health?level=indices&pretty

# 分片级健康
curl -s http://localhost:9200/_cluster/health?level=shards&pretty

# 集群分配解释 (分片未分配原因)
curl -s http://localhost:9200/_cluster/allocation/explain?pretty
```

### 3.2 分片分析

```bash
# 查看所有分片状态
curl -s http://localhost:9200/_cat/shards?v

# 查找未分配分片
curl -s http://localhost:9200/_cat/shards?v | grep UNASSIGNED

# 分片分配解释
curl -s -X POST "http://localhost:9200/_cluster/allocation/explain" -H 'Content-Type: application/json' -d '{
  "index": "<index_name>",
  "shard": 0,
  "primary": true
}'

# 查看索引列表
curl -s http://localhost:9200/_cat/indices?v

# 查看索引大小
curl -s http://localhost:9200/_cat/indices?v&s=store.size:desc

# 磁盘水位
curl -s http://localhost:9200/_cat/allocation?v
```

### 3.3 性能分析

```bash
# 慢搜索日志
curl -s http://localhost:9200/_cat/thread_pool/search?v&h=node_name,active,queue,rejected

# 慢写入日志
curl -s http://localhost:9200/_cat/thread_pool/write?v&h=node_name,active,queue,rejected

# 线程池状态
curl -s http://localhost:9200/_cat/thread_pool?v

# 熔断器状态
curl -s http://localhost:9200/_nodes/stats/breaker?pretty

# JVM 堆使用
curl -s http://localhost:9200/_cat/nodes?v&h=name,heap.percent,heap.current,heap.max,ram.percent,ram.current,ram.max

# 正在执行的任务
curl -s http://localhost:9200/_tasks?pretty

# 挂起的任务
curl -s http://localhost:9200/_cluster/pending_tasks?pretty
```

### 3.4 索引管理

```bash
# 查看索引 Mapping
curl -s http://localhost:9200/<index_name>/_mapping?pretty

# 查看索引 Settings
curl -s http://localhost:9200/<index_name>/_settings?pretty

# 查看索引统计
curl -s http://localhost:9200/<index_name>/_stats?pretty

# 慢查询配置
curl -s http://localhost:9200/<index_name>/_settings?pretty | grep -A 5 "slowlog"

# 索引模板
curl -s http://localhost:9200/_template?pretty

# 快照状态
curl -s http://localhost:9200/_snapshot/_status?pretty
```

---

## 4. 常见问题与解决方案

### 4.1 集群状态 RED

**现象**: 存在主分片未分配

**诊断步骤**:
```bash
# 1. 查看未分配分片
curl -s http://localhost:9200/_cat/shards?v | grep UNASSIGNED

# 2. 查看分配原因
curl -s http://localhost:9200/_cluster/allocation/explain?pretty

# 3. 检查磁盘水位
curl -s http://localhost:9200/_cat/allocation?v
```

**解决方案**:

| 原因 | 解决方案 | 风险 |
|------|---------|------|
| 节点宕机 | 重启节点 | 🟡 中 |
| 磁盘满 | 清理磁盘/调整水位 | 🟡 中 |
| 分片数超限 | 调整 `cluster.max_shards_per_node` | 🟢 低 |
| 手动分配 | `_cluster/reroute` | 🟡 中 |

### 4.2 JVM 堆内存不足

**现象**: 频繁 GC，熔断器触发

**诊断步骤**:
```bash
# 1. 查看堆使用
curl -s http://localhost:9200/_cat/nodes?v&h=name,heap.percent

# 2. 查看熔断器
curl -s http://localhost:9200/_nodes/stats/breaker?pretty
```

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 增大堆内存 | 修改 `-Xmx` (≤32GB) | 🟡 中 |
| 减少字段缓存 | 调整 `fielddata.cache` | 🟢 低 |
| 优化查询 | 避免 `script` / 大聚合 | 🟢 低 |
| 冷热分离 | 热数据单独节点 | 🟢 低 |

### 4.3 写入性能差

**现象**: 写入延迟高，bulk 队列满

**诊断步骤**:
```bash
# 1. 查看写入线程池
curl -s http://localhost:9200/_cat/thread_pool/write?v

# 2. 查看索引速率
curl -s http://localhost:9200/_cat/indices?v&h=index,docs.count,indexing.index_total,indexing.index_current
```

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 批量写入 | 使用 bulk API | 🟢 低 |
| 调大 refresh_interval | `refresh_interval=30s` | 🟢 低 |
| 增加分片数 | 重新索引 | 🟡 中 |
| 关闭副本写入时 | `number_of_replicas=0` (临时) | 🟡 中 |

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
_cat APIs, _cluster/health, _nodes/stats
_cluster/allocation/explain
GET _search, GET _mapping
```

### 5.2 需要确认的操作
```bash
_cluster/reroute (手动分片分配)
修改索引 settings
_force_merge (段合并)
```

### 5.3 危险操作禁止执行
```bash
DELETE /<index> (删除索引)
DELETE /_all (删除所有索引)
关闭安全配置
修改集群拓扑 (添加/移除节点)
```

---

## 6. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
