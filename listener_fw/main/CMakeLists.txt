idf_component_register(SRCS "main.c" "audio_out.c" "a2dp_dec.c" "host.c"
                       INCLUDE_DIRS "."
                       PRIV_REQUIRES bt nvs_flash esp_driver_i2s esp_driver_uart esp_timer ratematch mostctl)
