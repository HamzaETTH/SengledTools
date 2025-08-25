// flash.c
// Routines for flashing and relocating
#include "esp_http_server.h"
#include "esp_system.h"
#include "esp_ota_ops.h"     // understand where we are, where we can go, switch boot
#include "esp_partition.h"   // understand partition table

#include "endpoints.h"
#include "common.h"
#include "partition_map.h"

static bool resolve_target(const char* label, uint32_t *base, uint32_t *limit){
    const esp_partition_t *p = P_BY_LABEL(label);
    if (!p) return false;
    *base = p->address; *limit = p->address + p->size;
    // Don’t allow writes to/through the running image region
    uint32_t ceil = flash_ceiling_addr();
    if (*base < ceil && *limit > ceil) *limit = ceil; // clip at ceiling
    return true;
}

static esp_err_t flash_post(httpd_req_t *req){
    // Parse target
    char label[32]={0}; size_t ql = httpd_req_get_url_query_len(req)+1; char* q = ql?malloc(ql):NULL; if (q){ httpd_req_get_url_query_str(req,q,ql);} 
    httpd_query_key_value(q?:(char*)"", "target", label, sizeof(label)); free(q);
    if (!label[0]) strcpy(label, "boot");

    uint32_t base=0, limit=0; if (!resolve_target(label, &base, &limit))
        return send_text(req, "400 Bad Request", "text/plain", "Bad target, partition %s doesn't exist", label);

    size_t remaining = req->content_len;

    // Block only if the *actual write range* [base, base+len) overlaps the running image
    const esp_partition_t *run = running_part();
    if (run) {
        uint32_t r0 = run->address;
        uint32_t r1 = run->address + run->size;
        uint32_t w0 = base;
        uint32_t w1 = base + remaining;
        bool overlap = !(w1 <= r0 || w0 >= r1);
        if (overlap) {
            return send_text(req, "409 Conflict", "text/plain", "Target overlaps running image — relocate first");
        }
    }

    uint8_t buf[1024]; uint32_t addr = base; uint32_t erased_to = base;
    bool checked_magic=false;

    while (remaining > 0){
        int to_read = remaining > sizeof(buf) ? sizeof(buf) : remaining;
        int r = httpd_req_recv(req, (char*)buf, to_read);
        if (r <= 0) return send_text(req, "500 Internal Server Error", "text/plain", "recv fail\n");

        if (!checked_magic && base==0x00000){ if (buf[0] != 0xE9) return send_text(req, "400 Bad Request", "text/plain", "Not ESP8266 image slated for boot, avoiding brick\n"); checked_magic=true; }

        // erase as needed
        while (addr + r > erased_to){
            uint32_t sec = erased_to / SPI_FLASH_SEC_SIZE;
            if (spi_flash_erase_sector(sec) != 0) return send_text(req, "500 Internal Server Error", "text/plain", "erase fail at sector %d\n",sec);
            erased_to = (sec+1) * SPI_FLASH_SEC_SIZE;
        }
        int wr = (r + 3) & ~3; for (int i=r;i<wr;i++) buf[i]=0xFF;
        if (spi_flash_write(addr, (uint32_t*)buf, wr) != 0) return send_text(req, "500 Internal Server Error", "text/plain", "write fail at sector 0x%08x\n",addr);
        addr += r; remaining -= r;
    }

    send_text(req, NULL, "text/plain", "OK\n");
    vTaskDelay(pdMS_TO_TICKS(600)); esp_restart();
    return ESP_OK;
}

/* ---- Relocate Handler (clone ourselves to other OTA partition) ---- */
static esp_err_t clone_self_to_other(void) {
    const esp_partition_t *src = esp_ota_get_running_partition();
    const esp_partition_t *dst = esp_ota_get_next_update_partition(NULL);
    if (!src || !dst) return ESP_FAIL;
    
    // Pick the smaller of the two partitions so we don't overrun read/write on src/dest (ota_1 is 0x10000 bytes smaller than ota_0)
    size_t to_copy = src->size < dst->size ? src->size : dst->size;

    uint8_t *buf = malloc(SECTOR_SIZE + 4);   // +4 for write padding
    if (!buf) return ESP_ERR_NO_MEM;

    // loop each sector
    for (size_t off = 0; off < to_copy; off += SECTOR_SIZE) {
        // grab a collection of bytes that's either the full sector, or the remaining bytes (probably full sector all the way)
        size_t n = ((off + SECTOR_SIZE) <= to_copy) ? SECTOR_SIZE : (to_copy - off);

        // erase destination sector boundary as needed
        if ((off % SECTOR_SIZE) == 0) {
            if (spi_flash_erase_sector((dst->address + off) / SECTOR_SIZE) != 0) {
                free(buf); return ESP_FAIL;
            }
        }

        ESP_ERROR_CHECK(esp_partition_read(src, off, buf, n));

        // pad to 4B for write API
        size_t wr = (n + 3) & ~3;
        for (size_t i = n; i < wr; i++) buf[i] = 0xFF;

        if (esp_partition_write(dst, off, buf, wr) != ESP_OK) {
            free(buf); return ESP_FAIL;
        }
    }
    free(buf);

    // Switch boot slot to the cloned image
    return esp_ota_set_boot_partition(dst);
}

static esp_err_t relocate_post_handler(httpd_req_t *req){
  esp_err_t rc = clone_self_to_other();
  if (rc != ESP_OK) return send_text(req, "500 Internal Server Error", "text/plain", "relocate failed");
  httpd_resp_set_type(req, "text/plain");
  httpd_resp_send(req, "Relocated. Rebooting…\n", HTTPD_RESP_USE_STRLEN);
  vTaskDelay(pdMS_TO_TICKS(300));
  esp_restart();
  return ESP_OK;
}

/* ---- Boot other partition (switch) ---- */
static esp_err_t boot_other_post_handler(httpd_req_t *req){
  const esp_partition_t *other = esp_ota_get_next_update_partition(NULL);
  if (!other) return send_text(req, "500 Internal Server Error", "text/plain", "no other slot");
  if (esp_ota_set_boot_partition(other) != ESP_OK)
      return send_text(req, "500 Internal Server Error", "text/plain", "set boot failed");
  httpd_resp_send(req, "OK, rebooting\n", HTTPD_RESP_USE_STRLEN);
  vTaskDelay(pdMS_TO_TICKS(300));
  esp_restart();
  return ESP_OK;
}

esp_err_t register_flash_endpoints(httpd_handle_t srv) {
    static const httpd_uri_t flash_any = { .uri="/flash", .method=HTTP_POST, .handler=flash_post };
    static const httpd_uri_t relocate = { .uri="/relocate", .method=HTTP_POST, .handler=relocate_post_handler };
    static const httpd_uri_t boot_other = { .uri="/bootswitch", .method=HTTP_POST, .handler=boot_other_post_handler };
    esp_err_t rc = httpd_register_uri_handler(srv, &flash_any);
    rc |= httpd_register_uri_handler(srv, &relocate);
    rc |= httpd_register_uri_handler(srv, &boot_other);
    return rc;
}
