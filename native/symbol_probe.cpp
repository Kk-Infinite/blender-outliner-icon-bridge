#include <windows.h>
#include <dia2.h>
#include <diacreate.h>

#include <iostream>
#include <string>

namespace {

bool name_matches(BSTR name)
{
  return name != nullptr && std::wstring_view(name).find(L"tree_element_get_icon_from_id") != std::wstring_view::npos;
}

}  // namespace

int wmain(int argc, wchar_t **argv)
{
  if (argc != 3) {
    std::wcerr << L"Usage: symbol_probe <path-to-blender.pdb> <path-to-msdia140.dll|auto>\n";
    return 2;
  }

  if (FAILED(CoInitializeEx(nullptr, COINIT_MULTITHREADED))) {
    std::wcerr << L"CoInitializeEx failed.\n";
    return 1;
  }

  IDiaDataSource *source = nullptr;
  HRESULT result = std::wstring_view(argv[2]) == L"auto" ?
                             CoCreateInstance(__uuidof(DiaSource),
                                              nullptr,
                                              CLSCTX_INPROC_SERVER,
                                              __uuidof(IDiaDataSource),
                                              reinterpret_cast<void **>(&source)) :
                             NoRegCoCreate(argv[2],
                                            __uuidof(DiaSource),
                                            __uuidof(IDiaDataSource),
                                            reinterpret_cast<void **>(&source));
  if (FAILED(result)) {
    std::wcerr << L"NoRegCoCreate failed: 0x" << std::hex << result << L'\n';
    CoUninitialize();
    return 1;
  }

  result = source->loadDataFromPdb(argv[1]);
  if (FAILED(result)) {
    std::wcerr << L"loadDataFromPdb failed: 0x" << std::hex << result << L'\n';
    source->Release();
    CoUninitialize();
    return 1;
  }

  IDiaSession *session = nullptr;
  result = source->openSession(&session);
  source->Release();
  if (FAILED(result)) {
    std::wcerr << L"openSession failed: 0x" << std::hex << result << L'\n';
    CoUninitialize();
    return 1;
  }

  IDiaSymbol *global = nullptr;
  result = session->get_globalScope(&global);
  if (FAILED(result)) {
    std::wcerr << L"get_globalScope failed: 0x" << std::hex << result << L'\n';
    session->Release();
    CoUninitialize();
    return 1;
  }

  IDiaEnumSymbols *symbols = nullptr;
  result = global->findChildren(SymTagFunction, nullptr, nsNone, &symbols);
  global->Release();
  if (FAILED(result)) {
    std::wcerr << L"findChildren failed: 0x" << std::hex << result << L'\n';
    session->Release();
    CoUninitialize();
    return 1;
  }

  bool found = false;
  ULONG fetched = 0;
  IDiaSymbol *symbol = nullptr;
  while (symbols->Next(1, &symbol, &fetched) == S_OK) {
    BSTR name = nullptr;
    if (SUCCEEDED(symbol->get_undecoratedName(&name)) && name_matches(name)) {
      DWORD rva = 0;
      ULONGLONG length = 0;
      symbol->get_relativeVirtualAddress(&rva);
      symbol->get_length(&length);
      std::wcout << L"RVA 0x" << std::hex << rva << L"  length 0x" << length << L"  " << name << L'\n';
      found = true;
    }
    SysFreeString(name);
    symbol->Release();
  }
  symbols->Release();
  session->Release();
  CoUninitialize();

  if (!found) {
    std::wcerr << L"No matching function found.\n";
  }
  return found ? 0 : 1;
}
