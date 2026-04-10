# Systemd 服务自启动故障排查 Skill

## 职责边界
本 Skill 专门用于排查 **systemd 服务重启后不能自动恢复** 的问题，包括：
- 服务未设置开机自启动
- 服务启动失败
- 服务依赖关系问题
- 服务配置错误

---

## 1. 问题现象分类

| 现象 | 可能原因 | 优先级 |
|------|----------|--------|
| systemctl status 显示 inactive | 服务未启动或启动失败 | P0 |
| systemctl is-enabled 显示 disabled | 未设置开机自启 | P0 |
| 服务启动后立即退出 | ExecStart 配置错误或进程崩溃 | P0 |
| 服务依赖未就绪 | After/Wants 配置不当 | P1 |
| 服务文件修改后未生效 | 未执行 daemon-reload | P1 |

---

## 2. 标准排查流程

### 2.1 检查服务状态

```bash
systemctl status <service_name>
```

**关键输出分析**：
- `Active: inactive (dead)` → 服务未运行
- `Active: failed` → 服务启动失败，查看下方日志
- `Main PID: 1234 (code=exited, status=1/FAILURE)` → 进程异常退出

### 2.2 检查自启动配置

```bash
systemctl is-enabled <service_name>
```

**输出含义**：
| 输出 | 含义 | 处理方式 |
|------|------|----------|
| `enabled` | 已设置开机自启 | 继续排查其他原因 |
| `disabled` | 未设置开机自启 | 执行 `systemctl enable <service_name>` |
| `static` | 被其他服务依赖启动 | 检查依赖服务 |
| `masked` | 服务被禁用 | 执行 `systemctl unmask <service_name>` |

### 2.3 查看服务日志

```bash
journalctl -u <service_name> -n 50 --no-pager
journalctl -u <service_name> -f
journalctl -u <service_name> --since "1 hour ago"
```

### 2.4 检查服务文件配置

```bash
systemctl cat <service_name>
```

**关键配置项检查**：
```ini
[Unit]
Description=服务描述
After=network.target        # 依赖项，确保网络就绪后启动
Wants=network-online.target # 可选依赖

[Service]
Type=simple                 # simple/forking/oneshot/notify
ExecStart=/path/to/script   # 启动命令
ExecStop=/path/to/stop      # 停止命令（可选）
Restart=on-failure          # 重启策略: no/on-failure/always
RestartSec=5s               # 重启间隔
User=root                   # 运行用户
WorkingDirectory=/path      # 工作目录

[Install]
WantedBy=multi-user.target  # 安装目标
```

### 2.5 检查启动脚本可执行性

```bash
ls -la /path/to/script
file /path/to/script
head -1 /path/to/script
```

**常见问题**：
- 脚本无执行权限 → `chmod +x /path/to/script`
- 脚本 shebang 错误 → 检查第一行 `#!/bin/bash`
- 脚本路径错误 → 确认 ExecStart 路径正确

---

## 3. 典型场景排查

### 3.1 场景：持续写数据服务重启后不自动恢复

**问题描述**：用 systemctl 运行服务持续写数据到文件，重启服务器后服务未自动启动。

**排查步骤**：

```bash
# Step 1: 检查服务状态
systemctl status write-data.service

# Step 2: 检查是否设置自启动
systemctl is-enabled write-data.service

# Step 3: 如果是 disabled，设置自启动
systemctl enable write-data.service

# Step 4: 查看启动日志
journalctl -u write-data.service -n 100

# Step 5: 手动启动测试
systemctl start write-data.service

# Step 6: 检查服务文件
systemctl cat write-data.service
```

### 3.2 正确的服务配置示例

```ini
[Unit]
Description=Data Writer Service
Documentation=持续写数据到文件
After=network.target
After=local-fs.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/opt/scripts/write_data.sh
ExecStop=/bin/kill -SIGTERM $MAINPID
Restart=always
RestartSec=10s
User=root
Group=root
WorkingDirectory=/opt/scripts

# 日志配置
StandardOutput=journal
StandardError=journal
SyslogIdentifier=write-data

# 资源限制
LimitNOFILE=65535
TimeoutStartSec=30
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

### 3.3 写数据脚本示例

```bash
#!/bin/bash
# /opt/scripts/write_data.sh

DATA_FILE="/var/log/data/output.log"
mkdir -p "$(dirname "$DATA_FILE")"

while true; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Data entry" >> "$DATA_FILE"
    sleep 1
done
```

---

## 4. 常见问题与解决方案

### 4.1 服务启动后立即退出

**原因**：Type 配置错误，或脚本本身有问题

**排查**：
```bash
# 检查脚本是否在前台运行
# Type=simple 要求进程保持前台运行

