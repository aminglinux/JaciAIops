# AIOps 智能运维平台

基于多智能体架构的自动化运维诊断平台，集成了知识图谱、RAG知识库、动态决策引擎、邮件审批系统、Web Terminal、安全审计和成本分析，实现智能故障诊断、根因分析、安全威胁检测和自动化运维。

## 📋 目录

- [系统架构](#系统架构)
- [核心功能](#核心功能)
- [多智能体系统](#多智能体系统)
- [安全审计系统](#安全审计系统)
- [成本分析系统](#成本分析系统)
- [工作流程](#工作流程)
- [技术栈](#技术栈)
- [安装部署](#安装部署)
- [Kubernetes 部署](#kubernetes-部署)
- [使用指南](#使用指南)
- [配置说明](#配置说明)
- [项目结构](#项目结构)
- [API 接口](#api-接口)

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           前端界面层 (React + TypeScript)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  用户认证    │  │  故障诊断    │  │  Web Terminal │  │  知识图谱    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           后端服务层 (FastAPI)                               │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    Multi-Agent 协调器 (Orchestrator)                   │  │
│  │                                                                        │  │
│  │   ┌─────────────┐    ┌─────────────────────────────────────────────┐  │  │
│  │   │ SkillManager│───▶│              MasterAgent                    │  │  │
│  │   │ (技能文件)   │    │         (动态决策 + Function Calling)        │  │  │
│  │   └─────────────┘    └─────────────────────────────────────────────┘  │  │
│  │                                    │                                   │  │
│  │                                    ▼                                   │  │
│  │   ┌───────────────────────────────────────────────────────────────┐   │  │
│  │   │                      ToolRegistry                             │   │  │
│  │   │  • execute_command      • send_approval_email                 │   │  │
│  │   │  • save_diagnosis_plan  • check_approval_status               │   │  │
│  │   │  • save_execution_output• execute_approved_command            │   │  │
│  │   │  • query_knowledge_graph• ask_user_confirmation               │   │  │
│  │   └───────────────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  用户认证系统    │  │  WebSocket终端  │  │  邮件审批系统    │             │
│  │  (JWT + RBAC)   │  │  (xterm.js)     │  │  (SMTP)         │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
│        ┌─────────────────────┼─────────────────────┐                       │
│        ▼                     ▼                     ▼                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │  Neo4j       │  │  RAG 知识库   │  │  阿里云监控  │                     │
│  │  (知识图谱)   │  │  (SOP文档)   │  │  (实例状态)  │                     │
│  └──────────────┘  └──────────────┘  └──────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

## ✨ 核心功能

### 1. 用户认证系统
- **用户注册**: 支持新用户注册，密码 bcrypt 加密
- **用户登录**: JWT Token 认证，支持自动刷新
- **角色权限**: 管理员 (admin) 和普通用户 (user) 两种角色
- **权限控制**: Web Terminal 仅管理员可访问

### 2. 智能故障诊断
- **意图识别**: 自动识别用户查询意图和关键实体
- **动态决策**: LLM 根据 skill 文件动态规划诊断步骤
- **Function Calling**: LLM 自主调用工具执行操作
- **根因分析**: 综合分析收集的信息，定位问题根源
- **解决方案**: 提供具体可执行的修复建议

### 3. 邮件审批系统
- **审批请求**: 高风险操作自动发送审批邮件
- **邮件回复**: 支持 APPROVE/REJECT 关键词审批
- **审批记录**: 所有审批记录持久化存储
- **自动执行**: 审批通过后自动执行操作

### 4. Web Terminal
- **实时终端**: 基于 xterm.js 的 Web 终端
- **WebSocket**: 实时双向通信
- **PTY 支持**: 真实终端体验
- **权限控制**: 仅管理员可访问

### 5. 知识图谱集成
- **拓扑可视化**: 展示服务间的依赖关系
- **影响分析**: 分析故障影响范围
- **历史查询**: 查询节点的变更历史和关联信息

### 6. RAG 知识库
- **SOP 文档检索**: 检索相关故障排查文档
- **相似案例匹配**: 匹配历史故障处理案例
- **知识增强**: 结合知识库提供更准确的诊断建议

### 7. 安全审计系统
- **多源日志检测**: SSH、身份认证、云平台、应用服务器日志
- **异常检测**: 基于 Prophet 时间序列模型检测异常行为
- **告警关联**: 多源告警关联识别高级攻击
- **攻击识别**: 暴力破解、撞库攻击、横向移动、协同攻击

### 8. 成本分析系统
- **成本预测**: 基于 Prophet 模型预测云成本趋势
- **异常检测**: 自动识别成本异常波动
- **根因分析**: 定位导致成本异常的具体服务和项目
- **可视化报告**: 生成详细的成本分析报告

### 9. Skills 诊断技能系统
系统内置丰富的诊断技能文件，支持渐进式披露设计：

#### P0 - 核心诊断技能
| Skill | 触发关键词 | 适用场景 |
|-------|-----------|---------|
| **debug_skill** | 磁盘, 内存, CPU, 网络, 故障 | 单机服务器故障排查 |
| **gnn_rca_skill** | 根因分析, GNN, 微服务, 拓扑 | 微服务根因分析 |
| **mysql_deadlock_skill** | 死锁, deadlock, 锁等待 | MySQL 死锁排查 |
| **mysql_slow_query_skill** | 慢查询, SQL优化 | MySQL 慢查询分析 |
| **k8s_pod_skill** | Pod, k8s, Kubernetes | Kubernetes Pod 诊断 |
| **connectivity_skill** | ping, DNS, 防火墙, 端口 | 网络连通性诊断 |

#### P1 - 常用诊断技能
| Skill | 触发关键词 | 适用场景 |
|-------|-----------|---------|
| **redis_skill** | Redis, 缓存, 内存, key | Redis 诊断与优化 |
| **prometheus_skill** | Prometheus, 监控, PromQL | Prometheus 监控诊断 |
| **log_analysis_skill** | 日志, ELK, Loki | 日志分析与排查 |
| **ad_skill** | AD, 域控, LDAP, Kerberos | Active Directory 诊断 |

#### P2 - 辅助技能
| Skill | 触发关键词 | 适用场景 |
|-------|-----------|---------|
| **ssl_certificate_skill** | SSL, 证书, HTTPS | SSL 证书管理 |
| **backup_skill** | 备份, 恢复, 灾备 | 数据备份与恢复 |

### 10. Ansible 自动化集成
- **服务器状态采集**: 自动采集服务器状态并同步到 Neo4j
- **动态 Inventory**: 支持 Ansible inventory 管理
- **自动化运维**: 支持批量执行运维任务

## 🤖 多智能体系统

### 核心架构：动态决策模式

系统采用 **LLM + Function Calling** 的动态决策模式，不再使用硬编码流程：

```
┌─────────────────────────────────────────────────────────────────┐
│                      MasterAgent (大脑中枢)                      │
│                                                                  │
│   1. 加载相关 Skill 文件 (debug_skill.md, login_skill.md)       │
│   2. 构建 LLM Prompt (包含 skill 内容和可用工具)                 │
│   3. LLM 动态规划并调用工具                                      │
│   4. 根据工具返回结果继续决策                                    │
│   5. 循环直到得出最终结论                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1. IntentParseAgent (意图解析代理)
**职责**: 入口网关，准确识别意图和实体

**核心能力**:
- NER 命名实体识别
- 意图分类 (DIAGNOSE / QUERY_STATUS / EXECUTE_FIX / GENERAL_QA)
- 关键词提取
- 模糊输入处理

**提取实体类型**:
- SERVICE: 服务名称
- SERVER: 服务器/主机名
- IP: IP 地址
- SYMPTOM: 故障现象
- METRIC: 指标名称 (CPU/内存/磁盘等)
- ACTION: 操作动作

### 2. MasterAgent (主控代理)
**职责**: 大脑中枢，动态决策

**核心能力**:
- 根据 skill 文件动态生成诊断计划
- 使用 Function Calling 调用工具
- 根据执行结果动态决策下一步
- 生成最终诊断报告

**关键特性**:
- 不使用硬编码流程
- LLM 自主决策执行步骤
- 支持邮件审批高风险操作
- 最大迭代次数保护

### 3. SkillManager (技能管理器)
**职责**: 加载和管理技能文件

**核心能力**:
- 加载所有诊断技能文件 (debug_skill, mysql_skill, k8s_skill 等)
- 根据关键词匹配相关技能
- 提供技能内容给 LLM
- 支持渐进式披露设计

**技能分类**:
- **诊断类**: debug_skill, gnn_rca_skill, mysql_deadlock_skill, mysql_slow_query_skill, redis_skill, ad_skill
- **容器类**: k8s_pod_skill
- **网络类**: connectivity_skill, ssl_certificate_skill
- **监控类**: prometheus_skill, log_analysis_skill
- **备份类**: backup_skill
- **连接类**: login_skill

### 4. ToolRegistry (工具注册中心)
**职责**: 注册和执行工具

**可用工具**:

| 工具名称 | 功能 | 风险等级 |
|---------|------|---------|
| `execute_command` | 在目标服务器执行命令 | low-medium |
| `save_diagnosis_plan` | 保存诊断计划 | low |
| `save_execution_output` | 保存执行输出 | low |
| `send_approval_email` | 发送审批邮件 | low |
| `check_approval_status` | 检查审批状态 | low |
| `execute_approved_command` | 审批后执行命令 | high |
| `query_knowledge_graph` | 查询知识图谱 | low |
| `query_rag` | 查询 RAG 知识库 | low |
| `ask_user_confirmation` | 请求用户确认 | low |

### 5. EmailSender (邮件发送器)
**职责**: 发送审批邮件和处理回复

**核心能力**:
- 发送 HTML 格式审批邮件
- 管理待审批操作
- 处理邮件回复审批
- 审批记录持久化

## 🔒 安全审计系统

### 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Security Audit Pipeline                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ SSH Logs    │  │ Auth Logs   │  │ Cloud Logs  │  │ App Logs    │         │
│  │ Detector    │  │ Detector    │  │ Detector    │  │ Detector    │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                │                │
│         └────────────────┴────────────────┴────────────────┘                │
│                                   │                                          │
│                                   ▼                                          │
│                        ┌─────────────────────┐                               │
│                        │  Correlation Engine │                               │
│                        │  (关联分析引擎)      │                               │
│                        └──────────┬──────────┘                               │
│                                   │                                          │
│                                   ▼                                          │
│                        ┌─────────────────────┐                               │
│                        │   Incident Report   │                               │
│                        │   (安全事件报告)     │                               │
│                        └─────────────────────┘                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 检测器类型

| 检测器 | 功能 | 检测类型 |
|--------|------|----------|
| **SSHDetector** | SSH 登录失败检测 | 暴力破解、分布式攻击 |
| **AuthDetector** | 身份认证失败检测 | 撞库攻击、密码喷洒 |
| **CloudDetector** | 云平台 API 异常检测 | 异常调用、权限滥用 |
| **AppServerDetector** | 应用服务器错误检测 | 错误激增、服务异常 |

### 关联规则

| 规则名称 | 触发条件 | 严重级别 |
|----------|----------|----------|
| `Coordinated_Attack_Detected` | SSH + Auth 同时异常 | CRITICAL |
| `Lateral_Movement_Detected` | SSH + App Server 异常 | HIGH |
| `Cloud_Breach_Detected` | Cloud + Auth 异常 | HIGH |
| `Multi_Vector_Attack_Detected` | 3+ 检测器同时异常 | CRITICAL |

### 运行安全审计

```bash
cd time_sequence_prediction/security_audit

# 安装依赖
pip install -r requirements.txt

# 运行完整管道
python run_security_audit.py

# 运行测试
pytest tests/
```

### 输出示例

```json
{
  "incident_type": "Coordinated_Attack_Detected",
  "severity": "CRITICAL",
  "summary": "检测到协同攻击：系统同时遭受SSH暴力破解和身份认证撞库攻击",
  "correlated_events": [...],
  "recommendations": [
    "立即封锁攻击源IP",
    "强制重置目标用户密码",
    "启用多因素认证(MFA)"
  ]
}
```

## 💰 成本分析系统

### 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Cost Analysis Pipeline                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Step 1: 数据生成          Step 2: 数据清洗          Step 3: 模型训练        │
│  ┌─────────────┐          ┌─────────────┐          ┌─────────────┐          │
│  │ 生成模拟数据 │   ──▶   │ 清洗聚合数据 │   ──▶   │ Prophet训练 │          │
│  │ (周期+趋势) │          │ (按小时聚合) │          │ (学习模式)  │          │
│  └─────────────┘          └─────────────┘          └─────────────┘          │
│                                                                              │
│                                                      │                       │
│                                                      ▼                       │
│  Step 4: 异常检测 + 根因分析                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  • 预测成本趋势                                                       │   │
│  │  • 检测异常波动 (超出置信区间)                                         │   │
│  │  • 根因分析 (定位异常服务和项目)                                        │   │
│  │  • 生成告警报告                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 运行成本分析

```bash
cd time_sequence_prediction/cost_analysis

# 运行完整管道
python step1_generate_cost_data.py
python step2_clean_cost_data.py
python step3_train_cost_model.py
python step4_predict_cost_anomaly.py
```

### 输出示例

```
========== 成本异常检测报告 ==========
检测时间: 2024-01-15 14:00:00
异常点数量: 3

异常详情:
1. 时间: 2024-01-15 10:00
   实际成本: ¥15,230
   预测成本: ¥8,500
   偏差: +79.2%
   根因: project-A (compute引擎) 成本激增

建议操作:
- 检查 project-A 的计算资源使用情况
- 考虑调整资源配额或启用自动伸缩
```

## 🔄 工作流程

### 动态诊断流程

```
用户查询: "8.136.226.231 内存使用率过高"
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 1: 意图识别 (IntentParseAgent)                        │
│ • 识别服务器: 8.136.226.231                                 │
│ • 识别症状: 内存使用率过高                                   │
│ • 意图分类: DIAGNOSE                                        │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 2: 动态决策 (MasterAgent + LLM)                       │
│                                                              │
│ Iteration 1:                                                │
│   LLM 决策 → save_diagnosis_plan                            │
│   → 保存诊断计划: free -m, ps aux --sort=-%mem              │
│                                                              │
│ Iteration 2:                                                │
│   LLM 决策 → execute_command                                │
│   → 执行: ssh 8.136.226.231 "free -m"                       │
│                                                              │
│ Iteration 3:                                                │
│   LLM 决策 → save_execution_output                          │
│   → 保存执行结果                                             │
│                                                              │
│ Iteration 4:                                                │
│   LLM 决策 → execute_command                                │
│   → 执行: ssh 8.136.226.231 "ps aux --sort=-%mem | head"    │
│                                                              │
│ Iteration 5:                                                │
│   LLM 决策 → send_approval_email                            │
│   → 发送审批邮件: kill -9 1539                              │
│                                                              │
│ Iteration 6:                                                │
│   LLM 决策 → 最终结论                                        │
│   → 问题类型: memory                                        │
│   → 根本原因: stress 进程占用 3GB 内存                      │
│   → 建议操作: kill -9 1539 (需审批)                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ Stage 3: 邮件审批 (EmailSender)                             │
│ • 发送审批邮件到管理员邮箱                                   │
│ • 管理员回复 APPROVE 或 REJECT                              │
│ • 审批通过后自动执行操作                                     │
└─────────────────────────────────────────────────────────────┘
   │
   ▼
返回诊断结果
```

## 🛠️ 技术栈

### 后端
- **框架**: FastAPI
- **数据库**: SQLite (aiops.db)
- **图数据库**: Neo4j
- **AI 能力**: OpenAI API (通义千问 Qwen)
- **认证**: JWT + bcrypt
- **终端**: WebSocket + PTY
- **邮件**: SMTP (SSL)
- **自动化**: Ansible
- **监控集成**: 阿里云 SDK
- **时序预测**: Prophet

### 前端
- **框架**: React + TypeScript
- **UI 组件**: Ant Design
- **终端**: xterm.js
- **构建工具**: Vite
- **状态管理**: React Context + Hooks

### 关键依赖
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
pydantic==2.5.2
pydantic-settings==2.1.0
openai==1.6.1
neo4j==5.14.1
python-jose[cryptography]==3.3.0
bcrypt==4.1.2
websockets==12.0
python-dotenv==1.0.0
prophet==1.1.5
```

## 🚀 安装部署

### 1. 环境要求
- Docker Engine 24+ 与 Docker Compose
- Neo4j 5.x (可选，用于知识图谱)
- RAG 服务 (可选，用于知识库检索)

### 2. 推荐方式：Docker Compose 部署前后端

```bash
# 在仓库根目录执行
docker compose up --build -d

# 查看启动日志
docker compose logs -f
```

默认端口：

- 前端：`http://localhost:3000`
- 后端 API：`http://localhost:8000`
- Swagger：`http://localhost:8000/docs`

Compose 文件使用 `build` 模式构建两个镜像：

- `backend`：基于 `aiops-platform/backend/Dockerfile`
- `frontend`：基于 `aiops-platform/frontend/Dockerfile`

如需启用外部依赖，请在执行前导出宿主机环境变量：

```bash
export OPENAI_API_KEY=your_api_key
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=your_password
export RAG_SERVICE_URL=http://localhost:8001
```

未设置这些变量时，系统可以启动，但知识图谱、RAG 与部分 LLM 能力会退化为降级模式。

### 3. 本地源码开发

```bash
# 后端
cd aiops-platform/backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 前端（新终端）
cd aiops-platform/frontend
npm install
npm run dev
```

前端开发服务器会将 `/api` 代理到 `http://localhost:8000`。

### 4. Neo4j 部署 (可选)

```bash
docker run -d \
  --name aiops-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.14.1
```

访问 `http://localhost:7474`，使用 `neo4j/password` 登录。

## ☸️ Kubernetes 部署

### 集群要求

- Kubernetes 1.20+
- kubectl 已配置
- Docker 已安装
- 至少 3 节点集群

### 快速部署

```bash
# 1. 克隆项目
git clone <repository-url>
cd aiops-platform

# 2. 配置密钥
cp k8s/secrets.yaml.example k8s/secrets.yaml
vi k8s/secrets.yaml  # 填写实际密钥

# 3. 执行部署
chmod +x deploy.sh
./deploy.sh
```

### 部署架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Kubernetes Cluster                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Namespace: aiops                                                            │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                          │
│  │  Frontend   │  │  Backend    │  │   Neo4j     │                          │
│  │  (React)    │  │  (FastAPI)  │  │  (KG DB)    │                          │
│  │  NodePort   │  │  ClusterIP  │  │  ClusterIP  │                          │
│  │  :30080     │  │  :8000      │  │  :7687      │                          │
│  └─────────────┘  └─────────────┘  └─────────────┘                          │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐                                          │
│  │  RAG服务    │  │   Ingress   │                                          │
│  │  (Python)   │  │   (Nginx)   │                                          │
│  │  :8001      │  │             │                                          │
│  └─────────────┘  └─────────────┘                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 资源配置

| 组件 | CPU Request | Memory Request | 副本数 |
|------|------------|----------------|--------|
| Frontend | 100m | 128Mi | 2 |
| Backend | 250m | 512Mi | 2 |
| Neo4j | 500m | 1Gi | 1 |
| RAG Service | 500m | 1Gi | 1 |

### 访问服务

```bash
# 获取 NodePort
kubectl get svc -n aiops

# 访问前端
http://<NODE_IP>:30080

# 端口转发 Neo4j (调试用)
kubectl port-forward svc/neo4j-service 7474:7474 -n aiops
```

### 常用命令

```bash
# 查看 Pod 状态
kubectl get pods -n aiops

# 查看日志
kubectl logs -f deployment/backend -n aiops

# 重启服务
kubectl rollout restart deployment/backend -n aiops

# 扩缩容
kubectl scale deployment/backend --replicas=3 -n aiops
```

## 📝 使用指南

### 1. 用户注册与登录

访问 `http://localhost:5173/login`：

- **注册**: 点击"注册"按钮，填写用户名和密码
- **登录**: 使用注册的账号登录
- **权限**: 
  - 普通用户: 可使用诊断、知识图谱等功能
  - 管理员: 额外可使用 Web Terminal

### 2. 故障诊断

访问 `http://localhost:5173/diagnose`，输入故障描述：

**示例 1: 磁盘空间问题**
```
8.136.226.231 /dev/shm 出现了磁盘爆满
```

**示例 2: 内存使用率过高**
```
8.136.226.231 出现了 memory 使用率过高的情况
```

**示例 3: 需要审批的操作**
```
8.136.226.231 内存过高，帮我排查并处理
```

### 3. Web Terminal (管理员)

以管理员身份登录后，访问 `http://localhost:5173/terminal`：

- 实时终端操作
- 支持所有 shell 命令
- WebSocket 实时通信

### 4. 邮件审批

当系统检测到高风险操作时：

1. 自动发送审批邮件到管理员邮箱
2. 邮件包含操作详情和审批 ID
3. 管理员回复邮件：
   - `APPROVE <审批ID>` - 批准执行
   - `REJECT <审批ID>` - 拒绝执行
4. 系统自动处理审批结果

### 5. 知识图谱查询

访问 `http://localhost:5173/knowledge-graph`，输入节点名称查询：

**示例**:
```
order-service
```

## ⚙️ 配置说明

### 环境变量 (.env)

```bash
# 通用配置
APP_NAME="AIOps Platform"
DEBUG=True
SECRET_KEY="your-secret-key-change-in-production"

# 数据库配置
DATABASE_URL="sqlite:///./data/aiops.db"

# Neo4j 配置 (知识图谱)
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="password"

# RAG 服务配置
RAG_SERVICE_URL="http://localhost:8001"

# OpenAI API 配置
OPENAI_API_KEY="your_api_key"
OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
OPENAI_MODEL="qwen-plus"

# 阿里云 API 配置 (用于云主机监控)
ALIYUN_ACCESS_KEY_ID="your_access_key_id"
ALIYUN_ACCESS_KEY_SECRET="your_access_key_secret"
ALIYUN_REGION_ID="cn-hangzhou"

# SMTP 邮件配置 (用于审批邮件)
SMTP_HOST="smtp.163.com"
SMTP_PORT=465
SMTP_USER="your_email@163.com"
SMTP_PASSWORD="your_smtp_password"  # 163邮箱使用授权码
SMTP_FROM_EMAIL="your_email@163.com"
```

### debug_skill.md

系统核心知识库，定义了各类故障的排查方法：

**主要章节**:
1. **磁盘问题排查** - 磁盘使用率检查、大文件定位、/dev/shm 处理
2. **网络问题排查** - 连通性检测、DNS 解析、链路追踪
3. **内存问题排查** - 内存使用概览、进程监控、OOM Killer
4. **云服务器特殊检查** - 阿里云实例状态检查

### login_skill.md

定义了各类资源的连接方法和诊断工作流：

**连接方法**:
- 阿里云 ECS (SSH/Ansible)
- Kubernetes Pod (kubectl)
- MySQL 数据库

## 📂 项目结构

```
AIOps/
├── aiops-platform/                 # 主平台
│   ├── backend/                     # 后端服务
│   │   ├── app/
│   │   │   ├── agents/              # 多智能体系统
│   │   │   │   ├── intent_parse.py  # 意图解析
│   │   │   │   ├── master.py        # 主控代理 (动态决策)
│   │   │   │   ├── knowledge.py     # 知识专家
│   │   │   │   ├── observability.py # 可观测性分析
│   │   │   │   ├── action_execute.py# 执行代理
│   │   │   │   ├── orchestrator.py  # 协调器
│   │   │   │   ├── skill_manager.py # 技能管理器
│   │   │   │   └── tool_registry.py # 工具注册中心
│   │   │   ├── api/                 # API 接口
│   │   │   ├── core/                # 核心配置
│   │   │   └── utils/               # 工具类
│   │   ├── algorithm/               # 算法模块
│   │   │   ├── anomaly_detector.py  # 异常检测
│   │   │   └── gnn_rca.py           # GNN 根因分析
│   │   ├── data/                    # 数据目录
│   │   ├── skills/                  # 诊断技能文件
│   │   │   ├── skill.md             # 技能索引文件
│   │   │   ├── diagnosis/           # 诊断类技能
│   │   │   │   ├── debug_skill.md
│   │   │   │   ├── gnn_rca_skill.md
│   │   │   │   ├── mysql_deadlock_skill.md
│   │   │   │   ├── mysql_slow_query_skill.md
│   │   │   │   ├── redis_skill.md
│   │   │   │   └── ad_skill.md
│   │   │   ├── container/           # 容器类技能
│   │   │   │   └── k8s_pod_skill.md
│   │   │   ├── network/             # 网络类技能
│   │   │   │   ├── connectivity_skill.md
│   │   │   │   └── ssl_certificate_skill.md
│   │   │   ├── monitoring/          # 监控类技能
│   │   │   │   ├── prometheus_skill.md
│   │   │   │   └── log_analysis_skill.md
│   │   │   ├── backup/              # 备份类技能
│   │   │   │   └── backup_skill.md
│   │   │   └── connection/          # 连接类技能
│   │   │       └── login_skill.md
│   │   └── requirements.txt
│   ├── frontend/                    # 前端服务
│   │   ├── src/
│   │   │   ├── pages/               # 页面组件
│   │   │   ├── components/          # 通用组件
│   │   │   ├── contexts/            # Context
│   │   │   └── services/            # API 服务
│   │   └── package.json
│   ├── ansible/                     # Ansible 自动化
│   │   ├── inventory.ini            # 主机清单
│   │   ├── server_status.yml        # 服务器状态采集
│   │   └── server_to_neo4j.py       # 同步到 Neo4j
│   ├── k8s/                         # Kubernetes 部署文件
│   │   ├── namespace.yaml
│   │   ├── secrets.yaml
│   │   ├── neo4j-deployment.yaml
│   │   ├── kg-api-deployment.yaml
│   │   └── tsp-api-deployment.yaml
│   ├── docker/                      # Docker 构建文件
│   │   └── kg-api/
│   │       ├── Dockerfile
│   │       └── app.py
│   ├── deploy-kg.sh                 # 知识图谱部署脚本
│   └── README.md
│
├── time_sequence_prediction/        # 时间序列预测模块
│   ├── security_audit/              # 安全审计系统
│   │   ├── base/                    # 基础模块
│   │   │   ├── config.py            # 配置管理
│   │   │   ├── detector.py          # 检测器基类
│   │   │   └── logger.py            # 日志模块
│   │   ├── ssh_logs/                # SSH 日志检测器
│   │   ├── auth_logs/               # 身份认证检测器
│   │   ├── cloud_logs/              # 云平台检测器
│   │   ├── app_server_logs/         # 应用服务器检测器
│   │   ├── correlation_engine/      # 关联分析引擎
│   │   │   ├── engine.py            # 关联引擎
│   │   │   └── incidents.json       # 安全事件报告
│   │   ├── tests/                   # 测试文件
│   │   ├── config.yaml              # 配置文件
│   │   └── run_security_audit.py    # 主运行脚本
│   │
│   ├── cost_analysis/               # 成本分析系统
│   │   ├── data/                    # 数据目录
│   │   ├── models/                  # 模型文件
│   │   ├── step1_generate_cost_data.py
│   │   ├── step2_clean_cost_data.py
│   │   ├── step3_train_cost_model.py
│   │   └── step4_predict_cost_anomaly.py
│   │
│   └── microservice_rca/            # 微服务根因分析
│       ├── step1_generate_data.py   # 生成模拟数据
│       ├── step2_clean_data.py      # 数据清洗
│       ├── model.py                 # GNN 模型定义
│       ├── step3_train_model.py     # 模型训练
│       ├── step4_predict.py         # 预测与根因分析
│       └── run_all.py               # 完整流程
│
└── knowledge_graph/                 # 知识图谱模块
    ├── medical_kg_builder.py        # 医疗知识图谱构建
    ├── infra_text2cypher.py         # 基础设施 Text2Cypher
    └── query_medical_graph.py       # 图谱查询
```

## 🔌 API 接口

### 认证接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录 |
| GET | `/api/auth/me` | 获取当前用户信息 |

### Agent 接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/multi-agent/process` | 处理用户查询 |
| GET | `/api/agent/task/{task_id}` | 获取任务状态 |
| GET | `/api/agent/history` | 获取历史记录 |

### 知识图谱接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/knowledge/query` | 查询知识图谱 |
| POST | `/api/knowledge/rag/query` | RAG 知识库查询 |
| GET | `/api/knowledge/topology` | 获取拓扑图 |
| GET | `/api/knowledge/qa/chat` | 智能问答 |

### 审批接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/approval/status/{id}` | 获取审批状态 |
| POST | `/api/approval/approve/{id}` | 手动批准 |
| POST | `/api/approval/reject/{id}` | 手动拒绝 |
| GET | `/api/approval/pending` | 获取待审批列表 |

### WebSocket

| 路径 | 描述 |
|------|------|
| `/ws/terminal` | Web Terminal 连接 |

## 📁 中间文件管理

所有中间文件自动保存在 `backend/data/` 目录：

```
data/
├── approvals/                    # 审批记录
│   └── f95fd092.json            # 审批详情
├── diagnosis/                   # 诊断计划
│   └── diagnosis_plan_20260328.json
├── logs/                        # 执行日志
│   └── full_result_20260328.json
└── outputs/                     # 执行输出
    └── output_8.136.226.231_20260328.txt
```

## 📧 邮件审批示例

### 审批邮件内容

```
主题: [AIOps] 操作审批请求 - Kill high memory process

尊敬的管理员：

系统检测到需要人工审批的操作，请确认是否执行。

📋 操作详情
操作类型: Kill high memory process stress (PID 1539)
目标服务器: 8.136.226.231
风险等级: MEDIUM
影响范围: 终止 stress 进程将释放约 3GB 内存

🔧 执行命令
kill -9 1539

✅ 审批方式
审批ID: f95fd092
请回复: APPROVE f95fd092 或 REJECT f95fd092
```

### 审批记录

```json
{
  "approval_id": "f95fd092",
  "operation": "Kill high memory process stress (PID 1539)",
  "risk": "medium",
  "commands": ["kill -9 1539"],
  "target_host": "8.136.226.231",
  "status": "approved",
  "approved_at": "2026-03-28T22:52:11",
  "approved_by": "admin@example.com"
}
```

## 🎯 核心特性

### 1. 智能诊断
- ✅ 自动意图识别和实体提取
- ✅ 动态诊断计划生成 (基于 skill 文件)
- ✅ LLM Function Calling 自主决策
- ✅ 基于知识库的根因分析
- ✅ 可解释的决策过程

### 2. 自动化执行
- ✅ SSH 自动执行诊断命令
- ✅ 中间文件自动保存
- ✅ 执行结果自动解析
- ✅ Web Terminal 实时操作

### 3. 安全审批
- ✅ 高风险操作邮件审批
- ✅ 审批记录持久化
- ✅ 支持邮件回复审批
- ✅ 审批后自动执行

### 4. 用户管理
- ✅ 用户注册与登录
- ✅ JWT Token 认证
- ✅ 角色权限控制 (RBAC)
- ✅ 密码 bcrypt 加密

### 5. 知识增强
- ✅ Neo4j 知识图谱集成
- ✅ RAG 知识库检索
- ✅ Skill 文件动态加载
- ✅ 历史案例匹配

### 6. 安全审计
- ✅ 多源日志异常检测 (SSH/Auth/Cloud/App)
- ✅ Prophet 时间序列模型
- ✅ 多源告警关联分析
- ✅ 高级攻击识别 (暴力破解/撞库/横向移动)
- ✅ 安全事件报告生成

### 7. 成本分析
- ✅ 云成本趋势预测
- ✅ 成本异常自动检测
- ✅ 根因分析定位异常服务
- ✅ 可视化分析报告

### 8. 云原生部署
- ✅ Kubernetes 部署支持
- ✅ Docker 容器化
- ✅ 一键部署脚本
- ✅ 水平扩展能力

## 📄 License

MIT License
