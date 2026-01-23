import asyncio
import json
import logging
import socket
import time
from typing import Any, Dict, Optional, Tuple

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sengled UDP light platform."""
    hosts = config_entry.data.get("hosts")
    if not hosts:
        hosts = [config_entry.data["host"]]

    name_prefix = config_entry.data.get("name_prefix") or config_entry.data.get("name")
    host_types: dict[str, str] = config_entry.data.get("host_types") or {}

    multiple = len(hosts) > 1
    entities: list[SengledLight] = []
    for host in hosts:
        typ = host_types.get(host)
        if name_prefix:
            if typ == "rgb":
                base = f"{name_prefix} (RGB)"
            elif typ == "white":
                base = f"{name_prefix} (White)"
            else:
                base = name_prefix
            name = f"{base} ({host})" if multiple else base
        else:
            if typ == "white":
                base = "Sengled Bulb (White)"
            elif typ == "rgb":
                base = "Sengled Bulb (RGB)"
            else:
                base = "Sengled Bulb"
            name = f"{base} ({host})" if multiple else base
        unique_id = f"{config_entry.entry_id}_{host}"
        entities.append(SengledLight(host, name, unique_id, host_type=typ))

    async_add_entities(entities)


class SengledLight(LightEntity):
    """Representation of a Sengled UDP Light."""

    _attr_force_update = True

    def __init__(
            self,
            host: str,
            name: str,
            unique_id: str,
            host_type: str | None = None,
    ) -> None:
        """Initialize the light."""
        self._host = host
        self._name = name
        self._unique_id = unique_id
        self._port = 9080

        # State will be fetched from device
        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_rgb_color = (255, 255, 255)
        self._attr_color_temp_kelvin = None

        # --- CACHES FOR STABILITY ---
        self._req_kelvin = None
        self._req_rgb = None
        # ----------------------------

        # Debounce timer to prevent reading stale state immediately after a command
        self._last_req_time = 0.0

        self._attr_color_mode = ColorMode.RGB
        self._available = True
        self._optimistic_power = False

        if host_type == "rgb":
            self._is_rgb = True
        elif host_type == "white":
            self._is_rgb = False
        else:
            self._is_rgb = None

        self._attr_name = name
        self._attr_unique_id = unique_id
        if self._is_rgb is False:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_rgb_color = None
            self._attr_color_temp_kelvin = None
            self._attr_assumed_state = True
            self._optimistic_power = True
        else:
            self._attr_color_mode = ColorMode.RGB
            self._attr_supported_color_modes = {ColorMode.RGB, ColorMode.COLOR_TEMP}

        self._attr_min_color_temp_kelvin = 2000
        self._attr_max_color_temp_kelvin = 6500

    @property
    def is_on(self) -> bool:
        return self._attr_is_on

    @property
    def brightness(self) -> int:
        return self._attr_brightness

    @property
    def rgb_color(self) -> Tuple[int, int, int]:
        return self._attr_rgb_color

    @property
    def color_mode(self) -> ColorMode:
        return self._attr_color_mode

    @property
    def color_temp_kelvin(self) -> Optional[int]:
        return self._attr_color_temp_kelvin

    async def async_update(self) -> None:
        """Fetch new state data for this light."""
        if (time.time() - self._last_req_time) < 2.0:
            return

        status = await self._get_device_status()
        if status:
            if self._is_rgb is None:
                self._detect_capabilities(status)
            brightness_info = await self._get_device_brightness()
            self._update_state_from_status(status, brightness_info)

    def _detect_capabilities(self, status: Dict[str, Any]) -> None:
        has_rgb = "R" in status and "G" in status and "B" in status
        self._is_rgb = has_rgb

        if has_rgb:
            self._attr_supported_color_modes = {ColorMode.RGB, ColorMode.COLOR_TEMP}
            self._attr_color_mode = ColorMode.RGB
            _LOGGER.debug("Detected RGB bulb: %s (%s)", self._attr_name, self._host)
        else:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_assumed_state = True
            self._optimistic_power = True
            _LOGGER.debug("Detected white-only bulb: %s (%s)", self._attr_name, self._host)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        brightness_percent = None
        device_temp = None
        rgb = None

        # Handle brightness
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            brightness_percent = int((brightness / 255) * 100)
            self._attr_brightness = brightness

        if self._is_rgb:
            # RGB bulbs: handle color temperature
            if ATTR_COLOR_TEMP_KELVIN in kwargs:
                color_temp_kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
                device_temp = self._kelvin_to_device_temp(color_temp_kelvin)
                
                # Update attributes
                self._attr_color_temp_kelvin = color_temp_kelvin
                self._attr_color_mode = ColorMode.COLOR_TEMP
                self._attr_rgb_color = None
                
                # Update caches
                self._req_kelvin = color_temp_kelvin
                self._req_rgb = None

            # Handle RGB color
            elif ATTR_RGB_COLOR in kwargs:
                rgb = kwargs[ATTR_RGB_COLOR]
                
                # Update attributes
                self._attr_rgb_color = rgb
                self._attr_color_mode = ColorMode.RGB
                self._attr_color_temp_kelvin = None

                # Update caches
                self._req_rgb = rgb
                self._req_kelvin = None

        # Update local state before sending commands
        self._attr_is_on = True
        self._last_req_time = time.time()

        if ATTR_BRIGHTNESS in kwargs and brightness_percent is not None:
            await self._send_command(
                "set_device_brightness", {"brightness": brightness_percent}
            )

        if ATTR_COLOR_TEMP_KELVIN in kwargs and device_temp is not None:
            await self._send_command(
                "set_device_colortemp", {"colorTemperature": device_temp}
            )

        if ATTR_RGB_COLOR in kwargs and rgb is not None:
            await self._send_command(
                "set_device_color", {"red": rgb[0], "green": rgb[1], "blue": rgb[2]}
            )

        # Turn on the light
        if ATTR_COLOR_TEMP_KELVIN not in kwargs and ATTR_RGB_COLOR not in kwargs:
            await self._send_command("set_device_switch", {"switch": 1})

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        self._attr_is_on = False
        self._last_req_time = time.time()

        await self._send_command("set_device_switch", {"switch": 0})

        self.async_write_ha_state()

    async def _get_device_status(self) -> Optional[Dict[str, Any]]:
        response = await self._send_command("search_devices", {})
        if response and "result" in response:
            result = response["result"]
            if result.get("ret") == 0:
                return result
        return None

    async def _get_device_brightness(self) -> Optional[Dict[str, Any]]:
        response = await self._send_command("get_device_brightness", {})
        if response and "result" in response:
            result = response["result"]
            if result.get("ret") == 0:
                return result
        return None

    def _update_state_from_status(
            self, status: Dict[str, Any], brightness_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update internal state from device status."""
        try:
            # -------------------------------------------------------------------------
            # PART 1: WHITE-ONLY BULBS
            # -------------------------------------------------------------------------
            if self._is_rgb is False:
                w_obj = status.get("W") or status.get("w") or {}
                w_value = (w_obj or {}).get("value", 0)
                w_freq = (w_obj or {}).get("freq")

                device_brightness_percent: int | None = None
                if brightness_info and "brightness" in brightness_info:
                    try:
                        device_brightness_percent = int(brightness_info["brightness"])
                    except (TypeError, ValueError):
                        device_brightness_percent = None

                if w_freq == 0:
                    self._attr_is_on = True
                elif device_brightness_percent is not None:
                    if device_brightness_percent == 0:
                        self._attr_is_on = False
                    elif not self._optimistic_power:
                        self._attr_is_on = True
                else:
                    try:
                        w_percent = int(w_value)
                    except (TypeError, ValueError):
                        w_percent = None
                    if w_percent == 0:
                        self._attr_is_on = False
                    elif w_percent is not None and not self._optimistic_power:
                        self._attr_is_on = True
                    elif w_percent is None and not self._optimistic_power:
                        self._attr_is_on = bool(w_value)

                if device_brightness_percent is not None:
                    self._attr_brightness = min(
                        255, max(0, int((device_brightness_percent / 100) * 255))
                    )
                else:
                    try:
                        w_percent2 = int(w_value)
                    except (TypeError, ValueError):
                        w_percent2 = None
                    if w_percent2 is not None and 0 <= w_percent2 <= 100:
                        self._attr_brightness = min(255, max(0, int((w_percent2 / 100) * 255)))
                    else:
                        self._attr_brightness = self._attr_brightness if self._attr_is_on else 0

                self._attr_color_mode = ColorMode.BRIGHTNESS
                self._available = True
                return

            # -------------------------------------------------------------------------
            # PART 2: RGB BULBS & STRIPS
            # -------------------------------------------------------------------------
            r_raw = status.get("R", {}).get("value", 0)
            g_raw = status.get("G", {}).get("value", 0)
            b_raw = status.get("B", {}).get("value", 0)
            w_raw = status.get("W", {}).get("value", 0)

            r_freq = status.get("R", {}).get("freq", 1)
            g_freq = status.get("G", {}).get("freq", 1)
            b_freq = status.get("B", {}).get("freq", 1)
            w_freq = status.get("W", {}).get("freq", 1)

            self._attr_is_on = any(freq == 0 for freq in [r_freq, g_freq, b_freq, w_freq])

            if self._attr_is_on:
                # W channel active => Color Temp Mode
                if w_raw > 0:
                    self._attr_color_mode = ColorMode.COLOR_TEMP
                    self._attr_rgb_color = None

                    # Use cached request if available to prevent math drift/jitter
                    if self._req_kelvin is not None:
                        self._attr_color_temp_kelvin = self._req_kelvin
                    else:
                        # Fallback Math
                        max_raw = max(r_raw, g_raw, b_raw, w_raw, 1)
                        r_norm = int((r_raw / max_raw) * 255)
                        g_norm = int((g_raw / max_raw) * 255)
                        b_norm = int((b_raw / max_raw) * 255)
                        w_norm = int((w_raw / max_raw) * 255)

                        calc_k = int(
                            5 * r_norm
                            - 9.6 * g_norm
                            - 12.5 * b_norm
                            + 7.4 * w_norm
                            - 0.127 * r_norm**2
                            + 0.136 * r_norm * w_norm
                            + 0.277 * g_norm**2
                            - 0.613 * g_norm * b_norm
                            + 0.439 * g_norm * w_norm
                            + 0.33 * b_norm**2
                            - 0.216 * b_norm * w_norm
                            - 0.113 * w_norm**2
                            + 6245.18
                        )
                        self._attr_color_temp_kelvin = max(
                            self._attr_min_color_temp_kelvin,
                            min(self._attr_max_color_temp_kelvin, calc_k)
                        )

                else:
                    # RGB Mode (W is strictly 0)
                    self._attr_color_mode = ColorMode.RGB
                    self._attr_color_temp_kelvin = None
                    self._req_kelvin = None 

                    # Use cached request if values are zeroed out by dimness
                    if self._req_rgb is not None:
                        self._attr_rgb_color = self._req_rgb
                    else:
                        max_rgb = max(r_raw, g_raw, b_raw, 1)
                        self._attr_rgb_color = (
                            int((r_raw / max_rgb) * 255),
                            int((g_raw / max_rgb) * 255),
                            int((b_raw / max_rgb) * 255),
                        )

                # Brightness
                if brightness_info and "brightness" in brightness_info:
                    device_brightness = brightness_info["brightness"]
                    self._attr_brightness = min(255, int((device_brightness / 100) * 255))
                else:
                    max_channel_value = max(r_raw, g_raw, b_raw, w_raw)
                    if max_channel_value > 100:
                        self._attr_brightness = max_channel_value
                    else:
                        self._attr_brightness = int((max_channel_value / 100) * 255)
            else:
                self._attr_brightness = 0

            self._available = True

        except Exception as e:
            _LOGGER.error(f"Error updating state from status: {e}")
            self._available = False

    async def _send_command(
            self, func: str, param: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Send UDP command to the bulb."""
        command = {"func": func, "param": param}

        def send_udp():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3)
            try:
                message = json.dumps(command)
                _LOGGER.debug(f"Sending to {self._host}:{self._port}: {message}")
                sock.sendto(message.encode(), (self._host, self._port))
                try:
                    response, _ = sock.recvfrom(1024)
                    return json.loads(response.decode())
                except socket.timeout:
                    return None
                except json.JSONDecodeError:
                    return None
            except Exception:
                return None
            finally:
                sock.close()

        try:
            return await asyncio.get_event_loop().run_in_executor(None, send_udp)
        except Exception:
            return None

    def _kelvin_to_device_temp(self, kelvin: int) -> int:
        device_temp = int(1 + ((kelvin - 2000) / (6500 - 2000)) * 99)
        return max(1, min(100, device_temp))