# 权限问题排查技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `权限拒绝`, `Permission Denied`, `403`, `Forbidden`
- `ACL`, `sudo`, `文件权限`, `chown`, `chmod`
- `SELinux`, `AppArmor`, `安全上下文`
- `访问拒绝`, `认证失败`, `授权失败`

### 1.2 适用条件
- 文件/目录访问被拒绝
- 服务启动失败 (权限不足)
- sudo 权限问题
- SELinux/AppArmor 阻止操作
- 数据库访问权限问题

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 确认错误类型                                       │
│  - Permission Denied (文件)                                 │
│  - 403 Forbidden (HTTP)                                     │
│  - Access Denied (数据库)                                   │
│  - SELinux/AppArmor 拒绝                                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 文件权限检查                                       │
│  - 所有者/组/其他权限                                       │
│  - ACL 扩展权限                                             │
│  - 父目录权限                                               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 安全模块检查                                       │
│  - SELinux 模式与上下文                                     │
│  - AppArmor 配置文件                                        │
│  - 审计日志                                                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 服务权限检查                                       │
│  - 运行用户                                                 │
│  - 端口绑定权限                                             │
│  - 配置文件权限                                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 文件权限检查

```bash
# 查看文件权限
ls -la <file_or_dir>
stat <file_or_dir>

# 查看所有者
stat -c "%U:%G %a %n" <file_or_dir>

# 查看 ACL
getfacl <file_or_dir>

# 查看父目录权限 (需要执行权限才能进入)
namei -l <path>

# 查看当前用户
whoami
id

# 查看用户组
groups <username>

# 查看文件属性 (不可变)
lsattr <file>
```

### 3.2 SELinux 检查

```bash
# 查看 SELinux 模式
getenforce

# 查看 SELinux 详细配置
sestatus

# 查看 SELinux 上下文
ls -Z <file_or_dir>
ps -Z -C <process_name>

# 查看 SELinux 审计日志 (拒绝记录)
ausearch -m avc -ts recent
grep "denied" /var/log/audit/audit.log | tail -20

# 查看 SELinux 布尔值
getsebool -a | grep <service>

# 分析拒绝原因
sealert -a /var/log/audit/audit.log 2>/dev/null | tail -50
```

### 3.3 AppArmor 检查

```bash
# 查看 AppArmor 状态
aa-status

# 查看配置文件状态
aa-status --pretty

# 查看进程的 AppArmor 配置
cat /proc/<pid>/attr/current

# 查看拒绝日志
dmesg | grep -i apparmor | tail -20
grep apparmor /var/log/syslog | tail -20
```

### 3.4 服务权限检查

```bash
# 查看服务运行用户
ps aux | grep <service>
ps -o user,pid,cmd -C <process_name>

# 查看服务配置文件权限
ls -la /etc/<service>/

# 查看端口绑定权限 (< 1024 需要 root)
ss -tlnp | grep <service>

# 查看 sudo 配置
sudo -l
cat /etc/sudoers
cat /etc/sudoers.d/*

# 查看能力 (capabilities)
getcap <executable>
```

### 3.5 数据库权限

```sql
-- MySQL 权限
SHOW GRANTS FOR '<user>'@'<host>';
SELECT user, host FROM mysql.user;

-- PostgreSQL 权限
\du  -- 列出所有角色
SELECT * FROM information_schema.role_table_grants WHERE grantee = '<user>';

-- MongoDB 权限
db.getUser("<username>")
db.getRoles()
```

---

## 4. 常见问题与解决方案

### 4.1 文件 Permission Denied

**诊断步骤**:
```bash
# 1. 检查文件权限
ls -la <file>
stat <file>

# 2. 检查路径上所有目录
namei -l <file>

# 3. 检查 ACL
getfacl <file>

# 4. 检查 SELinux
ls -Z <file>
```

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 修改所有者 | `chown user:group <file>` | 🟡 中 |
| 修改权限 | `chmod 644 <file>` | 🟡 中 |
| 修改 ACL | `setfacl -m u:<user>:rwx <file>` | 🟢 低 |
| 修改父目录 | `chmod +x <parent_dir>` | 🟡 中 |

### 4.2 SELinux 阻止

**诊断步骤**:
```bash
# 1. 确认 SELinux 模式
getenforce

# 2. 查看拒绝日志
ausearch -m avc -ts recent

# 3. 分析原因
sealert -a /var/log/audit/audit.log
```

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 修复上下文 | `restorecon -Rv <path>` | 🟢 低 |
| 设置布尔值 | `setsebool -P <bool> on` | 🟢 低 |
| 临时 Permissive | `setenforce 0` | 🟡 中 (仅排查) |
| 永久关闭 | `/etc/selinux/config` | 🔴 高 (不推荐) |

### 4.3 sudo 权限不足

**诊断步骤**:
```bash
sudo -l
cat /etc/sudoers
```

**解决方案**:

| 方案 | 操作 | 风险 |
|------|------|------|
| 添加 sudo 规则 | 在 `/etc/sudoers.d/` 添加 | 🟡 中 |
| 使用 sudo 组 | `usermod -aG wheel <user>` | 🟡 中 |
| NOPASSWD | `<user> ALL=(ALL) NOPASSWD: ALL` | 🔴 高 (不推荐) |

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
ls -la, stat, getfacl
getenforce, sestatus, ls -Z
whoami, id, groups
sudo -l
```

### 5.2 需要确认的操作
```bash
chmod, chown, setfacl
setsebool, restorecon
修改 /etc/sudoers
```

### 5.3 危险操作禁止执行
```bash
chmod -R 777 (递归全权限)
setenforce 0 (生产环境)
chmod 777 /etc/shadow
rm -f /etc/sudoers
```

---

## 6. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
