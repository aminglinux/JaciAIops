# 安全事件排查技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `暴力破解`, `异常登录`, `SSH攻击`, `入侵检测`
- `可疑进程`, `挖矿`, `后门`, `反弹Shell`
- `权限提升`, `提权`, `sudo滥用`
- `异常网络连接`, `数据泄露`, `异常流量`
- `安全事件`, `应急响应`, `取证`

### 1.2 适用条件
- SSH 暴力破解告警
- 异常登录检测 (异地/非工作时间)
- 可疑进程 / 挖矿木马
- 反弹 Shell 检测
- 权限提升事件
- 异常外联 / 数据外泄

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 事件确认                                           │
│  - 确认安全事件类型                                         │
│  - 评估影响范围                                             │
│  - 确定响应等级 (P0/P1/P2)                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 登录安全检查                                       │
│  - SSH 登录日志                                             │
│  - 失败登录统计                                             │
│  - 异常登录来源                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 进程与文件检查                                     │
│  - 可疑进程                                                 │
│  - 异常定时任务                                             │
│  - 新增/修改文件                                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 网络连接检查                                       │
│  - 异常外联                                                 │
│  - 反弹 Shell 检测                                         │
│  - 可疑端口监听                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 用户与权限检查                                     │
│  - 新增用户                                                 │
│  - sudo 权限变更                                            │
│  - SSH 密钥变更                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┘
│  Step 5: 生成安全事件报告与处置建议                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 SSH 登录安全检查

```bash
# 查看最近登录记录
last -20
lastb -20  # 失败登录

# SSH 登录失败统计 (暴力破解检测)
grep "Failed password" /var/log/auth.log | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head -20

# CentOS/RHEL
grep "Failed password" /var/log/secure | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head -20

# 查看成功登录的来源 IP
grep "Accepted" /var/log/auth.log | awk '{print $11}' | sort | uniq -c | sort -rn | head -20

# 查看异常时间登录 (非工作时间: 22:00-08:00)
grep "Accepted" /var/log/auth.log | awk '{if ($3 ~ /^0[0-7]:/ || $3 ~ /^2[2-3]:/) print}'

# 查看从异常 IP 登录
grep "Accepted" /var/log/auth.log | grep -v -E "$(hostname -I | tr ' ' '|')|127.0.0.1|10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\."

# 查看当前登录用户
w
who

# 查看 SSH 配置安全项
grep -E "PermitRootLogin|PasswordAuthentication|MaxAuthTries|AllowUsers" /etc/ssh/sshd_config
```

### 3.2 可疑进程检查

```bash
# 查看所有进程 (关注高 CPU/内存)
ps aux --sort=-%cpu | head -20
ps aux --sort=-%mem | head -20

# 查找隐藏进程 (与 /proc 对比)
ls /proc | grep -E "^[0-9]+$" | sort -n > /tmp/proc_pids.txt
ps -eo pid | sort -n > /tmp/ps_pids.txt
diff /tmp/proc_pids.txt /tmp/ps_pids.txt

# 查找挖矿进程特征
ps aux | grep -iE "xmr|minerd|cpuminer|cryptonight|stratum"
ps aux | grep -iE "kworker.*-[0-9]" | grep -v "kworker/[0-9]"

# 查看进程可执行文件
ls -la /proc/<pid>/exe
cat /proc/<pid>/cmdline | tr '\0' ' '

# 查看进程打开的文件
lsof -p <pid>

# 查看进程网络连接
lsof -p <pid> -i

# 查看进程启动时间
ps -eo pid,lstart,cmd | grep <pid>
```

### 3.3 定时任务检查

```bash
# 查看系统定时任务
crontab -l
cat /etc/crontab
ls -la /etc/cron.d/
ls -la /etc/cron.daily/
ls -la /etc/cron.hourly/

# 查看所有用户的定时任务
for user in $(cut -f1 -d: /etc/passwd); do
  crontab_content=$(crontab -u $user -l 2>/dev/null)
  if [ -n "$crontab_content" ]; then
    echo "=== User: $user ==="
    echo "$crontab_content"
  fi
done

# 查看最近修改的定时任务
find /etc/cron* -mtime -7 -ls

# 查看 systemd 定时器
systemctl list-timers --all
```

### 3.4 网络连接检查

```bash
# 查看所有网络连接
netstat -antlp || ss -antlp

# 查看异常外联 (非内网 IP)
netstat -antp | grep ESTABLISHED | grep -v -E "127.0.0.1|10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\."

# 查看可疑端口监听
netstat -tlnp | grep -v -E ":22|:80|:443|:3306|:6379|:9092|:8080|:8000|:3000"

# 反弹 Shell 检测
# 特征: /bin/bash -i, /bin/sh -i, nc -e, /dev/tcp/
ps aux | grep -E "bash -i|sh -i|nc -e|/dev/tcp|socat"
lsof -i | grep -E "bash|sh|nc|socat|python|perl|ruby"

# 查看异常 DNS 查询
tcpdump -i any -n port 53 -c 100 2>/dev/null

# 查看异常流量
iftop -t -s 10 2>/dev/null
```

### 3.5 文件变更检查

```bash
# 查看最近 24 小时修改的文件
find / -mtime -1 -type f -not -path "/proc/*" -not -path "/sys/*" -not -path "/dev/*" 2>/dev/null | head -50

# 查看 SUID 文件 (提权风险)
find / -perm -4000 -type f 2>/dev/null

# 查看新增用户
grep -E "^[^:]+:[^:]*:[0-9]{4,}" /etc/passwd

# 查看 sudo 权限
cat /etc/sudoers
cat /etc/sudoers.d/*

# 查看 SSH 授权密钥
cat ~/.ssh/authorized_keys
find /home -name "authorized_keys" -exec ls -la {} \; -exec cat {} \;

# 查看最近修改的 SSH 配置
find /etc/ssh -mtime -7 -ls
```

