// backup.c
// Back up partitions

#include "partition_map.h"
#include "common.h"

static esp_err_t backup_get(httpd_req_t *req){
    // Store what partition was requested from HTTP query in "label"
    char label[32]={0}; size_t l = httpd_req_get_url_query_len(req)+1;
    char *q = l? malloc(l):NULL; if (q){ httpd_req_get_url_query_str(req,q,l);} // ?label=full|boot|ota_0|ota_1|nvs|otadata|phy_init
    httpd_query_key_value(q?:(char*)"", "label", label, sizeof(label));
    free(q);

    // Defaults if no partition was specified
    if (!label[0]) strcpy(label, "full");

    uint32_t base = 0;
    uint32_t size = 0;
    const esp_partition_t* p = NULL;

    if (!strcmp(label, "full")) {
        // Full backup, download everything
        base = 0x000000;
        size = spi_flash_get_chip_size();
    } else if (!strcmp(label, "boot")) {
        // "boot" == everything before ota_0 (bootloader + table + data regions)
        const esp_partition_t* o0 = P_OTA0();
        base = 0x000000;
        // Fall back to known address if we didn't find ota_0
        size = o0 ? o0->address : FALLBACK_TABLE_OFF; // fallback to 0x6000 if no ota_0
    } else {
        // Download a specific partition
        p = P_BY_LABEL(label);
        if (!p) return send_text(req, "400 Bad Request", "text/plain", "unknown label\n");
        base = p->address;
        size = p->size;
    }

    // Headers
    char disp[128];
    if (p) snprintf(disp, sizeof(disp), "attachment; filename=%s_0x%06x_%u.bin", p->label, p->address, (unsigned)p->size);
    else   snprintf(disp, sizeof(disp), "attachment; filename=%s_0x%06x_%u.bin", label, base, (unsigned)size);
    httpd_resp_set_type(req, "application/octet-stream");
    httpd_resp_set_hdr(req, "Content-Disposition", disp);

    uint8_t buf[1024]; uint32_t off=0;
    while (off < size) {
        size_t n = (size - off) > sizeof(buf) ? sizeof(buf) : (size - off);
        if (p) {
            if (esp_partition_read(p, off, buf, n) != ESP_OK)
                return send_text(req, "500 Internal Server Error", "text/plain", "read fail\n");
        } else {
            if (spi_flash_read(base + off, (uint32_t*)buf, n) != 0)
                return send_text(req, "500 Internal Server Error", "text/plain", "read fail\n");
        }
        if (httpd_resp_send_chunk(req, (const char*)buf, n) != ESP_OK) return ESP_FAIL;
        off += n;
    }
    return httpd_resp_send_chunk(req, NULL, 0);
}

esp_err_t register_backup_endpoints(httpd_handle_t srv) {
    static const httpd_uri_t backup = { .uri="/backup", .method=HTTP_GET, .handler=backup_get };
    esp_err_t rc = httpd_register_uri_handler(srv, &backup);
    return rc;
}