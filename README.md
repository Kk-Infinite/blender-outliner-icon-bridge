# Blender 大纲视图图标替换 / Outliner Icon Hook

## 中文

> 一句话：这是一个让 Blender 插件为任意对象替换 Outliner 原生图标的可复用运行时库，复制一个文件夹即可接入，无需重新编译 Blender。

本仓库同时是一个可直接安装的示例 Blender 插件、一个可嵌入其他插件的运行时包，以及该运行时包的 C++ 源码工程。它优先按 `blender.exe` SHA-256 查询已知 RVA；仅在未知构建时才通过 PDB 定位内部图标函数，再把 Blender 的动态 PNG 预览图标绑定到指定对象。

> **测试与风险说明**：目前仅在 Windows x64 环境测试。该项目会 Hook Blender 内部函数；其他操作系统、Blender 版本和复杂使用场景尚未充分验证，可能存在未知兼容性问题或稳定性风险，请先在副本文件上测试。

### 阅读与使用路线

1. **先试用**：将整个仓库作为 Blender 插件安装，打开 `View3D > Sidebar > Outliner Icon`。可创建示例对象，或选中任意物体后点击随机替换图标。
2. **接入自己的插件**：阅读下方“快速接入”，复制 `outliner_icon_runtime/` 到自己的插件目录；完整生命周期、异常和边界以 [接入合同](docs/INTEGRATION.md) 为准。
3. **修改原生实现或补充版本**：阅读“从源码构建”，修改 `native/outliner_icon_hook.cpp` 后重新编译。新的 DLL 会直接写入运行时包；通过 PDB 解析新版本 RVA 后，可将其精确哈希加入 `known_builds.json`。

### 内容

- `outliner_icon_runtime/`：可直接复制到其他 Blender 插件目录的完整运行时包。
- `outliner_icon_runtime/bridge.py`：供其他插件调用的独立 Python API。
- `outliner_icon_runtime/native/bin/Release/outliner_icon_hook_v3.dll`：预编译 x64 原生 Hook DLL。
- `outliner_icon_runtime/known_builds.json`：已验证 Blender 构建的 `blender.exe` SHA-256 与 RVA 地址表。
- `native/include/outliner_icon_hook_api.h`：稳定的原生 C ABI 声明。
- `outliner_icon_runtime/assets/icons/`：正在使用的透明背景示例图标；PNG 为运行时文件，SVG 为可编辑源文件，包含花朵、云朵、表情、UFO 和咖啡杯等。
- `__init__.py`：演示插件，不是接入方的必需文件；可创建示例对象或随机替换当前选中物体的图标。

### 运行条件

- Windows x64，且 Blender 的内部 ABI 与 Hook 兼容。
- 已收录在 `known_builds.json` 的精确 Blender 构建不需要 PDB 或 Microsoft DIA。
- 未收录的构建会退回 PDB 动态解析；此时需要同目录的匹配 `blender.pdb` 和已注册的 Microsoft DIA（通常由 Visual Studio 提供）。

接入时直接加载仓库附带的 DLL，无需编译原生代码。DLL 会优先按 `blender.exe` SHA-256 查询已知 RVA；只有未知构建才会通过匹配 PDB 查找 Blender 内部函数。

### 已验证构建

下列 Windows x64 构建已通过后台 Hook 安装验证，并可在没有 PDB 和 DIA 时使用地址表路径。完整 SHA-256 记录在 `outliner_icon_runtime/known_builds.json`。

| Blender | RVA |
| --- | --- |
| 4.1.1 | `0x1357200` |
| 4.2.9 | `0x14C2370` |
| 4.3.2 | `0x1852C80` |
| 4.4.3 | `0x1CBEEE0` |
| 4.5.3 | `0x1ECBA40` |
| 5.0.1 | `0x1FCA290` |
| 5.1.0 | `0x2E19B30` |
| 5.1.2 | `0x2E2E680` |
| 5.2.0 | `0x296B1E0` |

### 性能

