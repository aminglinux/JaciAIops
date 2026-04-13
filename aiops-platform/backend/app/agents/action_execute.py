import json
import re
from typing import Dict, Any, List
from app.services import llm_config_manager

class ActionExecuteAgent:
    """
    Action Execute Agent (执行层)
    核心职责：生成安全的阿里云 OOS 指令，严格执行红线管控。
    """
    
    REDLINE_OPERATIONS = ["delete", "release", "modify_security_group", "drop", "truncate"]
    HIGH_RISK_OPERATIONS = ["restart_database", "full_release", "traffic_switch", "restart_core_service"]
    
    def __init__(self):
        pass
    
    def _build_prompt(self, action_plan: str, target_entities: Dict) -> str:
        return f"""你是一个严谨的运维执行者。你负责将修复方案转化为具体的阿里云 OOS (Ops Orchestration Service) 执行指令。

执行计划: {action_plan}
目标资源: {json.dumps(target_entities, ensure_ascii=False, indent=2)} (由 Intent/Analyst 阶段确认的 IP/ID)

可用 OOS 模板:
- ACS-ECS-RebootInstance (重启实例)
- ACS-ECS-RunCommand (执行脚本)
- ACS-RDS-RestartInstance (重启数据库)

Safety Constraints (CRITICAL)
红线拦截: 涉及删除数据、释放实例、修改安全组规则的操作，必须标记 requires_approval: true。
参数校验: 所有 InstanceId 或 IP 必须来自 Context，严禁凭空捏造。
高危操作: 重启核心数据库、全量发布、流量切换均视为 HIGH 风险，需人工确认。

Output Format
JSON:
{{ 
    "tool_name": "oos_executor", 
    "template_name": "ACS-ECS-RebootInstance", 
    "parameters": {{ 
        "instanceIds": ["{{resolved_instance_id}}"], 
        "regionId": "{{region}}" 
    }}, 
    "risk_assessment": "MEDIUM", 
    "requires_approval": false,
    "execution_note": "将重启实例 i-bp1... 预计影响时长 30s"
}}"""

    async def execute(self, action_plan: str, target_entities: Dict) -> dict:
        prompt = self._build_prompt(action_plan, target_entities)
        
        client, llm_config = llm_config_manager.get_client_for_scene("action_execute")
        response = client.chat.completions.create(
            model=llm_config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=llm_config.temperature
        )
        
        content = response.choices[0].message.content.strip()
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            result = {
                "tool_name": "oos_executor",
                "template_name": None,
                "parameters": {},
                "risk_assessment": "HIGH",
                "requires_approval": True,
                "execution_note": "无法解析执行指令，需要人工确认",
                "raw_response": content
            }
        
        if self._check_redline(result):
            result["requires_approval"] = True
            result["risk_assessment"] = "HIGH"
            result["redline_triggered"] = True
        
        return result
    
    def _check_redline(self, result: Dict) -> bool:
        template = result.get("template_name", "").lower()
        params = json.dumps(result.get("parameters", {})).lower()
        
        for op in self.REDLINE_OPERATIONS:
            if op in template or op in params:
                return True
        
        return False
    
    def _assess_risk(self, result: Dict, target_entities: Dict) -> str:
        service = target_entities.get("service", "")
        
        if any(svc in service for svc in ["mysql", "redis", "database"]):
            return "HIGH"
        
        template = result.get("template_name", "")
        if "Reboot" in template or "Restart" in template:
            return "MEDIUM"
        
        return "LOW"
