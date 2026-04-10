# 全栈性能调优技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `性能调优`, `瓶颈`, `压测`, `性能测试`
- `RT 高`, `响应慢`, `延迟高`, `吞吐量低`
- `线程池`, `连接池`, `缓存`, `异步`
- `JVM 调优`, `GC 调优`, `数据库优化`
- `接口慢`, `P99`, `P95`, `SLA`

### 1.2 适用条件
- 接口响应时间过长
- 系统吞吐量不足
- 资源使用率异常 (CPU/内存/IO/网络)
- 压测发现性能瓶颈
- 生产环境性能退化

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 性能基线确认                                       │
│  - 确认性能指标 (RT/QPS/TPS/并发数)                        │
│  - 确认 SLA 要求 (P95/P99)                                 │
│  - 收集当前性能数据                                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 瓶颈定位                                          │
│  - CPU 瓶颈? → Step 2a                                    │
│  - 内存瓶颈? → Step 2b                                    │
│  - IO 瓶颈? → Step 2c                                     │
│  - 网络瓶颈? → Step 2d                                    │
│  - 锁竞争? → Step 2e                                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2a: CPU 分析      Step 2b: 内存分析                   │
│  - top/perf             - jmap/堆分析                      │
│  - 火焰图               - GC 日志分析                      │
│  - 线程栈               - 内存泄漏检测                     │
│                                                              │
│  Step 2c: IO 分析       Step 2d: 网络分析                   │
│  - iostat/iotop         - tcpdump/sar                      │
│  - 慢查询分析            - 连接数/带宽                     │
│  - 磁盘性能             - DNS 延迟                         │
│                                                              │
│  Step 2e: 锁竞争分析                                        │
│  - jstack 死锁检测                                           │
│  - 线程等待分析                                              │
│  - synchronized/Lock 竞争                                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 分层优化                                           │
│  - 应用层优化                                               │
│  - 中间件层优化                                             │
│  - 数据库层优化                                             │
│  - 基础设施层优化                                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 验证与回归                                         │
│  - 压测验证                                                 │
│  - 对比优化前后指标                                         │
│  - 持续监控                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 系统资源概览

```bash
# CPU 使用率
top -b -n 1 | head -20
mpstat 1 5

# 内存使用
free -m
vmstat 1 5

# 磁盘 IO
iostat -x 1 5
iotop -b -n 3 -o

# 网络流量
sar -n DEV 1 5
iftop -t -s 10 2>/dev/null

# 系统负载
uptime
cat /proc/loadavg

# 综合概览
dstat -cdngy 1 5 2>/dev/null
```

### 3.2 CPU 瓶颈分析

```bash
# 进程 CPU 排序
ps aux --sort=-%cpu | head -20

# 线程级 CPU 分析
top -Hp <pid> -b -n 1 | head -20

# perf 火焰图 (需安装 perf)
perf record -g -p <pid> -- sleep 30
perf script > perf.out
# 使用 FlameGraph 生成火焰图
# git clone https://github.com/brendangregg/FlameGraph
# ./FlameGraph/stackcollapse-perf.pl perf.out | ./FlameGraph/flamegraph.pl > flame.svg

# 上下文切换
vmstat 1 5 | awk '{print $12, $13}'  # cs (context switch)
pidstat -w 1 5  # 自愿/非自愿切换

# CPU 就绪队列
vmstat 1 5 | awk '{print $1}'  # r (running queue)
```

### 3.3 内存瓶颈分析

```bash
# 进程内存排序
ps aux --sort=-%mem | head -20

# 系统内存详情
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|Buffers|Cached|SwapTotal|SwapFree"

# 页面缓存
vmstat 1 5 | awk '{print $4, $5, $6}'  # buff, cache, si/so

# 缺页中断
perf stat -e page-faults -p <pid> sleep 10

# JVM 堆分析 (Java 应用)
jmap -heap <pid>
jmap -histo <pid> | head -20
```

### 3.4 IO 瓶颈分析

```bash
# 磁盘 IO 统计
iostat -x 1 5
# 重点关注: %util (>80% 瓶颈), await (>10ms 异常), svctm

# 进程 IO 排序
iotop -b -n 3 -o

# 查看进程 IO
pidstat -d 1 5

# 文件系统 IO
cat /proc/<pid>/io

# 慢查询分析 (数据库 IO)
# MySQL:
# SELECT * FROM mysql.slow_log ORDER BY query_time DESC LIMIT 20;
```

### 3.5 网络瓶颈分析

```bash
# 网络连接统计
netstat -antp | awk '{print $6}' | sort | uniq -c | sort -rn

# TCP 连接数
ss -s

# 网络延迟
ping -c 10 <target>
mtr -r -c 10 <target>

# TCP 重传率
netstat -s | grep -i retrans
sar -n EDEV 1 5 | grep -i retrans

# DNS 解析延迟
dig @<dns_server> <domain> | grep "Query time"

# 带宽测试
iperf3 -c <server> -t 10
```

