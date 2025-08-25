// common.c
// Common utilities between modules

#include "common.h"
#include <stdlib.h>
#include <strings.h>
#include <stdarg.h>

esp_err_t send_text(httpd_req_t* r, const char* status, const char* type, const char* format, ...){
    va_list args;
    va_start(args, format);
    if (status) httpd_resp_set_status(r, status);
    if (type)   httpd_resp_set_type(r, type);
    int len = snprintf(0, 0, format, args);
    va_end(args);
    char *output = malloc(len+1);
    va_start(args, format);
    vsnprintf(output, len+1, format, args);
    va_end(args);
    return httpd_resp_send(r, output, HTTPD_RESP_USE_STRLEN);
}
bool query_get(httpd_req_t* r, const char* key, char* out, size_t outlen){
    size_t ql = httpd_req_get_url_query_len(r) + 1;
    if (!ql) return false;
    char *q = malloc(ql); if (!q) return false;
    httpd_req_get_url_query_str(r, q, ql);
    bool ok = (httpd_query_key_value(q, key, out, outlen) == ESP_OK);
    free(q); return ok;
}
uint32_t parse_u32_auto(const char* s){
    if (!s || !*s) return 0;
    return (!strncasecmp(s,"0x",2)) ? strtoul(s,NULL,16) : strtoul(s,NULL,10);
}
