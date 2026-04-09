# 故障排查 Skill

## 职责边界
本 Skill 定义 **"连上之后怎么查"**：标准化排查流程、诊断命令集、分析判断逻辑。
连接模板与凭据 → `@reference: connection/login_skill.md`

调用原则：先低风险（只读），后高风险（需确认）。

---

## 1. 网络排查

### 1.1 连通性异常
**触发关键词**: Connection refused, Timeout, No route to host, 网络不通

| 步骤 | 命令 | 风险 | 分析 |
|------|------|------|------|
| 基础连通性 | `ping -c 4 <TARGET_IP>` | 🟢 低 | 100% loss → 检查路由/防火墙；延迟波动 → 检查带宽 |
| 端口测试 | `nc -zv -w 3 <TARGET_IP> <PORT>` | 🟢 低 | refused → 服务未启动/防火墙拦截 |
| 路由追踪 | `traceroute -n <TARGET_IP>` 或 `mtr -r -c 10 <TARGET_IP>` | 🟢 低 | 定位网络中断点在哪一跳 |

### 1.2 DNS 解析故障
**触发关键词**: Unknown host, DNS resolution failed, 域名无法访问

```bash
nslookup <DOMAIN>          # 或 dig <DOMAIN>
cat /etc/resolv.conf       # 检查 DNS 配置
systemctl status systemd-resolved  # 检查 DNS 服务状态
```
分析: IP 返回不正确 → DNS 服务器问题或缓存污染

### 1.3 网络流量/带宽异常
**触发关键词**: 网络慢, 带宽占满, 吞吐量低

```bash
sar -n DEV 1 5             # 实时网卡流量，观察 RX/TX 是否达上限
netstat -an | awk '/^tcp/ {print $NF}' | sort | uniq -c  # TIME_WAIT / ESTABLISHED 统计
ss -s                       # 连接数摘要（比 netstat 更快）
```

---

## 2. 存储排查

### 2.1 磁盘空间不足
**触发关键词**: No space left on device, Disk full, 磁盘报警

| 步骤 | 命令 | 风险 | 分析 |
|------|------|------|------|
| 使用率概览 | `df -h` | 🟢 低 | 找 Use% > 90% 的挂载点 |
| 大文件定位 | `du -h --max-depth=1 /path | sort -hr \| head -10` | 🟢 低 | 定位最大目录 |
| 已删除未释放 | `lsof \| grep deleted` | 🟢 低 | 大文件未释放 → 重启持有进程 |
| Inode 耗尽检查 | `df -i` | 🟢 低 | IUse%=100% → 小文件过多 |

### 2.2 磁盘 I/O 性能瓶颈
**触发关键词**: I/O wait high, 磁盘读写慢, Load 飙高

```bash
iostat -x 1 3              # 关注 %iowait 和 await（await >> svctm = I/O 响应慢）
iotop -oP                  # 找读写速率最高的进程
pidstat -d 1               # 按进程统计 I/O
```

---

## 3. 系统 (VM/OS) 排查

### 3.1 CPU 负载过高
**触发关键词**: High CPU usage, Load Average High, 服务器卡顿

```bash
uptime                      # load average (1/5/15分钟)
top -bn1 | head -15         # 系统负载概览
ps -eo pid,ppid,cmd,%cpu,%mem --sort=-%cpu | head -10  # CPU Top N 进程
top -H -p <PID>            # 多线程应用：定位具体线程 ID
```

分析: load > CPU 核心数 × 2 = 过载；短期突发 vs 持续高压需区分

### 3.2 内存不足/泄漏
**触发关键词**: OOM Killer, Out of memory, Memory usage high

```bash
free -m                     # 关注 available 列
ps -eo pid,ppid,cmd,%mem --sort=-%mem | head -10  # 内存 Top N 进程
dmesg | grep -i oom         # OOM Killer 日志
cat /proc/<PID>/status | grep VmRSS  # 单进程实际内存占用
```

### 3.3 系统僵死/假死
**触发关键词**: SSH 无法连接, 系统无响应

```bash
ps aux | awk '$8 ~ /D/ {print $0}'   # D 状态进程 (Uninterruptible Sleep)，通常是 I/O 阻塞
dmesg | tail -50                      # Kernel panic / Hardware Error
vmstat 1 5                            # 查看阻塞进程和上下文切换频率
```

---

## 4. 数据库排查

### 4.1 MySQL 连接数过多/慢查询
**触发关键词**: Too many connections, Database slow, Query timeout

```bash
mysql -e "SHOW STATUS LIKE 'Threads_connected';"     # 当前连接数
mysql -e "SHOW VARIABLES LIKE 'max_connections';"    # 最大连接限制
mysql -e "SHOW FULL PROCESSLIST;"                    # 找 Time 大、State 异常的 SQL
mysql -e "SELECT * FROM information_schema.INNODB_TRX;"  # 锁等待事务
mysql -e "SHOW ENGINE INNODB STATUS\G"               # 死锁和锁信息
```

