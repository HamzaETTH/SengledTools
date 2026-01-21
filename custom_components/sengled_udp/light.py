import asyncio
import json
import logging
import socket
from typing import Any, Dict, Optional, Tuple

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_COLOR_TEMP,
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
    # Backwards compat: older entries stored a single host under "host" + optional "name"
    hosts = config_entry.data.get("hosts")
    if not hosts:
        hosts = [config_entry.data["host"]]

    name_prefix = config_entry.data.get("name_prefix") or config_entry.data.get("name")
    host_types: dict[str, str] = config_entry.data.get("host_types") or {}

    multiple = len(hosts) > 1
    entities: list[SengledLight] = []
    for host in hosts:
        # Avoid duplicate names when adding many bulbs at once.
        # If no name_prefix provided, auto-name based on discovered type (rgb/white).
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
        self._is_on = False
        self._brightness = 255
        self._rgb_color = (255, 255, 255)
        self._color_temp_kelvin = None
        self._color_mode = ColorMode.RGB
        self._available = True
        self._optimistic_power = False
        # None = not yet detected. If provided (from config flow), we can set capabilities immediately.
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
            self._color_mode = ColorMode.BRIGHTNESS
            self._rgb_color = None
            self._color_temp_kelvin = None
            # Some white-only models do not expose a reliable power-state in UDP queries
            # (they keep reporting last brightness even when switched off). Mark assumed.
            self._attr_assumed_state = True
            self._optimistic_power = True
        else:
            self._attr_color_mode = ColorMode.RGB
            self._attr_supported_color_modes = {ColorMode.RGB, ColorMode.COLOR_TEMP}

        self._attr_min_color_temp_kelvin = 2000
        self._attr_max_color_temp_kelvin = 6500

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._is_on

    @property
    def brightness(self) -> int:
        """Return the brightness of the light."""
        return self._brightness

    @property
    def rgb_color(self) -> Tuple[int, int, int]:
        """Return the rgb color value."""
        return self._rgb_color

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        return self._color_mode

    @property
    def color_temp_kelvin(self) -> Optional[int]:
        """Return the color temperature in Kelvin."""
        return self._color_temp_kelvin

    async def async_update(self) -> None:
        """Fetch new state data for this light."""
        status = await self._get_device_status()
        if status:
            # Detect RGB vs white-only on first successful query
            if self._is_rgb is None:
                self._detect_capabilities(status)
            # Also get the actual brightness from the device
            brightness_info = await self._get_device_brightness()
            self._update_state_from_status(status, brightness_info)

    def _detect_capabilities(self, status: Dict[str, Any]) -> None:
        """Detect if bulb is RGB or white-only based on search_devices response."""
        # RGB bulbs have R, G, B keys; white-only bulbs only have W
        has_rgb = "R" in status and "G" in status and "B" in status
        self._is_rgb = has_rgb

        if has_rgb:
            self._attr_supported_color_modes = {ColorMode.RGB, ColorMode.COLOR_TEMP}
            self._attr_color_mode = ColorMode.RGB
            _LOGGER.debug("Detected RGB bulb: %s (%s)", self._attr_name, self._host)
        else:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._color_mode = ColorMode.BRIGHTNESS
            self._attr_assumed_state = True
            self._optimistic_power = True
            _LOGGER.debug("Detected white-only bulb: %s (%s)", self._attr_name, self._host)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        # White-only bulbs: only handle brightness + power
        if self._is_rgb is False:
            if ATTR_BRIGHTNESS in kwargs:
                brightness = kwargs[ATTR_BRIGHTNESS]
                brightness_percent = int((brightness / 255) * 100)
                await self._send_command(
                    "set_device_brightness", {"brightness": brightness_percent}
                )
                self._brightness = brightness
            await self._send_command("set_device_switch", {"switch": 1})
            self._is_on = True
            self.async_write_ha_state()
            return

        # RGB bulbs: handle color temperature
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            color_temp_kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            device_temp = self._kelvin_to_device_temp(color_temp_kelvin)
            await self._send_command(
                "set_device_colortemp", {"colorTemperature": device_temp}
            )
            self._color_temp_kelvin = color_temp_kelvin
            self._color_mode = ColorMode.COLOR_TEMP
            # Clear RGB color when using color temp
            self._rgb_color = None

        # Handle RGB color (only if not setting color temp)
        elif ATTR_RGB_COLOR in kwargs:
            rgb = kwargs[ATTR_RGB_COLOR]
            await self._send_command(
                "set_device_color", {"red": rgb[0], "green": rgb[1], "blue": rgb[2]}
            )
            self._rgb_color = rgb
            self._color_mode = ColorMode.RGB
            # Clear color temp when using RGB
            self._color_temp_kelvin = None

        # Handle brightness
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            brightness_percent = int((brightness / 255) * 100)
            await self._send_command(
                "set_device_brightness", {"brightness": brightness_percent}
            )
            self._brightness = brightness

        # Turn on the light if not already handling colors
        if ATTR_COLOR_TEMP not in kwargs and ATTR_RGB_COLOR not in kwargs:
            await self._send_command("set_device_switch", {"switch": 1})

        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._send_command("set_device_switch", {"switch": 0})
        self._is_on = False
        self.async_write_ha_state()

    async def _get_device_status(self) -> Optional[Dict[str, Any]]:
        """Get the current device status using search_devices command."""
        response = await self._send_command("search_devices", {})

        if response and "result" in response:
            result = response["result"]
            if result.get("ret") == 0:  # Success
                return result
            else:
                _LOGGER.warning(
                    f"Status query failed: {result.get('msg', 'Unknown error')}"
                )

        return None

    async def _get_device_brightness(self) -> Optional[Dict[str, Any]]:
        """Get the current device brightness using get_device_brightness command."""
        response = await self._send_command("get_device_brightness", {})

        if response and "result" in response:
            result = response["result"]
            if result.get("ret") == 0:  # Success
                return result
            else:
                _LOGGER.warning(
                    f"Brightness query failed: {result.get('msg', 'Unknown error')}"
                )

        return None

    def _update_state_from_status(
            self, status: Dict[str, Any], brightness_info: Optional[Dict[str, Any]] = None
        ) -> None:
            """Update internal state from device status."""
            try:
                # -------------------------------------------------------------------------
                # PART 1: WHITE-ONLY BULBS (Unchanged to prevent regression)
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
                        self._is_on = True
                    elif device_brightness_percent is not None:
                        if device_brightness_percent == 0:
                            self._is_on = False
                        elif not self._optimistic_power:
                            self._is_on = True
                    else:
                        try:
                            w_percent = int(w_value)
                        except (TypeError, ValueError):
                            w_percent = None

                        if w_percent == 0:
                            self._is_on = False
                        elif w_percent is not None and not self._optimistic_power:
                            self._is_on = True
                        elif w_percent is None and not self._optimistic_power:
                            self._is_on = bool(w_value)

                    if device_brightness_percent is not None:
                        self._brightness = min(
                            255, max(0, int((device_brightness_percent / 100) * 255))
                        )
                    else:
                        try:
                            w_percent2 = int(w_value)
                        except (TypeError, ValueError):
                            w_percent2 = None

                        if w_percent2 is not None and 0 <= w_percent2 <= 100:
                            self._brightness = min(255, max(0, int((w_percent2 / 100) * 255)))
                        else:
                            self._brightness = self._brightness if self._is_on else 0

                    self._color_mode = ColorMode.BRIGHTNESS
                    self._available = True
                    _LOGGER.debug(
                        "Updated white-only state: on=%s, brightness=%s, W=%s, freq=%s",
                        self._is_on, self._brightness, w_value, w_freq
                    )
                    return

                # -------------------------------------------------------------------------
                # PART 2: RGB BULBS & STRIPS (Fixed for Hybrid White)
                # -------------------------------------------------------------------------
                r_raw = status.get("R", {}).get("value", 0)
                g_raw = status.get("G", {}).get("value", 0)
                b_raw = status.get("B", {}).get("value", 0)
                w_raw = status.get("W", {}).get("value", 0)

                r_freq = status.get("R", {}).get("freq", 1)
                g_freq = status.get("G", {}).get("freq", 1)
                b_freq = status.get("B", {}).get("freq", 1)
                w_freq = status.get("W", {}).get("freq", 1)

                # Device is on if any LED frequency is 0
                self._is_on = any(freq == 0 for freq in [r_freq, g_freq, b_freq, w_freq])

                if self._is_on:
                    # FIX: If White channel is active (>0), we are in Color Temp mode.
                    # Even if R/G/B are present (used for mixing/tinting), 
                    # we must treat this as white to avoid "Ghost Colors" in Google Home.
                    if w_raw > 0:
                        self._color_mode = ColorMode.COLOR_TEMP
                        
                        # IMPORTANT: Clear RGB so HA/Google Home knows it's white
                        self._rgb_color = None

                        # Use raw values to estimate Kelvin. 
                        # Normalize first to ensure math works on both 0-100 and 0-255 firmware scales.
                        max_raw = max(r_raw, g_raw, b_raw, w_raw, 1)
                        r_norm = int((r_raw / max_raw) * 255)
                        g_norm = int((g_raw / max_raw) * 255)
                        b_norm = int((b_raw / max_raw) * 255)
                        w_norm = int((w_raw / max_raw) * 255)

                        self._color_temp_kelvin = int(
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
                        # Clamp to valid range
                        self._color_temp_kelvin = max(
                            self._attr_min_color_temp_kelvin, 
                            min(self._attr_max_color_temp_kelvin, self._color_temp_kelvin)
                        )

                    else:
                        # RGB Mode (W is strictly 0)
                        self._color_mode = ColorMode.RGB
                        self._color_temp_kelvin = None
                        
                        # Normalize RGB only here for display purposes
                        max_rgb = max(r_raw, g_raw, b_raw, 1)
                        self._rgb_color = (
                            int((r_raw / max_rgb) * 255),
                            int((g_raw / max_rgb) * 255),
                            int((b_raw / max_rgb) * 255),
                        )

                    # Brightness Handling
                    if brightness_info and "brightness" in brightness_info:
                        device_brightness = brightness_info["brightness"]
                        # Convert percentage (0-100) to HA byte (0-255)
                        self._brightness = min(255, int((device_brightness / 100) * 255))
                    else:
                        # Fallback: estimate from max channel value
                        max_channel_value = max(r_raw, g_raw, b_raw, w_raw)
                        # Handle firmware 0-100 scale vs 0-255 scale
                        if max_channel_value > 100: 
                            # Likely 0-255 scale
                            self._brightness = max_channel_value
                        else:
                            # Likely 0-100 scale (like your strip)
                            self._brightness = int((max_channel_value / 100) * 255)
                else:
                    self._brightness = 0

                self._available = True
                _LOGGER.debug(
                    f"Updated state: on={self._is_on}, brightness={self._brightness}, mode={self._color_mode}, RGBWRaw=({r_raw},{g_raw},{b_raw},{w_raw})"
                )

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

                # Try to receive response
                try:
                    response, _ = sock.recvfrom(1024)
                    response_str = response.decode()
                    _LOGGER.debug(f"Received response: {response_str}")
                    try:
                        return json.loads(response_str)
                    except json.JSONDecodeError:
                        return {"raw_response": response_str}
                except socket.timeout:
                    _LOGGER.warning(f"No response from {self._host}")
                    return None
            except Exception as e:
                _LOGGER.error(f"Error sending command to {self._host}: {e}")
                return None
            finally:
                sock.close()

        try:
            return await asyncio.get_event_loop().run_in_executor(None, send_udp)
        except Exception as e:
            _LOGGER.error(f"Failed to send command: {e}")
            return None

    def _kelvin_to_device_temp(self, kelvin: int) -> int:
        """Convert kelvin to device temperature (1-100 scale)."""

        device_temp = int(1 + ((kelvin - 2000) / (6500 - 2000)) * 99)
        return max(1, min(100, device_temp))

    def _device_temp_to_kelvin(self, device_temp: int) -> int:
        """Convert device temperature (1-100 scale) to kelvin."""

        kelvin = int(2000 + ((device_temp - 1) / 99) * (6500 - 2000))
        return max(2000, min(6500, kelvin))
