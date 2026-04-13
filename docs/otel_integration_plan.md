# OpenTelemetry 一体化接入方案（方案 B）

## 一、总体目标

把当前项目升级成统一的 AIOps 分析平台：

1. 观测后端提供运行时事实
2. 知识图谱提供长期结构化知识
3. 智能助手 / 分析 Agent 消费两者，输出分析和建议

一句话概括：

- 用观测后端提供实时证据
- 用图谱提供依赖语义
- 用智能体做分析和问答

---

## 二、为什么选方案 B

方案 B 指：

- 不直接先接 OpenTelemetry SDK / Collector 进本平台
- 而是从已经存在的观测后端 API 读取数据

例如：

- Jaeger Query API
- Tempo Query API
- Prometheus HTTP API
- Loki Query API
- Elasticsearch Search API

### 优点

1. 更容易落地  
   当前项目已经具备后端 API、Agent、图谱、智能助手，只需要新增“读取外部观测后端”的客户端。

2. 对现网侵入小  
   不需要立刻修改所有业务服务的埋点或 Collector。

3. 更符合当前项目定位  
   项目更像“分析平台”，不是“采集平台”。

---

## 三、目标架构

建议做成四层：

### 1. 数据接入层

从现有后端读取：

- Jaeger / Tempo：trace
- Prometheus：metrics
- Loki / Elasticsearch：logs

### 2. 统一观测抽象层

把不同数据源统一成平台自己的模型：

- TraceSpan
- ServiceDependency
- RuntimeTopologySnapshot
- MetricAnomaly
- LogSignal

### 3. 图谱融合层

把运行时依赖和静态依赖写入/映射到 Neo4j：

- 静态图谱：手工录入 / CMDB
- 动态图谱：Trace 推断

### 4. 消费层

供这些模块使用：

- 智能助手
- 分析问题模式
- 知识图谱页面
- 根因分析 Agent

---

## 四、与现有项目的对应关系

### 已有代码

- `aiops-platform/backend/app/agents/observability.py`
- `aiops-platform/backend/app/agents/knowledge.py`
- `aiops-platform/backend/app/api/knowledge.py`
- `aiops-platform/backend/app/utils/data_source_manager.py`
- `knowledge_graph/`

### 建议新增目录

- `aiops-platform/backend/app/observability/`

建议文件：

- `base.py`
- `schemas.py`
- `trace_provider.py`
- `jaeger_provider.py`
- `tempo_provider.py`
- `prometheus_provider.py`
- `loki_provider.py`
- `graph_sync.py`

---

## 五、统一观测抽象设计

### 1. TraceSpan

```python
class TraceSpan:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    service_name: str
    operation_name: str
    start_time: datetime
    duration_ms: float
    status_code: str | None
    span_kind: str | None
    attributes: dict
```

### 2. ServiceDependency

```python
class ServiceDependency:
    source_service: str
    target_service: str
    dependency_type: str
    avg_latency_ms: float
    error_rate: float
    call_count: int
    last_seen: datetime
    source: str
```

### 3. RuntimeTopologySnapshot

```python
class RuntimeTopologySnapshot:
    service: str
    window_minutes: int
    upstream: list[ServiceDependency]
    downstream: list[ServiceDependency]
    external_dependencies: list[dict]
```

### 4. TraceAnomaly

```python
class TraceAnomaly:
    service: str
    trace_id: str
    slow_span: str
    duration_ms: float
    suspected_dependency: str | None
    anomaly_type: str
```

---

## 六、观测后端接入设计

## 6.1 Trace Provider 抽象

```python
class TraceProvider:
    async def get_service_dependencies(self, service: str, minutes: int = 15) -> list[ServiceDependency]:
        ...

    async def get_recent_trace_anomalies(self, service: str, minutes: int = 15) -> list[TraceAnomaly]:
        ...

    async def get_trace_detail(self, trace_id: str) -> dict:
        ...
```

实现类：

- `JaegerTraceProvider`
- `TempoTraceProvider`

---

## 6.2 Jaeger Provider

如果现网有 Jaeger，优先从这里接。

### 配置项建议

在 `app/core/config.py` 增加：

- `TRACE_BACKEND: str = "jaeger"`
- `JAEGER_QUERY_URL: str = "http://localhost:16686"`
- `TRACE_QUERY_TIMEOUT: int = 15`

### 第一阶段只做三类能力

1. 查某服务最近 15 分钟 trace
2. 找最慢 span
3. 根据 parent-child / peer.service 构造依赖关系

---

## 6.3 Tempo Provider

如果使用 Tempo，做同样抽象：

- 先实现 Jaeger
- 再实现 Tempo
- 由 `TRACE_BACKEND` 切换

---

## 6.4 Metrics Provider

建议抽象：

```python
class MetricsProvider:
    async def query_service_metrics(self, service: str, minutes: int = 15) -> dict:
        ...
```

当前项目已有：

- `app/utils/data_source_manager.py`

建议优先复用。

---

## 6.5 Logs Provider

第一阶段可低优先级，只做：

- 根据 service 查询最近错误日志摘要
- 根据 trace_id / request_id 查询关联日志

---

## 七、图谱融合设计

保留两类图谱：

### 1. 静态图谱

来源：

- 人工录入
- 导入文件
- CMDB
- 配置中心

特点：

- 稳定
- 带业务语义
- 有 owner / SOP / team / system 等属性

### 2. 动态图谱

来源：

- Trace 推断
- Metrics 统计
- Runtime 发现

特点：

- 反映真实运行关系
- 有时间性
- 有统计值

---

## 7.1 建议节点

- `Service`
- `Database`
- `Cache`
- `MQ`
- `Host`
- `Pod`
- `Namespace`
- `Cluster`
- `Team`
- `SOP`
- `Incident`

