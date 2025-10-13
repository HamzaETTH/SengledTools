# Sengled-Rescue

**Sengled-Rescue** is a tiny, self-hosted web flasher that runs on ESP8266-based Sengled bulbs. It spins up a local AP + web UI so you can:

* back up flash (full or partition-level),
* flash partitions (`boot/0x000000`, `ota_0`, `ota_1`, and data regions),
* switch OTA slots (or relocate this app to the other slot),
* and ultimately replace the OEM firmware (e.g., install Tasmota/ESPHome) to keep bulbs out of e-waste.

It’s designed to be used for \~5 minutes and then never needed again. 💡🛠️

> This lives alongside the **SengledTools** Python scripts, which discover bulbs on your LAN, set params, and can upload this shim over the OEM OTA path.

---

## How it works (high level)

* Many Sengled ESP8266 bulbs ship with a **dual-OTA** layout:

  * partition table at **0x6000**
  * `nvs`, `otadata`, `phy_init` data blocks
  * app slots: `ota_0 @ 0x10000` and `ota_1 @ 0x110000` (sizes may differ)
* Sengled-Rescue is an **ESP8266 RTOS SDK** app built to fit either OTA slot (commonly built as `app2` for `ota_1`).
* When running, it starts a **SoftAP** (default SSID `Sengled-Rescue`) and serves a single-page web UI.
* The UI talks to JSON endpoints to discover the live partition table, preview a write window, and stream uploads safely (block if overlap with the running slot).
* You can then:

  * **Back up** full flash or a region,
  * **Flash** a new image (monolithic at `0x0`, or a slot),
  * **Relocate** Sengled-Rescue to the other OTA slot,
  * **Switch** the boot slot and reboot.

---

## Quick start

### Prereqs

* **ESP8266 RTOS SDK v3.x** (make/project.mk flow)
* Tooling: `make`, `python`, `esptool.py` (for recovery), your usual serial adapter.
* Optional: **SengledTools** Python helper (discovers/configures bulbs and can upload this firmware via OEM OTA).

### Build

This project embeds `index.html` via the SDK’s text embed:

```make
# main/component.mk
COMPONENT_SRCS := main.c info.c flash.c backup.c control.c common.c
COMPONENT_ADD_INCLUDEDIRS := .
COMPONENT_EMBED_TXTFILES := index.html
```

Then:

```bash
make app2     # build image sized/layout for ota_1
# or
make app      # if you prefer building for ota_0-style layout
```

You’ll get something like `build/sengled-ota.bin` (name depends on your project name).

> Why `app2`? It produces an image aligned for the second OTA slot. The bootloader still decides which slot to run based on `otadata`. Either slot works; the UI can relocate/switch later.

### Upload / first run

Use **SengledTools** (recommended) to push Sengled-Rescue into the *inactive* OTA slot via the OEM updater.
Or, as a dev shortcut with wires: write the image directly into the active OTA slot (e.g. `ota_1` at `0x110000`) using `esptool.py`.

Power up the bulb; it will:

* bring up **SoftAP**: `Sengled-Rescue` (open auth), IP `192.168.4.1`
* serve the UI at `http://192.168.4.1/`

---

## Web UI / Endpoints

### UI features

* Pick a **target**: `boot` (0x000000), `ota_0`, `ota_1`, or data regions: `nvs`, `otadata`, `phy_init`, plus `full` (backup only)
* **File picker** (for flashing)
* **Preview overlay** shows the exact write window (green = OK, red = blocked)
* **Status banner** explains the range and whether you must relocate first
* **Buttons**: `Flash selected`, `Backup selected`, `Relocate`, `Boot other`

### REST endpoints (served by the device)

* `GET /info` → JSON: running/boot slot, addresses
* `GET /map` → JSON array of `{label, addr, size}` for `boot, nvs, otadata, phy_init, ota_0, ota_1`
* `GET /probe?target=<label>[&len=<bytes>]` → JSON preview: `{ ok, overlap, base, wend, wlen }`
* `POST /flash?target=<label>` → stream raw `.bin` (Content-Type: `application/octet-stream`)
* `GET /backup?label=<label>` → downloads the selected range (or `full` for whole chip)
* `POST /relocate` → clones the running slot to the other slot (uses min(src, dst) size) and sets it to boot
* `POST /bootswitch` → just switches boot to the other slot

