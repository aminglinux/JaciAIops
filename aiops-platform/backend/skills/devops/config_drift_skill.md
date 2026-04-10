# 配置漂移检测技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `配置漂移`, `配置不一致`, `环境差异`
- `Apollo`, `Nacos`, `配置中心`, `Spring Cloud Config`
- `本地能跑线上不行`, `环境不一致`
- `配置变更`, `版本回退`, `灰度配置`
- `ConfigMap`, `Secret`, `配置热更新`

### 1.2 适用条件
- 同一服务在不同环境表现不同
- 配置变更后服务异常
- 多实例配置不一致
- 配置中心与本地配置冲突
- K8s ConfigMap/Secret 更新未生效

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 确认配置来源                                       │
│  - 配置中心 (Apollo/Nacos)                                  │
│  - K8s ConfigMap/Secret                                     │
│  - 本地配置文件                                             │
│  - 环境变量                                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 配置对比                                           │
│  - 不同环境配置对比                                         │
│  - 不同实例配置对比                                         │
│  - 配置中心 vs 实际生效配置                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 变更历史分析                                       │
│  - 最近配置变更记录                                         │
│  - 变更时间与故障时间关联                                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 配置生效验证                                       │
│  - 运行时配置检查                                           │
│  - 热更新是否生效                                           │
│  - 配置优先级                                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 Nacos 配置检查

```bash
# 查询配置列表
curl -s "http://nacos:8848/nacos/v1/cs/configs?dataId=&group=&tenant=<namespace>&pageNo=1&pageSize=100"

# 查询特定配置
curl -s "http://nacos:8848/nacos/v1/cs/configs?dataId=<dataId>&group=<group>&tenant=<namespace>"

# 查询配置历史
curl -s "http://nacos:8848/nacos/v1/cs/history?dataId=<dataId>&group=<group>&tenant=<namespace>&pageNo=1&pageSize=10"

# 查询配置监听者
curl -s "http://nacos:8848/nacos/v1/cs/listeners?dataId=<dataId>&group=<group>&tenant=<namespace>"

# 对比两个版本的配置
curl -s "http://nacos:8848/nacos/v1/cs/history?dataId=<dataId>&group=<group>&tenant=<namespace>&nid=<nid>"
```

### 3.2 Apollo 配置检查

```bash
# 查询配置 (通过 Apollo Open API)
curl -s "http://apollo:8070/openapi/v1/envs/<env>/apps/<appId>/clusters/<cluster>/namespaces/<namespace>/items" \
  -H "Authorization: <token>"

# 查询配置发布历史
curl -s "http://apollo:8070/openapi/v1/envs/<env>/apps/<appId>/clusters/<cluster>/namespaces/<namespace>/releases" \
  -H "Authorization: <token>"

# 查询当前生效配置
curl -s "http://apollo:8070/openapi/v1/envs/<env>/apps/<appId>/clusters/<cluster>/namespaces/<namespace>/releases/latest" \
  -H "Authorization: <token>"
```

### 3.3 K8s ConfigMap/Secret

```bash
# 查看 ConfigMap
kubectl get configmap <name> -n <namespace> -o yaml

# 查看 Secret
kubectl get secret <name> -n <namespace> -o yaml

# 查看所有 ConfigMap
kubectl get configmaps -n <namespace>

# 查看 ConfigMap 变更历史
kubectl describe configmap <name> -n <namespace>

# 查看挂载的配置文件 (在 Pod 内)
kubectl exec <pod> -n <namespace> -- cat /etc/config/<key>

# 查看 Pod 环境变量
kubectl exec <pod> -n <namespace> -- env | sort

# 查看 Pod 的完整配置
kubectl get pod <pod> -n <namespace> -o jsonpath='{.spec.containers[*].env}'

# 检查 ConfigMap 挂载是否更新 (subPath 不会自动更新)
kubectl exec <pod> -n <namespace> -- ls -la /etc/config/
```

### 3.4 应用运行时配置

