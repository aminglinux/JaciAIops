# 连接管理 Skill

## 职责边界
本 Skill 只定义 **"怎么连"**：连接模板、协议、端口、凭据引用。
连接成功后的故障诊断 → `@reference: diagnosis/debug_skill.md`

安全原则：所有 password / token 字段均指向环境变量或 Vault，禁止硬编码明文。

---

## 1. 操作系统与虚拟机 (Linux/VM/Host)

### 1.1 标准主机 SSH 连接
- **节点类型**: `linux_host`
- **协议**: SSH
- **默认端口**: 22
- **凭据来源**: `SSH_USER` (env), `SSH_KEY_PATH` (env)

Ansible 连接模板:
```json
{
  "ansible_connection": "ssh",
  "ansible_user": "{{ lookup('env', 'SSH_USER') }}",
  "ansible_ssh_private_key_file": "{{ lookup('env', 'SSH_KEY_PATH') }}",
  "ansible_ssh_common_args": "-o StrictHostKeyChecking=no -o ConnectTimeout=10"
}
```

Bash 登录指令:
```bash
ssh -i {{ ssh_key_path }} -p 22 -o StrictHostKeyChecking=no -o ConnectTimeout=10 {{ ssh_user }}@<HOST_IP>
```

### 1.2 网络设备
- **节点类型**: `network_switch`
- **协议**: SSH (network_cli)
- **凭据来源**: Vault

```json
{
  "ansible_connection": "network_cli",
  "ansible_network_os": "cisco.ios.ios",
  "ansible_user": "{{ vault_network_user }}",
  "ansible_password": "{{ vault_network_pass }}"
}
```

---

## 2. 数据库连接

### 2.1 本地/自建 MySQL/MariaDB
- **节点类型**: `mysql_db`
- **协议**: TCP (MySQL Protocol)
- **默认端口**: 3306

Bash 连接指令:
```bash
mysql -h <HOST_IP> -P 3306 -u {{ db_user }} -p'{{ db_pass }}' -e "<SQL>"
```

Ansible 模块:
```yaml
community.mysql.mysql_query:
  login_host: "<HOST_IP>"
  login_port: 3306
  login_user: "{{ db_user }}"
  login_password: "{{ db_pass }}"
  query: "SELECT 1"
```

### 2.2 Redis
- **节点类型**: `redis_cache`
- **协议**: TCP
- **默认端口**: 6379

Bash 连接指令:
```bash
redis-cli -h <HOST_IP> -p 6379 -a '{{ redis_pass }}' INFO
```

---

## 3. 阿里云数据库连接 (RDS / PolarDB / DMS)

### 3.1 连接方式总览

| 方式 | 适用场景 | 特点 |
|------|---------|------|
| DMS 控制台 | 日常运维、图形化操作 | Web 界面，无需客户端 |
| CLI 命令行 | 脚本自动化 | mysql/pg CLI + SSL |
| Python SQLAlchemy | 应用程序代码 | 推荐用于 AIOps 平台 |
| 内网 VPC 地址 | 生产环境 | 低延迟，高安全性 |
| 公网地址 | 开发测试 | 需配置白名单 |

### 3.2 必需环境变量

| 变量名 | 类型 | 说明 |
|--------|------|------|
| `RDS_HOST` | string | RDS/PolarDB 连接地址 (如 `rm-bp1xxxx.mysql.rds.aliyuncs.com`) |
| `RDS_PORT` | int | 端口 (MySQL=3306, PG=5432) |
| `RDS_USER` | string | 数据库用户名 |
| `RDS_PASSWORD` | string | 数据库密码 (通过 .env 注入) |
| `RDS_DB_NAME` | string | 默认数据库名 |
| `ALIYUN_ACCESS_KEY_ID` | string | 阿里云 AK (用于 API 操作) |
| `ALIYUN_ACCESS_KEY_SECRET` | string | 阿里云 SK |
| `ALIYUN_REGION_ID` | string | 地域 (如 `cn-hangzhou`) |

可选变量:

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `RDS_SSL_MODE` | `REQUIRED` | SSL 模式: DISABLED, REQUIRED, VERIFY_CA, VERIFY_IDENTITY |
| `RDS_CONNECTION_TIMEOUT` | `10` | 连接超时(秒) |
| `RDS_MAX_CONNECTIONS` | `20` | 连接池最大连接数 |
| `RDS_POOL_RECYCLE` | `3600` | 连接回收时间(秒) |
| `POLARDB_ENDPOINT_TYPE` | `cluster` | PolarDB 端点类型: cluster(主节点) / reader(只读) |

### 3.3 MySQL CLI 连接模板

```bash
mysql -h {{ rds_host }} -P {{ rds_port }} \
      -u {{ rds_user }} -p'{{ rds_pass }}' \
      --ssl-mode={{ rds_ssl_mode | default('REQUIRED') }} \
      --connect-timeout={{ rds_connection_timeout | default(10) }} \
      {{ rds_db_name }}
```

