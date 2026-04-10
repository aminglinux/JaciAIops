# RabbitMQ 诊断技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `RabbitMQ`, `队列堆积`, `死信队列`, `DLX`
- `Channel`, `Connection`, `Exchange`, `Binding`
- `消息丢失`, `重复消费`, `消费延迟`
- `连接泄漏`, `内存告警`, `磁盘告警`
- `集群`, `镜像队列`, `Federation`

### 1.2 适用条件
- 队列消息堆积
- 消费者连接异常 / Channel 泄漏
- 死信队列消息过多
- RabbitMQ 内存/磁盘告警
- 集群分区 / 节点异常

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 环境检测                                           │
│  - 检测 RabbitMQ 运行环境                                   │
│  - 确定连接方式与认证                                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 集群状态检查                                       │
│  - 节点状态                                                 │
│  - 集群健康                                                 │
│  - 内存/磁盘水位                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 队列分析                                           │
│  - 消息堆积队列                                             │
│  - 死信队列                                                 │
│  - 消费者状态                                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 连接与 Channel 分析                                │
│  - 连接数                                                   │
│  - Channel 泄漏                                             │
│  - 消费者分布                                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 环境检测与集群状态

```bash
# 检测 RabbitMQ 进程
ps aux | grep rabbit | grep -v grep

# 检测端口
netstat -tlnp | grep 5672 || ss -tlnp | grep 5672
netstat -tlnp | grep 15672  # 管理端口

# 集群状态
rabbitmqctl cluster_status

# 节点状态
rabbitmqctl status

# 查看内存水位
rabbitmqctl status | grep -A 5 "memory"

# 查看磁盘水位
rabbitmqctl status | grep -A 5 "disk"

# 管理界面 API
curl -u guest:guest http://localhost:15672/api/overview
curl -u guest:guest http://localhost:15672/api/nodes
```

### 3.2 队列分析

```bash
# 列出所有队列
rabbitmqctl list_queues name messages consumers durable auto_delete

# 列出队列详情 (含消息数、消费者数)
rabbitmqctl list_queues name messages messages_ready messages_unacknowledged consumers

# 查找堆积队列 (消息数 > 1000)
rabbitmqctl list_queues name messages | awk '$2 > 1000 {print}'

# 查看死信队列
rabbitmqctl list_queues name messages | grep -i "dlx\|dead\|retry"

# 查看队列内存使用
rabbitmqctl list_queues name memory

# 管理界面 API
curl -u guest:guest http://localhost:15672/api/queues | \
  python3 -c "import sys,json; queues=json.load(sys.stdin); [print(f\"{q['name']}: {q['messages']} msgs, {q['consumers']} consumers\") for q in sorted(queues, key=lambda x: x['messages'], reverse=True)[:10]]"
```

### 3.3 连接与 Channel

```bash
# 列出所有连接
rabbitmqctl list_connections name state channels user

# 连接数统计
rabbitmqctl list_connections | wc -l

# 查看 Channel 数
rabbitmqctl list_channels

# 查找空闲连接 (Channel=0)
rabbitmqctl list_connections name channels | awk '$2 == 0 {print}'

# 查看消费者列表
rabbitmqctl list_consumers

# 管理界面 API
curl -u guest:guest http://localhost:15672/api/connections | \
  python3 -c "import sys,json; conns=json.load(sys.stdin); print(f'Total: {len(conns)}'); [print(f\"{c['name']}: channels={c['channels']}, state={c['state']}\") for c in conns[:10]]"
```

### 3.4 Exchange 与 Binding

```bash
# 列出所有 Exchange
rabbitmqctl list_exchanges name type durable

# 列出所有 Binding
rabbitmqctl list_bindings source destination routing_key

# 查看特定 Exchange 的绑定
rabbitmqctl list_bindings | grep "<exchange_name>"

# 查看队列的绑定
rabbitmqctl list_bindings | grep "<queue_name>"
```

### 3.5 配置检查

```bash
# 查看内存水位线
rabbitmqctl eval 'application:get_env(rabbit, vm_memory_high_watermark).'

# 查看磁盘限制
rabbitmqctl eval 'application:get_env(rabbit, disk_free_limit).'

# 查看策略
rabbitmqctl list_policies

# 查看 VHost
rabbitmqctl list_vhosts

# 查看用户权限
rabbitmqctl list_permissions

# 查看插件
rabbitmq-plugins list -e
```

---

## 4. 常见问题与解决方案

### 4.1 队列消息堆积

**现象**: 队列消息数持续增长

**诊断步骤**:
```bash
# 1. 查看堆积队列
rabbitmqctl list_queues name messages consumers | awk '$2 > 1000 {print}'

# 2. 检查消费者状态
rabbitmqctl list_consumers | grep "<queue_name>"

# 3. 检查消费者连接
curl -u guest:guest http://localhost:15672/api/queues/%2F/<queue_name>
```

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 增加消费者 | 扩容消费服务 | 🟢 低 |
| 优化消费逻辑 | 减少单消息处理时间 | 🟢 低 |
| 临时消费者 | 快速消费堆积消息 | 🟢 低 |
| 清空队列 (紧急) | 删除并重建队列 | 🔴 高 (丢消息) |

### 4.2 内存告警

**现象**: RabbitMQ 触发内存水位线，阻塞发布

**诊断步骤**:
```bash
# 1. 查看内存使用
rabbitmqctl status | grep -A 10 "memory"

# 2. 查看内存水位线
rabbitmqctl eval 'application:get_env(rabbit, vm_memory_high_watermark).'

# 3. 查看各队列内存
rabbitmqctl list_queues name memory | sort -k2 -rn | head -10
```

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 调高水位线 | `vm_memory_high_watermark=0.6` | 🟡 中 |
| 清理堆积队列 | 消费或删除消息 | 🟡 中 |
| 惰性队列 | `x-queue-mode=lazy` | 🟢 低 |
| 升级内存 | 增加节点内存 | 🟢 低 |

### 4.3 连接泄漏

**现象**: 连接数持续增长，Channel 不释放

**诊断步骤**:
```bash
# 1. 查看连接数趋势
rabbitmqctl list_connections | wc -l

# 2. 查找空闲连接
rabbitmqctl list_connections name channels state | awk '$2 == 0 {print}'

# 3. 查看连接来源
rabbitmqctl list_connections name peer_host peer_port channels
```

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 关闭空闲连接 | `rabbitmqctl close_connection <name> "idle"` | 🟡 中 |
| 应用修复 | 检查连接池配置 | 🟢 低 (需发版) |
| 设置心跳 | `heartbeat=60` | 🟢 低 |

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
rabbitmqctl status, cluster_status
rabbitmqctl list_queues, list_connections, list_channels
curl API (GET)
```

### 5.2 需要确认的操作
```bash
rabbitmqctl close_connection
rabbitmqctl purge_queue
修改水位线配置
```

### 5.3 危险操作禁止执行
```bash
rabbitmqctl delete_queue (删除队列)
rabbitmqctl forget_cluster_node (移除集群节点)
rabbitmqctl reset (重置节点)
```

---

## 6. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