在 Blender 5.2.0 后台实测，首次绑定约 `669 ms`，主要花在一次性计算 `blender.exe` SHA-256、加载 DLL 和预览资源。成功安装后不会重复计算哈希；后续 19 次 `bind()` 合计约 `0.010 ms`，20 次原生映射写入约 `0.034 ms`。GUI 中 Outliner 的实际重绘时间取决于场景和界面状态，未包含在后台测量中。

### 快速接入

将整个 `outliner_icon_runtime/` 文件夹复制到接入方插件的根目录，无需复制仓库中的其他文件。接入方通过相对导入创建桥接实例：

```python
from .outliner_icon_runtime import OutlinerIconBridge

BRIDGE = OutlinerIconBridge()
BRIDGE.register_asset("warning", os.path.join(ASSET_DIR, "warning.png"))
BRIDGE.register_asset("approved", os.path.join(ASSET_DIR, "approved.png"))

if not BRIDGE.bind(obj, "warning"):
    print(BRIDGE.error)
```

必须在首次调用 `bind` 前注册全部图标。图标与对象的对应关系由接入方自行保存，桥接层不会写入对象自定义属性。`.blend` 文件加载后，应从接入方自己的数据重新构造映射，再调用 `rebind`：

```python
@persistent
def on_load(_):
    BRIDGE.rebind((obj, obj["my_icon_key"]) for obj in managed_objects())
```

删除已管理对象前调用 `BRIDGE.clear(obj)`，插件 `unregister()` 时调用 `BRIDGE.close()`。这两个操作只清理当前桥接实例创建的映射，不会清空其他插件的图标映射。

完整的边界、生命周期和异常约定见 [接入合同](docs/INTEGRATION.md)。`BRIDGE.diagnostics()` 可为诊断面板提供 Hook 状态、映射数、调用数和替换数。

### 从源码构建

在 Visual Studio Developer PowerShell 中执行，以便存在 `VSINSTALLDIR`：

```powershell
cmake -S . -B build -G 'Visual Studio 17 2022' -A x64
cmake --build build --config Release --target outliner_icon_hook
```

若 DIA SDK 不在 Visual Studio 默认目录，额外传入 `-DDIA_SDK_ROOT='C:/path/to/DIA SDK'`。输出 DLL 为 `outliner_icon_runtime/native/bin/Release/outliner_icon_hook_v3.dll`。

运行时包的固定结构如下；接入方只需要复制这一棵目录：

```text
outliner_icon_runtime/
  __init__.py              # 对外 API：OutlinerIconBridge
  bridge.py                # Python 实现
  known_builds.json        # 已验证构建的 RVA 地址表
  assets/icons/            # 可选的随包示例图标
  native/bin/Release/      # 预编译 Hook DLL
```

### 仓库说明

`temporary/` 是本地整理时归档的旧图标、历史 DLL 和构建产物，已被 Git 忽略，不属于发布内容。本项目采用 [MIT License](LICENSE)；MinHook 依赖保留其自身许可证。

---

## English

> In one sentence: this is a reusable runtime library that lets Blender add-ons replace an object's native Outliner icon by copying one folder, without rebuilding Blender.

This repository is simultaneously an installable example Blender add-on, an embeddable runtime package for other add-ons, and the C++ source project for that runtime. It first queries a known RVA by `blender.exe` SHA-256 and only resolves Blender's internal icon function from the matching PDB for an unknown build, then binds Blender dynamic PNG preview icons to selected objects.

> **Testing and risk notice**: this project has only been tested on Windows x64. It hooks an internal Blender function; other operating systems, Blender versions, and complex workflows have not been fully validated and may have unknown compatibility or stability risks. Test on a copy of your files first.

### Reading and usage paths

1. **Try it first**: install this repository as a Blender add-on, then open `View3D > Sidebar > Outliner Icon`. Create examples or select any object and randomize its icon.
2. **Integrate it**: read “Integration” below, copy `outliner_icon_runtime/` into the consumer add-on, then use the [integration contract](docs/INTEGRATION.md) for lifecycle, errors, and boundaries.
3. **Change the native implementation or support another build**: read “Build from source”, modify `native/outliner_icon_hook.cpp`, and rebuild. The new DLL is written directly into the runtime package; after resolving a new build's RVA from its PDB, add its exact hash to `known_builds.json`.

