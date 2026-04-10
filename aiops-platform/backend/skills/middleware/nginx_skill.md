# Nginx 诊断技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `Nginx`, `502`, `504`, `499`, `400`, `403`
- `反向代理`, `upstream`, `网关`, `负载均衡`
- `配置错误`, `重定向循环`, `SSL 错误`
- `连接超时`, `请求超时`, `上游不可用`

### 1.2 适用条件
- Nginx 502 Bad Gateway
- Nginx 504 Gateway Timeout
- Nginx 499 Client Closed Request
- 反向代理配置问题
- SSL/TLS 证书问题
- 性能瓶颈 (连接数/带宽)

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 环境检测                                           │
│  - 检测 Nginx 运行环境 (Docker/K8s/裸机)                   │
│  - 确定配置文件路径                                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Nginx 状态检查                                     │
│  - 进程状态                                                 │
│  - 配置语法检查                                             │
│  - 监听端口                                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 错误日志分析                                       │
│  - error.log 关键错误                                       │
│  - access.log 状态码统计                                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Upstream 连通性检查                                │
│  - 后端服务健康检查                                         │
│  - 网络连通性                                               │
│  - DNS 解析                                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 配置分析                                           │
│  - proxy_pass 配置                                          │
│  - 超时参数                                                 │
│  - 缓冲区设置                                               │
│  - SSL 配置                                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 环境检测与状态

```bash
# 检测 Nginx 进程
ps aux | grep nginx | grep -v grep

# 检测监听端口
netstat -tlnp | grep nginx || ss -tlnp | grep nginx

# 检测 Docker 容器
docker ps | grep nginx

# 检测 Nginx 版本与配置路径
nginx -V 2>&1

# 配置语法检查
nginx -t

# 查看配置文件路径
nginx -t 2>&1 | grep "configuration file"

# 重新加载配置 (需确认)
# nginx -s reload
```

### 3.2 错误日志分析

```bash
# 查找 Nginx 日志路径
grep -r "error_log\|access_log" /etc/nginx/nginx.conf

# 查看最近的错误日志
tail -100 /var/log/nginx/error.log

# 按错误类型过滤
grep -i "502\|upstream\|connect\|timeout\|refused" /var/log/nginx/error.log | tail -50

# 502 错误统计
grep " 502 " /var/log/nginx/access.log | tail -50

# 504 错误统计
grep " 504 " /var/log/nginx/access.log | tail -50

# 499 错误统计 (客户端主动断开)
grep " 499 " /var/log/nginx/access.log | tail -50

# 状态码分布统计
awk '{print $9}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head -20

# Upstream 响应时间分析
awk '{print $NF}' /var/log/nginx/access.log | sort -n | tail -20

# 最近 1 小时的 502 错误
find /var/log/nginx -name "access.log*" -newermt "1 hour ago" -exec grep " 502 " {} \;
```

### 3.3 Upstream 连通性检查

```bash
# 从配置中提取 upstream 地址
grep -r "proxy_pass\|upstream" /etc/nginx/ --include="*.conf"

# 测试 upstream 连通性
curl -v http://upstream_host:upstream_port/health

# 测试 DNS 解析
nslookup upstream_host
dig upstream_host

# 测试 TCP 连通性
nc -zv upstream_host upstream_port

# 测试 upstream 响应时间
curl -o /dev/null -s -w "connect: %{time_connect}\nttfb: %{time_starttransfer}\ntotal: %{time_total}\n" \
  http://upstream_host:upstream_port/

# 检查 upstream 服务进程
ssh upstream_host "ps aux | grep -E 'java|node|python|gunicorn|php-fpm'"
```

### 3.4 配置分析

```bash
# 查看完整配置
cat /etc/nginx/nginx.conf

# 查看所有虚拟主机配置
ls -la /etc/nginx/conf.d/
cat /etc/nginx/conf.d/*.conf

# 查看超时配置
grep -r "proxy_connect_timeout\|proxy_read_timeout\|proxy_send_timeout\|keepalive_timeout" /etc/nginx/

# 查看缓冲区配置
grep -r "proxy_buffer_size\|proxy_buffers\|proxy_busy_buffers_size\|client_body_buffer_size" /etc/nginx/

# 查看 proxy_pass 配置
grep -r "proxy_pass" /etc/nginx/ --include="*.conf"

# 查看 SSL 配置
grep -r "ssl_certificate\|ssl_protocols\|ssl_ciphers" /etc/nginx/

# 查看 upstream 配置块
grep -A 20 "upstream" /etc/nginx/conf.d/*.conf

# 查看负载均衡策略
grep -r "ip_hash\|least_conn\|least_time\|random\|hash" /etc/nginx/
```

### 3.5 Stub Status 监控

```bash
# 检查是否开启 stub_status
grep -r "stub_status" /etc/nginx/

# 如果已开启，查看状态
curl http://127.0.0.1/nginx_status

# 输出说明:
# Active connections: 当前活跃连接数
# server accepts handled requests: 接受/处理/请求总数
# Reading: 读取请求头的连接数
# Writing: 写入响应的连接数
# Waiting: 等待新请求的 keep-alive 连接数
```

