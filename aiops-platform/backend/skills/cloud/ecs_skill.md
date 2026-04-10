# 阿里云 ECS 实例诊断技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `ECS`, `实例`, `云服务器`, `阿里云`
- `磁盘扩容`, `安全组`, `自动恢复`
- `实例重启`, `系统事件`, `抢占式实例`
- `快照`, `镜像`, `实例规格`
- `无法连接`, `VNC`, `Workbench`

### 1.2 适用条件
- ECS 实例无法连接
- 磁盘空间不足 / 需要扩容
- 安全组规则问题
- 系统事件 (重启/迁移)
- 实例性能异常
- 实例状态异常 (停止/错误)

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 实例状态确认                                       │
│  - 通过 API 查询实例状态                                    │
│  - 确认实例 ID 和区域                                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 系统事件检查                                       │
│  - 计划内维护事件                                           │
│  - 突发重启事件                                             │
│  - 实例自动恢复事件                                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 网络与安全组检查                                   │
│  - 安全组入/出规则                                          │
│  - VPC / 交换机配置                                         │
│  - 公网 IP / 弹性 IP 状态                                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 磁盘与存储检查                                     │
│  - 磁盘使用率                                               │
│  - 云盘类型与性能                                           │
│  - 快照状态                                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 实例性能检查                                       │
│  - CPU / 内存使用率                                         │
│  - 实例规格是否匹配负载                                     │
│  - 网络带宽使用                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 实例状态查询

```bash
# 查询 ECS 实例列表
aliyun ecs DescribeInstances --RegionId cn-hangzhou

# 查询指定实例详情
aliyun ecs DescribeInstances --RegionId cn-hangzhou \
  --InstanceIds '["i-bp1xxxxxxxxx"]'

# 查询实例状态
aliyun ecs DescribeInstanceStatus --RegionId cn-hangzhou

# 查询实例 VNC 地址 (用于远程控制台)
aliyun ecs DescribeInstanceVncUrl --RegionId cn-hangzhou --InstanceId i-bp1xxxxxxxxx

# 查询实例自动恢复事件
aliyun ecs DescribeInstanceAutoRecoveryAttribute --RegionId cn-hangzhou --InstanceId i-bp1xxxxxxxxx
```

### 3.2 系统事件检查

```bash
# 查询实例系统事件
aliyun ecs DescribeInstanceHistoryEvents --RegionId cn-hangzhou \
  --InstanceId i-bp1xxxxxxxxx

# 查询计划内维护事件
aliyun ecs DescribeInstanceMaintenanceAttributes --RegionId cn-hangzhou \
  --InstanceId i-bp1xxxxxxxxx

# 查询最近重启事件
aliyun ecs DescribeInstanceHistoryEvents --RegionId cn-hangzhou \
  --InstanceId i-bp1xxxxxxxxx --EventCycleStatus Executed

# 查询突发事件
aliyun ecs DescribeInstanceHistoryEvents --RegionId cn-hangzhou \
  --InstanceId i-bp1xxxxxxxxx --EventIdType SystemMaintenance.Reboot
```

### 3.3 安全组检查

```bash
# 查询实例绑定的安全组
aliyun ecs DescribeInstanceAttribute --RegionId cn-hangzhou \
  --InstanceId i-bp1xxxxxxxxx | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('SecurityGroupIds',{}).get('SecurityGroupId',[]))"

# 查询安全组规则
aliyun ecs DescribeSecurityGroupAttribute --RegionId cn-hangzhou \
  --SecurityGroupId sg-xxx --Direction ingress

aliyun ecs DescribeSecurityGroupAttribute --RegionId cn-hangzhou \
  --SecurityGroupId sg-xxx --Direction egress

# 查询安全组引用 (哪些实例在使用)
aliyun ecs DescribeSecurityGroups --RegionId cn-hangzhou \
  --SecurityGroupId sg-xxx

# 检查 SSH 端口是否放行
aliyun ecs DescribeSecurityGroupAttribute --RegionId cn-hangzhou \
  --SecurityGroupId sg-xxx --Direction ingress | \
  python3 -c "import sys,json; rules=json.load(sys.stdin).get('Permissions',{}).get('Permission',[]); ssh_rules=[r for r in rules if '22' in str(r.get('PortRange',''))]; print(json.dumps(ssh_rules, indent=2, ensure_ascii=False))"
```