```bash
# Spring Boot Actuator 查看配置
curl -s http://localhost:actuator/env | python3 -m json.tool

# 查看特定配置项
curl -s "http://localhost:actuator/env/<key>"

# 查看配置属性源
curl -s http://localhost:actuator/env | python3 -c "
import sys, json
d = json.load(sys.stdin)
for ctx in d.get('contexts', {}).values():
    for bean in ctx.get('beans', {}).values():
        if 'propertySources' in bean:
            for ps in bean['propertySources']:
                print(f\"{ps['name']}: {len(ps.get('properties',{}))} properties\")
"

# 查看配置变更历史
curl -s http://localhost:actuator/configprops | python3 -m json.tool | head -100
```

### 3.5 配置对比

```bash
# 对比两个环境的配置
diff <(curl -s "http://nacos:8848/nacos/v1/cs/configs?dataId=app.yml&group=DEFAULT_GROUP&tenant=dev") \
     <(curl -s "http://nacos:8848/nacos/v1/cs/configs?dataId=app.yml&group=DEFAULT_GROUP&tenant=prod")

# 对比两个 Pod 的环境变量
diff <(kubectl exec <pod1> -n <ns> -- env | sort) \
     <(kubectl exec <pod2> -n <ns> -- env | sort)

# 对比两个实例的运行时配置
diff <(curl -s http://instance1:8080/actuator/env) \
     <(curl -s http://instance2:8080/actuator/env)
```

---

## 4. 常见问题与解决方案

### 4.1 配置变更未生效

**现象**: 修改了配置中心配置，但服务行为未变

**诊断步骤**:
```bash
# 1. 确认配置已发布
curl -s "http://nacos:8848/nacos/v1/cs/configs?dataId=<dataId>&group=<group>&tenant=<ns>"

# 2. 确认服务已监听
curl -s "http://nacos:8848/nacos/v1/cs/listeners?dataId=<dataId>&group=<group>&tenant=<ns>"

# 3. 确认运行时配置
curl -s http://localhost:actuator/env | grep "<key>"
```

**常见原因**:

| 原因 | 解决方案 | 风险 |
|------|---------|------|
| 配置未发布 | 在配置中心点击发布 | 🟢 低 |
| 服务未监听 | 检查 @RefreshScope / @NacosValue | 🟢 低 |
| 本地配置覆盖 | 检查 application.yml 优先级 | 🟢 低 |
| 缓存未刷新 | 重启服务 / 清除缓存 | 🟡 中 |
| subPath 不更新 | 重建 Pod | 🟡 中 |

### 4.2 多实例配置不一致

**现象**: 同一服务不同实例行为不同

**诊断步骤**:
```bash
# 1. 对比运行时配置
for pod in $(kubectl get pods -l app=<app> -n <ns> -o name); do
  echo "=== $pod ==="
  kubectl exec $pod -n <ns> -- env | grep -E "SPRING|NACOS|DB" | sort
done

# 2. 检查配置版本
for pod in $(kubectl get pods -l app=<app> -n <ns> -o name); do
  echo "=== $pod ==="
  kubectl exec $pod -n <ns> -- cat /etc/config/version 2>/dev/null || echo "no version file"
done
```

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 滚动重启 | `kubectl rollout restart` | 🟡 中 |
| 统一配置源 | 确保所有实例从同一配置中心拉取 | 🟢 低 |
| 配置校验 | 启动时校验配置版本 | 🟢 低 (需发版) |

### 4.3 K8s ConfigMap 更新未生效

**现象**: ConfigMap 已更新但 Pod 未使用新配置

**常见原因**:

| 原因 | 解决方案 | 风险 |
|------|---------|------|
| 使用 subPath | subPath 挂载不会自动更新，需重建 Pod | 🟡 中 |
| 未使用 volumeMounts | 环境变量方式需重启 Pod | 🟡 中 |
| ConfigMap 缓存 | kubelet 缓存，等待同步周期 | 🟢 低 |
| Immutable ConfigMap | 不可变 ConfigMap 无法更新 | 🟢 低 |

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
查看配置中心配置
kubectl get configmap/secret -o yaml
curl actuator/env
diff 配置对比
```

### 5.2 需要确认的操作
```bash
修改配置中心配置
kubectl rollout restart
修改 ConfigMap/Secret
```

### 5.3 危险操作禁止执行
```bash
删除配置中心配置
删除 ConfigMap/Secret
修改数据库连接/密码配置 (需变更审批)
修改安全相关配置 (TLS/认证)
```

---

## 6. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
