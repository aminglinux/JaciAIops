from app.services import runtime_graph_config_manager

from .jaeger_provider import JaegerTraceProvider


def get_trace_provider():
    runtime_config = runtime_graph_config_manager.get_effective_config()
    if runtime_config["traceBackend"] == "jaeger":
        return JaegerTraceProvider()
    raise ValueError(f"Unsupported TRACE_BACKEND: {runtime_config['traceBackend']}")
