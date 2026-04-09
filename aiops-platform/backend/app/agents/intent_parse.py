import json
import re
from typing import Optional, List, Dict, Any
from openai import OpenAI
from app.core.config import settings
from .schemas import IntentResult, EntitiesResult, NEREntity
from ..utils.llm_cache import llm_cache

class IntentParseAgent:
    """
    Intent Parse Agent (入口网关)
    核心职责：准确识别意图，标准化实体，处理模糊输入。
    支持 NER 实体命名识别，提取关键字。
    """
    
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        )
        self.cmdb_service_list = settings.CMDB_SERVICE_LIST
        
    def _build_ner_prompt(self, user_input: str) -> str:
        return f"""你是一个运维领域的 NER (命名实体识别) 专家。你的任务是从用户的自然语言描述中提取所有关键实体。

当前系统维护的服务列表 (CMDB)：{json.dumps(self.cmdb_service_list, ensure_ascii=False)}

请识别以下类型的实体：
1. **SERVICE**: 服务名称（如 order-service, payment-service, nginx, mysql）
2. **SERVER**: 服务器/主机名（如 prod-server-01, 8.136.226.231）
3. **IP**: IP 地址
4. **LOAD_BALANCER**: 负载均衡器实例 ID（阿里云格式：lb- 开头，如 lb-bp1bxqgw0jflid09i6xnq）
5. **ECS_INSTANCE**: ECS 实例 ID（阿里云格式：i- 开头，如 i-bp14cdse1t3ahqrkuooe）
6. **SYMPTOM**: 故障现象（如 超时, OOM, 重启, 连接失败, CPU飙高）
7. **TIME**: 时间描述（如 刚才, 最近1小时, 今天上午）
8. **DATABASE**: 数据库（如 mysql, redis, postgres）
9. **METRIC**: 指标名称（如 CPU, 内存, 连接池, 延迟）
10. **ACTION**: 操作动作（如 重启, 扩容, 回滚, 查询）
11. **LOG_TYPE**: 日志类型（如 应用日志, 系统日志, 错误日志, 访问日志）
12. **ANALYSIS_TYPE**: 分析类型（如 异常检测, 根因分析, 趋势分析, 预测）
13. **TIME_SERIES**: 时间序列相关（如 时间序列, 时序数据, 历史数据）

**重要提示**：
- 阿里云资源 ID 格式识别：
  - 负载均衡器：lb- 开头（如 lb-bp1bxqgw0jflid09i6xnq）
  - ECS 实例：i- 开头（如 i-bp14cdse1t3ahqrkuooe）
  - 安全组：sg- 开头
  - 这些是实例 ID，不是域名，不要误识别为 SERVER 或其他类型

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

    async def parse(self, user_input: str) -> IntentResult:
        ner_prompt = self._build_ner_prompt(user_input)
        
        cache_key_messages = json.dumps([{"role": "user", "content": ner_prompt}], ensure_ascii=False)
        cached = llm_cache.get(settings.OPENAI_MODEL, cache_key_messages, 0.1)
        if cached is not None:
            ner_result = cached
        else:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": ner_prompt}],
                temperature=0.1
            )
            content = response.choices[0].message.content.strip()
            content = re.sub(r'^```json\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
            try:
                ner_result = json.loads(content)
            except json.JSONDecodeError:
                ner_result = {
                    "entities": [],
                    "keywords": [],
                    "intent": "GENERAL_QA",
                    "confidence": "LOW"
                }
            llm_cache.set(settings.OPENAI_MODEL, cache_key_messages, 0.1, ner_result)
        
        entities = ner_result.get("entities", [])
        intent_prompt = self._build_intent_prompt(user_input, entities)
        
        cache_key_messages2 = json.dumps([{"role": "user", "content": intent_prompt}], ensure_ascii=False)
        cached2 = llm_cache.get(settings.OPENAI_MODEL, cache_key_messages2, 0.1)
        if cached2 is not None:
            intent_result = cached2
        else:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": intent_prompt}],
                temperature=0.1
            )
            content = response.choices[0].message.content.strip()
            content = re.sub(r'^```json\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
            try:
                intent_result = json.loads(content)
            except json.JSONDecodeError:
                intent_result = {
                    "intent": "GENERAL_QA",
                    "entities": {},
                    "confidence": "LOW",
                    "normalized_query": user_input,
                    "clarification_needed": True,
                    "raw_response": content
                }
            llm_cache.set(settings.OPENAI_MODEL, cache_key_messages2, 0.1, intent_result)
        
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
            intent=result.intent,
            confidence=result.confidence,
        )
