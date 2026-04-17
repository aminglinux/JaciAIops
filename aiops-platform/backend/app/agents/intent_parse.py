import json
import logging
import re
from typing import Optional, List, Dict, Any
from app.core.config import settings
from app.services import llm_config_manager
from .schemas import IntentResult, EntitiesResult, NEREntity
from ..utils.llm_cache import llm_cache

logger = logging.getLogger(__name__)

class IntentParseAgent:
    """
    Intent Parse Agent (入口网关)
    核心职责：准确识别意图，标准化实体，处理模糊输入。
    支持 NER 实体命名识别，提取关键字。
    """
    
    def __init__(self):
        self.cmdb_service_list = settings.CMDB_SERVICE_LIST
        
    def _build_ner_prompt(self, user_input: str) -> str:
        return f"""你是一个运维领域的 NER (命名实体识别) 专家。你的任务是从用户的自然语言描述中提取所有关键实体。

当前系统维护的服务列表 (CMDB)：{json.dumps(self.cmdb_service_list, ensure_ascii=False)}

请识别以下类型的实体：
1. **SERVICE**: 服务名称（如 order-service, payment-service, nginx, mysql）
2. **SERVER**: 服务器/主机名（如 prod-server-01, 8.136.226.231）
3. **IP**: IP 地址
4. **SSH_USER**: SSH 登录用户名（如 root, admin, jaci, ubuntu）
5. **LOAD_BALANCER**: 负载均衡器实例 ID（阿里云格式：lb- 开头，如 lb-bp1bxqgw0jflid09i6xnq）
6. **ECS_INSTANCE**: ECS 实例 ID（阿里云格式：i- 开头，如 i-bp14cdse1t3ahqrkuooe）
7. **SYMPTOM**: 故障现象（如 超时, OOM, 重启, 连接失败, CPU飙高）
8. **TIME**: 时间描述（如 刚才, 最近1小时, 今天上午）
9. **DATABASE**: 数据库（如 mysql, redis, postgres）
10. **METRIC**: 指标名称（如 CPU, 内存, 连接池, 延迟）
11. **ACTION**: 操作动作（如 重启, 扩容, 回滚, 查询）
12. **LOG_TYPE**: 日志类型（如 应用日志, 系统日志, 错误日志, 访问日志）
13. **ANALYSIS_TYPE**: 分析类型（如 异常检测, 根因分析, 趋势分析, 预测）
14. **TIME_SERIES**: 时间序列相关（如 时间序列, 时序数据, 历史数据）

**重要提示**：
- 阿里云资源 ID 格式识别：
  - 负载均衡器：lb- 开头（如 lb-bp1bxqgw0jflid09i6xnq）
  - ECS 实例：i- 开头（如 i-bp14cdse1t3ahqrkuooe）
  - 安全组：sg- 开头
  - 这些是实例 ID，不是域名，不要误识别为 SERVER 或其他类型
- SSH_USER 识别：
  - 当用户说"用户名是xxx"、"登录ID是xxx"、"用xxx用户登录"时，提取用户名
  - 常见用户名：root, admin, ubuntu, centos, ec2-user, jaci 等

用户输入：{user_input}

Output Format (纯 JSON，无 Markdown 标记):
{{
    "entities": [
        {{"type": "LOAD_BALANCER", "value": "lb-bp1bxqgw0jflid09i6xnq", "normalized": "lb-bp1bxqgw0jflid09i6xnq"}},
        {{"type": "SYMPTOM", "value": "服务能力异常", "normalized": "service_capacity_abnormal"}},
        {{"type": "METRIC", "value": "服务能力", "normalized": "service_capacity"}}
    ],
    "keywords": ["负载均衡", "lb-bp1bxqgw0jflid09i6xnq", "服务能力"],
    "intent": "DIAGNOSE",
    "confidence": "HIGH"
}}"""

    def _build_intent_prompt(self, user_input: str, entities: List[Dict]) -> str:
        return f"""你是一个运维意图识别专家。根据提取的实体，确定用户的意图。

提取的实体：{json.dumps(entities, ensure_ascii=False)}
用户输入：{user_input}

意图分类：
- DIAGNOSE: 故障排查、根因分析
- QUERY_STATUS: 查询运行状态、资源使用率
- EXECUTE_FIX: 执行重启、扩容、回滚等变更操作
- GENERAL_QA: 运维知识咨询

Output Format (纯 JSON):
{{
    "intent": "DIAGNOSE",
    "entities": {{"service": "order-service", "ip": null, "symptom": "连接池耗尽", "time_range": "last_15_minutes"}},
    "confidence": "HIGH",
    "normalized_query": "诊断 order-service 的连接池耗尽问题",
    "clarification_needed": false
}}"""

    def _fallback_ner_result(self, user_input: str) -> Dict[str, Any]:
        text = user_input or ""
        lowered = text.lower()
        keywords = [item for item in re.split(r"[\s,，。；;:：]+", text) if item][:12]
        entities: List[Dict[str, str]] = []

        service_match = re.search(r'([a-zA-Z0-9_-]+(?:service|svc|k8s)[a-zA-Z0-9_-]*)', lowered)
        if service_match:
            value = service_match.group(1)
            entities.append({"type": "SERVICE", "value": value, "normalized": value})

        ip_match = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text)
        if ip_match:
            ip_value = ip_match.group(0)
            entities.append({"type": "IP", "value": ip_value, "normalized": ip_value})

        symptom_value = ""
        for symptom in ["timeout", "超时", "error", "异常", "慢", "失败", "拒绝", "连接"]:
            if symptom in lowered or symptom in text:
                symptom_value = symptom
                break
        if symptom_value:
            entities.append({"type": "SYMPTOM", "value": symptom_value, "normalized": symptom_value})

        return {
            "entities": entities,
            "keywords": keywords,
            "intent": "DIAGNOSE" if ("[alert_rca]" in lowered or "分析" in text or "告警" in text) else "GENERAL_QA",
            "confidence": "MEDIUM",
        }

    def _fallback_intent_result(self, user_input: str, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        lowered = (user_input or "").lower()
        service = next((str(entity.get("normalized") or entity.get("value")) for entity in entities if entity.get("type") == "SERVICE"), None)
        symptom = next((str(entity.get("normalized") or entity.get("value")) for entity in entities if entity.get("type") == "SYMPTOM"), "unknown")
        ip = next((str(entity.get("normalized") or entity.get("value")) for entity in entities if entity.get("type") == "IP"), None)

        intent = "GENERAL_QA"
        if any(word in lowered for word in ["diagnose", "rca", "告警", "分析", "异常", "排查", "故障", "[alert_rca]"]):
            intent = "DIAGNOSE"
        elif any(word in lowered for word in ["重启", "执行", "fix", "repair"]):
            intent = "EXECUTE_FIX"
        elif any(word in lowered for word in ["状态", "status", "运行", "监控"]):
            intent = "QUERY_STATUS"

        return {
            "intent": intent,
            "entities": {
                "service": service,
                "ip": ip,
                "symptom": symptom,
                "time_range": "last_15_minutes",
            },
            "confidence": "MEDIUM",
            "normalized_query": user_input,
            "clarification_needed": False,
        }

    def _extract_response_text(self, response: Any) -> str:
        try:
            choice = response.choices[0]
            message = choice.message
        except Exception:
            return ""

        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    text_value = item.get("text")
                    if isinstance(text_value, str) and text_value.strip():
                        parts.append(text_value.strip())
            if parts:
                return "\n".join(parts).strip()

        # 兼容工具调用场景：有时 content 为 None，但 arguments 存在
        tool_calls = getattr(message, "tool_calls", None)
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                function_obj = getattr(tool_call, "function", None)
                arguments = getattr(function_obj, "arguments", None) if function_obj else None
                if isinstance(arguments, str) and arguments.strip():
                    return arguments.strip()
                if isinstance(tool_call, dict):
                    function_obj = tool_call.get("function", {})
                    arguments = function_obj.get("arguments")
                    if isinstance(arguments, str) and arguments.strip():
                        return arguments.strip()
        return ""

    async def parse(self, user_input: str) -> IntentResult:
        client, llm_config = llm_config_manager.get_client_for_scene("intent_parse")
        temperature = llm_config.temperature if llm_config.temperature is not None else 0.1
        ner_prompt = self._build_ner_prompt(user_input)
        
        cache_key_messages = json.dumps([{"role": "user", "content": ner_prompt}], ensure_ascii=False)
        cached = llm_cache.get(llm_config.model, cache_key_messages, temperature)
        if cached is not None:
            ner_result = cached
        else:
            try:
                response = client.chat.completions.create(
                    model=llm_config.model,
                    messages=[{"role": "user", "content": ner_prompt}],
                    temperature=temperature
                )
                content = self._extract_response_text(response)
                content = re.sub(r'^```json\s*', '', content)
                content = re.sub(r'\s*```$', '', content)
                ner_result = json.loads(content)
            except Exception as exc:
                logger.warning("IntentParseAgent NER fallback triggered: %s", exc)
                ner_result = {
                    **self._fallback_ner_result(user_input),
                    "confidence": "LOW",
                }
            llm_cache.set(llm_config.model, cache_key_messages, temperature, ner_result)
        
        entities = ner_result.get("entities", [])
        intent_prompt = self._build_intent_prompt(user_input, entities)
        
        cache_key_messages2 = json.dumps([{"role": "user", "content": intent_prompt}], ensure_ascii=False)
        cached2 = llm_cache.get(llm_config.model, cache_key_messages2, temperature)
        if cached2 is not None:
            intent_result = cached2
        else:
            try:
                response = client.chat.completions.create(
                    model=llm_config.model,
                    messages=[{"role": "user", "content": intent_prompt}],
                    temperature=temperature
                )
                content = self._extract_response_text(response)
                content = re.sub(r'^```json\s*', '', content)
                content = re.sub(r'\s*```$', '', content)
                intent_result = json.loads(content)
            except Exception as exc:
                logger.warning("IntentParseAgent intent fallback triggered: %s", exc)
                intent_result = {
                    **self._fallback_intent_result(user_input, entities),
                    "confidence": "LOW",
                }
            llm_cache.set(llm_config.model, cache_key_messages2, temperature, intent_result)
        
        return IntentResult(
            intent=intent_result.get("intent", "GENERAL_QA"),
            confidence=intent_result.get("confidence", "LOW"),
            entities=intent_result.get("entities", {}),
            normalized_query=intent_result.get("normalized_query", user_input),
            ner_entities=[NEREntity(**e) for e in ner_result.get("entities", [])],
            keywords=ner_result.get("keywords", []),
            clarification_needed=intent_result.get("clarification_needed", False),
        )
    
    async def extract_entities(self, user_input: str) -> EntitiesResult:
        result = await self.parse(user_input)
        
        entities_by_type: Dict[str, List[NEREntity]] = {}
        for entity in result.ner_entities:
            entity_type = entity.type
            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []
            entities_by_type[entity_type].append(entity)
        
        return EntitiesResult(
            entities_by_type=entities_by_type,
            keywords=result.keywords,
            services=entities_by_type.get("SERVICE", []),
            servers=entities_by_type.get("SERVER", []) + entities_by_type.get("IP", []),
            symptoms=entities_by_type.get("SYMPTOM", []),
            databases=entities_by_type.get("DATABASE", []),
            metrics=entities_by_type.get("METRIC", []),
            actions=entities_by_type.get("ACTION", []),
            ssh_users=entities_by_type.get("SSH_USER", []),
            intent=result.intent,
            confidence=result.confidence,
        )
