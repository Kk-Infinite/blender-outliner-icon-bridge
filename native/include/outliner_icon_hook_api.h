#pragma once

/* Stable C ABI exposed by the prebuilt native hook DLL. */

#ifndef OUTLINER_ICON_HOOK_API
#  ifdef _WIN32
#    define OUTLINER_ICON_HOOK_API __declspec(dllimport)
#  else
#    define OUTLINER_ICON_HOOK_API
#  endif
#endif

#ifdef __cplusplus
extern "C" {
#endif

OUTLINER_ICON_HOOK_API int outliner_icon_hook_install(void);
OUTLINER_ICON_HOOK_API int outliner_icon_hook_install_at_rva(unsigned int rva);
OUTLINER_ICON_HOOK_API void outliner_icon_hook_set(void *object, int icon_id);
OUTLINER_ICON_HOOK_API void outliner_icon_hook_clear(void *object);
OUTLINER_ICON_HOOK_API void outliner_icon_hook_clear_all(void);
OUTLINER_ICON_HOOK_API int outliner_icon_hook_target_rva(void);
OUTLINER_ICON_HOOK_API unsigned long long outliner_icon_hook_call_count(void);
OUTLINER_ICON_HOOK_API unsigned long long outliner_icon_hook_override_count(void);
OUTLINER_ICON_HOOK_API unsigned int outliner_icon_hook_mapping_count(void);

#ifdef __cplusplus
}
#endif
