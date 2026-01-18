## Sengled UDP (Home Assistant custom component)

Local-only Home Assistant integration for controlling **Sengled Wi‑Fi bulbs over UDP** on your LAN (**no cloud**).

### What you get

- `light` entity with **on/off**, **brightness**, **RGB color**, **color temperature**

### Requirements

- Home Assistant can reach the bulb on **UDP port 9080** (same LAN/VLAN, no firewall blocks)
- You know the bulb’s **local IP address**

### Install / setup (step-by-step)

1. Copy this folder to:
   - `config/custom_components/sengled_udp`
2. Restart Home Assistant.
3. Go to Settings → Devices & Services → Add Integration.
4. Search for and select **Sengled UDP**.
5. Choose:
   - **Discover** (tries to find bulbs on your LAN automatically), or
   - **Manual** (paste IPs yourself)
6. In **Hosts**, enter one or more bulb IPs (any of these formats work):
   - one per line
   - comma-separated
7. Set **Name prefix** (defaults to `Sengled`) and finish. If you add multiple bulbs at once, names will look like `Sengled (RGB) (192.168.x.x)`.
8. (Recommended) In your router, create a **DHCP reservation** for each bulb so it always gets the same IP. If an IP changes, that bulb entity will stop working until you update it.

### Notes / non-goals

- Direct-to-bulb UDP control only — **no MQTT**
- **Does not pair** the bulb or help it join Wi‑Fi; it assumes the bulb is already on your network
- **RGB vs white bulbs**: this integration detects white-only bulbs and exposes **brightness only** (no color controls). Names will include `(RGB)` / `(White)` when detected.