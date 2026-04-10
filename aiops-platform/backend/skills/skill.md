# Skill 索引与指引

本文档是智能运维诊断系统的 Skill 总索引，采用**渐进式披露（Progressive Disclosure）**设计原则。

---

## 1. 使用方法

### 1.1 渐进式披露流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 阅读本索引文件，了解可用的 Skill 分类              │
│          skill.md (当前文件)                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 根据用户问题和关键词，选择合适的 Skill 类别        │
│          使用 @reference 引用具体 Skill 文件                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 加载具体 Skill 文件，执行诊断流程                  │
│          diagnosis/debug_skill.md 或其他                    │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 引用语法

使用 `@reference` 引用具体 Skill 文件：

```
@reference: diagnosis/debug_skill.md
@reference: diagnosis/gnn_rca_skill.md
@reference: diagnosis/mysql_deadlock_skill.md
@reference: connection/login_skill.md
```

---

## 2. Skill 分类索引

### 2.1 诊断类 (Diagnosis)

用于故障排查和根因分析。

#### P0 - 核心诊断技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **debug_skill** | `diagnosis/debug_skill.md` | 磁盘, 内存, CPU, 网络, 故障, 排查, OOM, 502, 504, SSH不通, 死锁, CrashLoopBackOff, 防火墙 | 服务器/数据库/中间件/K8S 全栈故障排查 |
| **gnn_rca_skill** | `diagnosis/gnn_rca_skill.md` | 根因分析, RCA, GNN, 微服务, 拓扑 | 微服务根因分析 |
| **time_series_rca_skill** | `diagnosis/time_series_rca_skill.md` | 时间序列, 预测, 异常检测, 趋势分析 | 时间序列根因分析 |
| **mysql_deadlock_skill** | `diagnosis/mysql_deadlock_skill.md` | 死锁, deadlock, 锁等待, 事务阻塞 | MySQL 死锁排查与解决 |
| **mysql_slow_query_skill** | `diagnosis/mysql_slow_query_skill.md` | 慢查询, slow query, SQL优化, 查询慢 | MySQL 慢查询分析 |

#### P1 - 常用诊断技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **redis_skill** | `diagnosis/redis_skill.md` | Redis, 缓存, 内存, key, 缓存穿透 | Redis 诊断与优化 |
| **ad_skill** | `diagnosis/ad_skill.md` | AD, Active Directory, 域控, LDAP, Kerberos | Active Directory 诊断 |

**选择指南**：
- 单机故障 → `@reference: diagnosis/debug_skill.md`
- 微服务/多服务故障 → `@reference: diagnosis/gnn_rca_skill.md`
- 时间序列/指标异常 → `@reference: diagnosis/time_series_rca_skill.md`
- MySQL 死锁/锁等待 → `@reference: diagnosis/mysql_deadlock_skill.md`
- MySQL 慢查询 → `@reference: diagnosis/mysql_slow_query_skill.md`
- Redis 问题 → `@reference: diagnosis/redis_skill.md`
- AD/域控问题 → `@reference: diagnosis/ad_skill.md`

---

### 2.2 容器类 (Container)

用于容器和 Kubernetes 诊断。

#### P0 - 核心容器技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **k8s_pod_skill** | `container/k8s_pod_skill.md` | Pod, k8s, Kubernetes, 容器, CrashLoopBackOff | Kubernetes Pod 诊断 |

**选择指南**：
- K8s Pod 问题 → `@reference: container/k8s_pod_skill.md`

---

### 2.3 网络类 (Network)

用于网络连接和证书管理。

#### P0 - 核心网络技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **connectivity_skill** | `network/connectivity_skill.md` | 网络, 连接, ping, DNS, 防火墙, 端口 | 网络连通性诊断 |
| **lb_port_connectivity_skill** | `network/lb_port_connectivity_skill.md` | 负载均衡, SLB, 端口连不上, 健康检查失败 | 阿里云负载均衡端口连接诊断 (支持 Linux/Windows，支持远程云服务) |

#### P2 - 辅助网络技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **ssl_certificate_skill** | `network/ssl_certificate_skill.md` | SSL, 证书, HTTPS, 过期, Let's Encrypt | SSL 证书管理 |

