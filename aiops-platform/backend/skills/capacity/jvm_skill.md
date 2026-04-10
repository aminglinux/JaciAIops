# JVM 运行时诊断技能

## 目录
- [1. 适用场景](#1-适用场景)
- [2. 诊断流程](#2-诊断流程)
- [3. 诊断命令集](#3-诊断命令集)
- [4. 常见问题与解决方案](#4-常见问题与解决方案)
- [5. 权限边界](#5-权限边界)

---

## 1. 适用场景

### 1.1 触发关键词
- `JVM`, `OOM`, `OutOfMemoryError`, `Heap`, `堆内存`
- `GC`, `Full GC`, `STW`, `Stop-The-World`, `垃圾回收`
- `线程Dump`, `JStack`, `JMap`, `JStat`
- `CPU 飙高`, `内存泄漏`, `Metaspace`, `DirectBuffer`
- `Java`, `Spring Boot`, `Tomcat`

### 1.2 适用条件
- Java 应用 OOM (OutOfMemoryError)
- GC 频繁导致 STW 停顿
- CPU 飙高 (死循环/密集计算)
- 线程死锁 / 线程池耗尽
- 内存泄漏 (堆/非堆/Metaspace)
- 类加载冲突

---

## 2. 诊断流程

```
┌─────────────────────────────────────────────────────────────┐
│  Step 0: 环境检测                                           │
│  - 检测 Java 进程 (PID)                                    │
│  - 确定运行环境 (Docker/K8s/裸机)                           │
│  - 检测 JDK 版本与可用工具                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 1: 进程概览                                           │
│  - JVM 启动参数                                             │
│  - 内存概览                                                 │
│  - GC 统计                                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: 问题分类                                           │
│  - CPU 问题 → Step 3a                                      │
│  - 内存问题 → Step 3b                                      │
│  - GC 问题 → Step 3c                                       │
│  - 线程问题 → Step 3d                                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3a: CPU 诊断          Step 3b: 内存诊断               │
│  - top -H 找高 CPU 线程     - jmap -heap 堆概览             │
│  - jstack 线程栈            - jmap -histo 对象统计           │
│  - 火焰图分析               - 堆 Dump 分析                  │
│                                                              │
│  Step 3c: GC 诊断           Step 3d: 线程诊断               │
│  - jstat GC 统计            - jstack 线程栈                 │
│  - GC 日志分析              - 死锁检测                      │
│  - GC 调优建议              - 线程池状态                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: 定位问题并提供解决方案                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 诊断命令集

### 3.1 环境检测与进程定位

```bash
# 查找 Java 进程
jps -lv
ps aux | grep java | grep -v grep

# Docker 环境
docker exec <container> jps -lv
docker top <container> | grep java

# K8s 环境
kubectl exec <pod> -- jps -lv

# 检测 JDK 工具可用性
which jstack jmap jstat jinfo jcmd

# 查看 JVM 启动参数
jcmd <pid> VM.flags
jinfo -flags <pid>
cat /proc/<pid>/cmdline | tr '\0' ' '
```

### 3.2 进程概览

```bash
# JVM 版本与系统属性
jcmd <pid> VM.system_properties | grep -E "java.version|os.name|user.dir"

# 内存概览
jcmd <pid> GC.heap_info

# GC 统计 (每 1 秒采样 5 次)
jstat -gc <pid> 1000 5

# GC 汇总
jstat -gcutil <pid> 1000 5

# JVM 启动参数
jcmd <pid> VM.command_line
```

### 3.3 CPU 诊断

```bash
# 查找高 CPU 的 Java 进程
top -b -n 1 | grep java

# 查找进程内高 CPU 线程
top -Hp <pid> -b -n 1 | head -20

# 将线程 ID 转为十六进制
printf "%x\n" <thread_id>

# 查看线程栈
jstack <pid> | grep -A 30 "<hex_thread_id>"

# 查看所有线程状态统计
jstack <pid> | grep "java.lang.Thread.State" | sort | uniq -c | sort -rn

# 生成线程 Dump (3 次，间隔 5 秒)
jstack <pid> > /tmp/threaddump_1.txt
sleep 5
jstack <pid> > /tmp/threaddump_2.txt
sleep 5
jstack <pid> > /tmp/threaddump_3.txt

# 使用 jcmd 生成线程 Dump
jcmd <pid> Thread.print > /tmp/threaddump.txt
```

### 3.4 内存诊断

```bash
# 堆内存概览
jmap -heap <pid>
jcmd <pid> GC.heap_info

# 堆对象统计 (按大小排序 Top 20)
jmap -histo <pid> | head -20
jcmd <pid> GC.class_histogram | head -20

# 只看存活对象 (会触发 Full GC)
jmap -histo:live <pid> | head -20

# 生成堆 Dump (会暂停应用)
jmap -dump:format=b,file=/tmp/heapdump.hprof <pid>
jcmd <pid> GC.heap_dump /tmp/heapdump.hprof

# 生成堆 Dump (不暂停, JDK 8u40+)
jcmd <pid> GC.heap_dump -all /tmp/heapdump.hprof

# Metaspace 使用
jstat -gcmetacapacity <pid>
jcmd <pid> VM.metaspace

# DirectBuffer 使用
jcmd <pid> VM.native_memory
```

### 3.5 GC 诊断

```bash
# GC 统计信息
jstat -gc <pid> 1000 10

# GC 各代使用率
jstat -gcutil <pid> 1000 10

# GC 原因分析 (JDK 8+)
jcmd <pid> GC.last_gc_cause

# 查看 GC 日志位置
jcmd <pid> VM.command_line | grep -i "Xloggc\|Xlog:gc"

# 分析 GC 日志
tail -100 /path/to/gc.log

# Full GC 频率统计
grep "Full GC" /path/to/gc.log | wc -l

# GC 停顿时间统计
grep "Pause" /path/to/gc.log | tail -20

# 推荐 GC 参数 (G1)
# -XX:+UseG1GC
# -XX:MaxGCPauseMillis=200
# -XX:InitiatingHeapOccupancyPercent=45
# -XX:G1HeapRegionSize=8m
```

### 3.6 线程诊断

```bash
# 检测死锁
jstack <pid> | grep -A 5 "FOUND\|deadlock"
jcmd <pid> Thread.print -l  # -l 包含锁信息

# 查看线程池状态 (Spring Boot Actuator)
curl http://localhost:actuator/threaddump 2>/dev/null | python3 -m json.tool | head -100

# 统计线程状态
jstack <pid> | grep "java.lang.Thread.State" | sort | uniq -c | sort -rn

# 查找 BLOCKED 线程
jstack <pid> | grep -B 1 "BLOCKED" | head -30

# 查找 WAITING 线程 (可能是线程泄漏)
jstack <pid> | grep -c "WAITING"
jstack <pid> | grep -B 1 "WAITING" | head -30

# 查找长时间运行的线程
jstack <pid> | grep -E "RUNNABLE" -A 5 | head -50
```

---

## 4. 常见问题与解决方案

### 4.1 OOM (OutOfMemoryError)

**现象**: Java 进程抛出 OutOfMemoryError

**诊断步骤**:
```bash
# 1. 确认 OOM 类型
dmesg | grep -i "out of memory\|oom-killer" | tail -5
grep "OutOfMemoryError" /app/logs/*.log | tail -10

# 2. 查看堆内存使用
jmap -heap <pid>

# 3. 查看对象统计
jmap -histo <pid> | head -20

# 4. 生成堆 Dump
jcmd <pid> GC.heap_dump /tmp/heapdump.hprof
```

**OOM 类型与解决方案**:

| OOM 类型 | 原因 | 解决方案 |
|---------|------|---------|
| `Java heap space` | 堆内存不足 | 增大 -Xmx / 排查内存泄漏 |
| `Metaspace` | 类加载过多 | 增大 -XX:MaxMetaspaceSize / 排查动态类生成 |
| `GC overhead limit` | GC 回收效率过低 | 同 Java heap space 处理 |
| `Direct buffer memory` | 堆外内存不足 | 增大 -XX:MaxDirectMemorySize |
| `unable to create native thread` | 线程数超限 | 减少线程数 / 增大系统限制 |
| `requested array size exceeds VM limit` | 数组过大 | 优化代码逻辑 |

### 4.2 GC 频繁 / STW 停顿

**现象**: 应用间歇性卡顿，GC 耗时长

**诊断步骤**:
```bash
# 1. 查看 GC 统计
jstat -gcutil <pid> 1000 10

# 2. 分析 GC 日志
grep -E "Pause|Full GC" /path/to/gc.log | tail -20

# 3. 查看堆各代使用
jmap -heap <pid>
```

**解决方案**:

| 场景 | 配置调整 | 风险 |
|------|---------|------|
| Young GC 频繁 | 增大 -Xmn / -XX:NewRatio | 🟢 低 |
| Full GC 频繁 | 增大 -Xmx / 排查大对象 | 🟡 中 |
| GC 停顿过长 | 切换 G1 / ZGC | 🟡 中 |
| 元空间 GC | 增大 MaxMetaspaceSize | 🟢 低 |

### 4.3 CPU 飙高

**现象**: Java 进程 CPU 使用率持续 100%

**诊断步骤**:
```bash
# 1. 确认高 CPU 线程
top -Hp <pid> -b -n 1 | head -20

# 2. 转换线程 ID
printf "%x\n" <thread_id>

# 3. 查看线程栈
jstack <pid> | grep -A 30 "nid=0x<hex_id>"
```

**常见原因**:
| 原因 | 线程栈特征 | 解决方案 |
|------|-----------|---------|
| 死循环 | RUNNABLE + 同一代码行 | 修复代码逻辑 |
| 密集计算 | RUNNABLE + 计算/排序 | 优化算法 / 异步化 |
| GC 线程 | GC 线程高 CPU | 参见 GC 诊断 |
| 正则回溯 | RUNNABLE + Pattern/Matcher | 优化正则 / 设置回溯限制 |

### 4.4 线程死锁

**现象**: 应用部分功能卡死，线程 BLOCKED

**诊断步骤**:
```bash
# 1. 检测死锁
jstack <pid> | grep -A 10 "FOUND\|deadlock"

# 2. 查找 BLOCKED 线程
jstack <pid> | grep -B 1 -A 10 "BLOCKED" | head -50
```

**解决方案**:
| 方案 | 操作 | 风险 |
|------|------|------|
| 重启应用 | 重启 Java 进程 | 🟡 中 |
| 修复代码 | 调整锁顺序 | 🟢 低 (需发版) |
| 超时机制 | 使用 tryLock(timeout) | 🟢 低 (需发版) |

---

## 5. 权限边界

### 5.1 安全的只读操作
```bash
jps, jinfo, jstat
jstack (不影响运行)
jmap -heap, jmap -histo
jcmd <pid> GC.heap_info
```

### 5.2 需要确认的操作
```bash
jmap -histo:live (触发 Full GC)
jcmd <pid> GC.heap_dump (可能暂停应用)
jcmd <pid> GC.run (手动触发 GC)
```

### 5.3 危险操作禁止执行
```bash
kill -9 <pid> (强制杀死进程)
System.exit() (远程调用退出)
修改 JVM 参数后重启 (需变更审批)
```

---

## 6. 快速诊断脚本

```bash
#!/bin/bash
PID="${1}"

if [ -z "$PID" ]; then
  echo "Usage: $0 <java_pid>"
  echo "Java processes:"
  jps -lv
  exit 1
fi

echo "=== JVM 进程信息 ==="
jcmd $PID VM.command_line 2>/dev/null | head -5

echo -e "\n=== 堆内存概览 ==="
jcmd $PID GC.heap_info 2>/dev/null

echo -e "\n=== GC 统计 (5s 采样) ==="
jstat -gcutil $PID 1000 5 2>/dev/null

echo -e "\n=== 对象统计 Top 10 ==="
jmap -histo $PID 2>/dev/null | head -12

echo -e "\n=== 线程状态统计 ==="
jstack $PID 2>/dev/null | grep "java.lang.Thread.State" | sort | uniq -c | sort -rn

echo -e "\n=== 死锁检测 ==="
jstack $PID 2>/dev/null | grep -A 5 "FOUND\|deadlock" || echo "未检测到死锁"

echo -e "\n=== 高 CPU 线程 Top 5 ==="
top -Hp $PID -b -n 1 2>/dev/null | head -12
```

---

## 7. 版本信息

- 版本: 1.0.0
- 更新时间: 2025-04-08
- 维护者: AIOps Team
