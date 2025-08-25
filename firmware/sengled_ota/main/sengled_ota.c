#include <string.h>
#include "esp_system.h"
#include "esp_event_loop.h"
#include "esp_log.h"
#include "nvs_flash.h"       // direct flashing to 0x0

#include "tcpip_adapter.h"
#include "esp_wifi.h"
#include "esp_http_server.h"

#include "spi_flash.h"       // erase/write

#include "partition_map.h"
#include "endpoints.h"
#include "common.h"

// index.html page from binary
extern const uint8_t index_html_start[] asm("_binary_index_html_start");
extern const uint8_t index_html_end[]   asm("_binary_index_html_end");

static const char *TAG = "sengled_ota";

static esp_err_t event_handler(void *ctx, system_event_t *event) {
    return ESP_OK; // we don't need events for AP-only
}

static void start_softap_with_dhcp(void)
{
    // NVS + TCP/IP + Wi-Fi driver
    ESP_ERROR_CHECK(nvs_flash_init());
    tcpip_adapter_init();
    ESP_ERROR_CHECK(esp_event_loop_init(event_handler, NULL));

    wifi_init_config_t wic = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&wic));

    // Configure AP IP = 192.168.4.1/24 and start DHCP server
    tcpip_adapter_ip_info_t ip;
    IP4_ADDR(&ip.ip,      192,168,4,1);
    IP4_ADDR(&ip.gw,      192,168,4,1);
    IP4_ADDR(&ip.netmask, 255,255,255,0);

    // it’s harmless to stop before setting
    tcpip_adapter_dhcps_stop(TCPIP_ADAPTER_IF_AP);
    ESP_ERROR_CHECK(tcpip_adapter_set_ip_info(TCPIP_ADAPTER_IF_AP, &ip));
    ESP_ERROR_CHECK(tcpip_adapter_dhcps_start(TCPIP_ADAPTER_IF_AP));

    // Bring up the AP
    wifi_config_t ap = {0};
    strcpy((char*)ap.ap.ssid, "Sengled-Rescue");
    ap.ap.ssid_len       = strlen((char*)ap.ap.ssid);
    ap.ap.channel        = 6;
    ap.ap.authmode       = WIFI_AUTH_OPEN;   // open; we can add a PSK later if desired
    ap.ap.max_connection = 5;
    ap.ap.beacon_interval= 100;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "SoftAP up: SSID=%s  IP=" IPSTR,
             (char*)ap.ap.ssid, IP2STR(&ip.ip));
}

/* ---- HTTP server (Hello page) ---- */

static esp_err_t root_get_handler(httpd_req_t *req) {
    httpd_resp_set_type(req, "text/html");
    size_t len = index_html_end - index_html_start;
    return httpd_resp_send(req, (const char*)index_html_start, len);
}

static void start_httpd(void)
{
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.server_port = 80;

    httpd_handle_t srv = NULL;
    if (httpd_start(&srv, &cfg) == ESP_OK) {
        static const httpd_uri_t root = { .uri = "/", .method = HTTP_GET, .handler = root_get_handler };
        httpd_register_uri_handler(srv, &root);
        register_info_endpoints(srv);
        register_backup_endpoints(srv);
        register_flash_endpoints(srv);
        ESP_LOGI(TAG, "HTTP server started on port %d", cfg.server_port);
    } else {
        ESP_LOGE(TAG, "HTTP server start failed");
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "Sengled-Rescue ready to roll!");
    start_softap_with_dhcp();
    start_httpd();
}
