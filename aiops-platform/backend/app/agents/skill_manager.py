import os
import re
import json
from typing import Dict, Any, List, Optional, Tuple, Set
from pathlib import Path
from collections import defaultdict


class SkillManager:
    """
    Skill 文件管理器 - 渐进式披露（Progressive Disclosure）
    
    目录结构:
    skills/
    ├── skill.md                      # 主索引文件
    ├── diagnosis/                    # 诊断类 Skill
    │   ├── debug_skill.md           # 服务器故障排查
    │   ├── gnn_rca_skill.md         # GNN 根因分析
    │   └── mysql_deadlock_skill.md  # MySQL 死锁排查
    └── connection/                   # 连接类 Skill
        └── login_skill.md           # SSH 连接管理
    
    工作流程:
    1. 加载主索引文件 skill.md（轻量级概览）
    2. 根据用户问题匹配关键词
    3. 动态加载具体的 skill 文件（详细内容）
    """
    
    SKILL_REGISTRY = {
        "debug_skill": {
            "path": "diagnosis/debug_skill.md",
            "category": "diagnosis",
            "description": "故障排查 (网络/存储/CPU/内存/数据库/中间件/K8S/SSH恢复)",
            "keywords": [
                "磁盘", "disk", "空间", "space", "内存", "memory", "cpu", "负载", "load",
                "网络", "network", "连接", "connection", "超时", "timeout", "数据库", "database",
                "mysql", "redis", "nginx", "k8s", "kubernetes", "pod", "服务", "service",
                "异常", "error", "故障", "failure", "排查", "diagnose", "慢", "slow",
                "ssh不通", "端口不通", "防火墙", "白名单", "sshd", "selinux",
                "oom", "死锁", "deadlock", "锁等待", "502", "504", "crashloop"
            ]
        },
        "gnn_rca_skill": {
            "path": "diagnosis/gnn_rca_skill.md",
            "category": "diagnosis",
            "description": "GNN 根因分析",
            "keywords": [
                "根因分析", "rca", "root cause", "故障定位", "日志关联",
                "服务调用链", "异常传播", "gnn", "图神经网络", "微服务故障",
                "trace", "链路", "拓扑", "依赖", "传播路径", "海量日志",
                "服务依赖", "调用关系", "级联故障", "根因定位"
            ]
        },
        "time_series_rca_skill": {
            "path": "diagnosis/time_series_rca_skill.md",
            "category": "diagnosis",
            "description": "时间序列根因分析",
            "keywords": [
                "根因分析", "rca", "root cause analysis", "故障定位",
                "时间序列", "time series", "预测", "prediction",
                "异常检测", "anomaly detection", "故障预测",
                "指标分析", "metrics analysis", "性能分析",
                "趋势分析", "trend analysis", "容量规划",
                "prophet", "时序预测", "指标预测"
            ]
        },
        "mysql_deadlock_skill": {
            "path": "diagnosis/mysql_deadlock_skill.md",
            "category": "diagnosis",
            "description": "MySQL 死锁排查",
            "keywords": [
                "死锁", "deadlock", "lock", "锁等待", "lock wait",
                "事务", "transaction", "阻塞", "blocking",
                "mysql", "数据库", "db", "rds",
                "行锁", "表锁", "间隙锁", "gap lock", "next-key lock",
                "超时", "timeout", "回滚", "rollback",
                "innodb", "索引", "index"
            ]
        },
        "mysql_slow_query_skill": {
            "path": "diagnosis/mysql_slow_query_skill.md",
            "category": "diagnosis",
            "description": "MySQL 慢查询分析",
            "keywords": [
                "慢查询", "slow query", "sql优化", "查询慢", "慢sql",
                "mysql", "数据库", "db", "rds", "索引", "index",
                "执行计划", "explain", "全表扫描", "性能", "performance"
            ]
        },
        "redis_skill": {
            "path": "diagnosis/redis_skill.md",
            "category": "diagnosis",
            "description": "Redis 诊断与优化",
            "keywords": [
                "redis", "缓存", "cache", "内存", "memory", "key",
                "缓存穿透", "缓存击穿", "缓存雪崩", "bigkey",
                "连接数", "maxclients", "rdb", "aof", "持久化"
            ]
        },
        "ad_skill": {
            "path": "diagnosis/ad_skill.md",
            "category": "diagnosis",
            "description": "Active Directory 诊断",
            "keywords": [
                "ad", "active directory", "域控", "ldap", "kerberos",
                "域用户", "域登录", "认证失败", "gpo", "组策略",
                "dns", "replication", "复制", "信任关系"
            ]
        },
        "login_skill": {
            "path": "connection/login_skill.md",
            "category": "connection",
            "description": "连接管理 (SSH/RDS/PolarDB/DMS/K8S/中间件)",
            "keywords": [
                "连接", "connect", "登录", "login", "ssh", "远程", "remote",
                "主机", "host", "服务器", "server", "凭据", "credential",
                "阿里云", "aliyun", "rds", "polardb", "dms", "云数据库",
                "白名单", "安全组", "mysql", "postgresql", "redis", "rabbitmq",
                "k8s", "kubernetes", "vcenter", "vnc", "workbench"
            ]
        },
        "k8s_pod_skill": {
            "path": "container/k8s_pod_skill.md",
            "category": "container",
            "description": "Kubernetes Pod 诊断",
            "keywords": [
                "pod", "k8s", "kubernetes", "容器", "container",
                "crashloopbackoff", "imagepullbackoff", "pending",
                "oomkilled", "evicted", "restart", "重启",
                "deployment", "statefulset", "daemonset"
            ]
        },
        "connectivity_skill": {
            "path": "network/connectivity_skill.md",
            "category": "network",
            "description": "网络连通性诊断",
            "keywords": [
                "网络", "network", "连接", "ping", "telnet", "nc", "curl",
                "dns", "解析", "域名", "防火墙", "iptables", "端口",
                "连通性", "不可达", "unreachable", "超时", "timeout"
            ]
        },
        "lb_port_connectivity_skill": {
            "path": "network/lb_port_connectivity_skill.md",
            "category": "network",
            "description": "阿里云负载均衡端口连接诊断",
            "keywords": [
                "负载均衡", "slb", "alb", "clb", "nlb", "load balancer",
                "端口连不上", "健康检查失败", "后端服务器", "backend server",
                "阿里云负载均衡", "ecs 端口", "服务能力", "监听配置",
                "lb-", "实例id", "负载均衡器"
            ]
        },
        "ssl_certificate_skill": {
            "path": "network/ssl_certificate_skill.md",
            "category": "network",
            "description": "SSL 证书管理",
            "keywords": [
                "ssl", "证书", "certificate", "https", "tls",
                "过期", "expired", "renew", "续签",
                "lets encrypt", "certbot", "域名验证"
            ]
        },
        "deeplog_anomaly_detection_skill": {
            "path": "monitoring/deeplog_anomaly_detection_skill.md",
            "category": "monitoring",
            "description": "DeepLog 日志异常检测",
            "keywords": [
                "日志异常检测", "日志异常", "异常日志", "anomaly detection",
                "deeplog", "lstm", "日志序列", "日志模式",
                "日志预测", "日志分析", "log analysis",
                "时间序列", "time series", "日志模板",
                "drain", "日志解析", "事件模板"
            ]
        },
        "prometheus_skill": {
            "path": "monitoring/prometheus_skill.md",
            "category": "monitoring",
            "description": "Prometheus 监控诊断",
            "keywords": [
                "prometheus", "监控", "monitoring", "指标", "metrics",
                "promql", "告警", "alert", "alertmanager",
                "grafana", "target", "scrape", "采集"
            ]
        },
        "log_analysis_skill": {
            "path": "monitoring/log_analysis_skill.md",
            "category": "monitoring",
            "description": "日志分析与排查",
            "keywords": [
                "日志", "log", "elk", "loki", "日志分析",
                "grep", "awk", "sed", "日志搜索", "日志过滤",
                "结构化日志", "日志格式", "日志采集"
            ]
        },
        "backup_skill": {
            "path": "backup/backup_skill.md",
            "category": "backup",
            "description": "数据备份与恢复",
            "keywords": [
                "备份", "backup", "恢复", "restore", "灾备",
                "mysqldump", "pg_dump", "快照", "snapshot",
                "全量备份", "增量备份", "rpo", "rto"
            ]
        },
        "kafka_skill": {
            "path": "middleware/kafka_skill.md",
            "category": "middleware",
            "description": "Kafka 集群诊断与消息堆积处理",
            "keywords": [
                "kafka", "消息堆积", "consumer lag", "分区", "partition",
                "broker", "producer", "consumer", "offset", "topic",
                "rebalance", "副本", "replica", "isr", "消息丢失"
            ]
        },
        "nginx_skill": {
            "path": "middleware/nginx_skill.md",
            "category": "middleware",
            "description": "Nginx Web 服务器与反向代理诊断",
            "keywords": [
                "nginx", "502", "504", "反向代理", "reverse proxy",
                "upstream", "负载均衡", "load balance", "配置", "config",
                "重写", "rewrite", "location", "proxy_pass", "超时"
            ]
        },
        "rabbitmq_skill": {
            "path": "middleware/rabbitmq_skill.md",
            "category": "middleware",
            "description": "RabbitMQ 队列诊断与连接管理",
            "keywords": [
                "rabbitmq", "队列堆积", "死信队列", "dlx", "channel",
                "connection", "exchange", "binding", "消息丢失", "重复消费",
                "消费延迟", "连接泄漏", "内存告警", "磁盘告警",
                "集群", "镜像队列", "federation"
            ]
        },
        "elasticsearch_skill": {
            "path": "middleware/elasticsearch_skill.md",
            "category": "middleware",
            "description": "Elasticsearch 集群诊断与性能优化",
            "keywords": [
                "elasticsearch", "es", "集群状态red", "集群状态yellow",
                "分片未分配", "unassigned", "shard", "慢查询",
                "索引膨胀", "mapping冲突", "jvm堆", "gc",
                "熔断器", "circuit breaker", "rebalance", "snapshot"
            ]
        },
        "database_ha_skill": {
            "path": "database/database_ha_skill.md",
            "category": "database",
            "description": "数据库高可用与复制故障排查",
            "keywords": [
                "主从切换", "复制中断", "io线程", "sql线程", "binlog",
                "gtid", "mha", "数据库高可用", "主从延迟", "slave",
                "复制错误", "1236", "1062", "1032", "半同步", "组复制"
            ]
        },
        "postgresql_skill": {
            "path": "database/postgresql_skill.md",
            "category": "database",
            "description": "PostgreSQL 性能诊断与维护",
            "keywords": [
                "postgresql", "pg", "psql", "锁等待", "vacuum",
                "wal", "膨胀", "bloat", "复制槽", "逻辑复制",
                "流复制", "mvcc", "事务id回卷", "autovacuum",
                "连接数", "慢查询", "索引", "dead tuple"
            ]
        },
        "mongodb_skill": {
            "path": "database/mongodb_skill.md",
            "category": "database",
            "description": "MongoDB 副本集与分片诊断",
            "keywords": [
                "mongodb", "mongo", "副本集", "replicaset", "oplog",
                "分片", "sharding", "config server", "mongos",
                "wiredtiger", "wt", "缓存", "checkpoint",
                "慢查询", "连接池", "索引", "balancer"
            ]
        },
        "security_audit_skill": {
            "path": "security/security_audit_skill.md",
            "category": "security",
            "description": "安全事件检测与应急响应",
            "keywords": [
                "安全审计", "ssh暴力破解", "异常登录", "权限提升",
                "可疑进程", "入侵检测", "webshell", "挖矿",
                "后门", "异常网络连接", "文件篡改", "安全事件",
                "fail2ban", "入侵", "攻击", "漏洞"
            ]
        },
        "permission_troubleshoot_skill": {
            "path": "security/permission_troubleshoot_skill.md",
            "category": "security",
            "description": "文件/服务权限问题排查",
            "keywords": [
                "权限拒绝", "permission denied", "403", "forbidden",
                "acl", "sudo", "文件权限", "chown", "chmod",
                "selinux", "apparmor", "安全上下文",
                "访问拒绝", "认证失败", "授权失败", "capabilities"
            ]
        },
        "ecs_skill": {
            "path": "cloud/ecs_skill.md",
            "category": "cloud",
            "description": "阿里云 ECS 实例诊断",
            "keywords": [
                "ecs", "实例", "无法连接", "安全组", "磁盘",
                "快照", "自动扩缩容", "弹性伸缩", "实例状态",
                "公网ip", "eip", "vpc", "专有网络", "阿里云"
            ]
        },
        "vpc_skill": {
            "path": "cloud/vpc_skill.md",
            "category": "cloud",
            "description": "阿里云 VPC 网络诊断",
            "keywords": [
                "vpc", "交换机", "路由表", "vswitch", "nat网关",
                "对等连接", "云企业网", "cen", "vpn", "专线",
                "智能接入网关", "网络不通", "跨vpc", "私网访问",
                "网络acl", "流量镜像", "安全组"
            ]
        },
        "oss_skill": {
            "path": "cloud/oss_skill.md",
            "category": "cloud",
            "description": "阿里云 OSS 存储诊断",
            "keywords": [
                "oss", "对象存储", "bucket", "上传失败",
                "权限", "sts", "签名url", "跨域", "cors",
                "生命周期", "存储类型", "低频", "归档",
                "cdn", "加速", "回源", "防盗链"
            ]
        },
        "jvm_skill": {
            "path": "capacity/jvm_skill.md",
            "category": "capacity",
            "description": "Java 应用性能诊断",
            "keywords": [
                "jvm", "oom", "outofmemoryerror", "gc", "垃圾回收",
                "堆内存", "heap", "线程dump", "threaddump", "cpu飙高",
                "metaspace", "full gc", "young gc", "jstat", "jmap",
                "jstack", "jcmd", "arthas", "内存泄漏"
            ]
        },
        "performance_tuning_skill": {
            "path": "capacity/performance_tuning_skill.md",
            "category": "capacity",
            "description": "系统全链路性能优化",
            "keywords": [
                "性能调优", "接口慢", "rt高", "吞吐量", "qps",
                "p99延迟", "线程池", "连接池", "异步化", "缓存",
                "批量", "索引优化", "sql优化", "压测", "负载测试"
            ]
        },
        "capacity_planning_skill": {
            "path": "capacity/capacity_planning_skill.md",
            "category": "capacity",
            "description": "容量规划与资源预测",
            "keywords": [
                "容量规划", "扩容", "缩容", "资源预测", "水位",
                "利用率", "资源不足", "资源闲置", "大促", "活动",
                "流量预估", "压测", "成本", "预算", "降本增效",
                "hpa", "vpa", "弹性伸缩"
            ]
        },
        "incident_response_skill": {
            "path": "disaster_recovery/incident_response_skill.md",
            "category": "disaster_recovery",
            "description": "故障应急响应与止血",
            "keywords": [
                "服务雪崩", "熔断", "降级", "限流", "应急响应",
                "故障止血", "p0故障", "级联故障", "sentinel",
                "hystrix", "回滚", "rollback", "故障恢复",
                "故障报告", "时间线", "复盘"
            ]
        },
        "deployment_skill": {
            "path": "devops/deployment_skill.md",
            "category": "devops",
            "description": "CI/CD 流水线与部署故障排查",
            "keywords": [
                "部署失败", "ci/cd", "jenkins", "gitlab ci",
                "k8s部署", "imagepullbackoff", "crashloopbackoff",
                "流水线超时", "构建失败", "镜像构建", "发布回滚",
                "蓝绿部署", "金丝雀发布", "灰度发布", "helm"
            ]
        },
        "config_drift_skill": {
            "path": "devops/config_drift_skill.md",
            "category": "devops",
            "description": "配置漂移检测与修复",
            "keywords": [
                "配置漂移", "配置不一致", "环境差异", "apollo",
                "nacos", "配置中心", "spring cloud config",
                "本地能跑线上不行", "配置变更", "版本回退",
                "灰度配置", "configmap", "secret", "配置热更新"
            ]
        },
        "systemd_autostart_skill": {
            "path": "systemd/systemd_autostart_skill.md",
            "category": "systemd",
            "description": "Systemd 服务自启动故障排查",
            "keywords": [
                "systemd", "systemctl", "服务自启动", "开机启动",
                "服务不启动", "服务重启", "enable", "disabled",
                "服务恢复", "自动启动", "服务配置", "unit文件",
                "重启后服务不启动", "服务无法自启", "systemd服务",
                "service", "服务问题", "服务故障"
            ]
        }
    }
    
    CATEGORY_MAP = {
        "diagnosis": "诊断类",
        "connection": "连接类",
        "container": "容器类",
        "network": "网络类",
        "monitoring": "监控类",
        "backup": "备份类",
        "middleware": "中间件类",
        "database": "数据库类",
        "security": "安全类",
        "cloud": "云资源类",
        "capacity": "容量类",
        "disaster_recovery": "应急响应类",
        "devops": "DevOps类",
        "systemd": "系统服务类"
    }
    
    WEIGHTED_KEYWORDS = {
        "debug_skill": {
            "core": {
                "故障排查": 10, "故障诊断": 10, "排查": 8, "诊断": 8,
                "服务器故障": 9, "系统故障": 9, "故障": 7, "问题": 6,
                "异常": 6, "报错": 6, "错误": 6
            },
            "symptom": {
                "磁盘满": 8, "磁盘空间": 7, "内存不足": 8, "oom": 9,
                "cpu高": 7, "负载高": 7, "cpu飙高": 8, "内存泄漏": 8,
                "网络不通": 8, "连接超时": 7, "ssh不通": 9, "端口不通": 8,
                "服务异常": 6, "进程崩溃": 8, "502": 7, "504": 7,
                "磁盘空间不足": 8, "内存不够": 8, "cpu占用高": 7,
                "cpu过高": 7, "内存溢出": 8, "进程异常": 7
            },
            "component": {
                "磁盘": 5, "disk": 5, "内存": 5, "memory": 5,
                "cpu": 5, "负载": 5, "load": 5, "网络": 5,
                "进程": 4, "process": 4, "端口": 4, "port": 4,
                "服务器": 4, "系统": 4, "机器": 4
            },
            "alias": {}
        },
        "gnn_rca_skill": {
            "core": {
                "根因分析": 10, "rca": 10, "root cause": 9,
                "故障定位": 9, "根因定位": 9, "gnn": 9,
                "定位问题": 8, "问题定位": 8
            },
            "symptom": {
                "微服务故障": 8, "级联故障": 8, "服务雪崩": 8,
                "调用链异常": 7, "链路追踪": 7, "trace异常": 7,
                "服务依赖": 7, "传播路径": 7
            },
            "component": {
                "图神经网络": 5, "拓扑": 5, "依赖": 4,
                "调用链": 5, "trace": 5, "链路": 5
            },
            "alias": {}
        },
        "time_series_rca_skill": {
            "core": {
                "时间序列": 10, "时序分析": 9, "指标预测": 9,
                "异常检测": 9, "趋势预测": 8
            },
            "symptom": {
                "指标异常": 8, "性能预测": 7, "容量预测": 7,
                "趋势分析": 7, "prophet": 8
            },
            "component": {
                "时序": 5, "预测": 4, "指标": 5, "metrics": 5
            },
            "alias": {}
        },
        "mysql_deadlock_skill": {
            "core": {
                "死锁": 10, "deadlock": 10, "mysql死锁": 10,
                "锁等待": 9, "lock wait": 9, "锁死": 9, "锁冲突": 9
            },
            "symptom": {
                "事务阻塞": 8, "数据库锁": 8, "行锁冲突": 8,
                "表锁": 7, "间隙锁": 7, "锁超时": 8,
                "阻塞": 7, "事务卡住": 8
            },
            "component": {
                "innodb": 5, "事务": 5, "transaction": 5,
                "行锁": 5, "索引": 4, "index": 4
            },
            "alias": {}
        },
        "mysql_slow_query_skill": {
            "core": {
                "慢查询": 10, "slow query": 10, "sql慢": 9,
                "查询慢": 9, "慢sql": 9, "查询很慢": 9,
                "sql执行慢": 9, "sql慢查询": 9
            },
            "symptom": {
                "查询超时": 8, "sql超时": 8, "全表扫描": 8,
                "索引失效": 8, "执行慢": 7, "响应慢": 8,
                "查询卡顿": 7, "sql卡顿": 7
            },
            "component": {
                "explain": 5, "执行计划": 5, "索引": 5,
                "sql优化": 6, "性能优化": 5
            },
            "alias": {}
        },
        "redis_skill": {
            "core": {
                "redis": 10, "redis故障": 10, "缓存故障": 9
            },
            "symptom": {
                "缓存穿透": 9, "缓存击穿": 9, "缓存雪崩": 9,
                "bigkey": 8, "内存不足": 7, "连接数满": 7,
                "缓存问题": 7, "redis慢": 7
            },
            "component": {
                "缓存": 6, "cache": 6, "key": 4,
                "rdb": 5, "aof": 5, "持久化": 5
            },
            "alias": {}
        },
        "ad_skill": {
            "core": {
                "active directory": 10, "域控": 10, "ad": 9,
                "域控制器": 9
            },
            "symptom": {
                "域登录失败": 8, "域用户": 7, "认证失败": 7,
                "ldap错误": 7, "kerberos": 7
            },
            "component": {
                "ldap": 5, "gpo": 5, "组策略": 5,
                "域": 5, "domain": 5
            },
            "alias": {}
        },
        "login_skill": {
            "core": {
                "ssh连接": 10, "远程连接": 9, "服务器连接": 9,
                "登录服务器": 9, "连接数据库": 8
            },
            "symptom": {
                "连接失败": 8, "登录失败": 8, "认证失败": 7,
                "权限不足": 7, "白名单": 6
            },
            "component": {
                "ssh": 6, "凭据": 5, "credential": 5,
                "rds": 5, "polardb": 5, "dms": 5
            },
            "alias": {
                "连接": 6, "登录": 6
            }
        },
        "k8s_pod_skill": {
            "core": {
                "pod": 10, "k8s": 10, "kubernetes": 10,
                "pod故障": 9, "容器故障": 9, "k8s故障": 9
            },
            "symptom": {
                "crashloopbackoff": 10, "imagepullbackoff": 10,
                "pod pending": 8, "oomkilled": 9, "evicted": 8,
                "容器重启": 8, "pod重启": 8, "pod异常": 7,
                "容器崩溃": 8, "pod起不来": 8, "容器起不来": 8
            },
            "component": {
                "容器": 5, "container": 5, "deployment": 4,
                "statefulset": 4, "daemonset": 4, "docker": 5
            },
            "alias": {}
        },
        "connectivity_skill": {
            "core": {
                "网络连通性": 10, "网络不通": 10, "连通性诊断": 9,
                "网络连接": 8
            },
            "symptom": {
                "ping不通": 9, "telnet失败": 8, "端口不通": 8,
                "dns解析失败": 8, "域名无法访问": 7, "网络超时": 7,
                "连不上": 8, "无法连接": 8, "网络异常": 7
            },
            "component": {
                "ping": 5, "telnet": 5, "dns": 5,
                "防火墙": 5, "iptables": 5, "端口": 4
            },
            "alias": {
                "网络": 6, "network": 6
            }
        },
        "lb_port_connectivity_skill": {
            "core": {
                "负载均衡": 10, "slb": 10, "alb": 9, "clb": 9,
                "nlb": 9, "load balancer": 9, "lb": 8
            },
            "symptom": {
                "健康检查失败": 9, "端口连不上": 9, "后端不通": 8,
                "lb异常": 8, "负载均衡故障": 8, "lb故障": 8
            },
            "component": {
                "监听": 5, "listener": 5, "后端服务器": 5,
                "backend": 5, "健康检查": 5
            },
            "alias": {}
        },
        "ssl_certificate_skill": {
            "core": {
                "ssl证书": 10, "证书过期": 10, "https证书": 9,
                "tls证书": 9, "证书问题": 8
            },
            "symptom": {
                "证书失效": 9, "证书错误": 8, "https错误": 7,
                "ssl错误": 8, "证书续签": 7, "证书不信任": 7
            },
            "component": {
                "ssl": 5, "tls": 5, "https": 5,
                "lets encrypt": 6, "certbot": 6
            },
            "alias": {
                "证书": 7
            }
        },
        "deeplog_anomaly_detection_skill": {
            "core": {
                "日志异常检测": 10, "deeplog": 10, "日志异常": 9
            },
            "symptom": {
                "异常日志": 8, "日志模式异常": 8, "日志序列异常": 8
            },
            "component": {
                "lstm": 5, "日志模板": 5, "drain": 5,
                "日志解析": 5
            },
            "alias": {}
        },
        "prometheus_skill": {
            "core": {
                "prometheus": 10, "prometheus故障": 10, "监控故障": 8,
                "监控问题": 7
            },
            "symptom": {
                "指标采集失败": 8, "target down": 8, "告警不触发": 7,
                "promql错误": 7, "监控数据丢失": 7
            },
            "component": {
                "promql": 5, "监控": 5, "metrics": 5,
                "alertmanager": 5, "grafana": 4
            },
            "alias": {}
        },
        "log_analysis_skill": {
            "core": {
                "日志分析": 10, "日志排查": 9, "日志搜索": 8,
                "查日志": 8
            },
            "symptom": {
                "日志查询": 7, "日志过滤": 7, "日志报错": 7,
                "日志错误": 7
            },
            "component": {
                "elk": 5, "loki": 5, "grep": 4,
                "awk": 4, "日志": 5, "log": 5
            },
            "alias": {}
        },
        "backup_skill": {
            "core": {
                "数据备份": 10, "备份恢复": 10, "backup": 9
            },
            "symptom": {
                "备份失败": 9, "恢复失败": 9, "数据丢失": 8,
                "备份超时": 7
            },
            "component": {
                "mysqldump": 5, "pg_dump": 5, "快照": 5,
                "snapshot": 5, "rpo": 4, "rto": 4
            },
            "alias": {
                "备份": 7
            }
        },
        "kafka_skill": {
            "core": {
                "kafka": 10, "kafka故障": 10, "消息队列故障": 9
            },
            "symptom": {
                "消息堆积": 10, "consumer lag": 10, "消费延迟": 8,
                "消息丢失": 9, "生产失败": 8, "kafka超时": 8,
                "消息积压": 10, "kafka慢": 7, "消费卡住": 8
            },
            "component": {
                "broker": 5, "partition": 5, "topic": 5,
                "consumer": 5, "producer": 5, "offset": 5
            },
            "alias": {
                "mq": 7
            }
        },
        "nginx_skill": {
            "core": {
                "nginx": 10, "nginx故障": 10, "nginx配置": 8,
                "nginx问题": 7
            },
            "symptom": {
                "nginx 502": 10, "nginx 504": 10, "反向代理失败": 8,
                "upstream失败": 8, "nginx超时": 7, "nginx报错": 7,
                "代理失败": 7
            },
            "component": {
                "upstream": 5, "proxy_pass": 5, "location": 4,
                "rewrite": 4, "负载均衡": 5
            },
            "alias": {}
        },
        "rabbitmq_skill": {
            "core": {
                "rabbitmq": 10, "rabbitmq故障": 10, "rabbitmq问题": 7
            },
            "symptom": {
                "队列堆积": 9, "死信队列": 8, "dlx": 8,
                "消息丢失": 8, "连接泄漏": 8, "channel泄漏": 7,
                "消息积压": 8
            },
            "component": {
                "queue": 5, "exchange": 5, "channel": 5,
                "binding": 4, "vhost": 4
            },
            "alias": {
                "mq": 6
            }
        },
        "elasticsearch_skill": {
            "core": {
                "elasticsearch": 10, "es集群": 10, "es故障": 9,
                "es问题": 7
            },
            "symptom": {
                "集群状态red": 10, "集群状态yellow": 10, "分片未分配": 9,
                "unassigned": 8, "es慢查询": 8, "es内存不足": 7,
                "es异常": 7, "集群异常": 8
            },
            "component": {
                "shard": 5, "index": 5, "mapping": 4,
                "bulk": 4, "reindex": 4
            },
            "alias": {
                "es": 9
            }
        },
        "database_ha_skill": {
            "core": {
                "数据库高可用": 10, "主从切换": 10, "数据库复制": 9,
                "主从复制": 9
            },
            "symptom": {
                "复制中断": 9, "io线程停止": 9, "sql线程停止": 9,
                "主从延迟": 8, "slave延迟": 8, "gtid错误": 8,
                "同步中断": 8, "复制失败": 8
            },
            "component": {
                "binlog": 5, "gtid": 5, "mha": 5,
                "slave": 5, "master": 5, "半同步": 4
            },
            "alias": {}
        },
        "postgresql_skill": {
            "core": {
                "postgresql": 10, "postgres": 10, "pg数据库": 9,
                "pg问题": 7
            },
            "symptom": {
                "pg锁等待": 9, "表膨胀": 8, "vacuum失败": 8,
                "wal堆积": 8, "连接数满": 7, "pg慢查询": 7,
                "pg异常": 7
            },
            "component": {
                "psql": 5, "vacuum": 5, "wal": 5,
                "bloat": 5, "autovacuum": 5
            },
            "alias": {
                "pg": 9
            }
        },
        "mongodb_skill": {
            "core": {
                "mongodb": 10, "mongo": 10, "mongo故障": 9,
                "mongo问题": 7
            },
            "symptom": {
                "副本集异常": 9, "oplog堆积": 8, "分片不均衡": 8,
                "mongo慢查询": 7, "主从切换": 7, "mongo异常": 7
            },
            "component": {
                "replicaset": 5, "oplog": 5, "sharding": 5,
                "mongos": 5, "wiredtiger": 4
            },
            "alias": {}
        },
        "security_audit_skill": {
            "core": {
                "安全审计": 10, "入侵检测": 10, "安全事件": 9
            },
            "symptom": {
                "ssh暴力破解": 10, "异常登录": 9, "可疑进程": 8,
                "webshell": 9, "挖矿": 9, "后门": 8
            },
            "component": {
                "fail2ban": 5, "入侵": 6, "攻击": 5,
                "漏洞": 5, "安全": 5
            },
            "alias": {}
        },
        "permission_troubleshoot_skill": {
            "core": {
                "权限拒绝": 10, "permission denied": 10, "403错误": 9
            },
            "symptom": {
                "文件权限错误": 8, "sudo失败": 8, "selinux阻止": 8,
                "访问被拒绝": 8, "认证失败": 7
            },
            "component": {
                "chmod": 5, "chown": 5, "acl": 5,
                "selinux": 6, "apparmor": 5
            },
            "alias": {
                "权限": 7
            }
        },
        "ecs_skill": {
            "core": {
                "ecs": 10, "ecs实例": 10, "阿里云ecs": 9,
                "ecs问题": 7
            },
            "symptom": {
                "ecs无法连接": 10, "实例无法启动": 8, "ecs磁盘满": 8,
                "安全组配置": 7, "实例状态异常": 7, "ecs连不上": 8
            },
            "component": {
                "安全组": 5, "弹性伸缩": 5, "实例": 5,
                "eip": 5, "快照": 4
            },
            "alias": {}
        },
        "vpc_skill": {
            "core": {
                "vpc": 10, "vpc网络": 10, "专有网络": 9,
                "vpc问题": 7
            },
            "symptom": {
                "vpc不通": 10, "跨vpc不通": 9, "nat网关故障": 8,
                "路由错误": 8, "私网不通": 8, "vpc异常": 7
            },
            "component": {
                "交换机": 5, "vswitch": 5, "路由表": 5,
                "nat网关": 5, "对等连接": 5
            },
            "alias": {}
        },
        "oss_skill": {
            "core": {
                "oss": 10, "对象存储": 10, "阿里云oss": 9,
                "oss问题": 7
            },
            "symptom": {
                "oss上传失败": 10, "oss权限错误": 9, "bucket不存在": 8,
                "cors错误": 8, "签名错误": 7, "oss异常": 7
            },
            "component": {
                "bucket": 5, "sts": 5, "cors": 5,
                "生命周期": 4, "存储类型": 4
            },
            "alias": {}
        },
        "jvm_skill": {
            "core": {
                "jvm": 10, "jvm故障": 10, "java故障": 9,
                "java问题": 7, "jvm问题": 7, "java": 8
            },
            "symptom": {
                "java oom": 10, "outofmemoryerror": 10, "full gc频繁": 9,
                "jvm内存不足": 9, "cpu飙高": 8, "线程阻塞": 7,
                "java内存溢出": 10, "jvm崩溃": 8, "应用崩溃": 7,
                "内存溢出": 9, "oom": 9
            },
            "component": {
                "heap": 5, "gc": 5, "jstack": 5,
                "jmap": 5, "arthas": 5, "threaddump": 5
            },
            "alias": {}
        },
        "performance_tuning_skill": {
            "core": {
                "性能调优": 10, "性能优化": 10, "系统优化": 9,
                "性能问题": 8
            },
            "symptom": {
                "接口慢": 9, "rt高": 8, "响应慢": 8,
                "吞吐量低": 8, "qps上不去": 8, "p99延迟高": 8,
                "系统慢": 7, "性能差": 7, "卡顿": 7
            },
            "component": {
                "线程池": 5, "连接池": 5, "缓存": 5,
                "异步": 4, "批量": 4
            },
            "alias": {}
        },
        "capacity_planning_skill": {
            "core": {
                "容量规划": 10, "资源预测": 10, "容量评估": 9,
                "容量问题": 7
            },
            "symptom": {
                "大促准备": 8, "资源不足": 8, "扩容评估": 8,
                "成本优化": 7, "降本增效": 7, "容量不够": 7
            },
            "component": {
                "hpa": 5, "vpa": 5, "弹性伸缩": 5,
                "水位": 5, "利用率": 4
            },
            "alias": {}
        },
        "incident_response_skill": {
            "core": {
                "应急响应": 10, "p0故障": 10, "故障止血": 10,
                "紧急故障": 9
            },
            "symptom": {
                "服务雪崩": 10, "级联故障": 9, "大规模故障": 9,
                "熔断": 7, "降级": 7, "限流": 7,
                "系统崩溃": 9, "大规模异常": 8
            },
            "component": {
                "sentinel": 5, "hystrix": 5, "回滚": 5,
                "rollback": 5, "故障恢复": 5
            },
            "alias": {}
        },
        "deployment_skill": {
            "core": {
                "部署失败": 10, "ci/cd故障": 10, "流水线失败": 9
            },
            "symptom": {
                "jenkins失败": 9, "镜像构建失败": 9, "k8s部署失败": 9,
                "imagepullbackoff": 9, "发布失败": 8
            },
            "component": {
                "jenkins": 5, "gitlab ci": 5, "helm": 5,
                "docker": 4, "镜像": 5
            },
            "alias": {}
        },
        "config_drift_skill": {
            "core": {
                "配置漂移": 10, "配置不一致": 10, "环境差异": 9
            },
            "symptom": {
                "本地能跑线上不行": 9, "配置错误": 8, "配置未生效": 8,
                "nacos配置问题": 8, "apollo配置问题": 8
            },
            "component": {
                "apollo": 5, "nacos": 5, "configmap": 5,
                "配置中心": 5, "spring cloud config": 4
            },
            "alias": {}
        },
        "systemd_autostart_skill": {
            "core": {
                "systemd": 10, "systemctl": 10, "服务自启动": 10,
                "开机启动": 9, "服务不启动": 9, "服务无法自启": 9,
                "service": 8, "服务故障": 8
            },
            "symptom": {
                "服务重启后不启动": 10, "重启后服务不启动": 10,
                "服务不能自动恢复": 9, "enable失败": 8,
                "服务启动失败": 8, "服务inactive": 8,
                "服务disabled": 8, "服务masked": 8,
                "服务问题": 7, "服务异常": 7
            },
            "component": {
                "unit文件": 5, "service文件": 5, "systemd服务": 6,
                "daemon-reload": 5, "journalctl": 5
            },
            "alias": {}
        }
    }
    
    SYNONYM_MAP = {
        "故障": ["问题", "异常", "错误", "报错", "失败", "故障"],
        "排查": ["诊断", "检查", "排查", "定位", "分析", "排查问题"],
        "慢": ["缓慢", "卡顿", "延迟", "耗时", "响应慢", "执行慢"],
        "高": ["过高", "飙高", "飙升", "满载", "饱和", "占用高"],
        "不足": ["不够", "缺乏", "耗尽", "满", "溢出"],
        "不通": ["无法连接", "连不上", "连不通", "连接失败", "网络不通"],
        "失败": ["错误", "异常", "不成功", "失败"],
        "堆积": ["积压", "堆积", "堆积量", "lag", "延迟"],
        "死锁": ["锁死", "死锁", "锁等待", "锁冲突", "阻塞"],
        "超时": ["timeout", "超时", "timed out", "等待超时"],
        "崩溃": ["crash", "崩溃", "闪退", "异常退出", "重启"],
        "内存": ["memory", "内存", "mem"],
        "磁盘": ["disk", "磁盘", "硬盘", "存储"],
        "cpu": ["cpu", "处理器", "processor"],
        "网络": ["network", "网络", "net"],
        "连接": ["connection", "连接", "conn"],
        "数据库": ["database", "数据库", "db"],
        "缓存": ["cache", "缓存"],
        "队列": ["queue", "队列", "mq"],
        "集群": ["cluster", "集群"],
        "节点": ["node", "节点", "实例"],
        "主从": ["master-slave", "主从", "主备"],
        "复制": ["replication", "复制", "同步"],
        "证书": ["certificate", "证书", "cert", "ssl", "tls"],
        "权限": ["permission", "权限", "auth", "授权"],
        "配置": ["config", "配置", "configuration"],
        "部署": ["deploy", "部署", "发布", "release"],
        "监控": ["monitor", "监控", "monitoring"],
        "日志": ["log", "日志", "logging"],
        "性能": ["performance", "性能", "perf"],
        "安全": ["security", "安全", "secure"],
        "容器": ["container", "容器", "docker"],
        "负载": ["load", "负载", "负载均衡"],
    }
    
    SYNONYM_GROUPS = {
        "数据库故障": ["数据库异常", "数据库错误", "db故障", "数据库问题"],
        "消息堆积": ["消息积压", "消费延迟", "consumer lag", "消息延迟", "队列堆积"],
        "慢查询": ["sql慢", "查询慢", "慢sql", "sql执行慢", "查询超时"],
        "内存溢出": ["oom", "out of memory", "内存不足", "内存满", "内存泄漏"],
        "cpu飙高": ["cpu高", "cpu占用高", "cpu满", "cpu 100%", "处理器满载"],
        "磁盘满": ["磁盘空间不足", "磁盘空间满", "no space left", "磁盘满了"],
        "网络不通": ["网络连接失败", "网络异常", "无法访问", "网络中断"],
        "服务异常": ["服务故障", "服务不可用", "服务错误", "服务down"],
        "主从延迟": ["复制延迟", "同步延迟", "slave延迟", "主从同步慢"],
        "连接超时": ["连接失败", "连接不上", "timeout", "连接异常"],
        "证书过期": ["证书失效", "证书错误", "ssl错误", "https错误"],
        "权限拒绝": ["权限不足", "permission denied", "403", "访问被拒绝"],
        "部署失败": ["发布失败", "部署错误", "deploy失败", "流水线失败"],
        "配置错误": ["配置问题", "配置异常", "配置不一致", "配置漂移"],
    }
    
    def _expand_synonyms(self, text: str) -> str:
        expanded_parts = [text]
        
        for key, synonyms in self.SYNONYM_MAP.items():
            if key in text:
                expanded_parts.extend(synonyms)
        
        for group_key, group_synonyms in self.SYNONYM_GROUPS.items():
            if any(syn in text for syn in group_synonyms):
                expanded_parts.append(group_key)
                expanded_parts.extend(group_synonyms)
        
        return " ".join(expanded_parts)
    
    def __init__(self, skills_dir: str = None):
        if skills_dir is None:
            skills_dir = os.path.join(os.path.dirname(__file__), "..", "..", "skills")
        self.skills_dir = Path(skills_dir)
        
        self.index_content: Optional[str] = None
        self.loaded_skills: Dict[str, str] = {}
        
        self._load_index()
    
    def _load_index(self):
        """
        加载主索引文件 skill.md
        """
        index_path = self.skills_dir / "skill.md"
        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                self.index_content = f.read()
    
    def _load_skill(self, skill_name: str) -> Optional[str]:
        """
        加载指定的 skill 文件
        
        Args:
            skill_name: skill 名称 (debug_skill, gnn_rca_skill, login_skill)
            
        Returns:
            skill 内容，如果不存在返回 None
        """
        if skill_name in self.loaded_skills:
            return self.loaded_skills[skill_name]
        
        if skill_name not in self.SKILL_REGISTRY:
            return None
        
        skill_info = self.SKILL_REGISTRY[skill_name]
        skill_path = self.skills_dir / skill_info["path"]
        
        if skill_path.exists():
            with open(skill_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.loaded_skills[skill_name] = content
                return content
        
        return None
    
    def get_index(self) -> Optional[str]:
        """
        获取主索引内容
        """
        return self.index_content
    
    def get_skill(self, skill_name: str) -> Optional[str]:
        """
        获取指定的 skill 内容（渐进式加载）
        """
        return self._load_skill(skill_name)
    
    def get_all_skills(self) -> Dict[str, str]:
        """
        获取所有 skill 内容（加载所有）
        """
        for skill_name in self.SKILL_REGISTRY:
            if skill_name not in self.loaded_skills:
                self._load_skill(skill_name)
        return self.loaded_skills
    
    def get_skills_by_category(self, category: str) -> Dict[str, str]:
        """
        获取指定类别的所有 skill
        
        Args:
            category: 类别名称 (diagnosis, connection)
        """
        skills = {}
        for skill_name, info in self.SKILL_REGISTRY.items():
            if info["category"] == category:
                content = self._load_skill(skill_name)
                if content:
                    skills[skill_name] = content
        return skills
    
    def get_skill_summary(self) -> str:
        """
        获取所有 skill 的摘要（用于 LLM prompt）
        """
        summaries = []
        
        for skill_name, info in self.SKILL_REGISTRY.items():
            category = self.CATEGORY_MAP.get(info["category"], info["category"])
            summary = f"- **{skill_name}** [{category}]: {info['description']}"
            summaries.append(summary)
        
        return "\n".join(summaries)
    
    def search_relevant_skills(self, query: str, intent: Dict) -> List[str]:
        """
        根据查询和意图搜索相关的 skill (带权重版本 + 同义词扩展)
        
        Args:
            query: 用户查询
            intent: 意图识别结果
            
        Returns:
            相关的 skill 名称列表，按得分降序排列
        """
        scores: Dict[str, float] = defaultdict(float)
        matched_keywords: Dict[str, Set[str]] = defaultdict(set)
        
        query_lower = query.lower()
        
        symptoms = intent.get("symptoms", [])
        symptoms_str = " ".join([s.get("value", "") if isinstance(s, dict) else s for s in symptoms])
        
        entities = intent.get("entities", {})
        entities_str = " ".join([str(v) for v in entities.values()]) if entities else ""
        
        combined_text = f"{query_lower} {symptoms_str} {entities_str}".lower()
        
        expanded_text = self._expand_synonyms(combined_text)
        
        for skill_name, weighted_kws in self.WEIGHTED_KEYWORDS.items():
            for category, keywords in weighted_kws.items():
                for keyword, weight in keywords.items():
                    if keyword.lower() in expanded_text:
                        scores[skill_name] += weight
                        matched_keywords[skill_name].add(keyword)
        
        for skill_name, info in self.SKILL_REGISTRY.items():
            for keyword in info.get("keywords", []):
                if keyword.lower() in expanded_text:
                    scores[skill_name] += 2
                    matched_keywords[skill_name].add(keyword)
        
        if entities:
            db_type = entities.get("database", "").lower()
            if "mysql" in db_type:
                scores["mysql_deadlock_skill"] += 5
                scores["mysql_slow_query_skill"] += 5
            elif "postgresql" in db_type or "pg" in db_type:
                scores["postgresql_skill"] += 5
            elif "mongodb" in db_type or "mongo" in db_type:
                scores["mongodb_skill"] += 5
            elif "redis" in db_type:
                scores["redis_skill"] += 5
        
        if "java" in combined_text or "jvm" in combined_text:
            scores["jvm_skill"] += 15
        
        if "kafka" in combined_text:
            scores["kafka_skill"] += 10
        if "nginx" in combined_text:
            scores["nginx_skill"] += 10
        if "rabbitmq" in combined_text:
            scores["rabbitmq_skill"] += 10
        if "elasticsearch" in combined_text or "es集群" in combined_text:
            scores["elasticsearch_skill"] += 10
        if "redis" in combined_text and "mysql" not in combined_text:
            scores["redis_skill"] += 10
        
        if "systemd" in combined_text or "systemctl" in combined_text:
            scores["systemd_autostart_skill"] += 15
        if "服务自启动" in combined_text or "开机启动" in combined_text:
            scores["systemd_autostart_skill"] += 12
        if "服务重启后" in combined_text and "不" in combined_text:
            scores["systemd_autostart_skill"] += 10
        
        import re
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        has_ip = re.search(ip_pattern, combined_text)
        has_server_keyword = any(kw in combined_text for kw in ["服务器", "server", "主机", "host", "linux", "阿里云", "aliyun", "ecs"])
        
        if has_ip or has_server_keyword:
            scores["login_skill"] += 20
            matched_keywords["login_skill"].add("远程服务器" if has_server_keyword else "IP地址")
        
        if not scores:
            return ["debug_skill"]
        
        sorted_skills = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        top_skills = []
        for skill_name, score in sorted_skills:
            if score >= 5 or len(top_skills) < 3:
                top_skills.append(skill_name)
            if len(top_skills) >= 5:
                break
        
        return top_skills
    
    def search_relevant_skills_legacy(self, query: str, intent: Dict) -> List[str]:
        """
        根据查询和意图搜索相关的 skill (旧版本，保留兼容)
        
        Args:
            query: 用户查询
            intent: 意图识别结果
            
        Returns:
            相关的 skill 名称列表
        """
        relevant_skills = []
        
        query_lower = query.lower()
        symptoms = intent.get("symptoms", [])
        symptoms_str = " ".join([s.get("value", "") if isinstance(s, dict) else s for s in symptoms])
        
        combined_text = f"{query_lower} {symptoms_str}".lower()
        
        for skill_name, info in self.SKILL_REGISTRY.items():
            keywords = info["keywords"]
            if any(kw in combined_text for kw in keywords):
                relevant_skills.append(skill_name)
        
        if not relevant_skills:
            relevant_skills = ["debug_skill"]
        
        return list(set(relevant_skills))
    
    def get_match_details(self, query: str, intent: Dict) -> Dict[str, Any]:
        """
        获取匹配详情，用于调试和分析
        
        Args:
            query: 用户查询
            intent: 意图识别结果
            
        Returns:
            匹配详情，包含得分、匹配关键词等
        """
        scores: Dict[str, float] = defaultdict(float)
        matched_keywords: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        
        query_lower = query.lower()
        symptoms = intent.get("symptoms", [])
        symptoms_str = " ".join([s.get("value", "") if isinstance(s, dict) else s for s in symptoms])
        combined_text = f"{query_lower} {symptoms_str}".lower()
        
        expanded_text = self._expand_synonyms(combined_text)
        
        for skill_name, weighted_kws in self.WEIGHTED_KEYWORDS.items():
            for category, keywords in weighted_kws.items():
                for keyword, weight in keywords.items():
                    if keyword.lower() in expanded_text:
                        scores[skill_name] += weight
                        matched_keywords[skill_name][category].append(f"{keyword}({weight})")
        
        if "systemd" in combined_text or "systemctl" in combined_text:
            scores["systemd_autostart_skill"] += 15
        if "服务自启动" in combined_text or "开机启动" in combined_text:
            scores["systemd_autostart_skill"] += 12
        if "服务重启后" in combined_text and "不" in combined_text:
            scores["systemd_autostart_skill"] += 10
        if "java" in combined_text or "jvm" in combined_text:
            scores["jvm_skill"] += 15
        if "kafka" in combined_text:
            scores["kafka_skill"] += 10
        if "nginx" in combined_text:
            scores["nginx_skill"] += 10
        if "rabbitmq" in combined_text:
            scores["rabbitmq_skill"] += 10
        if "elasticsearch" in combined_text or "es集群" in combined_text:
            scores["elasticsearch_skill"] += 10
        
        import re
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        has_ip = re.search(ip_pattern, combined_text)
        has_server_keyword = any(kw in combined_text for kw in ["服务器", "server", "主机", "host", "linux", "阿里云", "aliyun", "ecs"])
        
        if has_ip or has_server_keyword:
            scores["login_skill"] += 20
            matched_keywords["login_skill"]["component"].append("远程服务器(20)" if has_server_keyword else "IP地址(20)")
        
        sorted_skills = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "query": query,
            "combined_text": combined_text,
            "expanded_text": expanded_text[:200] + "..." if len(expanded_text) > 200 else expanded_text,
            "top_matches": [
                {
                    "skill": skill_name,
                    "score": score,
                    "matched_keywords": dict(matched_keywords[skill_name])
                }
                for skill_name, score in sorted_skills
            ]
        }
    
    def get_relevant_skills_content(self, skill_names: List[str]) -> str:
        """
        获取相关 skill 的完整内容（用于 LLM prompt）
        
        Args:
            skill_names: skill 名称列表
            
        Returns:
            格式化的 skill 内容
        """
        contents = []
        
        for skill_name in skill_names:
            content = self._load_skill(skill_name)
            if content:
                info = self.SKILL_REGISTRY.get(skill_name, {})
                category = self.CATEGORY_MAP.get(info.get("category", ""), "")
                header = f"### {skill_name} [{category}]\n路径: {info.get('path', '')}"
                contents.append(f"{header}\n\n{content}")
        
        return "\n\n---\n\n".join(contents)
    
    def parse_reference(self, text: str) -> List[Tuple[str, str]]:
        """
        解析文本中的 @reference 引用
        
        Args:
            text: 包含 @reference 的文本
            
        Returns:
            [(skill_name, skill_path), ...]
        """
        pattern = r'@reference:\s*([\w/]+\.md)'
        matches = re.findall(pattern, text)
        
        results = []
        for path in matches:
            for skill_name, info in self.SKILL_REGISTRY.items():
                if info["path"] == path:
                    results.append((skill_name, path))
                    break
        
        return results
    
    def reload_skills(self):
        """
        重新加载所有 skill 文件
        """
        self.loaded_skills.clear()
        self._load_index()
    
    def list_available_skills(self) -> List[Dict[str, Any]]:
        """
        列出所有可用的 skill
        """
        skills = []
        for skill_name, info in self.SKILL_REGISTRY.items():
            skill_path = self.skills_dir / info["path"]
            skills.append({
                "name": skill_name,
                "category": info["category"],
                "category_name": self.CATEGORY_MAP.get(info["category"], ""),
                "description": info["description"],
                "path": info["path"],
                "exists": skill_path.exists(),
                "keywords_count": len(info["keywords"])
            })
        return skills
    
    def get_tools_definition(self) -> List[Dict[str, Any]]:
        """
        获取所有可用工具的定义，用于 LLM function calling
        """
        return [
            {
                "name": "execute_command",
                "description": "在目标服务器上执行 shell 命令",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_host": {
                            "type": "string",
                            "description": "目标服务器 IP 或主机名"
                        },
                        "command": {
                            "type": "string",
                            "description": "要执行的 shell 命令"
                        },
                        "risk_level": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "操作风险等级"
                        }
                    },
                    "required": ["target_host", "command"]
                }
            },
            {
                "name": "save_diagnosis_plan",
                "description": "保存诊断计划到中间文件",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plan_name": {
                            "type": "string",
                            "description": "计划名称"
                        },
                        "check_type": {
                            "type": "string",
                            "description": "检查类型"
                        },
                        "commands": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "要执行的命令列表"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "选择这些命令的原因"
                        }
                    },
                    "required": ["plan_name", "check_type", "commands"]
                }
            },
            {
                "name": "save_execution_output",
                "description": "保存命令执行输出到中间文件",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_host": {
                            "type": "string",
                            "description": "目标服务器"
                        },
                        "output": {
                            "type": "string",
                            "description": "命令执行输出"
                        },
                        "command": {
                            "type": "string",
                            "description": "执行的命令"
                        }
                    },
                    "required": ["target_host", "output"]
                }
            },
            {
                "name": "query_knowledge_graph",
                "description": "查询知识图谱获取服务拓扑关系",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "服务名称"
                        },
                        "depth": {
                            "type": "integer",
                            "description": "查询深度，默认为 2"
                        }
                    },
                    "required": ["service"]
                }
            },
            {
                "name": "query_rag",
                "description": "查询 RAG 知识库获取相关文档",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "查询问题"
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "返回结果数量，默认为 5"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "generate_playbook",
                "description": "生成 Ansible Playbook 用于自动化执行",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_host": {
                            "type": "string",
                            "description": "目标服务器"
                        },
                        "tasks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "command": {"type": "string"}
                                }
                            },
                            "description": "任务列表"
                        }
                    },
                    "required": ["target_host", "tasks"]
                }
            },
            {
                "name": "ask_user_confirmation",
                "description": "向用户确认高风险操作",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "description": "要执行的操作描述"
                        },
                        "risk": {
                            "type": "string",
                            "description": "风险说明"
                        },
                        "impact": {
                            "type": "string",
                            "description": "可能的影响"
                        }
                    },
                    "required": ["operation", "risk"]
                }
            }
        ]