### 3.4 磁盘与存储

```bash
# 查询实例磁盘
aliyun ecs DescribeDisks --RegionId cn-hangzhou \
  --InstanceId i-bp1xxxxxxxxx

# 查询磁盘详情
aliyun ecs DescribeDisks --RegionId cn-hangzhou \
  --DiskId d-bp1xxxxxxxxx

# 查询快照列表
aliyun ecs DescribeSnapshots --RegionId cn-hangzhou \
  --InstanceId i-bp1xxxxxxxxx

# 查询磁盘性能 (CloudMonitor)
aliyun cms QueryMetricList --Project acs_ecs_dashboard \
  --Metric DiskIOPSRead --Dimensions '{"instanceId":"i-bp1xxxxxxxxx"}' \
  --Period 60 --StartTime "$(date -d '1 hour ago' +%Y-%m-%d %H:%M:%S)"

# 磁盘扩容 (需确认)
# 1. 在控制台/CLI 扩容云盘
# aliyun ecs ResizeDisk --DiskId d-bp1xxx --NewSize 200
# 2. 在实例内扩展分区和文件系统
# growpart /dev/vda 1
# resize2fs /dev/vda1  (ext4)
# xfs_growfs /          (xfs)
```

### 3.5 实例性能监控

```bash
# CPU 使用率
aliyun cms QueryMetricList --Project acs_ecs_dashboard \
  --Metric CPUUtilization --Dimensions '{"instanceId":"i-bp1xxxxxxxxx"}' \
  --Period 60 --StartTime "$(date -d '1 hour ago' +%Y-%m-%d %H:%M:%S)"

# 内存使用率 (需安装 CloudMonitor 插件)
aliyun cms QueryMetricList --Project acs_ecs_dashboard \
  --Metric memory_usedutilization --Dimensions '{"instanceId":"i-bp1xxxxxxxxx"}' \
  --Period 60 --StartTime "$(date -d '1 hour ago' +%Y-%m-%d %H:%M:%S)"

# 网络流量
aliyun cms QueryMetricList --Project acs_ecs_dashboard \
  --Metric VPC_PublicIP_InternetInRate --Dimensions '{"instanceId":"i-bp1xxxxxxxxx"}' \
  --Period 60 --StartTime "$(date -d '1 hour ago' +%Y-%m-%d %H:%M:%S)"

# 实例内部检查
df -h
free -m
top -b -n 1 | head -20
iostat -x 1 3
```

---

## 4. 常见问题与解决方案

### 4.1 ECS 实例无法连接

**现象**: SSH 无法连接 ECS 实例

**诊断步骤**:
```bash
# 1. 检查实例状态
aliyun ecs DescribeInstanceStatus --RegionId cn-hangzhou | grep "i-bp1xxx"

# 2. 检查安全组 SSH 端口
aliyun ecs DescribeSecurityGroupAttribute --RegionId cn-hangzhou \
  --SecurityGroupId sg-xxx --Direction ingress

# 3. 检查公网 IP
aliyun ecs DescribeInstances --RegionId cn-hangzhou \
  --InstanceIds '["i-bp1xxx"]' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['Instances']['Instance'][0].get('PublicIpAddress',{}))"

# 4. 本地网络测试
ping <public_ip>
telnet <public_ip> 22
```

**常见原因与解决方案**:

| 原因 | 诊断方法 | 解决方案 |
|------|---------|---------|
| 实例已停止 | API 返回 Stopped | 启动实例 |
| 安全组未放行 22 端口 | 检查安全组规则 | 添加入方向规则 |
| 无公网 IP | 检查 EIP/公网带宽 | 绑定弹性公网 IP |
| 实例内部 SSH 服务停止 | VNC 登录检查 | 启动 sshd |
| 密码/密钥错误 | 检查认证方式 | 重置密码或更换密钥 |

### 4.2 磁盘空间不足

**现象**: 磁盘使用率 > 85%