## 7.2 建议关系

### 静态关系

- `DEPENDS_ON`
- `RUNS_ON`
- `OWNED_BY`
- `HAS_SOP`

### 动态关系

- `CALLS`
- `USES_DB`
- `USES_CACHE`
- `PUBLISHES_TO`
- `CONSUMES_FROM`

## 7.3 动态关系属性建议

例如 `CALLS` 边：

- `source = "otel"`
- `avg_latency_ms`
- `p95_latency_ms`
- `error_rate`
- `call_count`
- `last_seen`
- `window_minutes`
- `environment`

---

## 7.4 图谱写入策略

### 方式 1：按需计算

用户发起分析时：

- 临时拉最近 trace
- 临时组装运行时依赖
- 不一定立即写入图谱

### 方式 2：定时同步

后台每 5 分钟同步一次：

- 最近 15 分钟依赖边
- 更新到 Neo4j

### 建议

- 第一阶段先做按需计算
- 第二阶段再做定时同步

---

## 八、智能助手与 Agent 消费方式

## 8.1 智能助手

用户问：

- `payment-service 最近为什么慢？`
- `order-service 最近在依赖什么？`

系统可同时结合：

- 图谱静态依赖
- Trace 动态依赖
- RAG / SOP / incident

---

## 8.2 分析问题模式

流程建议：

1. `IntentParseAgent` 识别 service / symptom
2. `ObservabilityAgent` 查 metrics / logs / trace 异常
3. `KnowledgeAgent` 查静态图谱 + 动态依赖 + SOP / incident
4. `MasterAgent` 汇总根因

---

## 8.3 Knowledge Agent 扩展建议

增加：

- `_query_runtime_topology(service)`
- `_query_recent_trace_anomalies(service)`
- `_compare_static_vs_runtime_dependencies(service)`

---

## 8.4 Observability Agent 扩展建议

增加：

- Trace 热点 span 识别
- 下游慢依赖识别
- 错误率最高调用边识别

---

## 九、后端落地设计

## 9.1 配置项

在 `aiops-platform/backend/app/core/config.py` 新增：

- `TRACE_BACKEND: str = "jaeger"`
- `JAEGER_QUERY_URL: str = "http://localhost:16686"`
- `TEMPO_QUERY_URL: str = ""`
- `TRACE_QUERY_TIMEOUT: int = 15`
- `TRACE_DEFAULT_LOOKBACK_MINUTES: int = 15`
- `GRAPH_SYNC_ENABLED: bool = False`
- `GRAPH_SYNC_INTERVAL_SECONDS: int = 300`

---

## 9.2 新增目录

建议：

- `aiops-platform/backend/app/observability/`

### `schemas.py`

定义：

- `TraceSpan`
- `ServiceDependency`
- `RuntimeTopologySnapshot`
- `TraceAnomaly`

### `base.py`

定义抽象接口：

- `TraceProvider`
- `MetricsProvider`
- `LogsProvider`

### `jaeger_provider.py`

实现：

- `JaegerTraceProvider`

### `trace_provider.py`

根据配置选择：

- `get_trace_provider()`

### `graph_sync.py`

负责：

- 把动态依赖写入 Neo4j

---

## 9.3 新增 API

建议新增：

- `GET /api/observability/traces/dependencies?service=...`
- `GET /api/observability/traces/anomalies?service=...`
- `POST /api/knowledge-graph/sync/runtime`
- `GET /api/knowledge-graph/runtime-topology?service=...`

---

## 9.4 Neo4j 写入逻辑

建议增加：

- `aiops-platform/backend/app/services/runtime_graph_service.py`

职责：

- 查询节点是否存在
- 不存在则补建
- 更新 `CALLS` / `USES_DB` / `USES_CACHE` 等边
- 写入动态属性

---

## 十、前端落地设计

## 10.1 知识图谱页面增强

提供三种视图切换：

- 静态
- 动态
- 融合

动态视图展示：

- 最近活跃依赖
- 平均延迟
- 错误率
- 最近调用时间

---

## 10.2 分析页面增强

在诊断或智能助手中增加：

- 最近调用链
- top slow spans
- top error edges
- 相关图谱节点

---

## 十一、实施阶段

## Phase 1：接 Trace 查询

目标：

- 从 Jaeger 拉 trace
- 查询某服务最近依赖
- 查询慢 span / 错误 span

产出：

- `JaegerTraceProvider`
- `ServiceDependency`
- `TraceAnomaly`

## Phase 2：接入智能助手

目标：

- 通用问答可回答最近调用依赖
- 分析问题模式可引用 trace 证据

## Phase 3：写入 Neo4j 动态图谱

目标：

- 把 OTEL 推断关系写入图谱
- 页面展示动态依赖

## Phase 4：后台同步任务

目标：

- 定时更新动态图谱
- 边上维护调用统计

---

## 十二、最小 MVP 建议

第一版只做：

### 后端

- Jaeger 接入
- `get_service_dependencies(service)`
- `get_recent_trace_anomalies(service)`
- 智能助手里消费这两个结果

### 前端

- 智能助手展示：
  - 最近调用依赖
  - 最近慢依赖

图谱页可以后续再做。

---

## 十三、推荐开发顺序

1. 先做 Jaeger Provider
2. 先接智能助手“通用问答 / 分析问题”
3. 再做 Neo4j runtime graph 写入
4. 最后做图谱页面融合展示

---

## 十四、最终建议

方案 B 的最佳落地方式不是做一个独立的 OTEL 模块，而是：

- 让 Jaeger / Tempo 提供实时证据
- 让 Neo4j 提供结构化长期知识
- 让智能助手 / 多 Agent 消费两者

一句话总结：

- Jaeger / Tempo 给证据
- Neo4j 给结构
- Agent 给结论

