// endpoints.h
// Register endpoints for http server

#pragma once
#include "esp_http_server.h"

// Called from your main after httpd_start()
esp_err_t register_info_endpoints(httpd_handle_t srv);
esp_err_t register_backup_endpoints(httpd_handle_t srv);
esp_err_t register_flash_endpoints(httpd_handle_t srv);
