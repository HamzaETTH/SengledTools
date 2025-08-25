# Running Mosquitto for Local Development

This guide provides the commands to run the Mosquitto MQTT broker using the example `mosquitto.conf` file provided in this directory.

The `-c` flag specifies the configuration file, and `-v` enables verbose logging, which is useful for debugging.

## Windows

Navigate to the `docs/examples` directory in your terminal and run the following command. You may need to adjust the path to your `mosquitto.exe` installation.

```bash
mosquitto.exe -c mosquitto.conf -v
```

## Linux

Navigate to the `docs/examples` directory in your terminal and run the following command.

```bash
mosquitto -c mosquitto.conf -v
```
