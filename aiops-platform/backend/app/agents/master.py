import json
import re
import os
from typing import Dict, Any, List, Optional
from openai import OpenAI
from app.core.config import settings
from .skill_manager import SkillManager
from .tool_registry import ToolRegistry


class MasterAgent:
    """
    Master Agent (大脑中枢)
    
    核心职责：
    1. 根据 skill 文件动态生成诊断计划
    2. 使用 function calling 调用工具
    3. 根据执行结果动态决策下一步操作
    
    不再使用硬编码流程，而是根据 skill 文件和 LLM 动态决策
    """
    
    def __init__(self, tool_registry: ToolRegistry = None):
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        )
        self.skill_manager = SkillManager()
        self.tool_registry = tool_registry or ToolRegistry()
    
    async def plan_and_execute(
        self,
        user_query: str,
        intent_data: Dict,
        max_iterations: int = 40
    ) -> Dict[str, Any]:
        """
        根据 skill 文件动态规划并执行诊断流程
        
        Args:
            user_query: 用户查询
            intent_data: 意图识别结果
            max_iterations: 最大迭代次数
            
        Returns:
            诊断结果
        """
        relevant_skills = self.skill_manager.search_relevant_skills(user_query, intent_data)
        skills_content = self._get_skills_content(relevant_skills)
        
        messages = self._build_initial_messages(user_query, intent_data, skills_content)
        
        execution_history = []
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                tools=self.tool_registry.get_tools_for_llm(),
                tool_choice="auto",
                temperature=0.2
            )
            
            message = response.choices[0].message
            
            if message.content:
                messages.append({"role": "assistant", "content": message.content})
            
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": tool_call.function.arguments
                            }
                        }]
                    })
                    
                    tool_result = await self.tool_registry.execute(tool_name, **tool_args)
                    
                    execution_history.append({
                        "iteration": iteration,
                        "tool": tool_name,
                        "args": tool_args,
                        "result": tool_result
                    })
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })
                    
                    if tool_name == "ask_user_confirmation":
                        return {
                            "status": "needs_confirmation",
                            "execution_history": execution_history,
                            "confirmation_request": tool_result
                        }
                    
                    # ReAct 终止条件：LLM 主动提交诊断结果
                    if tool_name == "submit_diagnosis_result":
                        return {
                            "status": "completed",
                            "execution_history": execution_history,
                            "final_decision": {
                                "is_final": True,
                                "problem_type": tool_result.get("problem_type", "unknown"),
                                "root_cause": tool_result.get("root_cause", ""),
                                "impact": tool_result.get("impact", ""),
                                "recommendation": tool_result.get("recommendation", ""),
                                "risk_level": tool_result.get("risk_level", "MEDIUM"),
                                "confidence": tool_result.get("confidence", "MEDIUM"),
                                "analysis_summary": tool_result.get("analysis_summary", "")
                            },
                            "raw_response": tool_result.get("analysis_summary", "诊断完成")
                        }
        
        # 达到最大迭代次数仍未结束，返回未完成状态
        return {
            "status": "incomplete",
            "execution_history": execution_history,
            "message": "达到最大迭代次数，诊断未完成。请增加迭代次数或简化诊断范围。"
        }
    
    def _build_initial_messages(
        self,
        user_query: str,
        intent_data: Dict,
        skills_content: str
    ) -> List[Dict]:
        """
        构建初始消息
        """
        system_prompt = f"""你是一个智能运维诊断专家。你需要根据用户的问题和 skill 文件中的方法，动态规划并执行诊断流程。

## 可用的 Skill 文件
{skills_content}

---

## ⚠️ 权限边界与安全规则（必须严格遵守）

### 1. 危险命令绝对禁止执行
以下命令类型**绝对不可执行**，系统会自动拦截：
- **删除操作**: `rm -rf`, `drop database`, `truncate table`
- **系统操作**: `shutdown`, `reboot`, `init 0`, `init 6`
- **磁盘操作**: `dd if=`, `mkfs`, `fdisk`, `> /dev/sda`
- **权限修改**: `chmod -R 777`, `chown -R`
- **服务停止**: `systemctl stop`, `service stop`, `kill -9 -1`
- **远程脚本**: `wget ... | sh`, `curl ... | sh`
- **Fork Bomb**: `:(){{ :|:& }};:`

### 2. 需要确认的中风险操作
以下操作需要先调用 `ask_user_confirmation` 获取用户确认：
- 重启单个服务
- 停止容器或 Pod
- 修改配置文件
- 清理日志或临时文件
- 执行任何可能影响服务的操作

### 3. 安全的只读操作
以下操作可以安全执行（风险等级 low）：
- 查看日志: `cat`, `tail`, `head`, `grep`, `journalctl`
- 查看状态: `systemctl status`, `service status`, `docker ps`, `kubectl get`
- 查看资源: `df`, `du`, `free`, `top`, `ps`, `uptime`
- 网络诊断: `ping`, `traceroute`, `netstat`, `ss`, `nslookup`
- 查看配置: `cat /etc/...`, `docker inspect`

### 4. 数据源访问权限
- 默认数据源: `{settings.DEFAULT_DATA_SOURCE}`
- 可用数据源: `local`, `prometheus`, `elasticsearch`, `loki`, `jaeger`, `aliyun_monitor`
- 使用 `list_data_sources` 查看可用数据源
- 使用 `load_data_from_source` 从指定数据源加载数据

---

## ReAct 诊断工作流程

你必须严格遵循 ReAct (Reasoning + Acting) 模式进行诊断：

### 0. 规划阶段（必须首先执行）
在开始执行任何诊断命令之前，你必须：
1. 根据匹配的 skill 文件内容，制定诊断计划
2. 调用 `save_diagnosis_plan` 工具保存诊断计划
3. 然后按计划逐步执行诊断步骤

**诊断计划示例**：
```
plan_name: "mysql_deadlock_diagnosis"
check_type: "mysql_deadlock"
commands: [
  "SHOW ENGINE INNODB STATUS",
  "SELECT * FROM information_schema.innodb_trx",
  "SHOW VARIABLES LIKE 'transaction_isolation'"
]
reasoning: "根据 mysql_deadlock_skill，先获取死锁日志，再检查当前事务状态"
```

### 1. 思考 (Thought)
在每次行动前，你必须先思考：
- 当前已有哪些信息？
- 还需要哪些信息？
- 下一步应该做什么？
- 为什么选择这个工具？
- **这个操作是否安全？**

### 2. 行动 (Action)
根据思考结果，选择合适的工具执行：
- 仔细阅读工具的参数说明
- 根据实际情况填写参数
- 确保参数类型正确
- **确认操作在安全范围内**

### 3. 观察 (Observation)
分析工具返回的结果：
- 结果是否成功？
- 结果包含哪些关键信息？
- 是否需要进一步行动？
- **是否有安全警告？**

### 4. 决策
根据观察结果做出决策：
- 继续下一步？
- 回退重试？
- 结束诊断？

---

## Skill 执行指南

### 对于 debug_skill (服务器故障排查):
1. 先执行低风险只读命令收集信息
2. 分析命令输出，定位问题
3. 调用 submit_diagnosis_result 提交结果

### 对于 gnn_rca_skill (GNN 根因分析):
1. **数据收集阶段**: 调用 `list_data_sources` 查看可用数据源，然后调用 `load_data_from_source` 加载数据
   - 观察: 数据源是否可用、数据量、错误数量
   - 决策: 若数据源不可用，尝试其他数据源

2. **异常检测阶段**: 调用 `load_metrics_and_detect_anomalies`
   - 观察: 异常服务列表、异常分数
   - 决策: 若无异常，降低阈值或提示无故障

3. **图构建阶段**: 调用 `build_service_graph`
   - 观察: 节点数、边数
   - 决策: 若图构建失败，使用默认拓扑

4. **GNN 分析阶段**: 调用 `gnn_root_cause_analysis`
   - 观察: 根因服务、概率、传播路径
   - 决策: 若置信度低，结合其他方法验证

5. **报告生成阶段**: 调用 `generate_rca_report`
   - 观察: 报告是否生成成功

6. **结果提交阶段**: 调用 `submit_diagnosis_result`
   - 这是必须的终止步骤

### 对于 login_skill (SSH 连接):
1. 检查网络连通性
2. 尝试 SSH 连接
3. 若失败，使用替代方案

---

## SSH 连接参数说明

当用户查询中包含 SSH 用户名时（如"用户名是jaci"、"登录ID是xxx"），意图识别结果中会有 `ssh_users` 字段。

**重要**: 在调用 `execute_command` 工具时，如果需要远程连接服务器：

### 情况 1: 用户查询中包含用户名
检查 `intent_data.entities.ssh_users` 是否有值：
- 如果有，使用 `ssh_user` 参数传递用户名
- 示例: `execute_command(command="systemctl status xxx", target_host="47.114.77.62", ssh_user="jaci")`

### 情况 2: 用户查询中不包含用户名
**绝对禁止猜测用户名（如 root, admin 等）！**

正确做法：
1. 使用 `ask_user_confirmation` 工具询问用户
2. 询问内容示例：
   ```json
   {{
     "message": "需要连接服务器 47.114.77.62 进行诊断，请提供 SSH 登录用户名：",
     "options": ["root", "admin", "其他用户名"]
   }}
   ```
3. 获取用户确认后，再调用 `execute_command`

---

## 重要规则

1. **安全第一**: 任何操作前先考虑安全性
2. **工具调用规范**:
   - 每次只调用一个工具
   - 等待工具返回结果后再决定下一步
   - 不要假设工具执行结果

3. **风险控制**:
   - 只读操作风险等级为 low
   - 可能影响服务的操作风险等级为 high，需先调用 ask_user_confirmation

4. **终止条件**:
   - 必须调用 submit_diagnosis_result 工具提交诊断结果
   - 这是唯一正确的结束方式
   - 不要只在回复文本中输出结论

5. **错误处理**:
   - 若工具执行失败，分析错误原因
   - 尝试替代方案或回退到其他 skill
   - 若无法继续，提交结果说明需要人工介入

---

## 何时结束诊断

满足以下任一条件时，应调用 submit_diagnosis_result 结束诊断：
1. 已定位到明确的根本原因
2. 已排除所有可能性，确定无异常
3. 需要用户确认才能继续（高风险操作）
4. 已收集足够信息但无法确定根因（需要人工介入）
5. GNN 分析完成并生成报告
"""
        
        user_message = f"""## 用户查询
{user_query}

## 意图识别结果
{json.dumps(intent_data, ensure_ascii=False, indent=2)}

请根据 skill 文件中的方法，开始诊断流程。"""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    
    def _get_skills_content(self, skill_names: List[str]) -> str:
        """
        获取相关 skill 文件的内容
        """
        contents = []
        for name in skill_names:
            content = self.skill_manager.get_skill(name)
            if content:
                contents.append(f"### {name}\n\n{content}")
        return "\n\n---\n\n".join(contents)
    
    def _parse_final_result(self, content: str) -> Dict[str, Any]:
        """
        解析最终结果
        """
        if "## 最终诊断结果" not in content:
            return {"is_final": False}
        
        result = {"is_final": True, "raw": content}
        
        patterns = {
            "problem_type": r"\*\*问题类型\*\*:\s*(.+)",
            "root_cause": r"\*\*根本原因\*\*:\s*(.+)",
            "impact": r"\*\*影响范围\*\*:\s*(.+)",
            "recommendation": r"\*\*建议操作\*\*:\s*(.+)",
            "risk_level": r"\*\*风险等级\*\*:\s*(\w+)"
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                result[key] = match.group(1).strip()
        
        return result
    
    async def generate_diagnosis_plan(
        self,
        user_query: str,
        intent_data: Dict
    ) -> Dict[str, Any]:
        """
        生成诊断计划（兼容旧接口）
        """
        relevant_skills = self.skill_manager.search_relevant_skills(user_query, intent_data)
        skills_content = self._get_skills_content(relevant_skills)
        
        prompt = f"""你是一个运维诊断专家。根据用户问题和 skill 文件，生成诊断计划。

## 用户查询
{user_query}

## 意图识别结果
{json.dumps(intent_data, ensure_ascii=False, indent=2)}

## Skill 文件内容
{skills_content}

## 输出格式 (JSON)
{{
    "check_type": "disk|network|memory|general",
    "reasoning": "选择这些检查步骤的原因",
    "commands": ["df -h", "du -h --max-depth=1 /"],
    "expected_findings": ["磁盘使用率是否超过阈值"],
    "next_steps_if_anomaly_found": "如果发现异常的下一步操作"
}}

只返回 JSON，不要其他说明文字。"""
        
        response = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        content = response.choices[0].message.content.strip()
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {
                "check_type": "general",
                "reasoning": "无法解析检查计划，使用通用检查",
                "commands": ["uptime", "free -h", "df -h"]
            }
    
    async def orchestrate(
        self,
        user_query: str,
        intent_data: Dict,
        knowledge_context: Dict,
        observability_report: Dict
    ) -> Dict[str, Any]:
        """
        整合信息并决策（兼容旧接口）
        """
        prompt = self._build_orchestration_prompt(
            user_query, intent_data, knowledge_context, observability_report
        )
        
        response = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        content = response.choices[0].message.content.strip()
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {
                "root_cause_summary": "需要人工分析",
                "decision": "MANUAL_INTERVENTION",
                "action_plan": "请人工介入排查",
                "risk_level": "HIGH"
            }
    
    def _build_orchestration_prompt(
        self,
        user_query: str,
        intent_data: Dict,
        knowledge_context: Dict,
        observability_report: Dict
    ) -> str:
        server_status_section = ""
        if observability_report.get("server_status_check"):
            status_check = observability_report["server_status_check"]
            server_status_section = f"""
## 服务器状态检查结果
检查状态: {'成功' if status_check.get('success') else '失败'}
警告状态: {'已解除' if status_check.get('warning_cleared') else '存在异常'}
内存使用率: {status_check.get('memory_usage', 'N/A')}%
CPU 负载: {status_check.get('cpu_usage', 'N/A')}
磁盘使用率: {status_check.get('disk_usage', 'N/A')}%
发现的异常: {json.dumps(status_check.get('anomalies', []), ensure_ascii=False)}
"""
        
        return f"""你是一个运维指挥官。根据多源信息制定最终的故障治理方案。

## 用户原始查询
{user_query}

## 意图识别结果
{json.dumps(intent_data, ensure_ascii=False, indent=2)}
{server_status_section}
## 知识图谱与 RAG 信息
{json.dumps(knowledge_context, ensure_ascii=False, indent=2)[:1000]}

## 观测层分析报告
{json.dumps(observability_report, ensure_ascii=False, indent=2)[:1000]}

## 输出格式 (JSON)
{{
    "root_cause_summary": "根本原因描述",
    "decision": "EXECUTE_FIX|NEED_MORE_INFO|MANUAL_INTERVENTION|RESOLVED",
    "action_plan": "具体操作步骤",
    "risk_level": "LOW|MEDIUM|HIGH",
    "confidence": "HIGH|MEDIUM|LOW"
}}

只返回 JSON。"""
