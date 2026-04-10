# 数据库高可用与主从切换诊断技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `主从切换`, `failover`, `MHA`, `Orchestrator`
- `复制延迟`, `GTID`, `Binlog`, `relay log`
- `主从不一致`, `数据漂移`, `延迟从库`
- `半同步`, `异步复制`, `并行复制`
- `只读`, `read_only`, `super_read_only`

### 1.2 适用条件
- 主从复制延迟
- 主从切换失败 / 数据不一致
- MHA / Orchestrator 切换异常
- Binlog 损坏 / Relay Log 错误
- 从库无法启动复制
- 双主 / 环形复制冲突

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 环境检测                                           │
│  - 检测数据库类型 (MySQL/PostgreSQL)                        │
│  - 检测复制架构 (主从/MHA/Orchestrator/InnoDB Cluster)      │
│  - 检测运行环境 (Docker/RDS/裸机)                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 复制状态检查                                       │
│  - 主库 Binlog 状态                                        │
│  - 从库 IO/SQL 线程状态                                    │
│  - 复制延迟 (Seconds_Behind_Master)                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: GTID 与 Binlog 一致性检查                          │
│  - GTID 集合对比                                           │
│  - Binlog 位点对比                                         │
│  - 数据一致性校验                                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 切换风险评估                                       │
│  - 从库是否同步完成                                         │
│  - 是否存在长事务                                           │
│  - 从库只读状态                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 主库状态检查

```sql
-- 查看主库状态
SHOW MASTER STATUS;

-- 查看 Binlog 列表
SHOW BINARY LOGS;

-- 查看 Binlog 事件
SHOW BINLOG EVENTS IN 'mysql-bin.000001' LIMIT 10;

-- 查看已连接的从库
SHOW SLAVE HOSTS;

-- 查看 GTID 状态
SHOW GLOBAL VARIABLES LIKE 'gtid%';
SELECT @@GLOBAL.GTID_EXECUTED;
SELECT @@GLOBAL.GTID_PURGED;

-- 查看当前连接的从库信息
SELECT * FROM mysql.slave_master_info\G

-- 查看主库写入压力
SHOW GLOBAL STATUS LIKE 'Binlog_cache%';
```

### 3.2 从库状态检查

```sql
-- 查看从库状态 (关键命令)
SHOW SLAVE STATUS\G

-- 关键字段说明:
-- Slave_IO_Running: Yes/No (IO 线程状态)
-- Slave_SQL_Running: Yes/No (SQL 线程状态)
-- Seconds_Behind_Master: 延迟秒数 (NULL 表示复制中断)
-- Last_IO_Error / Last_SQL_Error: 最近错误
-- Retrieved_Gtid_Set / Executed_Gtid_Set: GTID 集合
-- Relay_Master_Log_File / Exec_Master_Log_Pos: 执行位点

-- 查看复制延迟详情
SELECT
  MASTER_POS_WAIT(@@GLOBAL.GTID_EXECUTED, 1, 5) AS wait_result;

-- 查看从库只读状态
SHOW VARIABLES LIKE 'read_only';
SHOW VARIABLES LIKE 'super_read_only';

-- 查看从库并行复制配置
SHOW VARIABLES LIKE 'slave_parallel%';
SHOW VARIABLES LIKE 'slave_pending_jobs_size_max';
```

### 3.3 复制延迟诊断

```sql
-- 查看延迟 (Seconds_Behind_Master)
SHOW SLAVE STATUS\G

-- 查看从库执行位点 vs 主库位点
-- 主库
SHOW MASTER STATUS;
-- 从库
SHOW SLAVE STATUS\G
-- 对比: Master_Log_File vs Relay_Master_Log_File

-- 查看并行复制 worker 状态
SELECT * FROM performance_schema.replication_applier_status_by_worker;

-- 查看 relay log 堆积
SHOW VARIABLES LIKE 'relay_log%';
```

```bash
# 检查网络延迟
ping -c 5 <master_host>

# 检查从库负载
top -b -n 1 | head -20
iostat -x 1 3
```

### 3.4 GTID 一致性检查

```sql
-- 主库 GTID 集合
SELECT @@GLOBAL.GTID_EXECUTED AS master_gtid;

-- 从库 GTID 集合
SELECT @@GLOBAL.GTID_EXECUTED AS slave_gtid;

-- 对比 GTID 差异
-- 从库上执行:
SELECT GTID_SUBTRACT(@@GLOBAL.GTID_EXECUTED, '<master_gtid>') AS slave_extra;
SELECT GTID_SUBTRACT('<master_gtid>', @@GLOBAL.GTID_EXECUTED) AS slave_missing;

-- 检查是否有事务跳过
SELECT @@GLOBAL.GTID_EXECUTED;
SHOW VARIABLES LIKE 'gtid_executed_compression_period';
```

### 3.5 数据一致性校验

```sql
-- 使用 pt-table-checksum (Percona Toolkit)
-- 在主库执行:
-- pt-table-checksum --host=master --user=checksum --password=xxx \
--   --databases=db_name --no-check-binlog-format

-- 使用 pt-table-sync 修复
-- pt-table-sync --host=master --user=sync --password=xxx \
--   --databases=db_name --print

-- 简单行数对比 (快速检查)
SELECT COUNT(*) FROM db_name.table_name;
-- 在主从分别执行，对比结果
```

### 3.6 阿里云 RDS 主从

```bash
# 查看 RDS 实例信息
aliyun rds DescribeDBInstances --RegionId cn-hangzhou

# 查看只读实例
aliyun rds DescribeReadOnlyDBInstances --DBInstanceId rm-xxx --RegionId cn-hangzhou

# 查看复制延迟
aliyun rds DescribeDBInstancePerformance --DBInstanceId rm-xxx \
  --Key MySQL_DataDelay --RegionId cn-hangzhou

# 手动主从切换 (需审批)
# aliyun rds SwitchDBInstanceHA --DBInstanceId rm-xxx --RegionId cn-hangzhou
```

