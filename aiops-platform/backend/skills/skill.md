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
| **debug_skill** | `diagnosis/debug_skill.md` | 磁盘, 内存, CPU, 网络, 故障, 排查 | 单机服务器故障排查 |
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
| **login_skill** | `connection/login_skill.md` | SSH, 连接, 登录, 远程, 凭据 | SSH 连接管理 |

**选择指南**：
- 需要连接服务器 → `@reference: connection/login_skill.md`

---

## 3. 快速决策树

```
用户问题
    │
    ├─ 是否涉及 Kubernetes/Pod？
    │   ├─ 是 → k8s_pod_skill (Pod 诊断)
    │   └─ 否 ↓
    │
    ├─ 是否涉及负载均衡/SLB？
    │   ├─ 是 → lb_port_connectivity_skill (负载均衡端口连接诊断)
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
    │   └─ 否 ↓
    │
    ├─ 是否涉及 Redis？
    │   ├─ 是 → redis_skill (Redis 诊断)
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
| 磁盘, 空间, disk, df, du | `diagnosis/debug_skill.md` |
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

### 4.6 连接类关键词

| 关键词 | 推荐 Skill |
|-------|-----------|
| SSH, 登录, 远程, 凭据 | `connection/login_skill.md` |

---

## 5. Skill 文件结构

```
skills/
├── skill.md                          # 主索引文件（当前文件）
├── diagnosis/                        # 诊断类 Skill
│   ├── debug_skill.md               # 服务器故障排查 (P0)
│   ├── gnn_rca_skill.md             # GNN 根因分析 (P0)
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
│   ├── prometheus_skill.md          # Prometheus 监控 (P1)
│   └── log_analysis_skill.md        # 日志分析 (P1)
├── backup/                           # 备份类 Skill
│   └── backup_skill.md              # 数据备份与恢复 (P2)
└── connection/                       # 连接类 Skill
    └── login_skill.md               # SSH 连接管理
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

- 版本: 1.2.2
- 更新时间: 2025-04-06
- 维护者: AIOps Team

### 更新日志

#### v1.2.2 (2025-04-06)
- 更新 `lb_port_connectivity_skill`: 新增远程云服务诊断支持
- 添加阿里云 CLI 环境检测和配置说明
- 支持通过阿里云 API 远程诊断 SLB 实例

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
