cmake_minimum_required(VERSION 3.24)

project(outliner_icon_hook LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(BUILD_SHARED_LIBS OFF CACHE BOOL "Build static third-party libraries" FORCE)
add_subdirectory(native/third_party/minhook EXCLUDE_FROM_ALL)

set(DIA_SDK_ROOT "" CACHE PATH "Path to the Visual Studio DIA SDK")
if(NOT DIA_SDK_ROOT AND DEFINED ENV{VSINSTALLDIR})
  set(DIA_SDK_ROOT "$ENV{VSINSTALLDIR}/DIA SDK" CACHE PATH "Path to the Visual Studio DIA SDK" FORCE)
endif()
find_path(DIA_SDK_INCLUDE_DIR dia2.h HINTS "${DIA_SDK_ROOT}/include" REQUIRED)
find_library(DIA_SDK_LIBRARY diaguids HINTS "${DIA_SDK_ROOT}/lib/amd64" REQUIRED)

add_library(outliner_icon_hook SHARED native/outliner_icon_hook.cpp)
target_compile_definitions(outliner_icon_hook PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX)
target_include_directories(outliner_icon_hook PRIVATE native/include "${DIA_SDK_INCLUDE_DIR}")
target_link_libraries(outliner_icon_hook PRIVATE minhook "${DIA_SDK_LIBRARY}" ole32 oleaut32)
set_target_properties(outliner_icon_hook PROPERTIES
  OUTPUT_NAME "outliner_icon_hook_v3"
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/outliner_icon_runtime/native/bin"
  LIBRARY_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/outliner_icon_runtime/native/bin"
)

add_executable(symbol_probe native/symbol_probe.cpp)
target_compile_definitions(symbol_probe PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX UNICODE _UNICODE)
target_include_directories(symbol_probe PRIVATE "${DIA_SDK_INCLUDE_DIR}")
target_link_libraries(symbol_probe PRIVATE "${DIA_SDK_LIBRARY}" ole32 oleaut32)