**选择指南**：
- 网络连通性问题 → `@reference: network/connectivity_skill.md`
- 负载均衡端口连接问题 → `@reference: network/lb_port_connectivity_skill.md`
- SSL 证书问题 → `@reference: network/ssl_certificate_skill.md`

---

### 2.4 监控类 (Monitoring)

用于监控系统和日志分析。

#### P0 - 核心监控技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **deeplog_anomaly_detection_skill** | `monitoring/deeplog_anomaly_detection_skill.md` | 日志异常检测, DeepLog, LSTM, 日志序列 | DeepLog 日志异常检测 |

#### P1 - 常用监控技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **prometheus_skill** | `monitoring/prometheus_skill.md` | Prometheus, 监控, 指标, PromQL, 告警 | Prometheus 监控诊断 |
| **log_analysis_skill** | `monitoring/log_analysis_skill.md` | 日志, log, ELK, Loki, 日志分析 | 日志分析与排查 |

**选择指南**：
- 日志异常检测 → `@reference: monitoring/deeplog_anomaly_detection_skill.md`
- Prometheus 问题 → `@reference: monitoring/prometheus_skill.md`
- 日志分析 → `@reference: monitoring/log_analysis_skill.md`

---

### 2.5 备份类 (Backup)

用于数据备份与恢复。

#### P2 - 备份管理技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **backup_skill** | `backup/backup_skill.md` | 备份, backup, 恢复, restore, 灾备 | 数据备份与恢复 |

**选择指南**：
- 备份恢复问题 → `@reference: backup/backup_skill.md`

---

### 2.6 连接类 (Connection)

用于服务器连接和认证管理。

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **login_skill** | `connection/login_skill.md` | SSH, 连接, 登录, 远程, 凭据, 阿里云, RDS, PolarDB, DMS, 云数据库, 白名单 | 连接管理 (SSH/RDS/PolarDB/DMS/K8S/中间件) |

**选择指南**：
- 需要连接服务器或数据库 → `@reference: connection/login_skill.md`

---

### 2.7 中间件类 (Middleware)

用于消息队列和搜索引擎等中间件诊断。

#### P0 - 核心中间件技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **kafka_skill** | `middleware/kafka_skill.md` | Kafka, 消息堆积, Consumer Lag, 分区, Broker, Producer, Consumer, Offset | Kafka 集群诊断与消息堆积处理 |
| **nginx_skill** | `middleware/nginx_skill.md` | Nginx, 502, 504, 反向代理, upstream, 负载均衡, 配置, 重写 | Nginx Web 服务器与反向代理诊断 |

#### P1 - 常用中间件技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **rabbitmq_skill** | `middleware/rabbitmq_skill.md` | RabbitMQ, 队列堆积, 死信队列, DLX, Channel, Connection, 消息丢失 | RabbitMQ 队列诊断与连接管理 |
| **elasticsearch_skill** | `middleware/elasticsearch_skill.md` | Elasticsearch, ES, 集群状态RED, YELLOW, 分片未分配, UNASSIGNED, 慢查询, JVM堆 | Elasticsearch 集群诊断与性能优化 |

**选择指南**：
- Kafka 消息堆积/分区问题 → `@reference: middleware/kafka_skill.md`
- Nginx 502/504/反向代理问题 → `@reference: middleware/nginx_skill.md`
- RabbitMQ 队列堆积/死信 → `@reference: middleware/rabbitmq_skill.md`
- ES 集群状态异常/分片问题 → `@reference: middleware/elasticsearch_skill.md`

---

### 2.8 数据库类 (Database)

用于数据库高可用与多模型数据库诊断。

#### P0 - 核心数据库技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **database_ha_skill** | `database/database_ha_skill.md` | 主从切换, 复制中断, IO线程, SQL线程, Binlog, GTID, MHA, 数据库高可用 | 数据库高可用与复制故障排查 |

#### P1 - 常用数据库技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **postgresql_skill** | `database/postgresql_skill.md` | PostgreSQL, PG, 锁等待, VACUUM, WAL, 膨胀, Bloat, 复制槽, Autovacuum | PostgreSQL 性能诊断与维护 |
| **mongodb_skill** | `database/mongodb_skill.md` | MongoDB, 副本集, ReplicaSet, Oplog, 分片, Sharding, WiredTiger | MongoDB 副本集与分片诊断 |

