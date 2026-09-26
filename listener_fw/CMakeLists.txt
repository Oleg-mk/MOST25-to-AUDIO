# M2, the ESP32 on the listener board. ESP-IDF v6.1.
cmake_minimum_required(VERSION 3.22)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
idf_build_set_property(MINIMAL_BUILD ON)
project(listener_fw)