### 3.4 PostgreSQL CLI 连接模板

```bash
PGPASSWORD='{{ rds_pass }}' psql \
    "host={{ rds_host }} port={{ rds_port }} \
     dbname={{ rds_db_name }} user={{ rds_user }} \
     sslmode=require connect_timeout={{ rds_connection_timeout | default(10) }}"
```

### 3.5 Python SQLAlchemy 连接 (推荐用于应用层)

#### MySQL:
```python
from sqlalchemy import create_engine, text
import os

engine = create_engine(
    f"mysql+pymysql://{os.getenv('RDS_USER')}:{os.getenv('RDS_PASSWORD')}"
    f"@{os.getenv('RDS_HOST')}:{os.getenv('RDS_PORT')}/{os.getenv('RDS_DB_NAME')}"
    f"?charset=utf8mb4&ssl_mode={os.getenv('RDS_SSL_MODE', 'REQUIRED')}",
    pool_size=int(os.getenv('RDS_MAX_CONNECTIONS', '10')),
    pool_recycle=int(os.getenv('RDS_POOL_RECYCLE', '3600')),
    pool_pre_ping=True,
)
with engine.connect() as conn:
    result = conn.execute(text("SELECT VERSION()"))
    print(result.scalar())
```

#### PostgreSQL:
```python
engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('RDS_USER')}:{os.getenv('RDS_PASSWORD')}"
    f"@{os.getenv('RDS_HOST')}:{os.getenv('RDS_PORT')}/{os.getenv('RDS_DB_NAME')}"
    f"?sslmode={os.getenv('RDS_SSL_MODE', 'require')}",
)
```

### 3.6 PolarDB 多节点连接

```python
# 写操作 → 主节点 (Cluster Endpoint)
WRITE_ENGINE = create_engine(
    f"mysql+pymysql://{user}:{passw}@{cluster_endpoint}:3306/{db}?ssl_mode=REQUIRED",
    pool_size=5,
)

# 读操作 → 只读节点 (Reader Endpoint, 格式: <集群ID>.ro.mysql.polardb.rds.aliyuncs.com)
READ_ENGINE = create_engine(
    f"mysql+pymysql://{user}:{passw}@{reader_endpoint}:3306/{db}?ssl_mode=REQUIRED",
    pool_size=10,
)
```

### 3.7 Ansible 执行 MySQL 查询

```yaml
- name: 检查 RDS 连接状态
  community.mysql.mysql_query:
    login_host: "{{ rds_host }}"
    login_port: "{{ rds_port }}"
    login_user: "{{ rds_user }}"
    login_password: "{{ rds_pass }}"
    login_db: "{{ rds_db_name }}"
    login_ssl_mode: REQUIRED
    query:
      - SELECT @@version
      - SHOW STATUS LIKE 'Threads_connected'
  register: rds_status
  ignore_errors: true
```

### 3.8 DMS (数据管理服务) 连接