**选择指南**：
- 数据库主从复制/高可用问题 → `@reference: database/database_ha_skill.md`
- PostgreSQL 锁/膨胀/VACUUM 问题 → `@reference: database/postgresql_skill.md`
- MongoDB 副本集/分片问题 → `@reference: database/mongodb_skill.md`

---

### 2.9 安全类 (Security)

用于安全审计与权限排查。

#### P0 - 核心安全技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **security_audit_skill** | `security/security_audit_skill.md` | 安全审计, SSH暴力破解, 异常登录, 权限提升, 可疑进程, 入侵检测 | 安全事件检测与应急响应 |

#### P1 - 常用安全技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **permission_troubleshoot_skill** | `security/permission_troubleshoot_skill.md` | 权限拒绝, Permission Denied, 403, ACL, sudo, SELinux, AppArmor | 文件/服务权限问题排查 |

**选择指南**：
- 安全事件/入侵检测 → `@reference: security/security_audit_skill.md`
- 文件权限/SELinux/sudo 问题 → `@reference: security/permission_troubleshoot_skill.md`

---

### 2.10 云资源类 (Cloud)

用于阿里云资源诊断。

#### P0 - 核心云资源技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **ecs_skill** | `cloud/ecs_skill.md` | ECS, 实例, 无法连接, 安全组, 磁盘, 快照, 自动扩缩容 | 阿里云 ECS 实例诊断 |

#### P1 - 常用云资源技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **vpc_skill** | `cloud/vpc_skill.md` | VPC, 交换机, 路由表, NAT网关, 对等连接, 云企业网, VPN, 网络不通 | 阿里云 VPC 网络诊断 |
| **oss_skill** | `cloud/oss_skill.md` | OSS, 对象存储, Bucket, 上传失败, 权限, STS, CORS, 防盗链 | 阿里云 OSS 存储诊断 |

**选择指南**：
- ECS 实例无法连接/磁盘问题 → `@reference: cloud/ecs_skill.md`
- VPC 网络不通/路由问题 → `@reference: cloud/vpc_skill.md`
- OSS 上传失败/权限问题 → `@reference: cloud/oss_skill.md`

---

### 2.11 容量类 (Capacity)

用于性能调优与容量规划。

#### P0 - 核心容量技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **jvm_skill** | `capacity/jvm_skill.md` | JVM, OOM, GC, 堆内存, 线程dump, CPU飙高, Metaspace | Java 应用性能诊断 |
| **performance_tuning_skill** | `capacity/performance_tuning_skill.md` | 性能调优, 接口慢, RT高, 吞吐量, QPS, P99延迟, 线程池, 连接池 | 系统全链路性能优化 |

#### P1 - 常用容量技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **capacity_planning_skill** | `capacity/capacity_planning_skill.md` | 容量规划, 扩容, 缩容, 资源预测, 水位, 利用率, 大促, 降本增效 | 容量规划与资源预测 |

**选择指南**：
- Java OOM/GC 问题 → `@reference: capacity/jvm_skill.md`
- 接口慢/吞吐量不足 → `@reference: capacity/performance_tuning_skill.md`
- 容量规划/大促评估 → `@reference: capacity/capacity_planning_skill.md`

---

### 2.12 应急响应类 (Disaster Recovery)

用于故障应急与灾备恢复。

#### P0 - 核心应急技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **incident_response_skill** | `disaster_recovery/incident_response_skill.md` | 服务雪崩, 熔断, 降级, 限流, 应急响应, 故障止血, P0故障 | 故障应急响应与止血 |

**选择指南**：
- P0 故障/服务雪崩 → `@reference: disaster_recovery/incident_response_skill.md`

---

### 2.13 DevOps 类 (DevOps)

用于 CI/CD 与配置管理。

#### P0 - 核心 DevOps 技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **deployment_skill** | `devops/deployment_skill.md` | 部署失败, CI/CD, Jenkins, GitLab CI, K8s部署, ImagePullBackOff, CrashLoopBackOff | CI/CD 流水线与部署故障排查 |

