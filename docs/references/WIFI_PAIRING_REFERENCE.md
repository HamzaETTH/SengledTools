# Wi-Fi Pairing Reference

This document details the local AP-mode pairing flow for Sengled bulbs, showing the exact sequence of commands and responses between the setup tool, bulb, HTTP server, and MQTT broker.

## Pairing Sequence Diagram

```mermaid
sequenceDiagram
    participant UserPC as "User PC"
    participant SetupTool as "Setup Tool"
    participant BulbAP as "Bulb (AP 192.168.8.1:9080)"
    participant HttpServer as "Local HTTP Setup Server"
    participant MqttBroker as "MQTT Broker (<broker-ip>)"

    UserPC->>SetupTool: "Run --setup-wifi (--ssid --password)"
    SetupTool->>HttpServer: "Start server (port 80 → 8080 fallback)"
    SetupTool->>BulbAP: "UDP startConfigRequest"
    BulbAP-->>SetupTool: "Handshake + MAC"

    opt "Interactive scan"
        SetupTool->>BulbAP: "scanWifiRequest"
        BulbAP-->>SetupTool: "scan in progress"
        SetupTool->>BulbAP: "getAPListRequest"
        BulbAP-->>SetupTool: "routers list"
    end

    SetupTool->>BulbAP: "UDP startConfigRequest (prep)"
    BulbAP-->>SetupTool: "result:true"
    SetupTool->>BulbAP: "setParamsRequest [RC4+Base64 encrypted]"
    Note right of SetupTool: "Includes appServerDomain and jbalancerDomain URLs\n+ Wi‑Fi SSID/password (or BSSID)"
    Note over SetupTool,BulbAP: Payload is RC4-encrypted and then base64-encoded (see KEY_STR in code)
    BulbAP-->>SetupTool: "ack"
    SetupTool->>BulbAP: "endConfigRequest"

    BulbAP->>HttpServer: "POST /life2/device/accessCloud.json"
    HttpServer-->>BulbAP: '{"success": true, "messageCode": "200"}'
    BulbAP->>HttpServer: "POST /jbalancer/new/bimqtt"
    HttpServer-->>BulbAP: '{"protocal":"mqtt","host":"<broker-ip>","port":8883}'

    BulbAP->>MqttBroker: "Connect"
    MqttBroker-->>BulbAP: "ConnAck / ready"
```

## Key Details

- **Encryption**: All sensitive data (Wi-Fi credentials, server URLs) is RC4-encrypted with `KEY_STR` and then base64-encoded
- **HTTP Endpoints**: The bulb expects specific JSON responses from `/life2/device/accessCloud.json` and `/jbalancer/new/bimqtt`
- **Port Fallback**: HTTP server starts on port 80, falls back to 8080 if needed
- **MQTT Port**: Default MQTT broker connection uses port 8883 (TLS)
