# MongoDB 诊断技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `MongoDB`, `Mongo`, `副本集`, `ReplicaSet`
- `Oplog`, `慢查询`, `连接池`, `索引`
- `分片`, `Sharding`, `Config Server`, `Mongos`
- `WT`, `WiredTiger`, `缓存`, `Checkpoint`

### 1.2 适用条件
- MongoDB 副本集状态异常
- 慢查询 / 性能下降
- 连接数耗尽
- Oplog 堆积 / 复制延迟
- 分片集群不均衡

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 环境检测                                           │
│  - 检测 MongoDB 运行环境                                    │
│  - 确定架构 (单机/副本集/分片)                              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 实例状态                                           │
│  - 服务器状态                                               │
│  - 副本集状态                                               │
│  - 连接数                                                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 性能分析                                           │
│  - 慢查询                                                   │
│  - 索引使用                                                 │
│  - WiredTiger 缓存                                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 复制与 Oplog                                       │
│  - 复制延迟                                                 │
│  - Oplog 窗口                                               │
│  - 选举状态                                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 实例状态

```javascript
// 服务器状态
db.serverStatus()

// 关键指标
db.serverStatus().connections    // 连接数
db.serverStatus().opcounters     // 操作计数
db.serverStatus().wiredTiger.cache  // WT 缓存

// 副本集状态
rs.status()

// 副本集配置
rs.conf()

// 当前操作
db.currentOp()

// 长时间运行的操作 (> 5 秒)
db.currentOp({"secs_running": {$gt: 5}})

// 连接数
db.serverStatus().connections
```

### 3.2 性能分析

```javascript
// 慢查询 (需开启 profiling)
db.getProfilingStatus()
db.setProfilingLevel(1, {slowms: 100})  // 记录 > 100ms 的查询

// 查看慢查询
db.system.profile.find().sort({ts: -1}).limit(20)

// 索引使用情况
db.collection.getIndexes()
db.collection.aggregate([{$indexStats: {}}])

// 执行计划
db.collection.find({...}).explain("executionStats")

// 集合统计
db.collection.stats()
db.collection.dataSize()
db.collection.indexSize()

// 数据库统计
db.stats()
```

### 3.3 复制与 Oplog

```javascript
// 副本集状态
rs.status()

// Oplog 窗口
db.getReplicationInfo()

// Oplog 大小
db.getMongo().getDB("local").oplog.rs.stats()

// 复制延迟 (从节点执行)
rs.printSlaveReplicationInfo()

// Oplog 最新条目
db.getMongo().getDB("local").oplog.rs.find().sort({$natural: -1}).limit(5)
```

### 3.4 分片集群

```javascript
// 分片状态
sh.status()

// 分片列表
sh.shardCollection("db.collection", {shardKey: 1})

// Balancer 状态
sh.getBalancerState()
sh.isBalancerRunning()

// Chunk 分布
db.collection.getShardDistribution()

// Config Server 状态 (在 mongos 执行)
db.getMongo().getDB("config").shards.find()
db.getMongo().getDB("config").databases.find()
```

---

## 4. 常见问题与解决方案

### 4.1 慢查询

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 添加索引 | `db.collection.createIndex({...})` | 🟢 低 |
| 覆盖查询 | 确保查询字段都有索引 | 🟢 低 |
| 限制返回字段 | `db.collection.find({...}, {field: 1})` | 🟢 低 |
| 分页优化 | 使用 `_id` 游标分页 | 🟢 低 |

### 4.2 复制延迟

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 增大 Oplog | 重新初始化 Oplog | 🟡 中 |
| 优化从节点硬件 | 升级 IO | 🟢 低 |
| 调整写关注 | `w:1` 替代 `w:majority` | 🟡 中 |
| 并行复制 | `replWriterWorkerThreads` | 🟢 低 |

### 4.3 连接数耗尽

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 增大限制 | `net.maxIncomingConnections` | 🟢 低 |
| 连接池 | 应用层配置连接池 | 🟢 低 |
| 终止空闲连接 | `db.killOp()` | 🟡 中 |

---

## 5. 权限边界

### 5.1 安全的只读操作
```javascript
db.serverStatus(), rs.status()
db.collection.find(), .explain()
db.collection.stats(), $indexStats
```

### 5.2 需要确认的操作
```javascript
db.collection.createIndex()
db.setProfilingLevel()
db.killOp()
```

### 5.3 危险操作禁止执行
```javascript
db.collection.drop()
db.dropDatabase()
rs.stepDown() (主节点降级)
sh.stopBalancer() (停止均衡器)
```

---

## 6. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
