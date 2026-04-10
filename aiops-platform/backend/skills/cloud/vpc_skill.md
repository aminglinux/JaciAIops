# 阿里云 VPC 网络诊断技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `VPC`, `交换机`, `路由表`, `vSwitch`
- `NAT网关`, `对等连接`, `云企业网`, `CEN`
- `VPN`, `专线`, `智能接入网关`
- `网络不通`, `跨VPC`, `私网访问`
- `安全组`, `网络ACL`, `流量镜像`

### 1.2 适用条件
- VPC 内网络不通
- 跨 VPC 通信问题
- NAT 网关配置问题
- 路由表配置错误
- VPN/专线连接问题

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 确认网络拓扑                                       │
│  - VPC ID / 交换机 / 路由表                                │
│  - 源端和目标端信息                                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 实例网络配置检查                                   │
│  - 弹性网卡 (ENI)                                          │
│  - 私网 IP / 公网 IP                                       │
│  - 安全组规则                                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 路由表检查                                         │
│  - 路由条目                                                 │
│  - 下一跳类型                                               │
│  - 路由优先级                                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 跨 VPC / 外网连通性                                │
│  - 对等连接 / CEN                                           │
│  - NAT 网关                                                 │
│  - VPN 网关                                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 VPC 基础查询

```bash
# 查询 VPC 列表
aliyun vpc DescribeVpcs --RegionId cn-hangzhou

# 查询 VPC 详情
aliyun vpc DescribeVpcAttribute --RegionId cn-hangzhou --VpcId vpc-xxx

# 查询交换机
aliyun vpc DescribeVSwitches --RegionId cn-hangzhou --VpcId vpc-xxx

# 查询路由表
aliyun vpc DescribeRouteTables --RegionId cn-hangzhou --VRouterId vrt-xxx

# 查询路由条目
aliyun vpc DescribeRouteEntryList --RegionId cn-hangzhou --RouteTableId vtb-xxx

# 查询网络 ACL
aliyun vpc DescribeNetworkAcls --RegionId cn-hangzhou --VpcId vpc-xxx
```

### 3.2 安全组检查

```bash
# 查询安全组规则
aliyun ecs DescribeSecurityGroupAttribute --RegionId cn-hangzhou \
  --SecurityGroupId sg-xxx --Direction ingress

# 查询安全组引用
aliyun ecs DescribeSecurityGroups --RegionId cn-hangzhou \
  --SecurityGroupIds '["sg-xxx"]'

# 查询实例安全组
aliyun ecs DescribeInstanceAttribute --RegionId cn-hangzhou \
  --InstanceId i-bp1xxx | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('SecurityGroupIds',{}))"
```

### 3.3 NAT 网关

```bash
# 查询 NAT 网关
aliyun vpc DescribeNatGateways --RegionId cn-hangzhou --VpcId vpc-xxx

# 查询 DNAT 条目
aliyun vpc DescribeForwardTableEntries --RegionId cn-hangzhou --ForwardTableId ftb-xxx

# 查询 SNAT 条目
aliyun vpc DescribeSnatTableEntries --RegionId cn-hangzhou --SnatTableId stb-xxx

# 查询弹性 IP
aliyun vpc DescribeEipAddresses --RegionId cn-hangzhou
```

### 3.4 跨 VPC 连接

```bash
# 查询对等连接
aliyun vpc DescribeVpcPeers --RegionId cn-hangzhou

# 查询云企业网 (CEN)
aliyun cen DescribeCens
aliyun cen DescribeCenAttachedInstances --CenId cen-xxx

# 查询 VPN 网关
aliyun vpc DescribeVpnGateways --RegionId cn-hangzhou

# 查询 VPN 连接
aliyun vpc DescribeVpnConnections --RegionId cn-hangzhou --VpnGatewayId vpn-xxx
```

### 3.5 网络连通性测试

```bash
# 实例内测试
ping <target_ip>
traceroute <target_ip>
telnet <target_ip> <port>
nc -zv <target_ip> <port>

# 阿里云网络智能服务
aliyun nis GetNetworkReachableAnalysis --RegionId cn-hangzhou \
  --Source '{"IpAddress":"10.0.0.1","NetworkType":"VPC","NetworkId":"vpc-xxx"}' \
  --Destination '{"IpAddress":"10.1.0.1","NetworkType":"VPC","NetworkId":"vpc-yyy","Port":"80"}'
```

---

## 4. 常见问题与解决方案

### 4.1 VPC 内网络不通

**诊断步骤**:
```bash
# 1. 检查安全组
aliyun ecs DescribeSecurityGroupAttribute --RegionId cn-hangzhou --SecurityGroupId sg-xxx --Direction ingress

# 2. 检查路由表
aliyun vpc DescribeRouteEntryList --RegionId cn-hangzhou --RouteTableId vtb-xxx

# 3. 检查网络 ACL
aliyun vpc DescribeNetworkAcls --RegionId cn-hangzhou --VpcId vpc-xxx
```

**常见原因**:

| 原因 | 诊断方法 | 解决方案 |
|------|---------|---------|
| 安全组未放行 | 检查入方向规则 | 添加安全组规则 |
| 路由缺失 | 检查路由表条目 | 添加路由条目 |
| 网络 ACL 拒绝 | 检查 ACL 规则 | 修改 ACL 规则 |
| 交换机 IP 耗尽 | 检查可用 IP 数 | 创建新交换机 |

### 4.2 跨 VPC 不通

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 对等连接 | 创建 VPC 对等连接 + 添加路由 | 🟢 低 |
| 云企业网 | CEN 加载 VPC + 路由发布 | 🟢 低 |
| VPN 网关 | 建立 IPsec VPN | 🟡 中 |

### 4.3 无法访问外网

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| NAT 网关 | 创建 NAT + SNAT 条目 | 🟢 低 |
| 弹性 IP | 绑定 EIP 到实例 | 🟢 低 |
| 路由配置 | 添加 0.0.0.0/0 路由到 NAT | 🟢 低 |

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
DescribeVpcs, DescribeVSwitches, DescribeRouteTables
DescribeSecurityGroupAttribute, DescribeNatGateways
DescribeNetworkAcls
```

### 5.2 需要确认的操作
```bash
AuthorizeSecurityGroup (添加安全组规则)
CreateRouteEntry (添加路由)
CreateSnatEntry (创建 SNAT)
```

### 5.3 危险操作禁止执行
```bash
DeleteVpc, DeleteVSwitch
DeleteRouteEntry (可能导致断网)
RevokeSecurityGroup (可能导致断连)
DeleteNatGateway
```

---

## 6. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