Web 控制台方式:
1. 登录 [DMS 控制台](https://dms.console.aliyun.com/)
2. 选择目标实例 → 点击「登录」
3. 使用已授权账号登录 → SQL Console 执行查询

API 自动化方式:
```python
import requests, os
from datetime import datetime, timezone

def dms_execute_sql(instance_id: str, sql: str, db_name: str):
    endpoint = f"dms-vpc.{os.getenv('ALIYUN_REGION_ID')}.aliyuncs.com"
    headers = {
        "Content-Type": "application/json",
        "x-acs-action": "ExecuteDataCorrect",
        "x-acs-version": "2022-01-06",
        "x-acs-accesskey-id": os.getenv("ALIYUN_ACCESS_KEY_ID"),
        "x-acs-signature-method": "HMAC-SHA256",
        "x-acs-timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    body = {"InstanceId": instance_id, "DbId": db_name, "Sql": sql, "OrderType": "COMMON"}
    return requests.post(f"https://{endpoint}/", headers=headers, json=body).json()
```

### 3.9 连通性快速验证 (仅验证能否连上)

```bash
# Step 1: TCP 端口可达性
nc -zv -w 5 {{ rds_host }} {{ rds_port }}
# 或: telnet {{ rds_host }} {{ rds_port }}

# Step 2: DNS 解析
nslookup {{ rds_host }}

# Step 3: 凭据验证 (MySQL)
mysqladmin -h {{ rds_host }} -P {{ rds_port }} -u {{ rds_user }} -p'{{ rds_pass }}' ping

# Step 3: 凭据验证 (PostgreSQL)
PGPASSWORD='{{ rds_pass }}' psql "host={{ rds_host }} port={{ rds_port }} dbname={{ rds_db_name }} user={{ rds_user }} sslmode=require" -c "SELECT 1;"
```

判断标准:
| 结果 | 含义 | 下一步 |
|------|------|--------|
| Connected / Succeeded | 端口可达 + 认证通过 | ✅ 连接正常 |
| Access denied | 用户名/密码错误 | 检查 `.env` 中 `RDS_USER` / `RDS_PASSWORD` |
| Connection timed out | 网络不通 | 检查白名单/安全组 (见 debug_skill) |
| SSL connection error | TLS 配置不匹配 | 调整 `--ssl-mode` 参数 |

---

## 4. 中间件连接

### 4.1 RabbitMQ
- **节点类型**: `rabbitmq_node`
- **协议**: HTTP API (15672) / AMQP (5672)

本地 CLI (通过 SSH 后执行):
```bash
rabbitmqctl status
```

远程 API:
```bash
curl -u <USER>:<PASS> http://<HOST_IP>:15672/api/overview
```

### 4.2 Nginx/Tomcat
- **节点类型**: `web_server`
- **访问方式**: 通过 SSH 进入宿主机操作，或 HTTP 接口探测

---

## 5. Kubernetes (K8S) 集群

- **节点类型**: `k8s_cluster`
- **协议**: HTTPS (Kube-apiserver)
- **默认端口**: 6443
- **认证**: kubeconfig 文件 或 ServiceAccount Token

Kubeconfig 方式:
```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get pods -n <NAMESPACE>
```

Token 远程调用:
```bash
kubectl --server=https::<K8S_API_IP>:6443 --token=<TOKEN> --insecure-skip-tls-verify get nodes
```

Ansible 模块:
```yaml
kubernetes.core.k8s_info:
  kubeconfig: "/path/to/kubeconfig"
  api_key: "{{ k8s_token }}"
  host: "https://<K8S_API_IP>:6443"
  validate_certs: false
  kind: Pod
```

---

## 6. 云平台/管理节点

### 6.1 vCenter/ESXi
- **节点类型**: `vmware_host`
- **协议**: HTTPS (SOAP/REST)

```yaml
hostname: "<VCENTER_IP>"
username: "{{ vcenter_user }}"
password: "{{ vcenter_pass }}"
validate_certs: no
```

### 6.2 备用连接方式 (当 SSH/RDP 不可用时)

当常规网络连接失败时使用：

**方式 A — 云厂商控制台 (Workbench/VNC)**:
适用: 阿里云 ECS、腾讯云 CVM、AWS EC2、Azure VM
步骤: 控制台 → 实例详情 → 远程连接/VNC → 使用控制台凭据登录

**方式 B — 虚拟化平台 VNC**:
适用: VMware vSphere、Proxmox、OpenStack
步骤: 管理界面 → 虚拟机 → 打开控制台会话

---

## 7. SSH 连通性快速验证 (仅 2 步)

> ⚠️ 深度故障恢复（服务重启、防火墙修复等）→ `@reference: diagnosis/debug_skill.md` 第 7 节

### Step 1: 网络层验证
```bash
ping -c 4 <HOST_IP>
```
- 成功 (丢包率 < 50%) → 进入 Step 2
- 失败 (100% loss) → 网络故障，检查路由/防火墙/安全组

### Step 2: 端口层验证
```bash
nc -zv -w 5 <HOST_IP> 22
```
- Connected → 端口开放，检查认证凭据
- Connection refused → 服务未启动或防火墙拦截
- timeout → 端口不可达，进入备用连接方式 (第 6.2 节)

---

## 8. 凭据映射表

供 Orchestrator 和 Agent 动态解析变量使用。

| 变量名 | 类型 | 说明 | 来源 |
|--------|------|------|------|
| `{{ ssh_key_path }}` | SSH Key | 运维机私钥路径 | Env: `SSH_KEY_PATH` (默认 `~/.ssh/id_rsa`) |
| `{{ ssh_user }}` | User | SSH 登录用户名 | Env: `SSH_USER` |
| `{{ rds_host }}` | Host | 阿里云 RDS/PolarDB 地址 | Env: `RDS_HOST` |
| `{{ rds_port }}` | Port | 数据库端口 | Env: `RDS_PORT` (默认 3306) |
| `{{ rds_user }}` | User | 数据库用户名 | Env: `RDS_USER` |
| `{{ rds_pass }}` | Password | 数据库密码 | Env: `RDS_PASSWORD` |
| `{{ rds_db_name }}` | Database | 数据库名 | Env: `RDS_DB_NAME` |
| `{{ aliyun_ak_id }}` | Key | 阿里云 AccessKey ID | Env: `ALIYUN_ACCESS_KEY_ID` |
| `{{ aliyun_ak_secret }}` | Secret | 阿里云 AccessKey Secret | Env: `ALIYUN_ACCESS_KEY_SECRET` |
| `{{ aliyun_region }}` | Region | 阿里云地域 | Env: `ALIYUN_REGION_ID` |
| `{{ vault_db_root_pass }}` | Password | 数据库 Root 密码 | Vault: `secret/data/mysql` |
| `{{ k8s_token }}` | Token | K8S 集群访问令牌 | Env: `K8S_API_TOKEN` |
