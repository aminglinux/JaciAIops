import asyncio
import shlex
import traceback
import os
import subprocess
import re
from typing import Dict, Any, List
from datetime import datetime, timedelta

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
        self.alert_log_keywords = [
            "error", "exception", "timeout", "timed out", "refused",
            "oom", "out of memory", "panic", "failed", "unavailable",
            "connection reset", "reset by peer", "deadlock", "slow query",
        ]
    
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
            "warnings": [],
            "warning_cleared": False,
            "mode": "dynamic"
        }
        
        try:
            is_alert_rca = self._is_alert_rca_query(user_query)
            result["stages"]["intent_parsing"] = await self._stage_intent_parsing(user_query)
            
            intent_data = result["stages"]["intent_parsing"]
            extra_context = None

            if is_alert_rca:
                extra_context = await self._stage_alert_rca_prefetch(user_query, intent_data)
                result["stages"]["alert_prefetch"] = extra_context
                prefetch_warnings = extra_context.get("warnings", []) if isinstance(extra_context, dict) else []
                if isinstance(prefetch_warnings, list):
                    result["warnings"] = prefetch_warnings
            
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
                extra_context=extra_context,
                max_iterations=12 if is_alert_rca else 40
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

            if extra_context:
                result["final_decision"] = self._merge_alert_prefetch_into_final_decision(
                    result.get("final_decision", {}) or {},
                    extra_context,
                )
            
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

    def _merge_alert_prefetch_into_final_decision(
        self,
        final_decision: Dict[str, Any],
        extra_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged_decision = dict(final_decision or {})
        prefetch_log = dict(extra_context.get("log_evidence_prefetch") or {})
        if not prefetch_log:
            return merged_decision

        existing_log_evidence = merged_decision.get("log_evidence")
        if not isinstance(existing_log_evidence, dict):
            existing_log_evidence = {}

        merged_log_evidence = {
            "status": prefetch_log.get("status", "not_found"),
            "summary": prefetch_log.get("message")
            or (
                f"日志预采集状态为 {prefetch_log.get('status', 'not_found')}，"
                f"匹配分数 {prefetch_log.get('match_score', 0)}。"
            ),
            "top_patterns": prefetch_log.get("matched_keywords", []),
            "sample_logs": prefetch_log.get("sample_messages", []),
            "suspected_component": extra_context.get("alert_context", {}).get("service", ""),
            "confidence": "HIGH" if prefetch_log.get("status") == "matched" else "MEDIUM" if prefetch_log.get("status") == "weak_matched" else "LOW",
            "match_score": prefetch_log.get("match_score", 0),
            "matched_fields": prefetch_log.get("matched_fields", []),
            "source_type": prefetch_log.get("source_type"),
            **existing_log_evidence,
        }

        if not existing_log_evidence:
            merged_decision["log_evidence"] = merged_log_evidence
        else:
            merged_decision["log_evidence"] = {
                **merged_log_evidence,
                **existing_log_evidence,
                "status": existing_log_evidence.get("status") or merged_log_evidence["status"],
                "summary": existing_log_evidence.get("summary") or merged_log_evidence["summary"],
                "top_patterns": existing_log_evidence.get("top_patterns") or merged_log_evidence["top_patterns"],
                "sample_logs": existing_log_evidence.get("sample_logs") or merged_log_evidence["sample_logs"],
                "suspected_component": existing_log_evidence.get("suspected_component") or merged_log_evidence["suspected_component"],
                "confidence": existing_log_evidence.get("confidence") or merged_log_evidence["confidence"],
            }

        if not merged_decision.get("affected_services"):
            alert_service = extra_context.get("alert_context", {}).get("service")
            related_services = extra_context.get("knowledge_context", {}).get("related_services", [])
            merged_decision["affected_services"] = [item for item in [alert_service, *related_services] if item]

        if not merged_decision.get("evidence_chain"):
            evidence_chain = []
            knowledge_report = extra_context.get("knowledge_context", {}).get("knowledge_report")
            if knowledge_report:
                evidence_chain.append(f"KG: {knowledge_report[:160]}")
            metrics_evidence = extra_context.get("metrics_evidence", {})
            if metrics_evidence.get("success"):
                evidence_chain.append(f"Metrics: 来自 {metrics_evidence.get('source_type', 'unknown')} 的指标预采集成功")
            evidence_chain.append(f"Logs: {merged_decision['log_evidence'].get('summary', '无日志证据')}")
            trace_evidence = extra_context.get("trace_evidence", {})
            if trace_evidence.get("success"):
                evidence_chain.append(f"Traces: 来自 {trace_evidence.get('source_type', 'unknown')} 的链路预采集成功")
            merged_decision["evidence_chain"] = evidence_chain

        return merged_decision

    def _is_alert_rca_query(self, user_query: str) -> bool:
        return "[ALERT_RCA]" in user_query

    def _extract_alert_context(self, user_query: str, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        def _match_field(field_name: str) -> str:
            pattern = rf"{field_name}:\s*(.+)"
            match = re.search(pattern, user_query)
            return match.group(1).strip() if match else ""

        entities = intent_data.get("entities", {}) if isinstance(intent_data, dict) else {}
        services = entities.get("services", []) or []
        service_from_intent = ""
        if services:
            first_service = services[0]
            if isinstance(first_service, dict):
                service_from_intent = first_service.get("normalized") or first_service.get("value") or ""
            else:
                service_from_intent = str(first_service)

        metrics = entities.get("metrics", []) or []
        metric_from_intent = ""
        if metrics:
            first_metric = metrics[0]
            if isinstance(first_metric, dict):
                metric_from_intent = first_metric.get("normalized") or first_metric.get("value") or ""
            else:
                metric_from_intent = str(first_metric)

        alert_time_raw = _match_field("发生时间")
        lookback_match = re.search(r"回看窗口:\s*告警时间前后\s*(\d+)\s*分钟", user_query)
        lookback_minutes = int(lookback_match.group(1)) if lookback_match else 15

        return {
            "alert_name": _match_field("告警名称"),
            "severity": _match_field("告警级别") or "warning",
            "service": _match_field("服务") or service_from_intent or "unknown",
            "instance": _match_field("实例/IP/Pod"),
            "metric_name": _match_field("指标") or metric_from_intent,
            "current_value": _match_field("当前值"),
            "threshold": _match_field("阈值"),
            "alert_time": alert_time_raw,
            "lookback_minutes": lookback_minutes,
            "description": _match_field("告警描述"),
        }

    def _build_alert_time_range(self, alert_time: str, lookback_minutes: int) -> List[str]:
        try:
            normalized = alert_time.replace("Z", "+00:00")
            alert_dt = datetime.fromisoformat(normalized)
        except Exception:
            alert_dt = datetime.utcnow()

        start_dt = alert_dt - timedelta(minutes=max(1, lookback_minutes))
        end_dt = alert_dt + timedelta(minutes=max(1, lookback_minutes))
        return [
            start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        ]

    async def _stage_alert_rca_prefetch(self, user_query: str, intent_data: Dict[str, Any]) -> Dict[str, Any]:
        alert_context = self._extract_alert_context(user_query, intent_data)
        time_range = self._build_alert_time_range(
            alert_context.get("alert_time", ""),
            int(alert_context.get("lookback_minutes", 15) or 15),
        )
        service = alert_context.get("service", "unknown")
        instance = alert_context.get("instance") or ""

        data_sources_info = await self.tool_registry._list_data_sources()
        available_sources = {
            item.get("name"): item.get("available", False)
            for item in data_sources_info.get("data_sources", [])
            if isinstance(item, dict)
        }

        symptoms = intent_data.get("entities", {}).get("symptoms", []) if isinstance(intent_data, dict) else []
        knowledge_context = await self._stage_knowledge_query(service, symptoms, intent_data.get("entities", {}))

        metrics_data = await self._prefetch_alert_metrics(service, available_sources)
        logs_data = await self._prefetch_alert_logs(alert_context, time_range, available_sources)
        traces_data = await self._prefetch_alert_traces(service, available_sources)

        return {
            "mode": "alert_prefetch_pipeline",
            "alert_context": alert_context,
            "time_range": time_range,
            "available_sources": available_sources,
            "knowledge_context": knowledge_context,
            "metrics_evidence": metrics_data,
            "log_evidence_prefetch": logs_data,
            "trace_evidence": traces_data,
            "warnings": knowledge_context.get("warnings", []) if isinstance(knowledge_context, dict) else [],
        }

    async def _prefetch_alert_metrics(self, service: str, available_sources: Dict[str, bool]) -> Dict[str, Any]:
        query = "up"
        if service and service != "unknown":
            query = f'up{{job=~".*{service}.*"}}'

        for source_name in ["prometheus", "aliyun_monitor"]:
            if not available_sources.get(source_name):
                continue
            result = await self.tool_registry._load_data_from_source(
                source_name=source_name,
                data_type="metrics",
                filters={"service": service},
                query=query,
            )
            if result.get("success"):
                return result

        return {
            "success": False,
            "status": "not_available",
            "message": "未获取到可用 metrics 数据源或数据",
        }

    async def _prefetch_alert_logs(
        self,
        alert_context: Dict[str, Any],
        time_range: List[str],
        available_sources: Dict[str, bool],
    ) -> Dict[str, Any]:
        service = alert_context.get("service", "")
        instance = alert_context.get("instance", "")
        metric_name = alert_context.get("metric_name", "")
        description = alert_context.get("description", "")

        elastic_query = {
            "size": 20,
            "sort": [{"@timestamp": {"order": "desc"}}],
            "query": {
                "bool": {
                    "must": [
                        {"range": {"@timestamp": {"gte": time_range[0], "lte": time_range[1]}}},
                        {
                            "bool": {
                                "should": [
                                    {"term": {"service.keyword": service}},
                                    {"term": {"service_name.keyword": service}},
                                    {"term": {"instance.keyword": instance}},
                                    {"match": {"message": description or metric_name or service}},
                                ],
                                "minimum_should_match": 1,
                            }
                        },
                    ]
                }
            },
        }
        loki_query = f'{{service="{service}"}} |= "error"'
        if description:
            loki_query = f'{{service="{service}"}} |= "{description.split(" ")[0]}"'

        for source_name in ["loki", "elasticsearch"]:
            if not available_sources.get(source_name):
                continue
            kwargs: Dict[str, Any] = {}
            if source_name == "loki":
                kwargs["query"] = loki_query
            else:
                kwargs["query"] = elastic_query

            result = await self.tool_registry._load_data_from_source(
                source_name=source_name,
                data_type="logs",
                time_range=time_range,
                filters={"service": service, "instance": instance},
                **kwargs,
            )
            if result.get("success"):
                log_assessment = self._assess_log_relevance(result, alert_context)
                return {
                    **result,
                    **log_assessment,
                }

        return {
            "success": False,
            "status": "not_found",
            "message": "未从 Loki/Elasticsearch 预采集到相关日志",
        }

    def _has_meaningful_logs(self, result: Dict[str, Any]) -> bool:
        if result.get("total_logs", 0) > 0:
            return True
        if result.get("logs"):
            return True
        if result.get("result"):
            return True
        return False

    def _extract_log_text_samples(self, result: Dict[str, Any]) -> List[str]:
        samples: List[str] = []

        for log_item in result.get("logs", [])[:10]:
            if isinstance(log_item, dict):
                message = (
                    log_item.get("message")
                    or log_item.get("content")
                    or log_item.get("log")
                    or json.dumps(log_item, ensure_ascii=False)
                )
                samples.append(str(message))

        for stream in result.get("result", [])[:10]:
            if not isinstance(stream, dict):
                continue
            values = stream.get("values", []) or []
            for value in values[:3]:
                if isinstance(value, list) and len(value) >= 2:
                    samples.append(str(value[1]))

        for log_item in result.get("sample_logs", [])[:10]:
            if isinstance(log_item, dict):
                samples.append(str(log_item.get("message") or log_item))
            else:
                samples.append(str(log_item))

        return [sample for sample in samples if sample.strip()]

    def _assess_log_relevance(self, result: Dict[str, Any], alert_context: Dict[str, Any]) -> Dict[str, Any]:
        samples = self._extract_log_text_samples(result)
        if not samples and not self._has_meaningful_logs(result):
            return {
                "status": "not_found",
                "match_score": 0,
                "matched_keywords": [],
                "matched_fields": [],
                "sample_messages": [],
            }

        service = str(alert_context.get("service", "") or "").lower()
        instance = str(alert_context.get("instance", "") or "").lower()
        metric_name = str(alert_context.get("metric_name", "") or "").lower()
        description = str(alert_context.get("description", "") or "").lower()

        score = 0
        matched_keywords: List[str] = []
        matched_fields: List[str] = []

        for sample in samples:
            sample_lower = sample.lower()

            for keyword in self.alert_log_keywords:
                if keyword in sample_lower and keyword not in matched_keywords:
                    matched_keywords.append(keyword)
                    score += 2

            if service and service in sample_lower:
                score += 2
                if "service" not in matched_fields:
                    matched_fields.append("service")
            if instance and instance in sample_lower:
                score += 2
                if "instance" not in matched_fields:
                    matched_fields.append("instance")
            if metric_name and metric_name in sample_lower:
                score += 1
                if "metric" not in matched_fields:
                    matched_fields.append("metric")

            description_tokens = [token for token in re.split(r"[\s,;|]+", description) if len(token) >= 4][:5]
            for token in description_tokens:
                if token in sample_lower:
                    score += 1
                    if "description" not in matched_fields:
                        matched_fields.append("description")
                    break

        if score >= 6:
            status = "matched"
        elif score >= 2:
            status = "weak_matched"
        else:
            status = "not_found"

        return {
            "status": status,
            "match_score": score,
            "matched_keywords": matched_keywords[:10],
            "matched_fields": matched_fields,
            "sample_messages": samples[:5],
        }

    async def _prefetch_alert_traces(self, service: str, available_sources: Dict[str, bool]) -> Dict[str, Any]:
        if not available_sources.get("jaeger"):
            return {
                "success": False,
                "status": "not_available",
                "message": "Jaeger 不可用，未预采集到 traces",
            }

        result = await self.tool_registry._load_data_from_source(
            source_name="jaeger",
            data_type="traces",
            service=service,
            filters={"service": service},
        )
        if result.get("success"):
            return result
        return {
            "success": False,
            "status": "not_available",
            "message": result.get("error", "未预采集到 traces"),
        }
    
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
        
        entities_dict = entities.model_dump() if hasattr(entities, 'model_dump') else entities
        
        return {
            "intent": intent_result.intent,
            "confidence": intent_result.confidence,
            "entities": entities_dict,
            "normalized_query": intent_result.normalized_query,
            "ner_entities": [e.model_dump() if hasattr(e, 'model_dump') else e for e in intent_result.ner_entities],
            "keywords": intent_result.keywords
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
        if hasattr(knowledge_result, "model_dump"):
            knowledge_payload = knowledge_result.model_dump()
        elif isinstance(knowledge_result, dict):
            knowledge_payload = knowledge_result
        else:
            knowledge_payload = {}

        topology_info = knowledge_payload.get("topology_info", {})
        if hasattr(topology_info, "model_dump"):
            topology_info = topology_info.model_dump()
        topology_info = topology_info if isinstance(topology_info, dict) else {}
        knowledge_report = str(knowledge_payload.get("knowledge_report", "") or "")
        rag_context = str(knowledge_payload.get("rag_context", "") or "")

        warnings: List[Dict[str, str]] = []
        if not rag_context.strip():
            warnings.append(
                {
                    "code": "RAG_UNAVAILABLE",
                    "message": "RAG 服务不可用或未返回上下文，当前 RCA 基于告警与日志证据降级分析。",
                    "impact": "知识参考缺失，结论置信度可能下降",
                }
            )
        if topology_info.get("error") or str(topology_info.get("source", "")).startswith("mock"):
            warnings.append(
                {
                    "code": "KG_DEGRADED",
                    "message": "知识图谱查询异常，已使用降级拓扑数据。",
                    "impact": "上下游依赖关系可能不完整",
                }
            )
        if "知识分析暂时不可用" in knowledge_report:
            warnings.append(
                {
                    "code": "KNOWLEDGE_ANALYSIS_DEGRADED",
                    "message": "知识分析模型暂时不可用，已跳过该部分详细推理。",
                    "impact": "建议动作的解释性会降低",
                }
            )

        return {
            "service": service,
            "topology_info": topology_info,
            "knowledge_report": knowledge_report,
            "rag_context": rag_context,
            "related_services": self._extract_related_services(topology_info),
            "warnings": warnings,
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