#### P1 - 常用 DevOps 技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **config_drift_skill** | `devops/config_drift_skill.md` | 配置漂移, 配置不一致, Apollo, Nacos, ConfigMap, 环境差异, 配置中心 | 配置漂移检测与修复 |

**选择指南**：
- CI/CD 流水线/部署失败 → `@reference: devops/deployment_skill.md`
- 配置不一致/配置中心问题 → `@reference: devops/config_drift_skill.md`

---

### 2.14 系统服务类 (Systemd)

用于 Systemd 服务自启动与配置管理。

#### P0 - 核心系统服务技能

| Skill | 文件路径 | 触发关键词 | 适用场景 |
|-------|---------|-----------|---------|
| **systemd_autostart_skill** | `systemd/systemd_autostart_skill.md` | systemd, systemctl, 服务自启动, 开机启动, 服务不启动, enable, disabled, 服务恢复 | Systemd 服务自启动故障排查 |

**选择指南**：
- 服务重启后不自动启动 → `@reference: systemd/systemd_autostart_skill.md`
- systemctl enable/disable 问题 → `@reference: systemd/systemd_autostart_skill.md`
- 服务配置文件问题 → `@reference: systemd/systemd_autostart_skill.md`

---

## 3. 快速决策树

```
用户问题
    │
    ├─ 是否涉及 P0 故障/服务雪崩？
    │   ├─ 是 → incident_response_skill (应急响应)
    │   └─ 否 ↓
    │
    ├─ 是否涉及 Kubernetes/Pod？
    │   ├─ 是 → k8s_pod_skill (Pod 诊断)
    │   └─ 否 ↓
    │
    ├─ 是否涉及 CI/CD 部署？
    │   ├─ 是 → deployment_skill (部署诊断)
    │   └─ 否 ↓
    │
    ├─ 是否涉及负载均衡/SLB？
    │   ├─ 是 → lb_port_connectivity_skill (负载均衡端口连接诊断)
    │   └─ 否 ↓
    │
    ├─ 是否涉及 VPC/云网络？
    │   ├─ 是 → vpc_skill (VPC 网络诊断)
    │   └─ 否 ↓
    │
    ├─ 是否涉及网络连通性？
    │   ├─ 是 → connectivity_skill (网络诊断)
    │   └─ 否 ↓
    │
    ├─ 是否涉及 SSL 证书？
    │   ├─ 是 → ssl_certificate_skill (证书管理)
    │   └─ 否 ↓
    │
    ├─ 是否涉及安全事件/入侵？
    │   ├─ 是 → security_audit_skill (安全审计)
    │   └─ 否 ↓
    │
    ├─ 是否涉及权限拒绝/SELinux？
    │   ├─ 是 → permission_troubleshoot_skill (权限排查)
    │   └─ 否 ↓
    │
    ├─ 是否涉及 Kafka？
    │   ├─ 是 → kafka_skill (Kafka 诊断)
    │   └─ 否 ↓
    │
    ├─ 是否涉及 RabbitMQ？
    │   ├─ 是 → rabbitmq_skill (RabbitMQ 诊断)
    │   └─ 否 ↓
    │
    ├─ 是否涉及 Elasticsearch？
    │   ├─ 是 → elasticsearch_skill (ES 诊断)
    │   └─ 否 ↓
    │
    ├─ 是否涉及 Nginx？
    │   ├─ 是 → nginx_skill (Nginx 诊断)
    │   └─ 否 ↓
    │
    ├─ 是否涉及 Java/JVM？
    │   ├─ 是 → jvm_skill (JVM 诊断)
    │   └─ 否 ↓
    │
    ├─ 是否涉及性能调优/容量规划？
    │   ├─ 性能调优 → performance_tuning_skill
    │   ├─ 容量规划 → capacity_planning_skill
    │   └─ 否 ↓
    │
    ├─ 是否涉及多服务/微服务？
    │   ├─ 是 → gnn_rca_skill (根因分析)
    │   └─ 否 ↓
    │
    ├─ 是否涉及时间序列/指标预测？
    │   ├─ 是 → time_series_rca_skill (时间序列根因分析)
    │   └─ 否 ↓
    │
    ├─ 是否涉及日志异常检测？
    │   ├─ 是 → deeplog_anomaly_detection_skill (DeepLog 日志异常检测)
    │   └─ 否 ↓
    │
    ├─ 是否涉及数据库？
    │   ├─ MySQL 死锁/锁等待 → mysql_deadlock_skill
    │   ├─ MySQL 慢查询 → mysql_slow_query_skill
    │   ├─ 主从复制/高可用 → database_ha_skill
    │   ├─ PostgreSQL → postgresql_skill
    │   ├─ MongoDB → mongodb_skill
    │   └─ 否 ↓
    │
    ├─ 是否涉及 ECS/云资源？
    │   ├─ ECS 实例 → ecs_skill
    │   ├─ OSS 存储 → oss_skill
    │   └─ 否 ↓
    │
    ├─ 是否涉及 Redis？
    │   ├─ 是 → redis_skill (Redis 诊断)
    │   └─ 否 ↓
    │
    ├─ 是否涉及配置漂移/配置中心？
    │   ├─ 是 → config_drift_skill (配置漂移检测)
    │   └─ 否 ↓
    │
    ├─ 是否涉及 systemd 服务自启动？
    │   ├─ 是 → systemd_autostart_skill (服务自启动排查)
    │   └─ 否 ↓
    │
    ├─ 是否涉及 AD/域控？
    │   ├─ 是 → ad_skill (Active Directory 诊断)
    │   └─ 否 ↓
    │
    ├─ 是否涉及监控？
    │   ├─ Prometheus → prometheus_skill
    │   ├─ 日志分析 → log_analysis_skill
    │   └─ 否 ↓
    │
    ├─ 是否涉及备份恢复？
    │   ├─ 是 → backup_skill
    │   └─ 否 ↓
    │
    ├─ 是否需要连接服务器？
    │   ├─ 是 → login_skill (SSH 连接)
    │   └─ 否 ↓
    │
    └─ 单机故障排查 → debug_skill (服务器诊断)
```

