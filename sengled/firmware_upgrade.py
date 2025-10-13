import os
import shutil
from sengled.log import section, info, warn, success, stop, firmware_warn


def prepare_firmware_bin(user_path):
    user_path = os.path.expanduser(user_path)
    if not os.path.isfile(user_path):
        warn(f"File does not exist: {user_path}")
        return None

    basename = os.path.basename(user_path)
    if not basename.lower().endswith(".bin"):
        warn("Firmware file must have a .bin extension.")
        return None

    script_dir = os.path.dirname(os.path.abspath(__file__))
    dest_path = os.path.join(script_dir, basename)

    if os.path.isfile(dest_path):
        return basename

    try:
        shutil.copy2(user_path, dest_path)
        success(f"Firmware file copied to: {dest_path}")
        return basename
    except Exception as e:
        warn(f"Error copying firmware file: {e}")
        return None


def print_upgrade_safety_warning() -> None:
    section("⚠️  FIRMWARE UPGRADE WARNING")
    firmware_warn("Firmware upgrades are DANGEROUS!", extra_indent=4)
    firmware_warn("File MUST be compatible ESP RTOS SDK for 'ota_1' slot at 0x110000", extra_indent=4)
    firmware_warn("Uploading standard ESP8266 firmware will BRICK your bulb!", extra_indent=4)
    firmware_warn("Use ONLY tested shim images or official Sengled firmware", extra_indent=4)
    info("")
    input("Press Enter if you are sure, or Ctrl+C to cancel...")


def print_morpheus_last_chance() -> None:
    info("")
    info('"This is your last chance. After this, there is no turning back.', extra_indent=4)
    info("You take the blue pill – the story ends, you wake up in your bed", extra_indent=4)
    info("and believe whatever you want to believe.", extra_indent=4)
    info("You take the red pill – you stay in Wonderland, and I show you", extra_indent=4)
    info("how deep the rabbit hole goes.", extra_indent=4)
    info("Remember, all I'm offering is the truth – nothing more.", extra_indent=4)
    info("― Morpheus", extra_indent=4)
    firmware_warn("After upload, there is no going back to Sengled. THIS IS YOUR LAST CHANCE.", extra_indent=4)
    info("", extra_indent=4)
    input("Press Enter if you're ready to send the update, or Ctrl+C to cancel...")


def print_upgrade_post_send_instructions(concise: bool = False) -> None:
    from sengled.log import section, success, info, warn, highlight
    section("Firmware Upgrade")
    success("Upgrade command sent!")
    
    # Make the WiFi SSID very prominent
    highlight("LOOK FOR WIFI NETWORK: 'Sengled-Rescue'")
    info("Connect to the 'Sengled-Rescue' WiFi network")
    info("Then browse to: http://192.168.4.1 to finish uploading")
    
    warn("⚠️  THERE'S NO GOING BACK - Your bulb only knows the shim firmware now")
    
    if not concise:
        info("Press Ctrl+C after you see firmware downloaded in your server window")
        info("Then your device should be running the uploaded code")


def run_firmware_upgrade(args, bulb_mac: str, setup_server, client) -> bool:
    """
    Handles the firmware upgrade process, including user prompts and sending the command.
    Returns True if the upgrade command was sent, False otherwise.
    """
    from sengled.utils import get_local_ip
    from sengled.mqtt_client import send_update_command, create_mqtt_client
    from sengled.utils import get_current_epoch_ms

    print_upgrade_safety_warning()
    # Resolve a robust default firmware path independent of CWD
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, os.pardir))
    candidate_paths = [
        os.path.join(repo_root, "firmware", "shim.bin"),  # canonical location
        os.path.join(script_dir, "shim.bin"),               # fallback if copied already
    ]
    default_fw = next((p for p in candidate_paths if os.path.isfile(p)), candidate_paths[0])
    
    use_default = input(f"Use default firmware path ({default_fw})? (Y)es or (n)o to enter custom path: ").strip().lower()
    
    if use_default in ['n', 'no']:
        user_fw = input("Enter the path to your firmware file: ").strip()
        if not user_fw:
            stop("No firmware path provided. Aborting upgrade.")
            return False
    else:
        user_fw = default_fw
    fw_basename = prepare_firmware_bin(user_fw)

    if not fw_basename:
        stop("Firmware preparation failed. Aborting upgrade.")
        return False

    http_host = get_local_ip()
    http_port = str(setup_server.port)
    firmware_url = f"http://{http_host}:{http_port}/{fw_basename}"
    info(f"Serving firmware from: {firmware_url}")

    print_morpheus_last_chance()

    ts = get_current_epoch_ms()
    command = [
        {
            "dn": bulb_mac,
            "type": "update",
            "value": firmware_url,
            "time": ts,
        }
    ]
    send_update_command(client, bulb_mac, command)
    
    success("Upgrade command sent.")
    print_upgrade_post_send_instructions(concise=True)
    
    # Wait for the bulb to download the firmware
    setup_server.wait_for_firmware_download(timeout_seconds=300)
    info("Firmware download initiated by bulb.")
    
    return True


