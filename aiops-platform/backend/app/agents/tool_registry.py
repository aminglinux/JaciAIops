import os
import json
import shlex
import subprocess
import asyncio
import re
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime
from pathlib import Path

from ..utils.file_manager import IntermediateFileManager
from ..utils.logger import get_logger
from ..core.config import settings

logger = get_logger("tool_registry")


class ToolRegistry:
    """
    工具注册中心
    注册所有可被 LLM 调用的工具，并提供统一的执行接口
    """
    
    def __init__(self, file_manager: IntermediateFileManager = None):
        self.tools: Dict[str, Callable] = {}
        self.file_manager = file_manager or IntermediateFileManager()
        self._pending_approvals: Dict[str, Dict] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """
        注册默认工具
        """
        self.register("execute_command", self._execute_command)
        self.register("save_diagnosis_plan", self._save_diagnosis_plan)
        self.register("save_execution_output", self._save_execution_output)
        self.register("query_knowledge_graph", self._query_knowledge_graph)
        self.register("query_rag", self._query_rag)
        self.register("generate_playbook", self._generate_playbook)
        self.register("ask_user_confirmation", self._ask_user_confirmation)
        self.register("send_approval_email", self._send_approval_email)
        self.register("check_approval_status", self._check_approval_status)
        self.register("execute_approved_command", self._execute_approved_command)
        self.register("submit_diagnosis_result", self._submit_diagnosis_result)
        self.register("parse_logs", self._parse_logs)
        self.register("load_metrics_and_detect_anomalies", self._load_metrics_and_detect_anomalies)
        self.register("build_service_graph", self._build_service_graph)
        self.register("gnn_root_cause_analysis", self._gnn_root_cause_analysis)
        self.register("generate_rca_report", self._generate_rca_report)
        self.register("list_data_sources", self._list_data_sources)
        self.register("load_data_from_source", self._load_data_from_source)
    
    def register(self, name: str, func: Callable):
        """
        注册工具
        """
        self.tools[name] = func
    
    def get_tool(self, name: str) -> Optional[Callable]:
        """
        获取工具
        """
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """
        列出所有工具
        """
        return list(self.tools.keys())
    
    async def execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        执行工具
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found",
                "available_tools": self.list_tools()
            }
        
        try:
            result = await tool(**kwargs)
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tool": tool_name,
                "params": kwargs
            }
    
    async def _execute_command(
        self,
        command: str,
        target_host: str = None,
        risk_level: str = "low",
        timeout: int = 60,
        ssh_user: str = None
    ) -> Dict[str, Any]:
        """
        执行命令（本地或远程）
        
        Args:
            command: 要执行的命令
            target_host: 目标主机地址，为 None 时在本地执行
            risk_level: 风险等级
            timeout: 超时时间
            ssh_user: SSH 用户名，优先级高于环境变量
            
        Returns:
            执行结果
        """
        security_check = self._check_command_security(command)
        if not security_check["safe"]:
            return {
                "success": False,
                "target_host": target_host,
                "command": command,
                "error": f"安全拒绝: {security_check['reason']}",
                "risk_level": "blocked"
            }
        
        try:
            if target_host:
                effective_ssh_user = ssh_user or settings.SSH_USER or "root"
                ssh_opts = f"-o ConnectTimeout={settings.SSH_CONNECT_TIMEOUT}"
                if not settings.SSH_STRICT_HOST_KEY_CHECK:
                    ssh_opts += " -o StrictHostKeyChecking=no"
                escaped_command = shlex.quote(command)
                ssh_command = f"ssh {ssh_opts} -i {settings.SSH_KEY_PATH} {effective_ssh_user}@{target_host} {escaped_command}"
                exec_command = ssh_command
            else:
                exec_command = command
            
            result = subprocess.run(
                exec_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            output = result.stdout + "\n" + result.stderr
            
            return {
                "success": result.returncode == 0,
                "target_host": target_host,
                "command": command,
                "risk_level": risk_level,
                "output": output,
                "return_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "target_host": target_host,
                "command": command,
                "error": "Command execution timeout"
            }
        except Exception as e:
            return {
                "success": False,
                "target_host": target_host,
                "command": command,
                "error": str(e)
            }
    
    def _check_command_security(self, command: str) -> Dict[str, Any]:
        command_lower = command.lower().strip()
        
        if len(command) > 2000:
            return {
                "safe": False,
                "reason": "命令长度超过 2000 字符限制"
            }
        
        injection_patterns = [
            (r';\s*rm\s', "检测到命令链注入（分号+删除）"),
            (r'\$\(', "检测到命令替换注入 $(...)"),
            (r'`[^`]+`', "检测到反引号命令替换"),
            (r'\|\s*rm\s', "检测到管道注入（管道+删除）"),
            (r'&&\s*rm\s', "检测到命令链注入（AND+删除）"),
            (r'\bexport\s+.*=\$\(.*\)', "检测到环境变量注入"),
            (r'/etc/passwd', "禁止访问 /etc/passwd"),
            (r'/etc/shadow', "禁止访问 /etc/shadow"),
            (r'nc\s+-[elp]', "检测到反向 Shell 模式"),
            (r'/dev/tcp/', "检测到 /dev/tcp 反向 Shell"),
            (r'bash\s+-i', "检测到交互式 Shell 注入"),
            (r'python[23]?\s+-c\s+.*import\s+socket', "检测到 Python 反向 Shell"),
        ]
        
        for pattern, reason in injection_patterns:
            if re.search(pattern, command_lower):
                return {"safe": False, "reason": reason}
        
        for dangerous_pattern in settings.DANGEROUS_COMMANDS:
            if re.search(dangerous_pattern, command_lower):
                return {
                    "safe": False,
                    "reason": f"命令包含危险操作模式: {dangerous_pattern}"
                }
        
        if "> /dev/sd" in command_lower or "> /dev/hd" in command_lower:
            return {
                "safe": False,
                "reason": "禁止直接写入磁盘设备"
            }
        
        if ":(){" in command:
            return {
                "safe": False,
                "reason": "检测到 fork bomb 攻击模式"
            }
        
        if re.search(r'(wget|curl)\s+.*\|.*sh', command_lower):
            return {
                "safe": False,
                "reason": "禁止从远程下载并执行脚本"
            }
        
        is_safe_command = False
        for safe_pattern in settings.SAFE_COMMANDS:
            if re.match(f"^{safe_pattern}", command_lower) or command_lower.startswith(safe_pattern):
                is_safe_command = True
                break
        
        if not is_safe_command:
            modify_keywords = ["rm", "mv", "cp", "chmod", "chown", "kill", "pkill",
                            "service", "docker rm", "docker stop",
                            "kubectl delete", "kubectl scale"]
            for kw in modify_keywords:
                if command_lower.startswith(kw):
                    return {
                        "safe": False,
                        "reason": f"命令 '{kw}' 需要人工确认，请使用 ask_user_confirmation 工具"
                    }
            
            if command_lower.startswith("systemctl"):
                dangerous_systemctl_actions = [
                    "systemctl stop", "systemctl start", "systemctl restart",
                    "systemctl reload", "systemctl kill", "systemctl isolate",
                    "systemctl enable", "systemctl disable", "systemctl mask",
                    "systemctl unmask", "systemctl edit", "systemctl daemon-reload",
                    "systemctl reset-failed", "systemctl set-property"
                ]
                for dangerous_action in dangerous_systemctl_actions:
                    if command_lower.startswith(dangerous_action):
                        return {
                            "safe": False,
                            "reason": f"命令 '{dangerous_action}' 需要人工确认，请使用 ask_user_confirmation 工具"
                        }
        
        return {"safe": True, "reason": "命令通过安全检查"}
    
    async def _save_diagnosis_plan(
        self,
        plan_name: str,
        check_type: str,
        commands: List[str],
        reasoning: str = "",
        expected_findings: List[str] = None
    ) -> Dict[str, Any]:
        """
        保存诊断计划
        """
        plan = {
            "plan_name": plan_name,
            "check_type": check_type,
            "commands": commands,
            "reasoning": reasoning,
            "expected_findings": expected_findings or [],
            "created_at": datetime.now().isoformat()
        }
        
        query_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.file_manager.save_diagnosis_plan(plan, query_id)
        
        return {
            "success": True,
            "plan": plan,
            "saved_to": filepath
        }
    
    async def _save_execution_output(
        self,
        output: str,
        command: str = "",
        target_host: str = None
    ) -> Dict[str, Any]:
        """
        保存执行输出
        """
        query_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.file_manager.save_execution_output(output, target_host or "local", query_id)
        
        return {
            "success": True,
            "target_host": target_host,
            "command": command,
            "saved_to": filepath
        }
    
    async def _query_knowledge_graph(
        self,
        service: str,
        depth: int = 2
    ) -> Dict[str, Any]:
        """
        查询知识图谱
        """
        try:
            from ..api.knowledge import get_knowledge_client
            client = get_knowledge_client()
            result = await client.query_topology(service=service, depth=depth)
            return {
                "success": True,
                "service": service,
                "topology": result
            }
        except Exception as e:
            return {
                "success": False,
                "service": service,
                "error": str(e)
            }
    
    async def _query_rag(
        self,
        query: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        查询 RAG 知识库
        """
        try:
            from ..api.knowledge import get_knowledge_client
            client = get_knowledge_client()
            result = await client.query_rag(query=query, top_k=top_k)
            return {
                "success": True,
                "query": query,
                "results": result
            }
        except Exception as e:
            return {
                "success": False,
                "query": query,
                "error": str(e)
            }
    
    async def _generate_playbook(
        self,
        target_host: str,
        tasks: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        生成 Ansible Playbook
        """
        try:
            import yaml
            
            playbook = [{
                "name": f"Diagnosis for {target_host}",
                "hosts": target_host,
                "gather_facts": False,
                "tasks": [
                    {
                        "name": task.get("name", f"Task {i}"),
                        "ansible.builtin.shell": task.get("command", ""),
                        "register": f"result_{i}"
                    }
                    for i, task in enumerate(tasks)
                ]
            }]
            
            query_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.file_manager.save_playbook(playbook, target_host, query_id)
            
            return {
                "success": True,
                "target_host": target_host,
                "playbook": playbook,
                "saved_to": filepath
            }
        except Exception as e:
            return {
                "success": False,
                "target_host": target_host,
                "error": str(e)
            }
    
    async def _ask_user_confirmation(
        self,
        operation: str,
        risk: str,
        impact: str = ""
    ) -> Dict[str, Any]:
        """
        向用户请求确认（高风险操作）
        """
        return {
            "success": True,
            "requires_confirmation": True,
            "operation": operation,
            "risk": risk,
            "impact": impact,
            "message": f"需要用户确认: {operation} (风险: {risk})"
        }
    
    async def _send_approval_email(
        self,
        to_email: str,
        operation: str,
        risk: str,
        impact: str,
        commands: List[str],
        target_host: str
    ) -> Dict[str, Any]:
        """
        发送审批请求邮件
        """
        try:
            from ..utils.email_sender import email_sender
            
            result = await email_sender.send_approval_request(
                to_email=to_email,
                operation=operation,
                risk=risk,
                impact=impact,
                commands=commands,
                target_host=target_host
            )
            
            if result.get("success"):
                approval_id = result.get("approval_id")
                self._pending_approvals[approval_id] = {
                    "operation": operation,
                    "commands": commands,
                    "target_host": target_host,
                    "status": "pending"
                }
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _check_approval_status(
        self,
        approval_id: str
    ) -> Dict[str, Any]:
        """
        检查审批状态
        """
        try:
            from ..utils.email_sender import email_sender
            
            result = await email_sender.check_approval(approval_id)
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _submit_diagnosis_result(
        self,
        problem_type: str,
        root_cause: str,
        impact: str,
        recommendation: str,
        risk_level: str = "MEDIUM",
        confidence: str = "MEDIUM",
        analysis_summary: str = "",
        evidence_chain: list | None = None,
        propagation_path: list | None = None,
        affected_services: list | None = None,
        log_evidence: dict | None = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        提交诊断结果，标志着诊断流程的结束
        这是 ReAct 流程的终止工具，LLM 在分析完成后必须调用此工具提交最终诊断结果
        """
        return {
            "success": True,
            "is_final": True,
            "problem_type": problem_type,
            "root_cause": root_cause,
            "impact": impact,
            "recommendation": recommendation,
            "risk_level": risk_level,
            "confidence": confidence,
            "analysis_summary": analysis_summary,
            "evidence_chain": evidence_chain or [],
            "propagation_path": propagation_path or [],
            "affected_services": affected_services or [],
            "log_evidence": log_evidence or {},
            "message": "诊断结果已提交",
            "extra_params": kwargs
        }
    
    async def _execute_approved_command(
        self,
        approval_id: str,
        wait_for_approval: bool = True,
        timeout_seconds: int = 3600
    ) -> Dict[str, Any]:
        """
        等待审批并执行命令
        """
        try:
            from ..utils.email_sender import email_sender
            
            if wait_for_approval:
                result = await email_sender.wait_for_approval(
                    approval_id=approval_id,
                    timeout_seconds=timeout_seconds
                )
                
                if not result.get("success"):
                    return result
                
                if not result.get("approved"):
                    return {
                        "success": True,
                        "approved": False,
                        "message": "操作被拒绝"
                    }
                
                approval = result.get("approval", {})
                commands = approval.get("commands", [])
                target_host = approval.get("target_host", "")
                
                execution_results = []
                for cmd in commands:
                    exec_result = await self._execute_command(
                        target_host=target_host,
                        command=cmd,
                        risk_level="high"
                    )
                    execution_results.append(exec_result)
                
                return {
                    "success": True,
                    "approved": True,
                    "executed": True,
                    "execution_results": execution_results
                }
            else:
                return await self._check_approval_status(approval_id)
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _parse_logs(
        self,
        log_path: str,
        time_range: List[str] = None,
        error_only: bool = False
    ) -> Dict[str, Any]:
        """
        解析日志数据
        """
        try:
            path = Path(log_path)
            if not path.exists():
                return {
                    "success": False,
                    "error": f"Log path not found: {log_path}"
                }
            
            logs = []
            log_parquet_path = path / "log-parquet"
            
            if log_parquet_path.exists():
                import pandas as pd
                for parquet_file in log_parquet_path.glob("*.parquet"):
                    try:
                        df = pd.read_parquet(parquet_file)
                        for _, row in df.iterrows():
                            logs.append(row.to_dict())
                    except Exception as e:
                        logger.error(f"Error loading {parquet_file}: {e}")
            
            error_logs = [l for l in logs if 'error' in str(l).lower() or 'exception' in str(l).lower()]
            
            return {
                "success": True,
                "total_logs": len(logs),
                "error_logs": len(error_logs),
                "sample_logs": logs[:5] if logs else [],
                "log_path": log_path
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _load_metrics_and_detect_anomalies(
        self,
        metric_path: str,
        services: List[str] = None,
        anomaly_threshold: float = 0.95
    ) -> Dict[str, Any]:
        """
        加载指标数据并检测异常
        """
        try:
            from ..algorithm.gnn_rca import GNNRootCauseAnalyzer
            
            analyzer = GNNRootCauseAnalyzer(data_path=metric_path)
            result = analyzer.detect_anomalies(threshold=anomaly_threshold)
            
            return {
                "success": True,
                "anomaly_services": result.get("anomaly_services", []),
                "anomaly_scores": result.get("anomaly_scores", {}),
                "threshold": anomaly_threshold
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _build_service_graph(
        self,
        services: List[str],
        dependencies: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        构建服务依赖图
        """
        try:
            from ..algorithm.gnn_rca import GNNRootCauseAnalyzer
            
            analyzer = GNNRootCauseAnalyzer()
            graph = analyzer.build_service_graph(services, dependencies)
            
            return {
                "success": True,
                "num_nodes": graph.num_nodes if hasattr(graph, 'num_nodes') else len(services),
                "num_edges": graph.num_edges if hasattr(graph, 'num_edges') else len(dependencies or []),
                "services": services
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _gnn_root_cause_analysis(
        self,
        data_path: str,
        anomaly_services: List[str] = None,
        top_k: int = 3,
        model_type: str = "GAT"
    ) -> Dict[str, Any]:
        """
        使用 GNN 进行根因分析
        """
        try:
            from ..algorithm.gnn_rca import GNNRootCauseAnalyzer
            
            analyzer = GNNRootCauseAnalyzer(data_path=data_path, model_type=model_type)
            result = analyzer.analyze(top_k=top_k)
            
            return {
                "success": True,
                "root_causes": result.get("root_causes", []),
                "propagation_path": result.get("propagation_path", []),
                "confidence": result.get("confidence", "MEDIUM")
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _generate_rca_report(
        self,
        rca_result: Dict[str, Any],
        logs: List[Dict] = None,
        metrics: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        生成根因分析报告
        """
        try:
            report = {
                "title": "GNN 根因分析报告",
                "generated_at": datetime.now().isoformat(),
                "root_causes": rca_result.get("root_causes", []),
                "propagation_path": rca_result.get("propagation_path", []),
                "confidence": rca_result.get("confidence", "MEDIUM"),
                "logs_analyzed": len(logs) if logs else 0,
                "metrics_analyzed": list(metrics.keys()) if metrics else []
            }
            
            query_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.file_manager.save_file(
                json.dumps(report, ensure_ascii=False, indent=2),
                f"rca_report_{query_id}.json"
            )
            
            return {
                "success": True,
                "report": report,
                "saved_to": filepath
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _list_data_sources(self) -> Dict[str, Any]:
        """
        列出所有可用的数据源
        """
        try:
            from ..utils.data_source_manager import data_source_manager
            
            sources = data_source_manager.list_available_sources()
            
            return {
                "success": True,
                "data_sources": sources,
                "default_source": settings.DEFAULT_DATA_SOURCE
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _load_data_from_source(
        self,
        source_name: str,
        data_type: str,
        time_range: List[str] = None,
        filters: Dict[str, Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        从指定数据源加载数据
        """
        try:
            from ..utils.data_source_manager import data_source_manager
            
            time_range_tuple = tuple(time_range) if time_range else None
            
            result = await data_source_manager.load_data(
                source_name=source_name,
                data_type=data_type,
                time_range=time_range_tuple,
                filters=filters,
                **kwargs
            )
            
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "source_name": source_name,
                "data_type": data_type
            }
    
    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
        """
        获取 LLM function calling 格式的工具定义
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "execute_command",
                    "description": "执行 shell 命令，用于诊断和排查问题。本地命令不需要设置 target_host，远程命令需要设置 target_host 使用 SSH 连接",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "要执行的 shell 命令"
                            },
                            "target_host": {
                                "type": "string",
                                "description": "目标服务器 IP 或主机名。本地命令不需要设置此参数；Docker 命令使用 docker exec 不需要设置此参数；只有远程服务器才需要设置"
                            },
                            "risk_level": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                                "description": "操作风险等级，默认为 low"
                            },
                            "ssh_user": {
                                "type": "string",
                                "description": "SSH 用户名，如果用户查询中提到了用户名则使用该用户名，否则使用默认配置"
                            }
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "save_diagnosis_plan",
                    "description": "保存诊断计划到中间文件，用于记录和后续分析",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "plan_name": {
                                "type": "string",
                                "description": "计划名称，如 'disk_space_check'"
                            },
                            "check_type": {
                                "type": "string",
                                "description": "检查类型，如 disk, network, memory, general"
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
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "save_execution_output",
                    "description": "保存命令执行输出到中间文件",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "output": {
                                "type": "string",
                                "description": "命令执行输出内容"
                            },
                            "command": {
                                "type": "string",
                                "description": "执行的命令"
                            },
                            "target_host": {
                                "type": "string",
                                "description": "目标服务器（可选）"
                            }
                        },
                        "required": ["output"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_knowledge_graph",
                    "description": "查询知识图谱获取服务拓扑关系和依赖信息",
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
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_rag",
                    "description": "查询 RAG 知识库获取相关文档和历史案例",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "查询问题或关键词"
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "返回结果数量，默认为 5"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_playbook",
                    "description": "生成 Ansible Playbook 用于自动化批量执行",
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
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "ask_user_confirmation",
                    "description": "向用户请求确认高风险操作，如重启服务、删除文件等",
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
            },
            {
                "type": "function",
                "function": {
                    "name": "send_approval_email",
                    "description": "发送审批请求邮件，用于高风险操作的人工审批。邮件包含操作详情和审批ID，用户回复 APPROVE 或 REJECT 进行审批",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to_email": {
                                "type": "string",
                                "description": "接收审批邮件的邮箱地址"
                            },
                            "operation": {
                                "type": "string",
                                "description": "要执行的操作描述"
                            },
                            "risk": {
                                "type": "string",
                                "description": "风险等级: low, medium, high"
                            },
                            "impact": {
                                "type": "string",
                                "description": "操作可能的影响"
                            },
                            "commands": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "要执行的命令列表"
                            },
                            "target_host": {
                                "type": "string",
                                "description": "目标服务器"
                            }
                        },
                        "required": ["to_email", "operation", "risk", "impact", "commands", "target_host"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_approval_status",
                    "description": "检查审批状态，查看用户是否已回复邮件进行审批",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "approval_id": {
                                "type": "string",
                                "description": "审批ID，在发送审批邮件时返回"
                            }
                        },
                        "required": ["approval_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_approved_command",
                    "description": "等待用户审批并执行命令。如果用户批准则执行，否则返回拒绝信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "approval_id": {
                                "type": "string",
                                "description": "审批ID"
                            },
                            "wait_for_approval": {
                                "type": "boolean",
                                "description": "是否等待审批，默认为 true"
                            },
                            "timeout_seconds": {
                                "type": "integer",
                                "description": "等待超时时间（秒），默认为 3600 秒"
                            }
                        },
                        "required": ["approval_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "submit_diagnosis_result",
                    "description": "【重要】提交最终诊断结果并结束诊断流程。当完成所有检查、分析出问题根因后，必须调用此工具提交诊断结论。这是诊断流程的终止标志。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "problem_type": {
                                "type": "string",
                                "enum": ["disk", "memory", "cpu", "network", "service", "configuration", "unknown", "none"],
                                "description": "问题类型"
                            },
                            "root_cause": {
                                "type": "string",
                                "description": "根本原因分析，详细说明导致问题的原因"
                            },
                            "impact": {
                                "type": "string",
                                "description": "影响范围，说明受影响的服务器、服务或用户"
                            },
                            "recommendation": {
                                "type": "string",
                                "description": "建议的修复操作或下一步行动"
                            },
                            "risk_level": {
                                "type": "string",
                                "enum": ["LOW", "MEDIUM", "HIGH"],
                                "description": "修复操作的风险等级"
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["HIGH", "MEDIUM", "LOW"],
                                "description": "诊断结论的置信度"
                            },
                            "analysis_summary": {
                                "type": "string",
                                "description": "分析过程摘要，包括执行的检查命令和关键发现"
                            },
                            "evidence_chain": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "用于支撑结论的关键证据链，建议按 KG/metrics/logs/traces 顺序组织"
                            },
                            "propagation_path": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "问题传播路径或依赖链路，例如 order-service -> payment-service -> redis"
                            },
                            "affected_services": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "确认受到影响的服务列表"
                            },
                            "log_evidence": {
                                "type": "object",
                                "description": "日志证据。即使没有命中相关日志，也必须给出状态说明。",
                                "properties": {
                                    "status": {
                                        "type": "string",
                                        "enum": ["matched", "weak_matched", "not_found"],
                                        "description": "日志证据状态：强命中/弱命中/未命中"
                                    },
                                    "summary": {
                                        "type": "string",
                                        "description": "日志证据摘要，未命中时说明原因"
                                    },
                                    "top_patterns": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "命中的关键日志模式或错误关键词"
                                    },
                                    "sample_logs": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "代表性日志样本，注意脱敏"
                                    },
                                    "suspected_component": {
                                        "type": "string",
                                        "description": "日志指向的可疑组件"
                                    },
                                    "confidence": {
                                        "type": "string",
                                        "enum": ["HIGH", "MEDIUM", "LOW"],
                                        "description": "基于日志证据的置信度"
                                    }
                                }
                            }
                        },
                        "required": ["problem_type", "root_cause", "impact", "recommendation"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "parse_logs",
                    "description": "解析日志数据，统计日志数量和错误日志",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "log_path": {
                                "type": "string",
                                "description": "日志数据路径"
                            },
                            "time_range": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "时间范围 [开始时间, 结束时间]"
                            },
                            "error_only": {
                                "type": "boolean",
                                "description": "是否只解析错误日志，默认为 false"
                            }
                        },
                        "required": ["log_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "load_metrics_and_detect_anomalies",
                    "description": "加载指标数据并使用 Isolation Forest 检测异常服务",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "metric_path": {
                                "type": "string",
                                "description": "指标数据路径"
                            },
                            "services": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "要分析的服务列表"
                            },
                            "anomaly_threshold": {
                                "type": "number",
                                "description": "异常检测阈值，默认 0.95"
                            }
                        },
                        "required": ["metric_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "build_service_graph",
                    "description": "构建服务依赖图，用于 GNN 分析",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "services": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "服务列表"
                            },
                            "dependencies": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "source": {"type": "string"},
                                        "target": {"type": "string"}
                                    }
                                },
                                "description": "服务依赖关系列表"
                            }
                        },
                        "required": ["services"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "gnn_root_cause_analysis",
                    "description": "使用 GNN 模型进行根因分析，返回 Top-K 根因候选",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data_path": {
                                "type": "string",
                                "description": "数据路径"
                            },
                            "anomaly_services": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "异常服务列表"
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "返回的根因数量，默认 3"
                            },
                            "model_type": {
                                "type": "string",
                                "enum": ["GAT", "GCN", "GraphSAGE"],
                                "description": "GNN 模型类型，默认 GAT"
                            }
                        },
                        "required": ["data_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_rca_report",
                    "description": "生成根因分析报告",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "rca_result": {
                                "type": "object",
                                "description": "GNN 分析结果"
                            },
                            "logs": {
                                "type": "array",
                                "items": {"type": "object"},
                                "description": "分析的日志数据"
                            },
                            "metrics": {
                                "type": "object",
                                "description": "分析的指标数据"
                            }
                        },
                        "required": ["rca_result"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_data_sources",
                    "description": "列出所有可用的数据源，包括本地文件系统、监控系统、日志平台等。在加载数据前应先调用此工具查看可用数据源。",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "load_data_from_source",
                    "description": "从指定数据源加载日志、指标或链路追踪数据。支持多种数据源：local(本地文件), prometheus, elasticsearch, loki, jaeger, aliyun_monitor。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source_name": {
                                "type": "string",
                                "enum": ["local", "prometheus", "elasticsearch", "loki", "jaeger", "aliyun_monitor"],
                                "description": "数据源名称"
                            },
                            "data_type": {
                                "type": "string",
                                "enum": ["logs", "metrics", "traces"],
                                "description": "数据类型"
                            },
                            "time_range": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "时间范围 [开始时间, 结束时间]，格式: YYYY-MM-DD HH:MM:SS"
                            },
                            "filters": {
                                "type": "object",
                                "description": "过滤条件，如服务名、日志级别等"
                            },
                            "data_path": {
                                "type": "string",
                                "description": "数据路径（仅用于 local 数据源）"
                            },
                            "query": {
                                "type": "string",
                                "description": "查询语句（用于 prometheus/elasticsearch/loki）"
                            },
                            "service": {
                                "type": "string",
                                "description": "服务名称（用于 jaeger）"
                            }
                        },
                        "required": ["source_name", "data_type"]
                    }
                }
            }
        ]
