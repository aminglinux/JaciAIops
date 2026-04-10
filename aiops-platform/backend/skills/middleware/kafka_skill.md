# Kafka 诊断技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `Kafka`, `消息队列`, `消息堆积`, `消费延迟`, `Lag`
- `Partition`, `Broker`, `Producer`, `Consumer`
- `Offset`, `Rebalance`, `ISR`, `副本同步`
- `消息丢失`, `重复消费`, `乱序`

### 1.2 适用条件
- Kafka 消息堆积 / 消费延迟
- Broker 宕机或不可用
- 分区 Leader 选举异常
- 消费者 Rebalance 风暴
- 副本同步滞后 (ISR 收缩)
- 生产者发送失败 / 超时

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 环境检测                                           │
│  - 检测 Kafka 运行环境 (Docker/K8s/裸机/阿里云)            │
│  - 确定连接方式与认证机制                                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 集群健康检查                                       │
│  - Broker 在线状态                                          │
│  - Controller 状态                                          │
│  - 集群元数据                                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Topic 与分区分析                                   │
│  - 分区 Leader 分布                                         │
│  - ISR 状态                                                 │
│  - 副本同步延迟                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 消费者组分析                                       │
│  - 消费 Lag                                                │
│  - Consumer 状态                                            │
│  - Rebalance 历史                                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 生产者与网络分析                                   │
│  - 发送延迟 / 错误率                                        │
│  - 网络吞吐                                                │
│  - 磁盘 IO                                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 环境检测

```bash
# 检测 Kafka 进程
ps aux | grep kafka | grep -v grep

# 检测 Kafka 端口
netstat -tlnp | grep 9092 || ss -tlnp | grep 9092

# 检测 Docker 容器
docker ps | grep kafka

# 检测 K8s Pod
kubectl get pods -A | grep kafka

# 检测 kafka 安装路径
find / -name "kafka-topics.sh" 2>/dev/null
```

### 3.2 集群健康检查

```bash
# 列出所有 Broker
kafka-broker-api-versions --bootstrap-server localhost:9092

# 查看集群元数据
kafka-metadata-quorum --bootstrap-server localhost:9092 describe --status

# 查看集群 ID
kafka-cluster --bootstrap-server localhost:9092 cluster-id

# 查看 Controller
kafka-metadata --bootstrap-server localhost:9092 describe --status

# 检查 Broker 配置
kafka-configs --bootstrap-server localhost:9092 --describe --broker 0

# JMX 指标 (需开启 JMX)
# Broker 在线数: kafka.controller:type=KafkaController,name=ActiveControllerCount
# 离线分区数: kafka.controller:type=KafkaController,name=OfflinePartitionsCount
```

### 3.3 Topic 与分区分析

```bash
# 列出所有 Topic
kafka-topics --bootstrap-server localhost:9092 --list

# 查看 Topic 详情
kafka-topics --bootstrap-server localhost:9092 --describe --topic <topic_name>

# 查看所有 Topic 的分区详情 (重点关注 Under-Replicated)
kafka-topics --bootstrap-server localhost:9092 --describe --under-replicated-partitions

# 查看离线分区
kafka-topics --bootstrap-server localhost:9092 --describe --unavailable-partitions

# 查看 Topic 配置
kafka-configs --bootstrap-server localhost:9092 --describe --topic <topic_name>

# 查看 Topic 大小 (需要 kafka-log-dirs)
kafka-log-dirs --bootstrap-server localhost:9092 --describe --topic-list <topic_name>
```

### 3.4 消费者组分析

```bash
# 列出所有消费者组
kafka-consumer-groups --bootstrap-server localhost:9092 --list

# 查看消费者组详情 (Lag)
kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group <group_id>

# 查看所有消费者组的 Lag 汇总
for group in $(kafka-consumer-groups --bootstrap-server localhost:9092 --list); do
  echo "=== Group: $group ==="
  kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group $group 2>/dev/null
done

# 查看消费者组 Offset
kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group <group_id> --verbose

# 查看消费者组状态
kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group <group_id> --state

# 查看消费者组成员
kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group <group_id> --members
```

### 3.5 生产者与性能分析

```bash
# 生产者性能测试
kafka-producer-perf-test --topic test --num-records 1000 --record-size 1024 \
  --throughput -1 --producer-props bootstrap.servers=localhost:9092

# 消费者性能测试
kafka-consumer-perf-test --topic test --messages 1000 \
  --bootstrap-server localhost:9092

# 查看磁盘使用
du -sh /kafka/data/*

# 查看 Broker 日志 (最近错误)
tail -100 /kafka/logs/server.log | grep -i "error\|warn\|exception"

# 网络连接数
netstat -an | grep :9092 | wc -l
```

### 3.6 阿里云 Kafka (SLS Kafka 兼容)

```bash
# 使用阿里云 CLI 查询 Kafka 实例
aliyun alikafka ListInstance --RegionId cn-hangzhou

# 查看 Topic 列表
aliyun alikafka ListTopic --RegionId cn-hangzhou --InstanceId alikafka_post-cn-xxx

# 查看消费者组
aliyun alikafka ListConsumerGroup --RegionId cn-hangzhou --InstanceId alikafka_post-cn-xxx

# 查看 Topic 状态
aliyun alikafka GetTopicStatus --RegionId cn-hangzhou --InstanceId alikafka_post-cn-xxx --Topic topic_name
```

---

## 4. 常见问题与解决方案

### 4.1 消息堆积 (Consumer Lag 过高)