### 3.1 重要提示

⚠️ **本地服务诊断注意事项**：

1. **本地 MySQL/数据库诊断**
   - 不要使用 SSH 连接本地数据库
   - Docker 环境: 使用 `docker exec` 命令
   - 本地安装: 直接执行 `mysql` 命令
   - 只有远程服务器才需要 SSH

2. **环境检测优先**
   - 所有诊断 Skill 应首先检测运行环境
   - 根据环境选择正确的命令执行方式

---

## 4. 关键词映射表

### 4.1 诊断类关键词

| 关键词 | 推荐 Skill |
|-------|-----------|
| 磁盘, 空间, disk, df, du, 内存, memory, free, OOM, CPU, 负载, load, top, 网络, 连接超时, network, 502, 504, 死锁, deadlock, SSH不通, 防火墙, CrashLoopBackOff | `diagnosis/debug_skill.md` |
| 内存, memory, free, OOM | `diagnosis/debug_skill.md` |
| CPU, 负载, load, top | `diagnosis/debug_skill.md` |
| 网络, 连接超时, network | `diagnosis/debug_skill.md` |
| 根因分析, RCA, root cause | `diagnosis/gnn_rca_skill.md` |
| GNN, 图神经网络, 拓扑 | `diagnosis/gnn_rca_skill.md` |
| 微服务, 调用链, trace | `diagnosis/gnn_rca_skill.md` |
| 死锁, deadlock | `diagnosis/mysql_deadlock_skill.md` |
| 锁等待, lock wait | `diagnosis/mysql_deadlock_skill.md` |
| 事务阻塞, transaction | `diagnosis/mysql_deadlock_skill.md` |
| 行锁, 表锁, 间隙锁 | `diagnosis/mysql_deadlock_skill.md` |
| 慢查询, slow query, SQL优化 | `diagnosis/mysql_slow_query_skill.md` |
| Redis, 缓存, 内存, key | `diagnosis/redis_skill.md` |
| 缓存穿透, 缓存击穿, 缓存雪崩 | `diagnosis/redis_skill.md` |
| AD, Active Directory, 域控 | `diagnosis/ad_skill.md` |
| LDAP, Kerberos, 域用户 | `diagnosis/ad_skill.md` |
| 域登录, 认证失败, GPO | `diagnosis/ad_skill.md` |

