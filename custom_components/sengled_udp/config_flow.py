import voluptuous as vol
from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
import socket
import json
import asyncio
import time
import re
from homeassistant.helpers import selector

DOMAIN = "sengled_udp"


class SengledConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sengled UDP."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["discover", "manual"],
        )

    async def async_step_manual(self, user_input=None):
        """Manually enter one or more bulb IPs."""
        return await self._async_hosts_form(step_id="manual", user_input=user_input)

    async def async_step_discover(self, user_input=None):
        """Discover bulbs on the local network (best-effort)."""
        if user_input is None:
            discovered = await self._discover_hosts()
            if not discovered:
                # Fall back to manual-style input, but show a useful error.
                return await self._async_hosts_form(
                    step_id="discover",
                    user_input=None,
                    default_hosts="",
                    show_no_devices_error=True,
                )

            options, host_types = await self._build_discovery_options(discovered)
            self._discovered_host_types = host_types

            data_schema = vol.Schema(
                {
                    vol.Required(
                        "hosts", default=discovered
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                    vol.Optional("name_prefix", default=""): cv.string,
                }
            )

            return self.async_show_form(
                step_id="discover",
                data_schema=data_schema,
                errors={},
            )

        try:
            hosts = self._parse_hosts(user_input["hosts"])
            if not hosts:
                raise ValueError("No hosts selected")

            for host in hosts:
                await self._test_connection(host)

            host_types = getattr(self, "_discovered_host_types", {}) or {}
            return self.async_create_entry(
                title=f"Sengled Bulbs ({len(hosts)})",
                data={
                    "hosts": hosts,
                    "name_prefix": user_input.get("name_prefix") or None,
                    "host_types": {h: host_types.get(h) for h in hosts},
                },
            )
        except Exception:
            errors = {"base": "cannot_connect"}
            # Re-show the discovery form with an error (use plain string input fallback)
            return await self._async_hosts_form(
                step_id="discover",
                user_input=None,
                default_hosts="",
                show_no_devices_error=False,
            )

    async def _async_hosts_form(
        self,
        step_id: str,
        user_input=None,
        default_hosts: str = "",
        show_no_devices_error: bool = False,
    ):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                hosts = self._parse_hosts(user_input["hosts"])
                if not hosts:
                    errors["base"] = "no_devices_found"
                else:
                    for host in hosts:
                        await self._test_connection(host)
                    return self.async_create_entry(
                        title=f"Sengled Bulbs ({len(hosts)})",
                        data={
                            "hosts": hosts,
                            "name_prefix": user_input.get("name_prefix"),
                        },
                    )
            except Exception:
                errors["base"] = "cannot_connect"

        if show_no_devices_error and "base" not in errors:
            errors["base"] = "no_devices_found"

        data_schema = vol.Schema(
            {
                vol.Required("hosts", default=default_hosts): cv.string,
                vol.Optional("name_prefix", default=""): cv.string,
            }
        )

        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    def _parse_hosts(hosts) -> list[str]:
        """Parse comma/whitespace/newline separated host list."""
        if isinstance(hosts, list):
            cleaned = [str(h).strip() for h in hosts if str(h).strip()]
            seen: set[str] = set()
            out: list[str] = []
            for h in cleaned:
                if h not in seen:
                    seen.add(h)
                    out.append(h)
            return out

        # Accept: "192.168.1.10, 192.168.1.11" or one per line, etc.
        raw = (
            hosts.replace("\r\n", "\n")
            .replace("\r", "\n")
            .replace(",", "\n")
            .replace(" ", "\n")
            .split("\n")
        )
        cleaned = [h.strip() for h in raw if h.strip()]
        # De-dupe while preserving order
        seen: set[str] = set()
        out: list[str] = []
        for h in cleaned:
            if h not in seen:
                seen.add(h)
                out.append(h)
        return out

    async def _build_discovery_options(
        self, hosts: list[str]
    ) -> tuple[list[dict], dict[str, str]]:
        """Return (selector options, host_types mapping)."""

        def extract_model(resp: dict) -> str:
            # Prefer explicit model field if present
            model = resp.get("MN")
            if model:
                return str(model)
            # Fallback: parse from version string, e.g. "..._W21-N13_SYSTEM_..."
            version = resp.get("version")
            if isinstance(version, str):
                m = re.search(r"_([A-Z]\d{2}-[A-Z]\d{2})_", version)
                if m:
                    return m.group(1)
            return ""

        async def probe(host: str) -> tuple[str, str]:
            # Default: unknown assumed RGB-capable
            try:
                resp = await self._send_udp(host, "search_devices", {})
                if resp and isinstance(resp, dict) and resp.get("ret") == 0:
                    # White bulbs typically only report W, RGB bulbs report R/G/B/W
                    is_rgb = all(k in resp for k in ("R", "G", "B"))
                    typ = "rgb" if is_rgb else "white"
                    model = extract_model(resp)
                    return typ, model
            except Exception:
                pass
            return "unknown", ""

        host_types: dict[str, str] = {}
        options: list[dict] = []

        for host in hosts:
            typ, model = await probe(host)
            host_types[host] = typ
            label_bits = [host]
            if model:
                label_bits.append(model)
            if typ in ("rgb", "white"):
                label_bits.append("RGB" if typ == "rgb" else "White")
            label = " — ".join(label_bits)
            options.append({"value": host, "label": label})

        return options, host_types

    async def _send_udp(self, host: str, func: str, param: dict) -> dict | None:
        """Send a UDP command and return parsed result (or None)."""

        def send_udp():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
            try:
                msg = json.dumps({"func": func, "param": param})
                sock.sendto(msg.encode(), (host, 9080))
                resp, _ = sock.recvfrom(2048)
                try:
                    payload = json.loads(resp.decode(errors="ignore"))
                except Exception:
                    return None
                # Most replies are {"func":..., "result": {...}}
                if isinstance(payload, dict) and "result" in payload and isinstance(
                    payload["result"], dict
                ):
                    return payload["result"]
                return payload
            finally:
                sock.close()

        return await asyncio.get_event_loop().run_in_executor(None, send_udp)

    async def _discover_hosts(self) -> list[str]:
        """Best-effort LAN discovery via UDP broadcast.

        This will only find bulbs on the same broadcast domain (same LAN/VLAN).
        """

        def discover_udp() -> list[str]:
            def infer_subnet_broadcast() -> str | None:
                """Infer a likely /24 broadcast address from the host's primary IPv4."""
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    try:
                        # Doesn't need to be reachable; used to pick the right interface
                        s.connect(("8.8.8.8", 80))
                        ip = s.getsockname()[0]
                    finally:
                        s.close()
                    parts = ip.split(".")
                    if len(parts) == 4:
                        return ".".join(parts[:3] + ["255"])
                except Exception:
                    return None
                return None

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(0.3)
            found: list[str] = []
            seen: set[str] = set()
            try:
                test_command = json.dumps({"func": "search_devices", "param": {}})
                targets: list[str] = ["255.255.255.255"]
                subnet_bcast = infer_subnet_broadcast()
                if subnet_bcast and subnet_bcast not in targets:
                    targets.append(subnet_bcast)

                # Some environments don't deliver 255.255.255.255 reliably; try both.
                for _ in range(2):
                    for addr in targets:
                        try:
                            sock.sendto(test_command.encode(), (addr, 9080))
                        except Exception:
                            continue

                # Collect responses for a short window
                end = time.time() + 2.0
                while time.time() < end:
                    try:
                        data, addr = sock.recvfrom(2048)
                    except socket.timeout:
                        continue
                    try:
                        payload = json.loads(data.decode(errors="ignore"))
                    except Exception:
                        continue

                    host = None
                    if isinstance(payload, dict):
                        result = payload.get("result") or {}
                        if isinstance(result, dict) and result.get("ret") == 0:
                            host = result.get("ip") or addr[0]
                    if host and host not in seen:
                        seen.add(host)
                        found.append(host)
            finally:
                sock.close()
            return found

        return await asyncio.get_event_loop().run_in_executor(None, discover_udp)

    async def _test_connection(self, host: str):
        """Test if we can connect to the bulb."""

        def test_udp():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3)
            try:
                # Send a test command
                test_command = json.dumps({"func": "search_devices", "param": {}})
                sock.sendto(test_command.encode(), (host, 9080))
                # Try to receive response (though we don't use it for state)
                sock.recvfrom(1024)
            finally:
                sock.close()

        await asyncio.get_event_loop().run_in_executor(None, test_udp)
