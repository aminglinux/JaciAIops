# 故障应急响应与止血技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `故障响应`, `应急`, `封网`, `止血`
- `降级`, `熔断`, `限流`, `回滚`
- `P0故障`, `线上故障`, `服务不可用`
- `雪崩`, `级联故障`, `全站不可用`
- `流量突增`, `超卖`, `容量不足`

### 1.2 适用条件
- P0/P1 线上故障，需要立即止血
- 服务雪崩 / 级联故障
- 流量突增导致系统过载
- 发布后故障需要回滚
- 数据库/中间件故障影响核心链路

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 故障定级与通报                                     │
│  - 确认故障等级 (P0/P1/P2)                                 │
│  - 通报相关方                                               │
│  - 启动应急响应                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 快速止血 (黄金 5 分钟)                             │
│  - 限流 / 降级 / 熔断                                      │
│  - 流量调度 / 切流                                          │
│  - 回滚最近变更                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 影响面评估                                         │
│  - 受影响服务/用户范围                                      │
│  - 数据一致性检查                                           │
│  - 上下游依赖状态                                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 根因定位                                           │
│  - 时间线梳理                                               │
│  - 变更关联分析                                             │
│  - 日志/指标/链路分析                                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 修复与恢复                                         │
│  - 执行修复方案                                             │
│  - 逐步恢复流量                                             │
│  - 验证服务正常                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 复盘与改进                                         │
│  - 故障报告                                                 │
│  - 改进措施                                                 │
│  - 监控告警优化                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 快速止血 — 限流

```bash
# Nginx 限流 (紧急)
# 限制单 IP 请求速率
# 在 nginx.conf 中添加:
# limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/s;
# limit_req zone=api_limit burst=200 nodelay;

# 查看当前 QPS
tail -10000 /var/log/nginx/access.log | awk -v start="$(date -d '1 min ago' +%d/%b/%Y:%H:%M)" \
  -v end="$(date +%d/%b/%Y:%H:%M)" '$4 ~ start || $4 ~ end' | wc -l

# Sentinel 限流 (Spring Cloud)
curl -X POST "http://localhost:8719/cluster/flow/rules" \
  -H "Content-Type: application/json" \
  -d '{"resource":"api","count":100,"grade":1}'

# 阿里云 WAF 限流
aliyun waf-openapi CreateProtectionModuleRule --RegionId cn-hangzhou \
  --InstanceId waf-xxx --Domain api.example.com \
  --Rule '{"name":"emergency-rate-limit","type":"rate_limit","config":{"qps":1000}}'
```

### 3.2 快速止血 — 降级

```bash
# Spring Cloud 降级开关
curl -X POST "http://localhost:8080/actuator/env" \
  -H "Content-Type: application/json" \
  -d '{"degrade.switch":"true"}'

# Sentinel 降级
curl -X POST "http://localhost:8719/degrade/rules" \
  -H "Content-Type: application/json" \
  -d '{"resource":"slow-api","grade":0,"count":0.5,"timeWindow":60}'

# 功能开关 (Apollo/Nacos)
# Apollo: 通过管理后台关闭非核心功能
# Nacos: 修改配置 publish
curl -X POST "http://nacos:8848/nacos/v1/cs/configs" \
  -d "dataId=feature-switch&group=DEFAULT_GROUP&content=feature.recommend=false&tenant=xxx"

# 静态降级页面
# Nginx 配置降级页面:
# error_page 502 503 504 /maintenance.html;
# location = /maintenance.html { root /usr/share/nginx/html; }
```

### 3.3 快速止血 — 回滚

```bash
# K8s Deployment 回滚
kubectl rollout history deployment/<app> -n <namespace>
kubectl rollout undo deployment/<app> -n <namespace>
kubectl rollout undo deployment/<app> --to-revision=<N> -n <namespace>

# 查看回滚状态
kubectl rollout status deployment/<app> -n <namespace>

# Docker 回滚
docker ps | grep <app>
docker stop <container_id>
docker run -d --name <app> <old_image>

# 阿里云 EDAS 回滚
aliyun edas ListChangeOrderInfo --RegionId cn-hangzhou --AppId app-xxx

# 数据库回滚 (需确认)
# mysql -u root -p < backup_$(date +%Y%m%d).sql
```

### 3.4 快速止血 — 流量调度

```bash
# Nginx 切流 (摘除故障节点)
# 修改 upstream 配置，注释故障节点:
# upstream backend {
#     server 10.0.0.1:8080;
#     # server 10.0.0.2:8080;  # 故障节点
#     server 10.0.0.3:8080;
# }
nginx -t && nginx -s reload

# 阿里云 SLB 切流
aliyun slb SetBackendServers --RegionId cn-hangzhou \
  --LoadBalancerId lb-xxx \
  --BackendServers '[{"ServerId":"i-bp1xxx","Weight":"0"}]'

# DNS 切流 (切换到灾备机房)
aliyun alidns UpdateDomainRecord --RecordId xxx \
  --RR www --Type A --Value <backup_ip>

# K8s Pod 摘流 (通过标签)
kubectl label pod <pod> traffic=disabled -n <namespace>
# 配合 Service 的 labelSelector 自动摘流
```

