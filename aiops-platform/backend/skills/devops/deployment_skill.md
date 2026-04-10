# CI/CD 流水线故障排查技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `部署失败`, `发布失败`, `构建失败`, `Pipeline 失败`
- `Jenkins`, `GitLab CI`, `GitHub Actions`, `ArgoCD`
- `回滚`, `Rollback`, `镜像构建`, `Docker Build`
- `代码合并`, `MR`, `PR`, `冲突`
- `制品`, `Artifact`, `镜像仓库`, `ACR`

### 1.2 适用条件
- CI 构建失败 (编译/测试/打包)
- CD 部署失败 (镜像推送/K8s 部署/健康检查)
- 流水线超时
- 镜像拉取失败
- Git 操作失败 (合并冲突/权限)

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 确认故障类型                                       │
│  - CI 阶段失败? (构建/测试)                                │
│  - CD 阶段失败? (部署/验证)                                │
│  - 基础设施问题? (Jenkins/GitLab/Registry)                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 流水线日志分析                                     │
│  - 定位失败阶段                                             │
│  - 提取错误信息                                             │
│  - 分析失败原因                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 分类诊断                                           │
│  - 构建错误 → Step 3a                                      │
│  - 测试失败 → Step 3b                                      │
│  - 镜像问题 → Step 3c                                      │
│  - 部署问题 → Step 3d                                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3a: 构建错误        Step 3b: 测试失败                 │
│  - 依赖下载失败            - 单元测试失败                   │
│  - 编译错误                - 集成测试失败                   │
│  - 代码质量检查            - 测试环境问题                   │
│                                                              │
│  Step 3c: 镜像问题        Step 3d: 部署问题                 │
│  - Docker Build 失败       - K8s 部署失败                   │
│  - 镜像推送失败            - 健康检查失败                   │
│  - 镜像拉取失败            - 资源不足                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 提供修复方案                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 Jenkins 诊断

```bash
# 查看 Jenkins 构建历史
curl -s "http://jenkins:8080/job/<job_name>/api/json?tree=builds[number,status,url,result,timestamp]" \
  --user <user>:<token>

# 查看构建日志
curl -s "http://jenkins:8080/job/<job_name>/<build_number>/consoleText" \
  --user <user>:<token>

# 查看构建详情
curl -s "http://jenkins:8080/job/<job_name>/<build_number>/api/json" \
  --user <user>:<token>

# 查看 Jenkins 节点状态
curl -s "http://jenkins:8080/computer/api/json" --user <user>:<token>

# 查看 Jenkins 磁盘空间
curl -s "http://jenkins:8080/computer/api/json?tree=computer[displayName,offline,offlineReason]" \
  --user <user>:<token>

# Jenkins Pipeline 日志
curl -s "http://jenkins:8080/job/<job_name>/<build_number>/wfapi/describe" \
  --user <user>:<token>
```

### 3.2 GitLab CI 诊断

```bash
# 查看流水线状态
curl -s "http://gitlab/api/v4/projects/<project_id>/pipelines" \
  --header "PRIVATE-TOKEN: <token>" | python3 -m json.tool

# 查看流水线 Job 日志
curl -s "http://gitlab/api/v4/projects/<project_id>/jobs/<job_id>/trace" \
  --header "PRIVATE-TOKEN: <token>"

# 查看 Job 详情
curl -s "http://gitlab/api/v4/projects/<project_id>/jobs/<job_id>" \
  --header "PRIVATE-TOKEN: <token>"

# 重试失败的 Job
curl -X POST "http://gitlab/api/v4/projects/<project_id>/jobs/<job_id>/retry" \
  --header "PRIVATE-TOKEN: <token>"

# 查看 Runner 状态
curl -s "http://gitlab/api/v4/runners" --header "PRIVATE-TOKEN: <token>"
```

### 3.3 Docker / 镜像诊断

```bash
# Docker Build 日志
docker build --no-cache -t <image> . 2>&1 | tail -50

# 查看镜像大小
docker images | grep <image>

# 查看镜像层
docker history <image>
dive <image>  # 需安装 dive 工具

# 推送镜像
docker push <registry>/<image>:<tag>

# 阿里云 ACR 镜像仓库
aliyun cr GetRepoList --RegionId cn-hangzhou
aliyun cr GetRepoTags --RegionId cn-hangzhou --RepoNamespace <ns> --RepoName <name>

# 检查镜像拉取
docker pull <registry>/<image>:<tag>

# K8s 镜像拉取错误
kubectl describe pod <pod> -n <namespace> | grep -A 5 "Events"
```

### 3.4 K8s 部署诊断