### 3.6 阿里云安全中心

```bash
# 查询安全告警
aliyun sas DescribeSuspEvents --RegionId cn-hangzhou --CurrentPage 1 --PageSize 20

# 查询漏洞列表
aliyun sas DescribeVulList --RegionId cn-hangzhou --Type cve

# 查询基线检查结果
aliyun sas DescribeCheckResult --RegionId cn-hangzhou

# 查询资产指纹 (进程/端口/软件)
aliyun sas DescribePropertyScaItem --RegionId cn-hangzhou
```

---

## 4. 常见问题与解决方案

### 4.1 SSH 暴力破解

**现象**: 大量 SSH 登录失败日志

**诊断步骤**:
```bash
# 1. 统计失败次数
grep "Failed password" /var/log/auth.log | wc -l

# 2. 统计攻击来源 IP
grep "Failed password" /var/log/auth.log | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head -10

# 3. 检查是否有成功入侵
grep "Accepted" /var/log/auth.log | grep "<攻击IP>"
```

**处置方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 封禁攻击 IP | `iptables -A INPUT -s <ip> -j DROP` | 🟢 低 |
| 禁用密码登录 | `PasswordAuthentication no` | 🟡 中 (需确认密钥已配置) |
| 安装 fail2ban | `apt install fail2ban` | 🟢 低 |
| 限制登录 IP | `AllowUsers *@10.* *@192.168.*` | 🟡 中 |
| 修改 SSH 端口 | `Port 2222` | 🟡 中 |

### 4.2 挖矿木马

**现象**: CPU 使用率异常飙高，可疑进程

**诊断步骤**:
```bash
# 1. 查找高 CPU 进程
top -b -n 1 | head -20

# 2. 检查进程详情
ls -la /proc/<pid>/exe
cat /proc/<pid>/cmdline | tr '\0' ' '

# 3. 检查定时任务 (通常有持久化)
crontab -l
cat /etc/crontab

# 4. 检查网络连接 (矿池)
netstat -antp | grep <pid>
```

**处置方案**:

| 步骤 | 操作 | 风险 |
|------|------|------|
| 1. 杀死进程 | `kill -9 <pid>` | 🟡 中 |
| 2. 删除文件 | `rm -f <恶意文件>` | 🟡 中 |
| 3. 清理定时任务 | `crontab -r` / 编辑 crontab | 🟡 中 |
| 4. 清理 SSH 密钥 | 删除异常 authorized_keys | 🟡 中 |
| 5. 修复漏洞 | 更新系统/应用补丁 | 🟢 低 |

### 4.3 反弹 Shell

**现象**: 服务器主动外联到攻击者 IP

**诊断步骤**:
```bash
# 1. 检查反弹 Shell 进程
ps aux | grep -E "bash -i|sh -i|nc -e|/dev/tcp"

# 2. 检查异常网络连接
netstat -antp | grep ESTABLISHED | grep -v -E "127.0.0.1|10\.|192\.168\."

# 3. 检查进程可执行文件
lsof -p <pid> | grep txt
```

**处置方案**:

| 步骤 | 操作 | 风险 |
|------|------|------|
| 1. 断开连接 | `kill -9 <pid>` | 🟡 中 |
| 2. 封禁 IP | `iptables -A OUTPUT -d <ip> -j DROP` | 🟡 中 |
| 3. 查找入口 | 分析日志找入侵路径 | 🟢 低 |
| 4. 修复漏洞 | 修补 Web 漏洞等 | 🟢 低 |

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
last, lastb, who, w
grep 日志文件
ps, netstat, ss, lsof
find (查找文件)
cat 配置文件
```

### 5.2 需要确认的操作
```bash
iptables 封禁 IP
kill 杀死可疑进程
修改 SSH 配置
删除恶意文件
```

### 5.3 危险操作禁止执行
```bash
rm -rf / (任何递归删除根目录)
关闭防火墙 (iptables -F)
修改 /etc/passwd (直接编辑)
修改 /etc/shadow
```

---

## 6. 快速诊断脚本

```bash
#!/bin/bash

echo "=== SSH 登录失败 Top 10 IP ==="
grep "Failed password" /var/log/auth.log 2>/dev/null | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head -10

echo -e "\n=== 当前登录用户 ==="
w 2>/dev/null

echo -e "\n=== 高 CPU 进程 Top 10 ==="
ps aux --sort=-%cpu | head -12

echo -e "\n=== 异常外联连接 ==="
netstat -antp 2>/dev/null | grep ESTABLISHED | grep -v -E "127.0.0.1|10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\." | head -10

echo -e "\n=== 可疑端口监听 ==="
ss -tlnp 2>/dev/null | grep -v -E ":22 |:80 |:443 |:3306 |:6379 |:9092 " | head -10

echo -e "\n=== 反弹 Shell 检测 ==="
ps aux | grep -E "bash -i|sh -i|nc -e|/dev/tcp" | grep -v grep || echo "未检测到反弹 Shell"

echo -e "\n=== 最近修改的定时任务 ==="
find /etc/cron* -mtime -7 -ls 2>/dev/null

echo -e "\n=== SUID 文件 ==="
find / -perm -4000 -type f 2>/dev/null | head -20

echo -e "\n=== 最近 24h 新增文件 ==="
find / -mtime -1 -type f -not -path "/proc/*" -not -path "/sys/*" -not -path "/dev/*" 2>/dev/null | head -20
```

---

## 7. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