分析: Threads_connected ≈ max_connections → 连接池耗尽；Sending data/Copying to tmp table → 慢查询

### 4.2 Redis 缓存问题
**触发关键词**: Redis connection refused, 内存溢出, 缓存穿透

```bash
redis-cli info memory | grep used_memory_human    # 内存使用
redis-cli info clients                           # 连接数
redis-cli slowlog get 10                         # 慢命令日志（O(N) 命令如 keys *）
redis-cli --bigkeys                               # 大 key 排查
```

### 4.3 PostgreSQL 排查
**触发关键词**: PG connection limit, 查询超时, 锁等待

```sql
SELECT count(*) FROM pg_stat_activity;                    -- 当前连接数
SELECT * FROM pg_stat_activity WHERE state != 'idle';    -- 活跃连接
SELECT pid, query, state, wait_event_type, wait_event
  FROM pg_stat_activity WHERE wait_event_type = 'Lock';  -- 锁等待
SELECT * FROM pg_locks WHERE NOT granted;                 -- 未授予的锁
```

---

## 5. 中间件排查

### 5.1 Nginx/Web 服务异常
**触发关键词**: 502 Bad Gateway, 504 Gateway Timeout, 服务不可用

```bash
tail -n 50 /var/log/nginx/error.log        # 502=后端挂了/端口不通；504=后端超时
nginx -t                                    # 配置语法检查
netstat -nlp | grep :80                     # 进程存活 + 端口监听
curl -I http://localhost:80/health          # 健康检查端点探测
ab -n 1000 -c 10 http://localhost:80/       # 并发压力测试（可选）
```

### 5.2 消息队列积压
**触发关键词**: 消息堆积, Consumer Lag, 处理延迟

```bash
rabbitmqctl list_queues name messages consumers    # RabbitMQ: messages 积压 + consumer 存活
kafka-consumer-groups.sh --bootstrap-server <IP>:9092 \
  --describe --group <GROUP_ID>                   # Kafka: LAG 列表
```

### 5.3 JVM 应用异常
**触发关键词**: Java 进程 CPU 高, Full GC频繁, Heap Space, OOM

```bash
jstack -l <PID> > /tmp/thread_dump.txt           # 线程堆栈（配合 top -H 定位高 CPU 线程）
jmap -histo <PID> | head -20                      # 对象实例排行（找内存泄漏）
jstat -gcutil <PID> 1000 5                        # GC 统计（Full GC 频率）
jinfo -flags <PID>                                # JVM 参数确认（-Xmx/-Xms）
```

---

## 6. Kubernetes (K8s) 排查

### 6.1 Pod 启动失败/异常重启
**触发关键词**: CrashLoopBackOff, ImagePullBackOff, ErrImagePull, Pending

```bash
kubectl describe pod <POD_NAME> -n <NAMESPACE>    # 重点看 Events
kubectl logs <POD_NAME> -n <NAMESPACE> --tail=100 # 容器标准输出
kubectl logs <POD_NAME> -n <NAMESPACE> --previous  # 上一次容器日志（重启过时用）
kubectl get events -n <NAMESPACE> --sort-by='.lastTimestamp' | tail -20  # 集群事件
```

### 6.2 Service 无法访问
**触发关键词**: Service unreachable, No endpoints, Connection refused

```bash
kubectl get endpoints <SVC_NAME> -n <NAMESPACE>    # Endpoints 为空 = Selector 未匹配或 Pod NotReady
kubectl get pods -n <NAMESPACE> --show-labels      # Pod Label 检查
kubectl get svc <SVC_NAME> -n <NAMESPACE> -o wide  # Service Port/Selector 检查
```

### 6.3 节点状态异常
**触发关键词**: Node NotReady, 节点驱逐, DiskPressure

```bash
kubectl describe node <NODE_NAME>                  # Conditions: Ready/MemoryPressure/DiskPressure
systemctl status kubelet                           # Kubelet 是否运行
journalctl -u kubelet -n 50                        # Kubelet 日志
kubectl get nodes -o wide                          # 节点概览
```

---

## 7. SSH 服务深度恢复 (从 login_skill 的连通性验证延伸)

> ⚠️ 本节操作涉及服务重启、配置修改，执行前需通过 `ask_user_confirmation` 工具确认。

前置条件: login_skill 的 Step 1 (ping) ✅ + Step 2 (nc/telnet) 显示端口不通

### 7.1 认证层排查

```bash
ls -la <SSH_KEY_PATH>                              # 密钥权限应为 600
chmod 600 <SSH_KEY_PATH>                            # 修复权限
ssh -v -i <SSH_KEY_PATH> -p 22 <USER>@<HOST_IP>     # verbose 模式查看详细错误
ssh -o PreferredAuthentications=password <USER>@<HOST_IP>  # 尝试密码登录
```

### 7.2 通过备用方式登录后 — SSHD 服务恢复

当常规 SSH 不通但可通过 Workbench/VNC 登录时（见 login_skill 第 6.2 节）：

