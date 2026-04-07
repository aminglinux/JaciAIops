import os
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path


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
            "description": "服务器故障排查",
            "keywords": [
                "磁盘", "disk", "空间", "space", "内存", "memory", "cpu", "负载", "load",
                "网络", "network", "连接", "connection", "超时", "timeout", "数据库", "database",
                "mysql", "redis", "nginx", "k8s", "kubernetes", "pod", "服务", "service",
                "异常", "error", "故障", "failure", "排查", "diagnose", "慢", "slow"
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
        "login_skill": {
            "path": "connection/login_skill.md",
            "category": "connection",
            "description": "SSH 连接管理",
            "keywords": [
                "连接", "connect", "登录", "login", "ssh", "远程", "remote",
                "主机", "host", "服务器", "server", "凭据", "credential"
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
        }
    }
    
    CATEGORY_MAP = {
        "diagnosis": "诊断类",
        "connection": "连接类",
        "network": "网络类",
        "monitoring": "监控类"
    }
    
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
        根据查询和意图搜索相关的 skill
        
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