```bash
# 查看 Deployment 状态
kubectl get deployment <app> -n <namespace>
kubectl describe deployment <app> -n <namespace>

# 查看 Pod 状态
kubectl get pods -l app=<app> -n <namespace>
kubectl describe pod <pod> -n <namespace>

# 查看 Pod 事件 (部署失败原因)
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep <app>

# 查看 Pod 日志
kubectl logs <pod> -n <namespace> --tail=100
kubectl logs <pod> -n <namespace> -p  # 上一个容器

# 查看 ReplicaSet (回滚历史)
kubectl get rs -l app=<app> -n <namespace>

# 查看 Rollout 状态
kubectl rollout status deployment/<app> -n <namespace>

# ArgoCD 诊断
argocd app get <app>
argocd app logs <app>
```

### 3.5 Git 操作诊断

```bash
# 查看合并冲突
git status
git diff --name-only --diff-filter=U

# 查看最近提交
git log --oneline -10

# 查看分支差异
git diff main..feature-branch --stat

# 查看 Git 远程仓库状态
git remote -v
git fetch --dry-run

# 查看子模块状态
git submodule status
```

---

## 4. 常见问题与解决方案

### 4.1 构建失败 — 依赖下载

**现象**: Maven/npm/pip 依赖下载超时或 404

**诊断步骤**:
```bash
# 1. 检查仓库连通性
curl -I https://repo.maven.apache.org/maven2/
curl -I https://registry.npmjs.org/

# 2. 检查代理配置
cat ~/.m2/settings.xml | grep -A 5 "mirror"
cat ~/.npmrc

# 3. 检查磁盘空间
df -h
```

**解决方案**:

| 原因 | 解决方案 | 风险 |
|------|---------|------|
| 网络超时 | 配置国内镜像源 | 🟢 低 |
| 私有仓库不可达 | 检查 VPN/代理 | 🟢 低 |
| 磁盘空间不足 | 清理 workspace | 🟢 低 |
| 版本不存在 | 锁定依赖版本 | 🟢 低 |
| 证书过期 | 更新证书 | 🟡 中 |

### 4.2 镜像构建失败

**现象**: Docker Build 报错

**诊断步骤**:
```bash
# 1. 查看 Build 日志
docker build --no-cache -t <image> . 2>&1

# 2. 检查 Dockerfile
cat Dockerfile

# 3. 检查基础镜像
docker pull <base_image>
```

**常见错误与解决方案**:

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `COPY failed` | 文件不存在 | 检查 .dockerignore 和文件路径 |
| `npm install failed` | 依赖冲突 | 删除 node_modules 重新安装 |
| `permission denied` | 文件权限 | 修改 COPY 的 --chown |
| `no space left` | 磁盘满 | 清理 Docker 缓存: `docker system prune` |
| `base image not found` | 基础镜像不存在 | 检查镜像名/Tag |

### 4.3 K8s 部署失败

**现象**: Pod 无法启动或 CrashLoopBackOff

**诊断步骤**:
```bash
# 1. 查看 Pod 状态
kubectl describe pod <pod> -n <namespace>

# 2. 查看容器日志
kubectl logs <pod> -n <namespace> --tail=100

# 3. 查看事件
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | tail -20
```

**常见错误与解决方案**:

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `ImagePullBackOff` | 镜像拉取失败 | 检查镜像名/Tag/Secret |
| `CrashLoopBackOff` | 容器启动后崩溃 | 查看日志修复启动错误 |
| `OOMKilled` | 内存不足 | 增大 resources.limits.memory |
| `Insufficient` | 节点资源不足 | 扩容节点/调整请求 |
| `Liveness probe failed` | 健康检查失败 | 调整探针参数 |

### 4.4 流水线超时

**现象**: 流水线执行时间过长或超时

**诊断步骤**:
```bash
# 1. 查看各阶段耗时
# Jenkins: Pipeline Stage View
# GitLab: Pipeline -> Jobs -> Duration

# 2. 检查慢阶段
# 通常是: 依赖下载 > 测试 > 构建 > 部署
```

**优化方案**:

| 方案 | 操作 | 效果 |
|------|------|------|
| 缓存依赖 | Maven/Gradle/npm 缓存 | 构建 RT 降低 50% |
| 并行执行 | 并行测试/构建 | 总时间降低 40% |
| 增量构建 | 只构建变更模块 | 构建 RT 降低 60% |
| 镜像缓存 | 多阶段构建 + 缓存层 | 镜像构建 RT 降低 70% |

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
查看流水线日志/状态
kubectl get/describe/logs
docker images/history
git log/status/diff
```

### 5.2 需要确认的操作
```bash
重试失败的 Job
回滚 Deployment
重新触发 Pipeline
清理 Docker 缓存
```

### 5.3 危险操作禁止执行
```bash
删除 Jenkins Job
删除镜像仓库 Tag (可能影响其他服务)
删除 K8s Namespace
强制推送 Git (git push -f)
```

---

## 6. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