### 4.2 容器类关键词

| 关键词 | 推荐 Skill |
|-------|-----------|
| Pod, k8s, Kubernetes | `container/k8s_pod_skill.md` |
| 容器, CrashLoopBackOff, ImagePullBackOff | `container/k8s_pod_skill.md` |
| docker, containerd | `container/k8s_pod_skill.md` |

### 4.3 网络类关键词

| 关键词 | 推荐 Skill |
|-------|-----------|
| ping, telnet, nc, curl | `network/connectivity_skill.md` |
| DNS, 解析, 域名 | `network/connectivity_skill.md` |
| 防火墙, iptables, 端口 | `network/connectivity_skill.md` |
| 负载均衡, SLB, ALB, CLB, NLB | `network/lb_port_connectivity_skill.md` |
| 端口连不上, 健康检查失败, 后端服务器 | `network/lb_port_connectivity_skill.md` |
| 阿里云负载均衡, ECS 端口 | `network/lb_port_connectivity_skill.md` |
| SSL, 证书, HTTPS | `network/ssl_certificate_skill.md` |
| Let's Encrypt, certbot | `network/ssl_certificate_skill.md` |

### 4.4 监控类关键词

| 关键词 | 推荐 Skill |
|-------|-----------|
| 日志异常检测, DeepLog, LSTM | `monitoring/deeplog_anomaly_detection_skill.md` |
| 日志序列, 日志模式, 日志预测 | `monitoring/deeplog_anomaly_detection_skill.md` |
| Drain, 日志解析, 事件模板 | `monitoring/deeplog_anomaly_detection_skill.md` |
| Prometheus, 监控, 指标 | `monitoring/prometheus_skill.md` |
| PromQL, 告警, alert | `monitoring/prometheus_skill.md` |
| 日志, log, ELK, Loki | `monitoring/log_analysis_skill.md` |
| grep, awk, 日志分析 | `monitoring/log_analysis_skill.md` |

### 4.5 诊断类关键词（新增）

| 关键词 | 推荐 Skill |
|-------|-----------|
| 时间序列, 时序预测, 指标预测 | `diagnosis/time_series_rca_skill.md` |
| Prophet, 趋势分析, 容量规划 | `diagnosis/time_series_rca_skill.md` |
| 异常检测, 故障预测, 性能分析 | `diagnosis/time_series_rca_skill.md` |

### 4.6 备份类关键词

| 关键词 | 推荐 Skill |
|-------|-----------|
| 备份, backup, 恢复, restore | `backup/backup_skill.md` |
| mysqldump, pg_dump | `backup/backup_skill.md` |
| 快照, snapshot, 灾备 | `backup/backup_skill.md` |

### 4.7 中间件类关键词

| 关键词 | 推荐 Skill |
|-------|-----------|
| Kafka, 消息堆积, Consumer Lag, 分区, Broker | `middleware/kafka_skill.md` |
| Nginx, 502, 504, 反向代理, upstream | `middleware/nginx_skill.md` |
| RabbitMQ, 队列堆积, 死信队列, DLX, Channel | `middleware/rabbitmq_skill.md` |
| Elasticsearch, ES, 集群状态RED, 分片未分配 | `middleware/elasticsearch_skill.md` |

### 4.8 数据库类关键词

| 关键词 | 推荐 Skill |
|-------|-----------|
| 主从切换, 复制中断, IO线程, Binlog, GTID | `database/database_ha_skill.md` |
| PostgreSQL, PG, VACUUM, WAL, 膨胀, Bloat | `database/postgresql_skill.md` |
| MongoDB, 副本集, ReplicaSet, Oplog, 分片 | `database/mongodb_skill.md` |

### 4.9 安全类关键词

| 关键词 | 推荐 Skill |
|-------|-----------|
| 安全审计, SSH暴力破解, 异常登录, 入侵检测 | `security/security_audit_skill.md` |
| 权限拒绝, Permission Denied, 403, ACL, sudo, SELinux | `security/permission_troubleshoot_skill.md` |

### 4.10 云资源类关键词

