from ipaddress import ip_address, ip_network
from typing import List, Optional

from fastapi import HTTPException, Request

from app.services.alert_security_config_manager import alert_security_config_manager


class IPAccessController:
    def _parse_whitelist(self) -> List[str]:
        config = alert_security_config_manager.get_effective_config()
        return [str(item).strip() for item in config.get("ipWhitelist", []) if str(item).strip()]

    def _extract_client_ip(self, request: Request) -> Optional[str]:
        config = alert_security_config_manager.get_effective_config()
        if bool(config.get("trustProxyHeaders")):
            forwarded_for = request.headers.get("x-forwarded-for", "").strip()
            if forwarded_for:
                return forwarded_for.split(",")[0].strip()
            real_ip = request.headers.get("x-real-ip", "").strip()
            if real_ip:
                return real_ip
        if request.client:
            return request.client.host
        return None

    def is_allowed(self, request: Request) -> bool:
        whitelist = self._parse_whitelist()
        if not whitelist:
            return True

        client_ip = self._extract_client_ip(request)
        if not client_ip:
            return False

        try:
            client_addr = ip_address(client_ip)
        except ValueError:
            return False

        for rule in whitelist:
            try:
                if "/" in rule:
                    if client_addr in ip_network(rule, strict=False):
                        return True
                elif client_addr == ip_address(rule):
                    return True
            except ValueError:
                continue
        return False

    def enforce_alert_webhook_whitelist(self, request: Request) -> None:
        if self.is_allowed(request):
            return
        raise HTTPException(status_code=403, detail="当前来源 IP 不在告警 webhook 白名单中")


ip_access_controller = IPAccessController()