> **Safety:** flashing will fail with `409` if the *actual* `[base .. base+len)` write window overlaps the running slot. For `boot` writes, only small chunks (e.g., updating just the header/bootstrap) are allowed when running from `ota_0` — otherwise relocate first.

---

## Typical workflows

### 1) Full backup (recommended)

* Select **`full`** → **Backup selected**
  Saves the entire chip (for “unbrick me” days or disassembling/debugging). Probably have to reflash this with serial, not OTA.

### 2) Install third-party firmware (monolithic)

* Select **`boot`**.
* Choose your `tasmota.bin` / `esphome.bin`.
* Confirm preview shows `0x000000..0x0xxxxx` and **OK** (green). If it’s blocked, click **Relocate** first.
* **Flash selected** → the device reboots into the new firmware.

### 3) Dev flash to a slot

* Select **`ota_0`** or **`ota_1`**.
* Pick your slot-sized `.bin`.
* **Flash selected** → optional **Boot other** to test.

---

## Recovery

If something goes sideways, use your backup:

```bash
# Example: restore whole chip (adjust size/params to your dump)
esptool.py --chip esp8266 --port /dev/ttyUSB0 --baud 460800 \
  write_flash -fm dout 0x000000 full_backup.bin
```

Or restore a partition by offset/size.

---

## Known quirks / limitations

* Some Sengled variants use slightly different slot sizes/offsets. The app reads the table at **0x6000** at runtime and adapts, but UI visuals may not be perfect on oddball layouts. The write logic respects real ranges either way.
* OEM NVS params may be obfuscated/legacy (can't read existing Wi-Fi creds). This tool sidesteps that by using SoftAP.
* Open AP (by design). You’re on a closed, temporary network while flashing; don’t leave it powered indefinitely.
* This is ESP8266-specific (RTOS SDK). ESP32 users: different table/tools.
* Partition display/flash target may not be quite right, but it's close enough to understand.

---

## Build details (for devs)

* **SDK:** ESP8266 RTOS SDK v3.x (make/project.mk)
* **HTTP server:** `esp_http_server`
* **Embedding:** `COMPONENT_EMBED_TXTFILES := index.html`
* **Code layout:** split modules (`info.c`, `backup.c`, `flash.c`, `control.c`, `common.c`) + `endpoints.h`
* **Map rendering:** inline HTML/JS (no external libs), SVG overlay for the write window

---

## Contributing

PRs welcome—particularly:

* partition map visual polish (still intentionally minimal),
* additional device variants,
* doc tweaks and recovery recipes.

Please keep changes dependency-free (no CDN/libs; device is offline on its own AP).

---

## Credits & license

* **Author:** Matt Falcon (**FalconFour**)
* **SengledTools** Python scripts: https://github.com/HamzaETTH/
* Inspirations: `tuya-convert`, general OTA-shim patterns in the ESP community
* Built on Espressif’s **ESP8266 RTOS SDK** and HTTP server (license: Apache 2.0, Espressif)

**License:** MIT

---

## Disclaimer

You can (soft-)brick devices if you flash the wrong thing to the wrong place, requiring breaking apart the bulb/device and soldering wires to recover. Always make a **full backup** first. You own the risk; this project is provided **as-is**, with no warranty.

---

## One-page “how to ship”

1. Build `app2` → get your `.bin`. The most recent version is already compiled for you in **SengledTools** as `firmware/shim.bin`.
2. Use **SengledTools** to upload Sengled-Rescue into the inactive OTA slot.
3. Connect to `Sengled-Rescue` AP → open `http://192.168.4.1/`.
4. **Backup full**.
5. Pick target + file → **Flash** (relocate first if needed).
6. Reboot into your new firmware. Recycle the shim (it just did its job).