# 如果脚本会退出，使用 Type=forking 或添加 --no-daemon 参数
```

### 4.2 服务依赖未就绪

**原因**：After/Wants 配置不当

**解决**：
```ini
[Unit]
After=network.target
After=network-online.target
Wants=network-online.target
```

### 4.3 服务文件修改后未生效

**原因**：未执行 daemon-reload

**解决**：
```bash
systemctl daemon-reload
systemctl restart <service_name>
```

### 4.4 服务被 mask 禁用

**排查**：
```bash
systemctl is-enabled <service_name>
# 输出: masked

# 解决
systemctl unmask <service_name>
systemctl enable <service_name>
```

### 4.5 服务依赖远程文件系统未就绪（重要！）

**现象**：
- 服务状态显示 `failed (Result: start-limit)`
- 日志显示类似 "目录未挂载"、"文件不存在" 等错误
- 服务已设置 `enabled`，但重启后仍无法启动

**根因分析**：
- `/etc/fstab` 中配置的挂载点使用了 `_netdev` 标记
- 服务配置只写了 `After=network.target`，未等待远程文件系统
- 服务启动时，网络文件系统尚未挂载完成

**排查步骤**：
```bash
# 1. 检查 fstab 中的挂载配置
cat /etc/fstab | grep -v "^#" | grep -v "^$"

# 2. 检查挂载点状态
df -h | grep <mount_point>
mount | grep <mount_point>

# 3. 查看服务日志中的具体错误
journalctl -u <service_name> -n 50 --no-pager
```

**解决方案**：
```ini
[Unit]
Description=Data Writer Service
After=network.target remote-fs.target
Requires=remote-fs.target

[Service]
Type=simple
ExecStart=/path/to/script.sh
Restart=on-failure
RestartSec=5s
User=root

[Install]
WantedBy=multi-user.target
```

**关键配置说明**：
| 配置项 | 说明 |
|--------|------|
| `After=remote-fs.target` | 等待远程文件系统挂载完成 |
| `Requires=remote-fs.target` | 强制依赖远程文件系统 |

**验证修复**：
```bash
# 重新加载配置
systemctl daemon-reload

# 重启服务
systemctl restart <service_name>

# 检查状态
systemctl status <service_name>
```

---

## 5. 验证自启动配置

### 5.1 模拟重启验证

```bash
# 方法1: 检查服务状态
systemctl is-enabled <service_name>
systemctl is-active <service_name>

# 方法2: 查看启动链接
ls -la /etc/systemd/system/multi-user.target.wants/

# 方法3: 模拟启动流程
systemd-analyze verify /etc/systemd/system/<service_name>.service
```

### 5.2 实际重启验证

```bash
# 记录当前状态
systemctl status <service_name> > /tmp/before_reboot.txt

# 重启服务器
reboot

# 重启后检查
systemctl status <service_name>
```

---

## 6. 最佳实践

### 6.1 服务配置建议

| 配置项 | 建议 | 原因 |
|--------|------|------|
| `Restart=always` | 推荐 | 确保异常退出后自动重启 |
| `RestartSec=10s` | 推荐 | 避免频繁重启 |
| `After=network.target` | 推荐 | 确保网络就绪 |
| `StandardOutput=journal` | 推荐 | 便于日志收集 |
| `LimitNOFILE=65535` | 按需 | 避免文件描述符耗尽 |

### 6.2 监控与告警

```bash
# 检查服务是否运行
systemctl is-active <service_name> || echo "ALERT: Service not running"

# 检查自启动是否启用
systemctl is-enabled <service_name> || echo "ALERT: Auto-start disabled"

# 检查服务最近是否重启
systemctl show <service_name> -p NRestarts
```

---

## 7. 快速诊断命令汇总

```bash
# 一键诊断脚本
#!/bin/bash
SERVICE=$1

echo "=== Service Status ==="
systemctl status $SERVICE --no-pager

echo -e "\n=== Auto-start Status ==="
systemctl is-enabled $SERVICE

echo -e "\n=== Recent Logs ==="
journalctl -u $SERVICE -n 20 --no-pager

echo -e "\n=== Service Config ==="
systemctl cat $SERVICE

echo -e "\n=== Dependency Tree ==="
systemctl list-dependencies $SERVICE --all

echo -e "\n=== Failed Services ==="
systemctl list-units --state=failed
```

---

## 8. 相关 Skill 引用

- 网络排查 → `@reference: diagnosis/debug_skill.md#网络排查`
- 进程排查 → `@reference: diagnosis/debug_skill.md#系统排查`
- 日志分析 → `@reference: diagnosis/log_analysis_skill.md`