| 关键词 | 推荐 Skill |
|-------|-----------|
| ECS, 实例无法连接, 安全组, 磁盘 | `cloud/ecs_skill.md` |
| VPC, 交换机, 路由表, NAT网关, 网络不通 | `cloud/vpc_skill.md` |
| OSS, 对象存储, Bucket, 上传失败, CORS | `cloud/oss_skill.md` |

### 4.11 容量类关键词

| 关键词 | 推荐 Skill |
|-------|-----------|
| JVM, OOM, GC, 堆内存, 线程dump | `capacity/jvm_skill.md` |
| 性能调优, 接口慢, RT高, 吞吐量, QPS | `capacity/performance_tuning_skill.md` |
| 容量规划, 扩容, 缩容, 资源预测, 大促 | `capacity/capacity_planning_skill.md` |

### 4.12 应急响应类关键词

| 关键词 | 推荐 Skill |
|-------|-----------|
| 服务雪崩, 熔断, 降级, 限流, 应急响应 | `disaster_recovery/incident_response_skill.md` |
| P0故障, 故障止血, 级联故障 | `disaster_recovery/incident_response_skill.md` |

### 4.13 DevOps 类关键词

| 关键词 | 推荐 Skill |
|-------|-----------|
| 部署失败, CI/CD, Jenkins, K8s部署 | `devops/deployment_skill.md` |
| 配置漂移, 配置不一致, Apollo, Nacos, ConfigMap | `devops/config_drift_skill.md` |

### 4.14 系统服务类关键词

| 关键词 | 推荐 Skill |
|-------|-----------|
| systemd, systemctl, 服务自启动, 开机启动 | `systemd/systemd_autostart_skill.md` |
| 服务不启动, 服务无法自启, enable, disabled | `systemd/systemd_autostart_skill.md` |
| 重启后服务不启动, 服务不能自动恢复 | `systemd/systemd_autostart_skill.md` |
| unit文件, service文件, daemon-reload | `systemd/systemd_autostart_skill.md` |

### 4.15 连接类关键词

| 关键词 | 推荐 Skill |
|-------|-----------|
| SSH, 登录, 远程, 凭据, 阿里云, RDS, PolarDB, DMS, 云数据库, 白名单, 安全组 | `connection/login_skill.md` |

---

## 5. Skill 文件结构

```
skills/
├── skill.md                          # 主索引文件（当前文件）
├── diagnosis/                        # 诊断类 Skill
│   ├── debug_skill.md               # 服务器故障排查 (P0)
│   ├── gnn_rca_skill.md             # GNN 根因分析 (P0)
│   ├── time_series_rca_skill.md     # 时间序列根因分析 (P0)
│   ├── mysql_deadlock_skill.md      # MySQL 死锁排查 (P0)
│   ├── mysql_slow_query_skill.md    # MySQL 慢查询分析 (P0)
│   ├── redis_skill.md               # Redis 诊断 (P1)
│   └── ad_skill.md                  # Active Directory 诊断 (P1)
├── container/                        # 容器类 Skill
│   └── k8s_pod_skill.md             # Kubernetes Pod 诊断 (P0)
├── network/                          # 网络类 Skill
│   ├── connectivity_skill.md        # 网络连通性诊断 (P0)
│   ├── lb_port_connectivity_skill.md # 阿里云负载均衡端口连接诊断 (P0)
│   └── ssl_certificate_skill.md     # SSL 证书管理 (P2)
├── monitoring/                       # 监控类 Skill
│   ├── deeplog_anomaly_detection_skill.md # DeepLog 日志异常检测 (P0)
│   ├── prometheus_skill.md          # Prometheus 监控 (P1)
│   └── log_analysis_skill.md        # 日志分析 (P1)
├── backup/                           # 备份类 Skill
│   └── backup_skill.md              # 数据备份与恢复 (P2)
├── connection/                       # 连接类 Skill
│   └── login_skill.md               # SSH 连接管理
├── middleware/                       # 中间件类 Skill
│   ├── kafka_skill.md               # Kafka 集群诊断 (P0)
│   ├── nginx_skill.md               # Nginx 诊断 (P0)
│   ├── rabbitmq_skill.md            # RabbitMQ 队列诊断 (P1)
│   └── elasticsearch_skill.md       # Elasticsearch 集群诊断 (P1)
├── database/                        # 数据库类 Skill
│   ├── database_ha_skill.md         # 数据库高可用 (P0)
│   ├── postgresql_skill.md          # PostgreSQL 诊断 (P1)
│   └── mongodb_skill.md             # MongoDB 诊断 (P1)
├── security/                        # 安全类 Skill
│   ├── security_audit_skill.md      # 安全审计 (P0)
│   └── permission_troubleshoot_skill.md # 权限排查 (P1)
├── cloud/                           # 云资源类 Skill
│   ├── ecs_skill.md                 # ECS 实例诊断 (P0)
│   ├── vpc_skill.md                 # VPC 网络诊断 (P1)
│   └── oss_skill.md                 # OSS 存储诊断 (P1)
├── capacity/                        # 容量类 Skill
│   ├── jvm_skill.md                 # JVM 诊断 (P0)
│   ├── performance_tuning_skill.md  # 性能调优 (P0)
│   └── capacity_planning_skill.md   # 容量规划 (P1)
├── disaster_recovery/               # 应急响应类 Skill
│   └── incident_response_skill.md   # 故障应急响应 (P0)
├── devops/                          # DevOps 类 Skill
│   ├── deployment_skill.md          # CI/CD 部署诊断 (P0)
│   └── config_drift_skill.md        # 配置漂移检测 (P1)
└── systemd/                         # 系统服务类 Skill
    └── systemd_autostart_skill.md   # 服务自启动排查 (P0)
```

