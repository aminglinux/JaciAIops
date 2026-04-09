import asyncio
import shlex
import traceback
import os
import subprocess
from typing import Dict, Any, List
from datetime import datetime

from .intent_parse import IntentParseAgent
from .knowledge import KnowledgeExpertAgent
from .observability import ObservabilityAnalystAgent
from .master import MasterAgent
from .action_execute import ActionExecuteAgent
from .skill_manager import SkillManager
from .tool_registry import ToolRegistry
from ..utils.file_manager import IntermediateFileManager
from ..utils.logger import get_logger
from ..core.config import settings

logger = get_logger("orchestrator")


class MultiAgentOrchestrator:
    """
    Multi-Agent 协调器 (动态决策版本)
    
    核心改进：
    1. 不再使用硬编码流程
    2. LLM 根据 skill 文件动态决策执行步骤
    3. 通过 function calling 调用工具
    4. 按需生成中间文件
    """
    
    def __init__(self):
        self.intent_agent = IntentParseAgent()
        self.knowledge_agent = KnowledgeExpertAgent()
        self.observability_agent = ObservabilityAnalystAgent()
        self.file_manager = IntermediateFileManager()
        self.skill_manager = SkillManager()
        self.tool_registry = ToolRegistry(self.file_manager)
        self.master_agent = MasterAgent(self.tool_registry)
        self.action_agent = ActionExecuteAgent()
    
    async def process_query(self, user_query: str) -> Dict[str, Any]:
        """
        处理用户查询 - 动态决策版本
        
        流程：
        1. 意图识别（固定步骤）
        2. LLM 根据 skill 文件动态规划并执行
        3. 返回结果
        """
        start_time = datetime.now()
        
        result = {
            "query": user_query,
            "start_time": start_time.isoformat(),
            "stages": {},
            "final_decision": None,
            "execution_result": None,
            "warning_cleared": False,
            "mode": "dynamic"
        }
        
        try:
            result["stages"]["intent_parsing"] = await self._stage_intent_parsing(user_query)
            
            intent_data = result["stages"]["intent_parsing"]
            
            matched_skills = self.skill_manager.search_relevant_skills(user_query, intent_data)
            skills_content = self.skill_manager.get_relevant_skills_content(matched_skills)
            
            logger.info(f"Skill matching result: {matched_skills}, content_length={len(skills_content)}")
            
            result["stages"]["skill_matching"] = {
                "matched_skills": matched_skills,
                "skills_content_length": len(skills_content),
                "skills_preview": skills_content[:1000] + "..." if len(skills_content) > 1000 else skills_content
            }
            
            dynamic_result = await self.master_agent.plan_and_execute(
                user_query=user_query,
                intent_data=intent_data,
                max_iterations=40
            )
            
            result["stages"]["dynamic_execution"] = {
                "status": dynamic_result.get("status"),
                "iterations": len(dynamic_result.get("execution_history", [])),
                "execution_history": dynamic_result.get("execution_history", [])
            }
            
            if dynamic_result.get("status") == "completed":
                result["final_decision"] = dynamic_result.get("final_decision", {})
                result["raw_response"] = dynamic_result.get("raw_response", "")
                
                if dynamic_result.get("final_decision", {}).get("problem_type") == "none":
                    result["warning_cleared"] = True
            
            elif dynamic_result.get("status") == "needs_confirmation":
                result["final_decision"] = {
                    "decision": "NEEDS_CONFIRMATION",
                    "confirmation_request": dynamic_result.get("confirmation_request", {})
                }
            
            else:
                result["final_decision"] = {
                    "decision": "MANUAL_INTERVENTION",
                    "reason": dynamic_result.get("message", "动态执行未完成")
                }
            
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Error in process_query: {error_trace}")
            result["error"] = str(e)
            result["error_trace"] = error_trace
            result["final_decision"] = {
                "decision": "ERROR",
                "error": str(e),
                "root_cause_summary": "处理过程中发生错误",
                "action_plan": "请检查系统日志或人工介入"
            }
        
        end_time = datetime.now()
        result["end_time"] = end_time.isoformat()
        result["duration_seconds"] = (end_time - start_time).total_seconds()
        
        query_id = start_time.strftime("%Y%m%d_%H%M%S")
        full_result_file = self.file_manager.save_full_result(result, query_id)
        result["saved_to"] = full_result_file
        
        return result
    
    async def process_query_legacy(self, user_query: str) -> Dict[str, Any]:
        """
        处理用户查询 - 旧版本流程（保留作为 fallback）
        """
        start_time = datetime.now()
        
        result = {
            "query": user_query,
            "start_time": start_time.isoformat(),
            "stages": {},
            "final_decision": None,
            "execution_result": None,
            "warning_cleared": False,
            "mode": "legacy"
        }
        
        try:
            result["stages"]["intent_parsing"] = await self._stage_intent_parsing(user_query)
            
            entities = result["stages"]["intent_parsing"]["entities"]
            servers_list = entities.get("servers", [])
            symptoms = entities.get("symptoms", [])
            
            if servers_list:
                target_host = servers_list[0].get("normalized") if isinstance(servers_list[0], dict) else servers_list[0]
                
                result["stages"]["diagnosis_plan"] = await self.master_agent.generate_diagnosis_plan(
                    user_query, result["stages"]["intent_parsing"]
                )
                
                diagnosis_plan_file = self.file_manager.save_diagnosis_plan(
                    result["stages"]["diagnosis_plan"],
                    query_id=start_time.strftime("%Y%m%d_%H%M%S")
                )
                result["stages"]["diagnosis_plan"]["saved_to"] = diagnosis_plan_file
                
                result["stages"]["server_status_check"] = await self._execute_diagnosis_plan(
                    target_host, result["stages"]["diagnosis_plan"]
                )
                
                if result["stages"]["server_status_check"].get("raw_output"):
                    output_file = self.file_manager.save_execution_output(
                        result["stages"]["server_status_check"]["raw_output"],
                        target_host,
                        query_id=start_time.strftime("%Y%m%d_%H%M%S")
                    )
                    result["stages"]["server_status_check"]["output_saved_to"] = output_file
                
                status_check = result["stages"]["server_status_check"]
                
                if status_check.get("warning_cleared", False):
                    result["warning_cleared"] = True
                    result["final_decision"] = {
                        "decision": "RESOLVED",
                        "root_cause_summary": "服务器状态正常",
                        "action_plan": f"服务器 {target_host} 的状态检查完成，未发现异常。警告已解除。",
                        "confidence": "HIGH",
                        "affected_servers": [target_host]
                    }
                    
                    end_time = datetime.now()
                    result["end_time"] = end_time.isoformat()
                    result["duration_seconds"] = (end_time - start_time).total_seconds()
                    
                    return result
            
            services_list = entities.get("services", [])
            service = services_list[0].get("normalized", "unknown") if services_list else "unknown"
            
            result["stages"]["knowledge_query"] = await self._stage_knowledge_query(
                service, symptoms, entities
            )
            
            observability_report = await self._stage_observability(
                service, entities, result["stages"]["knowledge_query"]
            )
            
            if result["stages"].get("server_status_check"):
                observability_report["server_status_check"] = result["stages"]["server_status_check"]
            
            result["stages"]["observability_analysis"] = observability_report
            
            result["stages"]["master_decision"] = await self.master_agent.orchestrate(
                user_query,
                result["stages"]["intent_parsing"],
                result["stages"]["knowledge_query"],
                result["stages"]["observability_analysis"]
            )
            
            result["final_decision"] = result["stages"]["master_decision"]
            
        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"Error in process_query: {error_trace}")
            result["error"] = str(e)
            result["error_trace"] = error_trace
            result["final_decision"] = {
                "decision": "ERROR",
                "error": str(e),
                "root_cause_summary": "处理过程中发生错误",
                "action_plan": "请检查系统日志或人工介入"
            }
        
        end_time = datetime.now()
        result["end_time"] = end_time.isoformat()
        result["duration_seconds"] = (end_time - start_time).total_seconds()
        
        full_result_file = self.file_manager.save_full_result(
            result,
            query_id=start_time.strftime("%Y%m%d_%H%M%S")
        )
        result["saved_to"] = full_result_file
        
        return result
    
    async def _stage_intent_parsing(self, user_query: str) -> Dict[str, Any]:
        """
        阶段1: NER 实体识别和意图解析
        """
        intent_result = await self.intent_agent.parse(user_query)
        entities = await self.intent_agent.extract_entities(user_query)
        
        return {
            "intent": intent_result.get("intent"),
            "confidence": intent_result.get("confidence"),
            "entities": entities,
            "normalized_query": intent_result.get("normalized_query"),
            "ner_entities": intent_result.get("ner_entities", []),
            "keywords": intent_result.get("keywords", [])
        }
    
    async def _execute_diagnosis_plan(
        self,
        target_host: str,
        diagnosis_plan: Dict
    ) -> Dict[str, Any]:
        """
        执行诊断计划
        """
        commands = diagnosis_plan.get("commands", [])
        
        if not commands:
            return {
                "success": False,
                "warning_cleared": False,
                "error": "诊断计划中没有可执行的命令"
            }
        
        try:
            all_outputs = []
            for i, cmd in enumerate(commands):
                ssh_user = settings.SSH_USER or "root"
                ssh_opts = f"-o ConnectTimeout={settings.SSH_CONNECT_TIMEOUT}"
                if not settings.SSH_STRICT_HOST_KEY_CHECK:
                    ssh_opts += " -o StrictHostKeyChecking=no"
                escaped_cmd = shlex.quote(cmd)
                full_command = f"ssh {ssh_opts} -i {settings.SSH_KEY_PATH} {ssh_user}@{target_host} {escaped_cmd}"
                
                try:
                    result = subprocess.run(
                        full_command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    output = result.stdout + "\n" + result.stderr
                    all_outputs.append(f"=== CMD_{i}: {cmd} ===")
                    all_outputs.append(output)
                    all_outputs.append("")
                    
                except subprocess.TimeoutExpired:
                    all_outputs.append(f"=== CMD_{i}: {cmd} ===")
                    all_outputs.append("ERROR: Command timeout")
                    all_outputs.append("")
                except Exception as e:
                    all_outputs.append(f"=== CMD_{i}: {cmd} ===")
                    all_outputs.append(f"ERROR: {str(e)}")
                    all_outputs.append("")
            
            output = "\n".join(all_outputs)
            
            parsed_result = self._parse_diagnosis_output(output, diagnosis_plan)
            
            warning_cleared = False
            if parsed_result.get("success") and not parsed_result.get("anomalies"):
                warning_cleared = True
            
            return {
                "success": parsed_result.get("success", False),
                "warning_cleared": warning_cleared,
                "check_type": diagnosis_plan.get("check_type"),
                "reasoning": diagnosis_plan.get("reasoning"),
                "memory_usage": parsed_result.get("memory_usage"),
                "cpu_usage": parsed_result.get("cpu_usage"),
                "disk_usage": parsed_result.get("disk_usage"),
                "shm_usage": parsed_result.get("shm_usage"),
                "anomalies": parsed_result.get("anomalies", []),
                "raw_output": output[:5000]
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "warning_cleared": False,
                "error": "SSH 执行超时"
            }
        except Exception as e:
            return {
                "success": False,
                "warning_cleared": False,
                "error": str(e)
            }
    
    def _parse_diagnosis_output(self, output: str, diagnosis_plan: Dict) -> Dict[str, Any]:
        """
        解析诊断输出
        """
        result = {
            "success": False,
            "memory_usage": None,
            "cpu_usage": None,
            "disk_usage": None,
            "shm_usage": None,
            "anomalies": [],
            "raw_output": output
        }
        
        if "timed out" in output.lower() or "connection refused" in output.lower():
            result["anomalies"].append("连接失败或主机不可达")
            return result
        
        result["success"] = True
        
        lines = output.split('\n')
        
        for line in lines:
            if "Mem:" in line and "free" in output:
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        total_str = parts[1].rstrip('GMTP')
                        used_str = parts[2].rstrip('GMTP')
                        total = float(total_str)
                        used = float(used_str)
                        if total > 0:
                            result["memory_usage"] = round(used / total * 100, 2)
                            if result["memory_usage"] > 80:
                                result["anomalies"].append(f"内存使用率过高: {result['memory_usage']}%")
                    except (ValueError, IndexError):
                        pass
            
            if "load average" in line.lower():
                try:
                    load_part = line.split("load average:")[1].strip()
                    load_1 = float(load_part.split(',')[0].strip())
                    result["cpu_usage"] = load_1
                    if load_1 > 4:
                        result["anomalies"].append(f"系统负载过高: {load_1}")
                except (ValueError, IndexError):
                    pass
            
            if "/dev/shm" in line and "tmpfs" in line:
                try:
                    parts = line.split()
                    if len(parts) >= 5:
                        use_percent = parts[4].replace('%', '')
                        result["shm_usage"] = int(use_percent)
                        if result["shm_usage"] >= 90:
                            result["anomalies"].append(f"/dev/shm 使用率过高: {result['shm_usage']}%")
                except (ValueError, IndexError):
                    pass
            
            if "Filesystem" not in line and "/" in line:
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        use_percent = parts[4].replace('%', '')
                        disk_usage = int(use_percent)
                        if disk_usage > 85:
                            result["disk_usage"] = disk_usage
                            result["anomalies"].append(f"磁盘使用率过高: {disk_usage}% on {parts[5]}")
                    except (ValueError, IndexError):
                        pass
        
        return result
    
    async def _stage_knowledge_query(
        self, 
        service: str, 
        symptoms: List, 
        entities: Dict
    ) -> Dict[str, Any]:
        """
        查询知识图谱和 RAG
        """
        symptom_str = ", ".join([s.get("value", "") if isinstance(s, dict) else s for s in symptoms])
        
        knowledge_result = await self.knowledge_agent.query(
            service=service,
            symptom=symptom_str
        )
        
        return {
            "service": service,
            "topology_info": knowledge_result.get("topology_info", {}),
            "knowledge_report": knowledge_result.get("knowledge_report", ""),
            "rag_context": knowledge_result.get("rag_context", ""),
            "related_services": self._extract_related_services(knowledge_result.get("topology_info", {}))
        }
    
    async def _stage_observability(
        self,
        service: str,
        entities: Dict,
        knowledge_context: Dict
    ) -> Dict[str, Any]:
        """
        查询节点状态和日志
        """
        observability_result = await self.observability_agent.analyze_with_skills(
            service=service,
            entities=entities,
            knowledge_context=knowledge_context
        )
        
        return observability_result
    
    def _extract_related_services(self, topology_info: Dict) -> List[str]:
        """
        从拓扑信息中提取相关服务
        """
        related = []
        
        if "upstream" in topology_info:
            related.extend(topology_info["upstream"])
        if "downstream" in topology_info:
            related.extend(topology_info["downstream"])
        
        return list(set(related))