**诊断步骤**:
```bash
# 1. 查看磁盘使用
df -h

# 2. 查看大文件
du -sh /* 2>/dev/null | sort -rh | head -10

# 3. 查看云盘信息
aliyun ecs DescribeDisks --RegionId cn-hangzhou --InstanceId i-bp1xxx
```

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 清理日志 | `find /var/log -name "*.gz" -mtime +30 -delete` | 🟢 低 |
| 清理缓存 | `apt clean` / `yum clean all` | 🟢 低 |
| 云盘扩容 | API 扩容 + resize2fs | 🟡 中 |
| 挂载新云盘 | 创建并挂载新云盘 | 🟢 低 |
| 对象存储归档 | 冷数据迁移到 OSS | 🟢 低 |

### 4.3 安全组误配

**现象**: 服务端口无法访问

**诊断步骤**:
```bash
# 1. 查看安全组规则
aliyun ecs DescribeSecurityGroupAttribute --RegionId cn-hangzhou \
  --SecurityGroupId sg-xxx --Direction ingress

# 2. 本地端口测试
telnet <ip> <port>
curl -v http://<ip>:<port>
```

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 添加入方向规则 | API 添加安全组规则 | 🟡 中 (需指定最小范围) |
| 修改现有规则 | API 修改规则 | 🟡 中 |
| 切换安全组 | 实例更换安全组 | 🟡 中 |

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
DescribeInstances, DescribeDisks, DescribeSnapshots
DescribeSecurityGroupAttribute, DescribeInstanceStatus
QueryMetricList (CloudMonitor)
```

### 5.2 需要确认的操作
```bash
StartInstance, StopInstance, RebootInstance
ResizeDisk (磁盘扩容)
AuthorizeSecurityGroup (添加安全组规则)
AttachDisk (挂载云盘)
```

### 5.3 危险操作禁止执行
```bash
DeleteInstance (释放实例)
DeleteDisk (删除云盘)
RevokeSecurityGroup (删除安全组规则, 可能断开连接)
ReplaceSystemDisk (更换系统盘, 数据丢失)
```

---

## 6. 快速诊断脚本

```bash
#!/bin/bash
INSTANCE_ID="${1}"
REGION="${2:-cn-hangzhou}"

if [ -z "$INSTANCE_ID" ]; then
  echo "Usage: $0 <instance_id> [region]"
  exit 1
fi

echo "=== 实例状态 ==="
aliyun ecs DescribeInstances --RegionId $REGION \
  --InstanceIds "[\"$INSTANCE_ID\"]" 2>/dev/null | \
  python3 -c "import sys,json; d=json.load(sys.stdin); i=d['Instances']['Instance'][0]; print(f\"Status: {i['Status']}\nIP: {i.get('PublicIpAddress',{}).get('IpAddress',[])}\nVPC: {i.get('VpcAttributes',{}).get('VpcId','N/A')}\")"

echo -e "\n=== 系统事件 ==="
aliyun ecs DescribeInstanceHistoryEvents --RegionId $REGION --InstanceId $INSTANCE_ID 2>/dev/null | \
  python3 -c "import sys,json; events=json.load(sys.stdin).get('InstanceSystemEventSet',{}).get('InstanceSystemEventType',[]); [print(f\"{e.get('EventId','')}: {e.get('EventType','')} - {e.get('EventCycleStatus',{}).get('Name','')}\") for e in events[:5]]" 2>/dev/null

echo -e "\n=== 磁盘信息 ==="
aliyun ecs DescribeDisks --RegionId $REGION --InstanceId $INSTANCE_ID 2>/dev/null | \
  python3 -c "import sys,json; disks=json.load(sys.stdin).get('Disks',{}).get('Disk',[]); [print(f\"{d['DiskId']}: {d['Size']}GB ({d['Category']}) - {d['Status']}\") for d in disks]" 2>/dev/null

echo -e "\n=== 安全组 ==="
aliyun ecs DescribeInstanceAttribute --RegionId $REGION --InstanceId $INSTANCE_ID 2>/dev/null | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('SecurityGroupIds',{}).get('SecurityGroupId',[]))" 2>/dev/null
```

---

## 7. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
