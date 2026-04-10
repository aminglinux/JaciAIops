# PostgreSQL 诊断技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `PostgreSQL`, `PG`, `psql`
- `锁等待`, `连接数`, `VACUUM`, `WAL`
- `慢查询`, `索引`, `膨胀`, `Bloat`
- `复制槽`, `逻辑复制`, `流复制`
- `MVCC`, `事务ID回卷`, `Autovacuum`

### 1.2 适用条件
- PostgreSQL 连接数耗尽
- 慢查询 / 查询性能差
- 锁等待 / 死锁
- 表膨胀 / 索引膨胀
- 复制延迟
- WAL 堆积

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 环境检测                                           │
│  - 检测 PostgreSQL 运行环境                                 │
│  - 确定连接方式                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 实例状态检查                                       │
│  - 连接数                                                   │
│  - 活跃查询                                                 │
│  - 锁等待                                                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 性能分析                                           │
│  - 慢查询                                                   │
│  - 索引使用                                                 │
│  - 表膨胀                                                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 复制与 WAL 检查                                    │
│  - 复制状态                                                 │
│  - WAL 堆积                                                 │
│  - 复制槽                                                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 环境检测与连接

```bash
# 检测 PostgreSQL 进程
ps aux | grep postgres | grep -v grep

# 检测端口
netstat -tlnp | grep 5432 || ss -tlnp | grep 5432

# Docker 环境
docker ps | grep postgres
docker exec <container> psql -U postgres -c "SELECT version();"

# 连接测试
psql -h <host> -p <port> -U <user> -d <database> -c "SELECT 1;"
```

### 3.2 实例状态

```sql
-- 版本信息
SELECT version();

-- 连接数
SELECT count(*) AS total_connections,
       count(*) FILTER (WHERE state = 'active') AS active,
       count(*) FILTER (WHERE state = 'idle') AS idle,
       count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_transaction
FROM pg_stat_activity;

-- 最大连接数
SHOW max_connections;

-- 活跃查询
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE state != 'idle' AND query NOT LIKE '%pg_stat_activity%'
ORDER BY duration DESC;

-- 长事务 (> 60 秒)
SELECT pid, now() - xact_start AS duration, query, state
FROM pg_stat_activity
WHERE xact_start IS NOT NULL AND now() - xact_start > interval '60 seconds'
ORDER BY duration DESC;

-- 锁等待
SELECT blocked.pid AS blocked_pid,
       blocked.query AS blocked_query,
       blocking.pid AS blocking_pid,
       blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_locks blocked_locks ON blocked.pid = blocked_locks.pid
JOIN pg_locks blocking_locks ON blocked_locks.locktype = blocking_locks.locktype
  AND blocked_locks.database IS NOT DISTINCT FROM blocking_locks.database
  AND blocked_locks.relation IS NOT DISTINCT FROM blocking_locks.relation
  AND blocked_locks.page IS NOT DISTINCT FROM blocking_locks.page
  AND blocked_locks.tuple IS NOT DISTINCT FROM blocking_locks.tuple
  AND blocked_locks.pid != blocking_locks.pid
JOIN pg_stat_activity blocking ON blocking_locks.pid = blocking.pid
WHERE NOT blocked_locks.granted;
```

### 3.3 性能分析

```sql
-- 慢查询 (pg_stat_statements, 需启用扩展)
SELECT query, calls, total_exec_time, mean_exec_time, max_exec_time
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;

-- 未使用索引
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;

-- 缺失索引 (全表扫描多的表)
SELECT schemaname, relname, seq_scan, idx_scan,
       seq_scan::float / GREATEST(idx_scan, 1) AS seq_ratio
FROM pg_stat_user_tables
WHERE seq_scan > 100
ORDER BY seq_ratio DESC
LIMIT 20;

-- 表膨胀 (Bloat)
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
       n_dead_tup, n_live_tup,
       ROUND(n_dead_tup::float / GREATEST(n_live_tup, 1) * 100, 2) AS bloat_ratio
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY n_dead_tup DESC;

-- 索引膨胀
SELECT schemaname, tablename, indexname,
       pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
       idx_scan
FROM pg_stat_user_indexes
WHERE pg_relation_size(indexrelid) > 100 * 1024 * 1024  -- > 100MB
ORDER BY pg_relation_size(indexrelid) DESC;

-- 缓存命中率
SELECT sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) AS cache_hit_ratio
FROM pg_statio_user_tables;
```

