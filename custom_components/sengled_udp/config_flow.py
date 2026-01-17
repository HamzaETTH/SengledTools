import voluptuous as vol
from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
import socket
import json
import asyncio

DOMAIN = "sengled_udp"


class SengledConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sengled UDP."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Test connection to the bulb
            try:
                await self._test_connection(user_input["host"])
                return self.async_create_entry(
                    title=f"Sengled Bulb ({user_input['host']})", data=user_input
                )
            except Exception:
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema(
            {
                vol.Required("host"): cv.string,
                vol.Optional("name", default="Sengled Bulb"): cv.string,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

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