### 3.5 影响面评估

```bash
# 查看受影响的 K8s Pod
kubectl get pods -A --field-selector=status.phase!=Running

# 查看服务健康状态
curl -s http://localhost:actuator/health | python3 -m json.tool

# 查看错误率
tail -10000 /var/log/nginx/access.log | awk '{print $9}' | sort | uniq -c | sort -rn

# 查看上下游依赖
curl -s http://localhost:actuator/dependencies | python3 -m json.tool

# 阿里云 ARMS 链路追踪
aliyun arms SearchTraces --RegionId cn-hangzhou \
  --StartTime "$(date -d '30 min ago' +%s)000" \
  --EndTime "$(date +%s)000" --MinDuration 3000
```

### 3.6 根因定位

```bash
# 查看最近变更
kubectl get events -A --sort-by='.lastTimestamp' | tail -30

# 查看最近部署
kubectl rollout history deployment/<app> -n <namespace> | tail -5

# 查看配置变更
# Nacos: 查询历史配置
curl "http://nacos:8848/nacos/v1/cs/history?dataId=xxx&group=DEFAULT_GROUP&tenant=xxx&pageNo=1&pageSize=10"

# 时间线梳理
echo "=== 故障时间线 ==="
echo "$(date): 开始排查"
echo "变更时间: $(kubectl get events -A --sort-by='.lastTimestamp' | head -1)"

# 日志分析
grep -E "ERROR|Exception|OOM|timeout" /app/logs/*.log | tail -50
```

---

## 4. 常见问题与解决方案

### 4.1 服务雪崩

**现象**: 上游服务超时导致下游服务线程池耗尽，级联崩溃

**止血方案**:

| 步骤 | 操作 | 风险 |
|------|------|------|
| 1. 熔断上游 | Sentinel/Hystrix 熔断 | 🟢 低 (快速失败优于级联) |
| 2. 降级非核心功能 | 关闭推荐/搜索等 | 🟢 低 |
| 3. 扩容核心服务 | K8s HPA / 手动扩容 | 🟢 低 |
| 4. 限流入口 | Nginx/WAF 限流 | 🟡 中 |
| 5. 逐步恢复 | 逐步放开限流 | 🟡 中 |

### 4.2 流量突增

**现象**: QPS 突增导致系统过载

**止血方案**:

| 步骤 | 操作 | 风险 |
|------|------|------|
| 1. 限流 | Nginx/WAF 限流到系统能承受的水平 | 🟡 中 |
| 2. 弹性扩容 | K8s HPA 自动扩容 | 🟢 低 |
| 3. CDN 卸载 | 静态资源走 CDN | 🟢 低 |
| 4. 缓存预热 | 预加载热点数据 | 🟢 低 |

### 4.3 发布故障

**现象**: 新版本发布后服务异常

**止血方案**:

| 步骤 | 操作 | 风险 |
|------|------|------|
| 1. 立即回滚 | `kubectl rollout undo` | 🟡 中 |
| 2. 保留现场 | 保留异常 Pod 日志 | 🟢 低 |
| 3. 验证回滚 | 健康检查 + 冒烟测试 | 🟢 低 |
| 4. 根因分析 | 对比新旧版本差异 | 🟢 低 |

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
查看日志/指标/状态
kubectl get/describe/logs
curl actuator/health
```

### 5.2 需要确认的操作 (P0 故障可简化审批)
```bash
限流 / 降级 / 熔断
回滚 Deployment
SLB 摘流
扩容 Pod
```

### 5.3 危险操作禁止执行
```bash
删除数据库/表
删除 K8s Namespace
修改核心配置 (数据库连接/密钥)
全量重启所有服务
```

---

## 6. 应急响应模板

```markdown
# 故障应急报告

## 基本信息
- 故障时间: YYYY-MM-DD HH:MM ~ HH:MM
- 故障等级: P0/P1/P2
- 影响范围: [服务/用户/业务]
- 处理人: [姓名]

## 时间线
| 时间 | 事件 | 操作 |
|------|------|------|
| HH:MM | 告警触发 | - |
| HH:MM | 确认故障 | - |
| HH:MM | 执行止血 | [具体操作] |
| HH:MM | 根因定位 | [原因] |
| HH:MM | 修复完成 | [具体操作] |
| HH:MM | 服务恢复 | - |

## 根因分析
- 直接原因:
- 深层原因:

## 改进措施
1. [监控/告警改进]
2. [架构优化]
3. [流程改进]
```

---

## 7. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