---

## 4. 常见问题与解决方案

### 4.1 502 Bad Gateway

**现象**: Nginx 返回 502，upstream 不可达

**诊断步骤**:
```bash
# 1. 查看 error.log
grep "502\|upstream\|connect\|refused" /var/log/nginx/error.log | tail -20

# 2. 检查 upstream 服务
curl -v http://upstream_host:port/health

# 3. 检查 Nginx 配置
grep -A 5 "proxy_pass" /etc/nginx/conf.d/*.conf
```

**常见原因与解决方案**:

| 原因 | error.log 特征 | 解决方案 |
|------|---------------|---------|
| upstream 进程崩溃 | `Connection refused` | 重启后端服务 |
| upstream 端口错误 | `Connection refused` | 修正 proxy_pass 端口 |
| upstream 超时 | `upstream timed out` | 增大 proxy_read_timeout |
| DNS 解析失败 | `no live upstreams` | 检查 DNS / 使用 resolver |
| upstream 返回无效响应 | `upstream sent invalid header` | 检查后端响应格式 |

### 4.2 504 Gateway Timeout

**现象**: Nginx 返回 504，upstream 处理超时

**诊断步骤**:
```bash
# 1. 查看 error.log
grep "504\|timed out" /var/log/nginx/error.log | tail -20

# 2. 检查超时配置
grep -r "proxy_.*timeout" /etc/nginx/

# 3. 测试 upstream 响应时间
curl -o /dev/null -s -w "%{time_total}\n" http://upstream:port/api
```

**解决方案**:
```nginx
# 调整超时参数
proxy_connect_timeout 10s;    # 连接超时
proxy_read_timeout 120s;      # 读取超时
proxy_send_timeout 120s;      # 发送超时

# 针对慢接口单独配置
location /slow-api {
    proxy_read_timeout 300s;
    proxy_pass http://upstream;
}
```

### 4.3 499 Client Closed Request

**现象**: 客户端在 Nginx 等待 upstream 响应期间断开连接

**诊断步骤**:
```bash
# 1. 统计 499 比例
total=$(wc -l < /var/log/nginx/access.log)
code_499=$(grep -c " 499 " /var/log/nginx/access.log)
echo "499 比例: $(echo "scale=2; $code_499*100/$total" | bc)%"

# 2. 分析 499 请求的 upstream 响应时间
grep " 499 " /var/log/nginx/access.log | awk '{print $NF}' | sort -n | tail -20
```

**解决方案**:
```nginx
# 方案 1: 忽略客户端断开，继续等待 upstream 响应
proxy_ignore_client_abort on;

# 方案 2: 优化 upstream 响应速度 (根本解决)
# - 增加后端处理能力
# - 添加缓存
# - 异步化慢操作
```

### 4.4 连接数耗尽

**现象**: 新连接被拒绝，日志出现 `worker_connections are not enough`

**诊断步骤**:
```bash
# 1. 查看当前连接数
curl http://127.0.0.1/nginx_status 2>/dev/null

# 2. 检查 worker_connections 配置
grep "worker_connections" /etc/nginx/nginx.conf

# 3. 检查系统文件描述符限制
ulimit -n
cat /proc/$(pgrep -x nginx | head -1)/limits | grep "open files"
```

**解决方案**:
```nginx
# 增大 worker_connections
events {
    worker_connections 10240;
}

# 增大系统限制
# /etc/security/limits.conf
# * soft nofile 65535
# * hard nofile 65535
```

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
nginx -t
cat /etc/nginx/*.conf
tail/grep 日志文件
curl 测试 upstream
```

### 5.2 需要确认的操作
```bash
nginx -s reload
修改 proxy_timeout 参数
修改 upstream 配置
```

### 5.3 危险操作禁止执行
```bash
nginx -s stop
nginx -s quit
rm -f 日志文件
修改 listen 端口为非标准端口
```

---

## 6. 快速诊断脚本

```bash
#!/bin/bash
NGINX_CONF="${1:-/etc/nginx/nginx.conf}"

echo "=== Nginx 进程状态 ==="
ps aux | grep nginx | grep -v grep

echo -e "\n=== 配置语法检查 ==="
nginx -t 2>&1

echo -e "\n=== 监听端口 ==="
ss -tlnp | grep nginx

echo -e "\n=== 状态码分布 (最近 10000 条) ==="
tail -10000 /var/log/nginx/access.log 2>/dev/null | awk '{print $9}' | sort | uniq -c | sort -rn | head -10

echo -e "\n=== 最近 502/504 错误 ==="
grep -E " 502 | 504 " /var/log/nginx/access.log 2>/dev/null | tail -10

echo -e "\n=== Upstream 配置 ==="
grep -r "proxy_pass" /etc/nginx/ --include="*.conf" 2>/dev/null

echo -e "\n=== 超时配置 ==="
grep -r "proxy_.*timeout" /etc/nginx/ 2>/dev/null
```

---

## 7. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
