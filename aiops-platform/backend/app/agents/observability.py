import json
import re
import subprocess
import os
from typing import Optional, Dict, Any, List
from openai import OpenAI
from app.core.config import settings
from ..utils.logger import get_logger

logger = get_logger("observability")

class ObservabilityAnalystAgent:
    """
    Observability & Analyst Agent (感知层)
    核心职责：分析原始数据，产出"有观点"的分析报告，而非罗列数据。
    支持通过 Ansible 连接节点并查询状态和日志。
    """
    
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        )
        self.ansible_inventory_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "ansible", "inventory.ini"
        )
        self.skills_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "login_skill.md"
        )
    
    async def analyze_with_skills(
        self, 
        service: str, 
        entities: Dict[str, Any],
        knowledge_context: Dict[str, Any]
    ) -> dict:
        servers = entities.get("servers", [])
        symptoms = entities.get("symptoms", [])
        
        if not servers:
            servers = self._get_servers_from_knowledge(knowledge_context)
        
        all_metrics = {}
        all_logs = {}
        all_analysis = []
        
        for server_info in servers:
            server_ip = server_info.get("normalized") if isinstance(server_info, dict) else server_info
            if not server_ip:
                continue
            
            metrics = await self._collect_server_metrics(server_ip)
            logs = await self._collect_server_logs(server_ip, symptoms)
            
            all_metrics[server_ip] = metrics
            all_logs[server_ip] = logs
            
            analysis = await self._analyze_server_data(
                server_ip, metrics, logs, symptoms, knowledge_context
            )
            all_analysis.append(analysis)
        
        return {
            "service": service,
            "servers_checked": list(all_metrics.keys()),
            "metrics_data": all_metrics,
            "logs_data": all_logs,
            "analysis_reports": all_analysis,
            "summary": await self._generate_summary(all_analysis)
        }
    
    def _get_servers_from_knowledge(self, knowledge_context: Dict) -> List[str]:
        topology = knowledge_context.get("topology_info", {})
        servers = []
        
        if "runs_on" in topology:
            servers.extend([s.get("name") for s in topology["runs_on"] if s.get("name")])
        
        if "dependencies" in topology:
            for dep in topology.get("dependencies", []):
                if dep.get("type") in ["Server", "Infra"]:
                    servers.append(dep.get("name"))
        
        return servers
    
    async def _collect_server_metrics(self, server_ip: str) -> Dict:
        playbook_content = f"""
- name: Collect Server Metrics
  hosts: all
  gather_facts: no
  tasks:
    - name: Check Uptime
      ansible.builtin.command: uptime
      changed_when: false
      register: uptime_output
    
    - name: Check Memory
      ansible.builtin.command: free -m
      changed_when: false
      register: memory_output
    
    - name: Check Disk
      ansible.builtin.command: df -h
      changed_when: false
      register: disk_output
    
    - name: Check CPU Processes
      ansible.builtin.shell: ps aux --sort=-%cpu | head -n 10
      changed_when: false
      register: cpu_output
      ignore_errors: true
    
    - name: Check Network Connections
      ansible.builtin.shell: netstat -tulnp | grep LISTEN
      changed_when: false
      register: network_output
      ignore_errors: true
"""
        
        try:
            result = await self._run_ansible_playbook(playbook_content, server_ip)
            return self._parse_metrics_result(result)
        except Exception as e:
            logger.warning(f"[MOCK DATA] Ansible 收集 {server_ip} 指标失败: {str(e)}，fallback 到模拟数据")
            return {
                "server": server_ip,
                "error": str(e),
                **self._generate_mock_metrics(server_ip)
            }
    
    async def _collect_server_logs(self, server_ip: str, symptoms: List) -> Dict:
        symptom_keywords = [s.get("value", "") if isinstance(s, dict) else s for s in symptoms]
        grep_pattern = "|".join(symptom_keywords) if symptom_keywords else "error|ERROR|fail|FAIL"
        
        playbook_content = f"""
- name: Collect Server Logs
  hosts: all
  gather_facts: no
  tasks:
    - name: Check System Logs
      ansible.builtin.shell: journalctl -u *service* --no-pager -n 50 2>/dev/null || tail -n 50 /var/log/syslog 2>/dev/null || echo "No logs found"
      changed_when: false
      register: system_logs
      ignore_errors: true
    
    - name: Check for OOM Events
      ansible.builtin.shell: dmesg | grep -i 'out of memory' | tail -n 10
      changed_when: false
      register: oom_logs
      ignore_errors: true
    
    - name: Check for Error Patterns
      ansible.builtin.shell: grep -rE '{grep_pattern}' /var/log/*.log 2>/dev/null | tail -n 20 || echo "No matching patterns"
      changed_when: false
      register: error_logs
      ignore_errors: true
"""
        
        try:
            result = await self._run_ansible_playbook(playbook_content, server_ip)
            return self._parse_logs_result(result)
        except Exception as e:
            logger.warning(f"[MOCK DATA] Ansible 收集 {server_ip} 日志失败: {str(e)}，fallback 到模拟数据")
            return {
                "server": server_ip,
                "error": str(e),
                **self._generate_mock_logs(server_ip)
            }
    
    async def _run_ansible_playbook(self, playbook_content: str, target_host: str) -> Dict:
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(playbook_content)
            playbook_path = f.name
        
        try:
            cmd = [
                "ansible-playbook",
                "-i", f"{target_host},",
                "-u", settings.SSH_USER or "root",
                "--private-key", settings.SSH_KEY_PATH,
                playbook_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        finally:
            os.unlink(playbook_path)
    
    def _parse_metrics_result(self, result: Dict) -> Dict:
        stdout = result.get("stdout", "")
        
        metrics = {
            "uptime": "",
            "cpu_usage": "unknown",
            "memory_usage": "unknown",
            "disk_usage": "unknown",
            "top_processes": [],
            "network_ports": []
        }
        
        if "uptime" in stdout.lower():
            lines = stdout.split("\n")
            for line in lines:
                if "load average" in line.lower():
                    metrics["uptime"] = line.strip()
        
        return metrics
    
    def _parse_logs_result(self, result: Dict) -> Dict:
        stdout = result.get("stdout", "")
        
        return {
            "system_logs": stdout[:2000] if stdout else "",
            "oom_events": [],
            "error_patterns": []
        }
    
    async def _analyze_server_data(
        self,
        server_ip: str,
        metrics: Dict,
        logs: Dict,
        symptoms: List,
        knowledge_context: Dict
    ) -> dict:
        prompt = f"""你是一个资深 SRE 分析师。请分析以下服务器数据并给出诊断结论。

服务器: {server_ip}
故障现象: {json.dumps(symptoms, ensure_ascii=False)}
知识背景: {json.dumps(knowledge_context.get("knowledge_report", ""), ensure_ascii=False)[:500]}

指标数据:
{json.dumps(metrics, ensure_ascii=False, indent=2)}

日志数据:
{json.dumps(logs, ensure_ascii=False, indent=2)[:1000]}

请分析:
1. 黄金信号分析：CPU、内存、磁盘、网络是否异常
2. 根因假设：根据指标和日志推断可能原因
3. 建议操作：下一步排查或修复建议

Output Format (JSON):
{{
    "server": "{server_ip}",
    "health_status": "CRITICAL|WARNING|NORMAL",
    "anomalies": ["异常1", "异常2"],
    "root_cause_hypothesis": "根因假设",
    "recommendations": ["建议1", "建议2"],
    "confidence": "HIGH|MEDIUM|LOW"
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            content = response.choices[0].message.content.strip()
            content = re.sub(r'^```json\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
            return json.loads(content)
        except Exception as e:
            return {
                "server": server_ip,
                "health_status": "UNKNOWN",
                "anomalies": [],
                "root_cause_hypothesis": f"分析失败: {str(e)}",
                "recommendations": ["建议人工介入排查"],
                "confidence": "LOW"
            }
    
    async def _generate_summary(self, all_analysis: List[Dict]) -> str:
        if not all_analysis:
            return "未收集到分析数据"
        
        critical_servers = [a for a in all_analysis if a.get("health_status") == "CRITICAL"]
        warning_servers = [a for a in all_analysis if a.get("health_status") == "WARNING"]
        
        summary_parts = []
        if critical_servers:
            summary_parts.append(f"发现 {len(critical_servers)} 个严重问题服务器")
        if warning_servers:
            summary_parts.append(f"发现 {len(warning_servers)} 个警告状态服务器")
        
        all_hypotheses = [a.get("root_cause_hypothesis") for a in all_analysis if a.get("root_cause_hypothesis")]
        
        return " | ".join(summary_parts) + f"。主要怀疑原因: {all_hypotheses[0] if all_hypotheses else '未知'}"
    
    def _build_prompt(self, service: str, metrics_data: Dict, logs_data: Dict, trace_data: Dict) -> str:
        return f"""你是一个资深 SRE 分析师。你拥有访问阿里云监控、日志 (SLS) 和链路追踪 (ARMS) 的权限。

你已获取以下实时数据（由系统注入）：

Metrics Data: {json.dumps(metrics_data, ensure_ascii=False, indent=2)}
Log Samples: {json.dumps(logs_data, ensure_ascii=False, indent=2)}
Trace Info: {json.dumps(trace_data, ensure_ascii=False, indent=2)}

Task
针对服务 {service} 的异常，完成以下分析：

黄金信号分析：判断 Latency, Traffic, Errors, Saturation (CPU/Mem) 是否存在异常波动。
时间相关性：确认指标异常时间点与错误日志爆发时间点是否吻合。
根因假设：
如果 CPU/Mem 高：怀疑代码死循环或内存泄漏。
如果 Error Log 显现 "Connection refused"：怀疑下游依赖或连接池耗尽。
如果下游服务延迟高：标记为下游传递问题。

Output Format
请用简洁的技术语言总结，严禁直接粘贴原始日志。示例输出：
"【分析结论】order-service 在 10:05 分 P99 延迟从 200ms 飙升至 2s。【异常特征】同时伴随大量 'Connection Timeout' 日志，错误集中在支付接口。【初步定位】下游 payment-service 响应正常，排除下游因素；本地连接池活跃数已满，怀疑是连接池配置不足或慢查询阻塞。" """

    async def analyze(self, service: str, metrics_data: Dict = None, logs_data: Dict = None, trace_data: Dict = None) -> dict:
        used_mock = False
        if metrics_data is None:
            metrics_data = self._generate_mock_metrics(service)
            used_mock = True
        if logs_data is None:
            logs_data = self._generate_mock_logs(service)
            used_mock = True
        if trace_data is None:
            trace_data = self._generate_mock_traces(service)
            used_mock = True
        
        if used_mock:
            logger.warning(f"[MOCK DATA] 服务 '{service}' 的分析使用了模拟数据（metrics/logs/traces），诊断结论可能不准确")
        
        prompt = self._build_prompt(service, metrics_data, logs_data, trace_data)
        
        response = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        content = response.choices[0].message.content.strip()
        
        return {
            "service": service,
            "analysis_report": content,
            "_data_source": {
                "metrics": metrics_data.get("source", "unknown"),
                "logs": logs_data.get("source", "unknown"),
                "traces": trace_data.get("source", "unknown"),
                "has_mock_data": any([
                    metrics_data.get("_is_mock", False),
                    logs_data.get("_is_mock", False),
                    trace_data.get("_is_mock", False),
                ])
            },
            "metrics_summary": {
                "latency_p99": metrics_data.get("latency_p99"),
                "error_rate": metrics_data.get("error_rate"),
                "cpu_usage": metrics_data.get("cpu_usage"),
                "memory_usage": metrics_data.get("memory_usage")
            },
            "log_patterns": logs_data.get("patterns", []),
            "trace_anomalies": trace_data.get("anomalies", [])
        }
    
    def _generate_mock_metrics(self, service: str) -> Dict:
        logger.warning(f"[MOCK DATA] 监控数据源不可用，为服务 '{service}' 返回模拟指标。此数据仅供参考，不应用于生产诊断决策。")
        return {
            "service": service,
            "latency_p99": "2.5s",
            "latency_p50": "200ms",
            "error_rate": "5.2%",
            "cpu_usage": "85%",
            "memory_usage": "72%",
            "traffic": "1200 req/s",
            "active_connections": 450,
            "max_connections": 500,
            "timestamp": "2026-03-23T10:05:00Z",
            "_is_mock": True,
            "source": "mock_data",
            "disclaimer": "⚠️ 此为模拟数据，监控数据源（Prometheus/Elasticsearch）不可用。"
        }
    
    def _generate_mock_logs(self, service: str) -> Dict:
        logger.warning(f"[MOCK DATA] 日志数据源不可用，为服务 '{service}' 返回模拟日志。此数据仅供参考，不应用于生产诊断决策。")
        return {
            "service": service,
            "total_errors": 156,
            "patterns": [
                "Connection Timeout to payment-service",
                "Pool exhausted exception",
                "Slow query detected (>5s)"
            ],
            "samples": [
                {"timestamp": "2026-03-23T10:05:12Z", "level": "ERROR", "message": "Connection timeout after 30000ms"},
                {"timestamp": "2026-03-23T10:05:15Z", "level": "ERROR", "message": "HikariPool-1 - Connection is not available"}
            ],
            "_is_mock": True,
            "source": "mock_data",
            "disclaimer": "⚠️ 此为模拟数据，日志数据源（Elasticsearch/Loki）不可用。"
        }
    
    def _generate_mock_traces(self, service: str) -> Dict:
        logger.warning(f"[MOCK DATA] 链路追踪数据源不可用，为服务 '{service}' 返回模拟链路数据。此数据仅供参考，不应用于生产诊断决策。")
        return {
            "service": service,
            "total_spans": 5000,
            "error_spans": 156,
            "anomalies": [
                {"span": "db.query", "duration": "5.2s", "anomaly": "slow_query"},
                {"span": "http.call", "duration": "3.1s", "anomaly": "timeout"}
            ],
            "_is_mock": True,
            "source": "mock_data",
            "disclaimer": "⚠️ 此为模拟数据，链路追踪数据源（Jaeger）不可用。"
        }