```bash
systemctl status sshd                               # 检查服务状态
journalctl -u sshd -n 30 --no-pager                # 查看 SSHD 日志中的报错
```

| 状态 | 处置 | 风险 |
|------|------|------|
| inactive/dead | `systemctl start sshd && systemctl enable sshd` | 🟡 中 |
| active (running) 但连不上 | 进入 7.3 检查防火墙 | — |

### 7.3 防火墙排查与修复

```bash
iptables -L -n -line-numbers | grep 22              # iptables 规则检查
firewall-cmd --list-ports                           # firewalld 检查
getenforce                                          # SELinux 状态
```

修复方案（需确认）:

| 方案 | 命令 | 风险 |
|------|------|------|
| iptables 放行 | `iptables -I INPUT -p tcp --dport 22 -j ACCEPT` | 🟡 中 |
| firewalld 放行 | `firewall-cmd --add-port=22/tcp --permanent && firewall-cmd --reload` | 🟡 中 |
| SELinux 临时关闭 | `setenforce 0` | 🔴 高（仅用于排查，生产环境应配置正确策略） |

### 7.4 SSHD 配置检查与修复

关键配置文件: `/etc/ssh/sshd_config`

| 配置项 | 含义 | 常见问题 |
|--------|------|----------|
| `Port 22` | 监听端口 | 改过默认端口导致连接失败 |
| `ListenAddress 0.0.0.0` | 监听地址 | 绑定了特定 IP 导致其他 IP 不可达 |
| `PasswordAuthentication yes/no` | 密码登录 | 关闭了密码但密钥也不对 |
| `PermitRootLogin yes/no/prohibit-password` | Root 登录 | 禁止 Root 登录导致无法进入 |
| `MaxAuthTries 6` | 最大认证尝试次数 | 太小导致多次重试后被 ban |

修改后重载: `systemctl reload sshd` （🟡 中风险）

### 7.5 阿里云安全组 / 白名单排查

当目标为阿里云 ECS 且端口不通时：

```bash
aliyun ecs DescribeSecurityGroupAttribute \
    --SecurityGroupId <SG_ID> \
    --region <REGION_ID> \
    --output cols=PortRange,Protocol,Policy,SourceCidrIp rows[]
```

常见原因及修复:
- 安全组未放行 22/TCP → 在控制台添加入站规则
- ECS 公网 IP 未绑定 → 检查 EIP 绑定状态
- 实例已停止 → 先在控制台启动实例

---

## 8. 阿里云 RDS/PolarDB 连接故障排查

> ⚠️ 连接模板见 `@reference: connection/login_skill.md` 第 3 节。本节聚焦"连不上"时的排查。

### 8.1 白名单排查

```bash
aliyun rds DescribeDBInstanceIPArrayList \
    --DBInstanceId <INSTANCE_ID> \
    --region cn-hangzhou
```

或通过控制台: 实例 → 数据安全性 → 白名单设置 → 确认当前出口 IP 在列表中

### 8.2 实例状态检查

```bash
aliyun rds DescribeDBInstances \
    --DBInstanceId <INSTANCE_ID> \
    --region cn-hangzhou \
    --output cols=DBInstanceId,DBInstanceStatus,Engine,EngineVersion rows[]
```

| DBInstanceStatus | 含义 | 处置 |
|------------------|------|------|
| Running | 正常 | — |
| Creating | 创建中 | 等待完成 |
| Rebooting | 重启中 | 等待完成 |
| TransingToOtherZone | 迁移中 | 等待完成 |
| DBInstanceClassChanging | 变更规格中 | 等待完成 |

### 8.3 SSL/TLS 问题

```bash
wget https://downloads.mysql.com/docs/sandbox-ca.pem -O /etc/mysql/certs/ca.pem
mysql -h {{ rds_host }} -P {{ rds_port }} -u {{ rds_user }} -p'{{ rds_pass }}' \
      --ssl-ca=/etc/mysql/certs/ca.pem --ssl-mode=VERIFY_IDENTITY {{ rds_db_name }}
```

### 8.4 连接池耗尽

```sql
SHOW STATUS LIKE 'Threads_connected';
SHOW VARIABLES LIKE 'max_connections';
SHOW PROCESSLIST;
KILL <PROCESS_ID>;    -- ⚠️ 需确认后才执行
```

Python 连接池优化建议:
```python
engine = create_engine(url,
    pool_size=5, max_overflow=10, pool_timeout=30,
    pool_recycle=1800, pool_pre_ping=True)
```

---

## 风险等级说明

| 等级 | 图标 | 说明 | 示例 |
|------|------|------|------|
| 低 | 🟢 | 只读查询，无副作用 | `df -h`, `ps aux`, `show processlist` |
| 中 | 🟡 | 可能影响服务可用性 | `systemctl restart`, `iptables -I`, KILL 连接 |
| 高 | 🔴 | 数据丢失风险或安全降级 | `setenforce 0`, `DROP TABLE`, `rm -rf` |
