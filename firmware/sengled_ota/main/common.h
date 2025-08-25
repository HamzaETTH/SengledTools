// common.h

#pragma once
#include "esp_http_server.h"

#ifndef HTTPD_RESP_USE_STRLEN
#define HTTPD_RESP_USE_STRLEN (-1)
#endif

#define SECTOR_SIZE   4096
#define RECV_CHUNK    1024

esp_err_t send_text(httpd_req_t* r, const char* status, const char* type, const char* body, ...);
bool      query_get(httpd_req_t* r, const char* key, char* out, size_t outlen);
uint32_t  parse_u32_auto(const char* s); // 123 or 0x123
static inline esp_err_t httpd_resp_sendstr_chunk(httpd_req_t *r, const char *s) {
    return httpd_resp_send_chunk(r, s, HTTPD_RESP_USE_STRLEN);
}
