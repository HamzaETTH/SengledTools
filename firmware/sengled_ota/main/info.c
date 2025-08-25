// info.c
// Running partition info and partition map
#include "esp_system.h"
#include "esp_ota_ops.h"     // understand where we are, where we can go, switch boot
#include "esp_partition.h"   // understand partition table
#include "esp_log.h"

#include "endpoints.h"
#include "partition_map.h"
#include "common.h"

static const char *TAG = "info";

static esp_err_t info_json(httpd_req_t *req){
    const esp_partition_t *run  = running_part();
    const esp_partition_t *boot = boot_part();
    const esp_partition_t *o0 = P_OTA0();
    const esp_partition_t *o1 = P_OTA1();

    char buf[360];
    int n = snprintf(buf, sizeof(buf),
        "{\
  \"running\":\"%s\", \"run_addr\":\"0x%06x\",\
  \"boot\":\"%s\",    \"boot_addr\":\"0x%06x\",\
  \"ota_0\":\"0x%06x\", \"ota_1\":\"0x%06x\",\
  \"safe_to_flash\":%s, \"ceiling\":\"0x%06x\"\n}\n",
        run?run->label:"?", run?run->address:0,
        boot?boot->label:"?", boot?boot->address:0,
        o0?o0->address:0, o1?o1->address:0,
        (run && run==o1)?"true":"false", flash_ceiling_addr());
    httpd_resp_set_type(req, "application/json");
    return httpd_resp_send(req, buf, n);
}

static esp_err_t table_json(httpd_req_t *req){
	ESP_LOGI(TAG, "Generating and sending json map...");
    // Emit all registered data partitions we care about
    const char* labels[] = {"boot","nvs","otadata","phy_init","ota_0","ota_1",NULL};
    char line[160]; httpd_resp_set_type(req, "application/json");
    httpd_resp_sendstr_chunk(req, "[\n");
    for (int i=0; labels[i]; ++i){
    	ESP_LOGI(TAG,"... for %s",labels[i]);
        const esp_partition_t* p = P_BY_LABEL(labels[i]);
        if (!p && !strcmp(labels[i],"nvs")) p = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_NVS, "nvs");
        if (!p && !strcmp(labels[i],"otadata")) p = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_OTA, "otadata");
        if (!p && !strcmp(labels[i],"phy_init")) p = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_DATA_PHY, "phy_init");
        if (!p) continue;
        int n = snprintf(line, sizeof(line), "  {\"label\":\"%s\",\"addr\":\"0x%06x\",\"size\":%u}%s\n",
                         p->label, p->address, (unsigned)p->size, labels[i+1]?",":"");
        httpd_resp_send_chunk(req, line, n);
    }
    httpd_resp_sendstr_chunk(req, "]\n");
	esp_err_t rc = httpd_resp_send_chunk(req, NULL, 0);  // close out the HTTP response
    ESP_LOGI(TAG, "Completed sending json map.");
    return rc;
}

// Probe target safety & range preview (supports optional ?len= for write preview)
static esp_err_t probe_json(httpd_req_t *req){
    char label[32]={0};
    char len_s[32]={0};
    size_t ql = httpd_req_get_url_query_len(req)+1; 
    char* q = ql?malloc(ql):NULL; 
    if (q) {
    	httpd_req_get_url_query_str(req,q,ql);
    } 
    httpd_query_key_value(q?:(char*)"", "target", label, sizeof(label));
    httpd_query_key_value(q?:(char*)"", "len",    len_s, sizeof(len_s));
    free(q);
    if (!label[0]) strcpy(label, "boot");

    // Resolve base/limit for the target
    uint32_t base=0, limit=0; bool ok=false;
    if (!strcmp(label, "boot")) { // for backup preview only
        base = 0x000000;
        limit = spi_flash_get_chip_size();
        ok=true;
    } else {
        const esp_partition_t *p = P_BY_LABEL(label);
        if (p) {
        	base=p->address;
            limit=p->address+p->size;
            ok=true;
        }
    }

    // Optional requested write length (bytes)
    uint32_t req_len = 0;
    if (len_s[0]) {
        // accept decimal or hex with 0x prefix
        if (!strncasecmp(len_s, "0x", 2)) req_len = strtoul(len_s, NULL, 16);
        else req_len = strtoul(len_s, NULL, 10);
    }

    // Compute write window [w0, w1) if len given
    uint32_t w0 = base;
    uint32_t w1 = req_len ? base+req_len : limit;

    const esp_partition_t *run = running_part();
    bool overlap=false; 
    if (ok && run){ 
        uint32_t r0=run->address, r1=run->address+run->size; 
        overlap = !(w1 <= r0 || w0 >= r1);
        if (overlap) ok = false;
    }

    char buf[256];
    int n = snprintf(buf, sizeof(buf),
        "{\
  \"ok\":%s, \"label\":\"%s\", \"base\":\"0x%08x\", \"limit\":\"0x%08x\",\
  \"wlen\":%u, \"wend\":\"0x%08x\", \"overlap\":%s, \"running\":\"%s\"\
}",
        ok?"true":"false", label, base, limit,
        (unsigned) (w1 - w0), w1, overlap?"true":"false", run?run->label:"?");
    httpd_resp_set_type(req, "application/json");
    return httpd_resp_send(req, buf, n);
}

esp_err_t register_info_endpoints(httpd_handle_t srv) {
    static const httpd_uri_t info  = { .uri="/info",  .method=HTTP_GET, .handler=info_json };
    static const httpd_uri_t map   = { .uri="/map",   .method=HTTP_GET, .handler=table_json };
    static const httpd_uri_t probe = { .uri="/probe", .method=HTTP_GET, .handler=probe_json };
    esp_err_t rc = httpd_register_uri_handler(srv, &info);
    rc |= httpd_register_uri_handler(srv, &map);
    rc |= httpd_register_uri_handler(srv, &probe);
    return rc;
}