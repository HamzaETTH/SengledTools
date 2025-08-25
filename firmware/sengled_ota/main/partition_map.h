// partition_map.h
// partition map, detection and constants

#pragma once
#include "esp_ota_ops.h"
#include "esp_partition.h"
#include "esp_http_server.h"
#include "spi_flash.h"
#include "esp_system.h"

#include "common.h"

// Known regions (fallbacks; real addresses come from the table at runtime)
#define FALLBACK_TABLE_OFF   0x6000


static inline const esp_partition_t* P_OTA0(void){
    return esp_partition_find_first(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_OTA_0, NULL);
}
static inline const esp_partition_t* P_OTA1(void){
    return esp_partition_find_first(ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_OTA_1, NULL);
}
static inline const esp_partition_t* P_BOOT(void){
    // Bootloader is not a registered partition on 8266; synthesize a descriptor
    static esp_partition_t fake = { .type=ESP_PARTITION_TYPE_APP, .subtype=ESP_PARTITION_SUBTYPE_APP_FACTORY,
        .address=0x00000, .size=FALLBACK_TABLE_OFF, .label="boot" };
    return &fake;
}
static inline const esp_partition_t* P_BY_LABEL(const char* label){
    if (!label) return NULL;
    if (!strcmp(label, "ota_0")) return P_OTA0();
    if (!strcmp(label, "ota_1")) return P_OTA1();
    if (!strcmp(label, "boot"))  return P_BOOT();
    return esp_partition_find_first(ESP_PARTITION_TYPE_DATA, ESP_PARTITION_SUBTYPE_ANY, label);
}

static inline const esp_partition_t* running_part(void){ return esp_ota_get_running_partition(); }
static inline const esp_partition_t* boot_part(void){ return esp_ota_get_boot_partition(); }

static inline uint32_t flash_ceiling_addr(void){
    const esp_partition_t *run = running_part();
    return run ? run->address : 0x110000; // safe default
}