### 3.6 应用层性能分析

```bash
# Spring Boot Actuator 指标
curl -s http://localhost:actuator/metrics/http.server.requests | \
  python3 -c "import sys,json; d=json.load(sys.stdin); [print(f\"{m['statistic']}: {m['value']}\") for m in d['measurements']]"

# 接口 RT 分布
curl -s http://localhost:actuator/metrics/http.server.requests?tag=uri:/api/xxx

# 线程池状态
curl -s http://localhost:actuator/metrics/hikaricp.connections.active
curl -s http://localhost:actuator/metrics/tomcat.threads.busy

# 连接池状态
curl -s http://localhost:actuator/metrics/hikaricp.connections | python3 -m json.tool

# Redis 延迟
redis-cli --latency -h <host> -p <port>
redis-cli --latency-history -h <host> -p <port>
```

---

## 4. 常见问题与解决方案

### 4.1 接口响应慢

**现象**: 接口 RT 超过 SLA，P99 延迟高

**诊断步骤**:
```bash
# 1. 确认慢接口
curl -s http://localhost:actuator/metrics/http.server.requests | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d, indent=2))"

# 2. 分析调用链 (ARMS/SkyWalking)
# 3. 检查数据库慢查询
# 4. 检查外部服务调用延迟
```

**优化方案**:

| 层次 | 优化方向 | 具体措施 | 效果 |
|------|---------|---------|------|
| 应用层 | 异步化 | 消息队列/CompletableFuture | RT 降低 50%+ |
| 应用层 | 缓存 | Redis/本地缓存 | RT 降低 80%+ |
| 应用层 | 批量 | 批量查询/批量写入 | RT 降低 60%+ |
| 数据库 | 索引 | 添加缺失索引 | RT 降低 90%+ |
| 数据库 | SQL 优化 | 避免 SELECT * / 子查询 | RT 降低 50%+ |
| 中间件 | 连接池 | 调整连接池大小 | RT 降低 30%+ |
| 基础设施 | 扩容 | 增加实例/资源 | 线性提升 |

### 4.2 吞吐量不足

**现象**: QPS 上不去，压测无法达标

**诊断步骤**:
```bash
# 1. 确认瓶颈资源
top -b -n 1 | head -5
iostat -x 1 3 | grep -v "^$"

# 2. 检查线程池配置
curl -s http://localhost:actuator/metrics/tomcat.threads.config.max
curl -s http://localhost:actuator/metrics/tomcat.threads.busy

# 3. 检查连接池
curl -s http://localhost:actuator/metrics/hikaricp.connections.max
```

**优化方案**:

| 方案 | 配置 | 风险 |
|------|------|------|
| 增大线程池 | `server.tomcat.max-threads=500` | 🟡 中 |
| 增大连接池 | `spring.datasource.hikari.maximum-pool-size=50` | 🟡 中 |
| 异步处理 | 非核心逻辑异步化 | 🟢 低 |
| 水平扩容 | K8s HPA / 增加实例 | 🟢 低 |
| 缓存优化 | 多级缓存 / 缓存预热 | 🟢 低 |

### 4.3 数据库性能瓶颈

**现象**: 数据库成为系统瓶颈

**诊断步骤**:
```sql
-- 慢查询
SELECT * FROM mysql.slow_log ORDER BY query_time DESC LIMIT 20;

-- 锁等待
SELECT * FROM information_schema.innodb_trx ORDER BY trx_started;

-- 连接数
SHOW STATUS LIKE 'Threads_connected';
SHOW VARIABLES LIKE 'max_connections';
```

**优化方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 索引优化 | EXPLAIN 分析 + 添加索引 | 🟢 低 |
| 读写分离 | 从库读 / 主库写 | 🟢 低 |
| 分库分表 | ShardingSphere / 自研 | 🟡 中 |
| 缓存层 | Redis 缓存热点数据 | 🟢 低 |
| 连接池调优 | 调整最大连接数 | 🟡 中 |

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
top, vmstat, iostat, mpstat, sar
ps, netstat, ss
jstack, jmap -histo, jstat
curl actuator/metrics
```

### 5.2 需要确认的操作
```bash
修改线程池/连接池参数
修改 JVM 参数
添加/修改数据库索引
修改缓存配置
```

### 5.3 危险操作禁止执行
```bash
ALTER TABLE (大表变更)
DROP INDEX (可能导致查询全表扫描)
修改数据库最大连接数 (需评估)
重启生产服务 (需变更审批)
```

---

## 6. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
