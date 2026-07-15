#include <windows.h>
#include <dia2.h>
#include <MinHook.h>

#define OUTLINER_ICON_HOOK_API __declspec(dllexport)
#include "outliner_icon_hook_api.h"

#include <atomic>
#include <cstdint>
#include <shared_mutex>
#include <string>
#include <string_view>
#include <unordered_map>

namespace {

using IconFromIdFn = int (*)(const void *id);

IconFromIdFn g_original = nullptr;
std::unordered_map<const void *, int> g_icon_by_object;
std::shared_mutex g_icon_mutex;
std::atomic<int> g_install_state = 0;
std::atomic<unsigned long long> g_call_count = 0;
std::atomic<unsigned long long> g_override_count = 0;

std::uintptr_t resolve_outliner_icon_rva()
{
  wchar_t executable_path[MAX_PATH]{};
  if (GetModuleFileNameW(nullptr, executable_path, MAX_PATH) == 0) {
    return 0;
  }

  std::wstring pdb_path(executable_path);
  const size_t extension = pdb_path.find_last_of(L'.');
  if (extension == std::wstring::npos) {
    return 0;
  }
  pdb_path.replace(extension, std::wstring::npos, L".pdb");
  if (GetFileAttributesW(pdb_path.c_str()) == INVALID_FILE_ATTRIBUTES) {
    return 0;
  }

  const HRESULT co_status = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
  const bool should_uninitialize = SUCCEEDED(co_status);

  IDiaDataSource *source = nullptr;
  HRESULT result = CoCreateInstance(__uuidof(DiaSource),
                                    nullptr,
                                    CLSCTX_INPROC_SERVER,
                                    __uuidof(IDiaDataSource),
                                    reinterpret_cast<void **>(&source));
  if (FAILED(result)) {
    if (should_uninitialize) {
      CoUninitialize();
    }
    return 0;
  }

  result = source->loadDataFromPdb(pdb_path.c_str());
  if (FAILED(result)) {
    source->Release();
    if (should_uninitialize) {
      CoUninitialize();
    }
    return 0;
  }

  IDiaSession *session = nullptr;
  result = source->openSession(&session);
  source->Release();
  if (FAILED(result)) {
    if (should_uninitialize) {
      CoUninitialize();
    }
    return 0;
  }

  IDiaSymbol *global = nullptr;
  result = session->get_globalScope(&global);
  if (FAILED(result)) {
    session->Release();
    if (should_uninitialize) {
      CoUninitialize();
    }
    return 0;
  }

  IDiaEnumSymbols *symbols = nullptr;
  result = global->findChildren(SymTagFunction, nullptr, nsNone, &symbols);
  global->Release();
  if (FAILED(result)) {
    session->Release();
    if (should_uninitialize) {
      CoUninitialize();
    }
    return 0;
  }

  std::uintptr_t rva = 0;
  ULONG fetched = 0;
  IDiaSymbol *symbol = nullptr;
  while (symbols->Next(1, &symbol, &fetched) == S_OK) {
    BSTR name = nullptr;
    const bool is_target = SUCCEEDED(symbol->get_undecoratedName(&name)) && name != nullptr &&
                           std::wstring_view(name).find(L"tree_element_get_icon_from_id") !=
                               std::wstring_view::npos;
    if (is_target) {
      DWORD symbol_rva = 0;
      if (SUCCEEDED(symbol->get_relativeVirtualAddress(&symbol_rva))) {
        rva = symbol_rva;
      }
    }
    SysFreeString(name);
    symbol->Release();
    if (rva != 0) {
      break;
    }
  }

  symbols->Release();
  session->Release();
  if (should_uninitialize) {
    CoUninitialize();
  }
  return rva;
}

int hook_icon_from_id(const void *id)
{
  g_call_count.fetch_add(1, std::memory_order_relaxed);
  if (id != nullptr) {
    std::shared_lock lock(g_icon_mutex);
    const auto item = g_icon_by_object.find(id);
    if (item != g_icon_by_object.end()) {
      g_override_count.fetch_add(1, std::memory_order_relaxed);
      return item->second;
    }
  }
  return g_original(id);
}

bool minhook_ok(MH_STATUS status)
{
  return status == MH_OK || status == MH_ERROR_ALREADY_INITIALIZED || status == MH_ERROR_ENABLED;
}

bool install_hook_at_rva(std::uintptr_t rva)
{
  if (g_install_state.load() == 1) {
    return true;
  }
  if (rva == 0) {
    return false;
  }

  HMODULE blender_module = GetModuleHandleW(nullptr);
  if (blender_module == nullptr) {
    return false;
  }
  void *target = reinterpret_cast<void *>(reinterpret_cast<std::uintptr_t>(blender_module) + rva);

  if (!minhook_ok(MH_Initialize())) {
    return false;
  }
  if (MH_CreateHook(target, hook_icon_from_id, reinterpret_cast<void **>(&g_original)) != MH_OK) {
    return false;
  }
  if (!minhook_ok(MH_EnableHook(target))) {
    MH_RemoveHook(target);
    return false;
  }

  g_install_state.store(1);
  return true;
}

}  // namespace

extern "C" int outliner_icon_hook_install()
{
  const std::uintptr_t rva = resolve_outliner_icon_rva();
  return install_hook_at_rva(rva) ? 1 : 0;
}

extern "C" int outliner_icon_hook_install_at_rva(unsigned int rva)
{
  return install_hook_at_rva(rva) ? 1 : 0;
}

extern "C" void outliner_icon_hook_set(void *object, int icon_id)
{
  if (object == nullptr || icon_id <= 0) {
    return;
  }
  std::unique_lock lock(g_icon_mutex);
  g_icon_by_object[object] = icon_id;
}

extern "C" void outliner_icon_hook_clear(void *object)
{
  std::unique_lock lock(g_icon_mutex);
  g_icon_by_object.erase(object);
}

extern "C" void outliner_icon_hook_clear_all()
{
  std::unique_lock lock(g_icon_mutex);
  g_icon_by_object.clear();
}

extern "C" int outliner_icon_hook_target_rva()
{
  return static_cast<int>(resolve_outliner_icon_rva());
}

extern "C" unsigned long long outliner_icon_hook_call_count()
{
  return g_call_count.load(std::memory_order_relaxed);
}

extern "C" unsigned long long outliner_icon_hook_override_count()
{
  return g_override_count.load(std::memory_order_relaxed);
}

extern "C" unsigned int outliner_icon_hook_mapping_count()
{
  std::shared_lock lock(g_icon_mutex);
  return static_cast<unsigned int>(g_icon_by_object.size());
}