**现象**: 消费者组 Lag 持续增长，消息处理延迟

**诊断步骤**:
```bash
# 1. 查看 Lag
kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group <group_id>

# 2. 检查消费者数量 vs 分区数
kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group <group_id> --members

# 3. 检查 Topic 分区数
kafka-topics --bootstrap-server localhost:9092 --describe --topic <topic_name>
```

**解决方案**:
| 方案 | 操作 | 风险 |
|------|------|------|
| 扩容消费者 | 增加消费者实例数 (≤分区数) | 🟢 低 |
| 增加分区 | `kafka-topics --alter --topic <t> --partitions <n>` | 🟡 中 (不可减少) |
| 跳过堆积 | 重置 Offset 到最新 | 🟡 中 (丢消息) |
| 临时消费者 | 启动独立消费者快速消费 | 🟢 低 |

### 4.2 Broker 宕机

**现象**: Broker 下线，分区 Leader 切换

**诊断步骤**:
```bash
# 1. 检查 Broker 列表
kafka-broker-api-versions --bootstrap-server localhost:9092

# 2. 检查 Under-Replicated 分区
kafka-topics --bootstrap-server localhost:9092 --describe --under-replicated-partitions

# 3. 检查离线分区
kafka-topics --bootstrap-server localhost:9092 --describe --unavailable-partitions

# 4. 检查 Broker 日志
tail -200 /kafka/logs/server.log | grep -i "error\|shutdown\|fatal"
```

**解决方案**:
| 方案 | 操作 | 风险 |
|------|------|------|
| 重启 Broker | 重启 Kafka 进程/容器 | 🟡 中 |
| 手动 Leader 切换 | `kafka-leader-election` | 🟡 中 |
| 优先副本选举 | `kafka-preferred-replica-election` | 🟢 低 |

### 4.3 Rebalance 风暴

**现象**: 消费者组频繁 Rebalance，消费暂停

**诊断步骤**:
```bash
# 1. 查看消费者组状态
kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group <group_id> --state

# 2. 检查消费者心跳配置
kafka-configs --bootstrap-server localhost:9092 --describe --entity-type clients

# 3. 检查消费者日志
grep -i "rebalance\|revoked\|assigned" /app/logs/consumer.log | tail -50
```

**解决方案**:
| 方案 | 配置 | 风险 |
|------|------|------|
| 增大 Session Timeout | `session.timeout.ms=30000` | 🟢 低 |
| 增大 Heartbeat 间隔 | `heartbeat.interval.ms=10000` | 🟢 低 |
| 增大 Max Poll 间隔 | `max.poll.interval.ms=600000` | 🟢 低 |
| 减少 Max Poll Records | `max.poll.records=100` | 🟢 低 |
| 使用 Sticky 分配器 | `partition.assignment.strategy=sticky` | 🟢 低 |

### 4.4 消息丢失

**现象**: 生产者发送成功但消费者未收到

**诊断步骤**:
```bash
# 1. 检查生产者 ACK 配置
# acks=all 确保消息写入所有 ISR

# 2. 检查 Topic 副本因子
kafka-topics --bootstrap-server localhost:9092 --describe --topic <topic_name>

# 3. 检查 ISR 状态
kafka-topics --bootstrap-server localhost:9092 --describe --under-replicated-partitions

# 4. 检查 min.insync.replicas
kafka-configs --bootstrap-server localhost:9092 --describe --topic <topic_name>
```

**解决方案**:
| 方案 | 配置 | 风险 |
|------|------|------|
| 生产者 ACK=all | `acks=all` | 🟢 低 |
| 副本因子 ≥3 | `replication.factor=3` | 🟢 低 |
| min.insync.replicas=2 | `min.insync.replicas=2` | 🟢 低 |
| 启用幂等生产者 | `enable.idempotence=true` | 🟢 低 |

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
kafka-topics --list, --describe
kafka-consumer-groups --list, --describe
kafka-broker-api-versions
kafka-configs --describe
```

### 5.2 需要确认的操作
```bash
kafka-topics --alter (增加分区)
kafka-consumer-groups --reset-offsets
kafka-preferred-replica-election
kafka-leader-election
```

### 5.3 危险操作禁止执行
```bash
kafka-topics --delete (删除 Topic)
kafka-consumer-groups --delete (删除消费者组)
kafka-reassign-partitions (分区重分配, 需专项审批)
```

---

## 6. 快速诊断脚本

```bash
#!/bin/bash
BOOTSTRAP="${1:-localhost:9092}"

echo "=== Kafka 集群状态 ==="
kafka-broker-api-versions --bootstrap-server $BOOTSTRAP 2>&1 | head -5

echo -e "\n=== Under-Replicated 分区 ==="
kafka-topics --bootstrap-server $BOOTSTRAP --describe --under-replicated-partitions 2>&1

echo -e "\n=== 消费者组 Lag Top 10 ==="
for group in $(kafka-consumer-groups --bootstrap-server $BOOTSTRAP --list 2>/dev/null); do
  lag=$(kafka-consumer-groups --bootstrap-server $BOOTSTRAP --describe --group $group 2>/dev/null | tail -n +2 | awk '{sum+=$5} END {print sum+0}')
  if [ "$lag" -gt 0 ]; then
    echo "Group: $group, Total Lag: $lag"
  fi
done | sort -t: -k3 -n -r | head -10

echo -e "\n=== Topic 列表 ==="
kafka-topics --bootstrap-server $BOOTSTRAP --list 2>&1
```

---

## 7. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