### 3.4 复制与 WAL

```sql
-- 复制状态 (主库)
SELECT pid, state, client_addr, sent_lsn, write_lsn, flush_lsn, replay_lsn,
       sent_lsn - replay_lsn AS replication_lag
FROM pg_stat_replication;

-- 复制延迟 (从库)
SELECT now() - pg_last_xact_replay_timestamp() AS replication_lag;

-- WAL 状态
SELECT pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')) AS wal_generated;

-- WAL 文件数
SELECT count(*) AS wal_files FROM pg_ls_waldir();

-- 复制槽
SELECT slot_name, plugin, slot_type, active, restart_lsn
FROM pg_replication_slots;

-- 未激活的复制槽 (可能导致 WAL 堆积)
SELECT slot_name, restart_lsn, pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS lag_bytes
FROM pg_replication_slots
WHERE active = false;
```

### 3.5 VACUUM 分析

```sql
-- Autovacuum 状态
SHOW autovacuum;
SHOW autovacuum_max_workers;

-- 最近 VACUUM 时间
SELECT relname, last_vacuum, last_autovacuum, last_analyze, last_autoanalyze
FROM pg_stat_user_tables
ORDER BY last_autovacuum DESC NULLS LAST;

-- 需要 VACUUM 的表
SELECT schemaname, relname, n_dead_tup,
       ROUND(n_dead_tup::float / GREATEST(n_live_tup + n_dead_tup, 1) * 100, 2) AS dead_ratio
FROM pg_stat_user_tables
WHERE n_dead_tup > GREATEST(1000, n_live_tup * 0.1)
ORDER BY n_dead_tup DESC;

-- 事务 ID 回卷风险
SELECT datname, age(datfrozenxid) AS xid_age,
       2147483647 - age(datfrozenxid) AS xids_until_wraparound
FROM pg_database
ORDER BY age(datfrozenxid) DESC;
```

---

## 4. 常见问题与解决方案

### 4.1 连接数耗尽

**现象**: `FATAL: sorry, too many clients already`

**诊断步骤**:
```sql
SELECT count(*), state FROM pg_stat_activity GROUP BY state ORDER BY count DESC;
```

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 增大 max_connections | `ALTER SYSTEM SET max_connections = 200` | 🟡 中 |
| 使用连接池 | PgBouncer / Pgpool-II | 🟢 低 |
| 终止空闲事务 | `SELECT pg_terminate_backend(pid)` | 🟡 中 |
| 设置 idle_timeout | `idle_in_transaction_session_timeout` | 🟢 低 |

### 4.2 表膨胀

**现象**: 表占用空间远大于实际数据量

**诊断步骤**:
```sql
SELECT schemaname, relname, n_dead_tup, n_live_tup,
       ROUND(n_dead_tup::float / GREATEST(n_live_tup + n_dead_tup, 1) * 100, 2) AS bloat_ratio
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY bloat_ratio DESC;
```

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| VACUUM | `VACUUM <table>` | 🟢 低 |
| VACUUM FULL | `VACUUM FULL <table>` (锁表) | 🟡 中 |
| pg_repack | 在线重建表 | 🟢 低 |
| 调整 Autovacuum | 降低触发阈值 | 🟢 低 |

### 4.3 复制延迟

**现象**: 从库数据落后主库

**诊断步骤**:
```sql
-- 主库
SELECT client_addr, state, sent_lsn - replay_lsn AS lag_bytes
FROM pg_stat_replication;

-- 从库
SELECT now() - pg_last_xact_replay_timestamp() AS lag;
```

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 优化从库硬件 | 升级 IO | 🟢 低 |
| 调整恢复参数 | `max_wal_senders`, `wal_keep_size` | 🟢 低 |
| 清理复制槽 | 删除未使用复制槽 | 🟡 中 |
| 并行恢复 | `max_parallel_apply_workers` | 🟢 低 |

---

## 5. 权限边界

### 5.1 安全的只读操作
```sql
SELECT from pg_stat_*, pg_statio_*
SHOW configuration parameters
EXPLAIN ANALYZE (只读查询)
```

### 5.2 需要确认的操作
```sql
VACUUM, ANALYZE
pg_terminate_backend
ALTER SYSTEM SET
```

### 5.3 危险操作禁止执行
```sql
VACUUM FULL (大表)
DROP TABLE / DROP DATABASE
ALTER TABLE (大表变更)
pg_terminate_backend (大量终止)
```

---

## 6. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