### Contents

- `outliner_icon_runtime/`: complete runtime package that can be copied into another Blender add-on.
- `outliner_icon_runtime/bridge.py`: reusable Python API for other add-ons.
- `outliner_icon_runtime/native/bin/Release/outliner_icon_hook_v3.dll`: prebuilt x64 hook DLL.
- `outliner_icon_runtime/known_builds.json`: SHA-256-to-RVA table for verified Blender builds.
- `native/include/outliner_icon_hook_api.h`: stable native C ABI declaration.
- `outliner_icon_runtime/assets/icons/`: active transparent example icons. PNG files are loaded at runtime; SVG files are editable sources, including flowers, clouds, faces, a UFO, and coffee.
- `__init__.py`: example Blender add-on, not required by an integrating add-on; it can create examples or randomize the active object's icon.

### Requirements

- Windows x64 and a Blender build whose internal ABI is compatible with the hook.
- Exact Blender builds listed in `known_builds.json` require neither a PDB nor Microsoft DIA.
- Unknown builds fall back to dynamic PDB resolution and then require a matching adjacent `blender.pdb` and registered Microsoft DIA, normally supplied by Visual Studio.

The bundled DLL is loaded directly, so integration does not require a native build. It first queries the known RVA table by `blender.exe` SHA-256 and only resolves the Blender internal function through the matching PDB for unknown builds.

### Verified builds

The following Windows x64 builds passed background hook-installation verification and can use the known-RVA path without a PDB or DIA. Full SHA-256 records are stored in `outliner_icon_runtime/known_builds.json`.

| Blender | RVA |
| --- | --- |
| 4.1.1 | `0x1357200` |
| 4.2.9 | `0x14C2370` |
| 4.3.2 | `0x1852C80` |
| 4.4.3 | `0x1CBEEE0` |
| 4.5.3 | `0x1ECBA40` |
| 5.0.1 | `0x1FCA290` |
| 5.1.0 | `0x2E19B30` |
| 5.1.2 | `0x2E2E680` |
| 5.2.0 | `0x296B1E0` |

### Performance

Measured in Blender 5.2.0 background mode, the first bind took about `669 ms`, mainly for the one-time `blender.exe` SHA-256, DLL load, and preview-resource load. After successful installation the hash is not recalculated: 19 further `bind()` calls took about `0.010 ms` total, and 20 native mapping writes took about `0.034 ms`. GUI Outliner redraw time depends on the scene and UI state and is not included in the background measurement.

### Integration

Copy the entire `outliner_icon_runtime/` directory into the consumer add-on, then import `OutlinerIconBridge` with `from .outliner_icon_runtime import OutlinerIconBridge`. Register every asset before the first `bind`; persist object-to-asset metadata in the consumer; call `rebind` after a `.blend` load; call `clear` before deleting an owned object; and call `close` during `unregister()`.

The bridge never writes Blender custom properties and only removes mappings it created. See the [integration contract](docs/INTEGRATION.md) for the full API, lifecycle, and error behavior. The Python examples in the Chinese section above are language-independent.

### Build from source

Use a Visual Studio developer PowerShell so `VSINSTALLDIR` is set:

```powershell
cmake -S . -B build -G 'Visual Studio 17 2022' -A x64
cmake --build build --config Release --target outliner_icon_hook
```

Set `-DDIA_SDK_ROOT='C:/path/to/DIA SDK'` when DIA is installed outside the Visual Studio default path. The output is `outliner_icon_runtime/native/bin/Release/outliner_icon_hook_v3.dll`.

### Repository hygiene

`temporary/` contains archived legacy assets, historical DLLs, and local build outputs. It is ignored by Git and is not distributed. This project uses the [MIT License](LICENSE); MinHook retains its upstream license.