---

## 6. 扩展指南

### 6.1 添加新 Skill

1. 确定 Skill 类别（diagnosis/connection/其他）
2. 在对应目录创建 `.md` 文件
3. 在本索引文件中添加条目
4. 更新关键词映射表
5. 更新 `skill_manager.py` 中的 `SKILL_REGISTRY`

### 6.2 Skill 文件模板

```markdown
# [Skill 名称]

## 适用场景
- 场景 1
- 场景 2

## 触发关键词
- 关键词 1
- 关键词 2

## 执行流程
1. 步骤 1
2. 步骤 2

## 工具调用
...
```

---

## 7. 权限边界

所有 Skill 执行时必须遵守以下安全规则：

### 7.1 危险命令禁止执行
- `rm -rf`, `shutdown`, `reboot`, `dd if=`, `mkfs`
- `chmod -R 777`, `curl ... | sh`
- `DROP TABLE`, `DROP DATABASE`, `TRUNCATE`

### 7.2 需要确认的操作
- 重启服务、停止容器、修改配置
- `KILL` 数据库连接
- `ALTER TABLE` 修改表结构
- `SET GLOBAL` 修改数据库配置

### 7.3 安全的只读操作
- `ls`, `cat`, `df`, `free`, `top`, `ps`, `netstat`
- `SHOW ENGINE INNODB STATUS`, `SHOW PROCESSLIST`
- 查询 `information_schema`, `performance_schema`

---

## 8. 版本信息

- 版本: 2.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team

### 更新日志

#### v2.0.0 (2025-04-08)
- 新增 7 个 Skill 分类: middleware, database, security, cloud, capacity, disaster_recovery, devops
- 新增 9 个 P0 Skills: kafka, nginx, jvm, database_ha, security_audit, ecs, incident_response, performance_tuning, deployment
- 新增 9 个 P1 Skills: rabbitmq, elasticsearch, postgresql, mongodb, vpc, oss, permission_troubleshoot, config_drift, capacity_planning
- 更新快速决策树，覆盖所有新 Skill
- 更新关键词映射表，新增 7 个分类关键词
- 更新文件结构，反映完整目录树

#### v1.2.1 (2025-04-06)
- 更新 `lb_port_connectivity_skill`: 新增 Windows 操作系统支持
- 添加 Windows PowerShell 诊断命令和快速诊断脚本
- 更新诊断报告模板，支持多操作系统

#### v1.2.0 (2025-04-06)
- 新增 `lb_port_connectivity_skill`: 阿里云负载均衡端口连接诊断技能
- 更新快速决策树，添加负载均衡判断逻辑
- 更新关键词映射表，添加负载均衡相关关键词

#### v1.1.0 (2025-04-02)
- 新增 `ad_skill`: Active Directory 诊断技能
- 维护者: AIOps Team