---

## 4. 常见问题与解决方案

### 4.1 复制中断 (IO/SQL 线程停止)

**现象**: `Slave_IO_Running: No` 或 `Slave_SQL_Running: No`

**诊断步骤**:
```sql
-- 查看错误信息
SHOW SLAVE STATUS\G
-- 重点关注: Last_IO_Error, Last_SQL_Error
```

**常见错误与解决方案**:

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `Error 1236` (Binlog 不存在) | 主库 Binlog 已清理 | 重新搭建从库 |
| `Error 1062` (Duplicate entry) | 主键冲突 | 跳过或修复冲突行 |
| `Error 1032` (Can't find record) | 从库数据缺失 | 补数据或跳过 |
| `Error 1594` (Relay log corrupt) | Relay log 损坏 | 重新拉取 Binlog |
| `Connection refused` | 主库不可达 | 检查网络/主库状态 |

**跳过复制错误 (需确认)**:
```sql
-- 方式 1: GTID 跳过 (推荐)
SET GTID_NEXT='<uuid>:<transaction_id>';
BEGIN;
COMMIT;
SET GTID_NEXT='AUTOMATIC';
START SLAVE;

-- 方式 2: 跳过 N 个事务 (不推荐, 仅紧急使用)
STOP SLAVE;
SET GLOBAL SQL_SLAVE_SKIP_COUNTER=1;
START SLAVE;
```

### 4.2 复制延迟过高

**现象**: `Seconds_Behind_Master` 持续增长

**诊断步骤**:
```sql
-- 1. 检查从库负载
SHOW PROCESSLIST;
SHOW GLOBAL STATUS LIKE 'Threads_running';

-- 2. 检查并行复制
SHOW VARIABLES LIKE 'slave_parallel_workers';
SHOW VARIABLES LIKE 'slave_parallel_type';

-- 3. 检查大事务
SELECT * FROM information_schema.innodb_trx
ORDER BY trx_started LIMIT 5;
```

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 开启并行复制 | `slave_parallel_workers=8; slave_parallel_type=LOGICAL_CLOCK` | 🟢 低 |
| 增大 relay log 空间 | `relay_log_space_limit=0` | 🟢 低 |
| 优化从库硬件 | 升级 CPU/IO | 🟢 低 |
| 减少主库大事务 | 拆分批量操作 | 🟢 低 |
| 使用多线程复制 | MySQL 8.0+ `slave_parallel_workers` | 🟢 低 |

### 4.3 主从切换失败

**现象**: MHA / Orchestrator 切换后从库无法提升为主库

**诊断步骤**:
```bash
# 1. 检查 MHA 日志
tail -100 /var/log/masterha/mha.log

# 2. 检查候选从库状态
ssh <candidate_slave> "mysql -e 'SHOW SLAVE STATUS\G'"

# 3. 检查 SSH 连通性
ssh <candidate_slave> "echo OK"

# 4. 检查 MHA 配置
cat /etc/masterha/app1.cnf
```

**常见原因**:
| 原因 | 诊断方法 | 解决方案 |
|------|---------|---------|
| 从库延迟过大 | `Seconds_Behind_Master > 30` | 等待追平后重试 |
| SSH 不通 | MHA 日志 Connection refused | 修复 SSH 连接 |
| 从库只读未关闭 | `read_only=ON` | MHA 自动处理 / 手动关闭 |
| VIP 绑定失败 | `ip addr show` | 手动绑定 VIP |
| GTID 有空洞 | GTID 集合对比 | 修复数据后重试 |

---

## 5. 权限边界

### 5.1 安全的只读操作
```sql
SHOW MASTER STATUS;
SHOW SLAVE STATUS;
SHOW BINARY LOGS;
SELECT @@GLOBAL.GTID_EXECUTED;
SHOW VARIABLES LIKE 'slave%';
```

### 5.2 需要确认的操作
```sql
START SLAVE;
STOP SLAVE;
RESET SLAVE;
CHANGE MASTER TO;
SET GLOBAL SQL_SLAVE_SKIP_COUNTER;
```

### 5.3 危险操作禁止执行
```sql
RESET MASTER;
STOP SLAVE; (长时间停止)
主从切换 (需专项审批)
数据修复 (需变更工单)
```

---

## 6. 快速诊断脚本

```bash
#!/bin/bash
MYSQL_CMD="mysql -u root -p"

echo "=== 主库状态 ==="
$MYSQL_CMD -e "SHOW MASTER STATUS\G" 2>/dev/null

echo -e "\n=== 从库状态 ==="
$MYSQL_CMD -e "SHOW SLAVE STATUS\G" 2>/dev/null | grep -E "Slave_IO_Running|Slave_SQL_Running|Seconds_Behind|Last_IO_Error|Last_SQL_Error|Master_Log_File|Relay_Master_Log_File"

echo -e "\n=== GTID 状态 ==="
$MYSQL_CMD -e "SELECT @@GLOBAL.GTID_EXECUTED AS gtid_executed" 2>/dev/null

echo -e "\n=== 活跃事务 ==="
$MYSQL_CMD -e "SELECT trx_id, trx_state, TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS running_seconds FROM information_schema.innodb_trx ORDER BY trx_started" 2>/dev/null

echo -e "\n=== 复制线程 ==="
$MYSQL_CMD -e "SHOW PROCESSLIST" 2>/dev/null | grep -E "system user|Binlog|Slave"
```

---

## 7. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
