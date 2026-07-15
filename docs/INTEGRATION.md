# 接入合同 / Integration Contract

## 中文

### 适用范围

`OutlinerIconBridge` 是原生 ABI 版本 `2` 的 Python 适配层。它接收 Blender 对象和图片路径，取得 Blender 的动态预览图标 ID，并仅向 DLL 写入 `Object* -> icon_id` 映射。它不会创建对象、修改对象属性、添加 UI，也不会自行注册文件加载处理器。

接入方只需将仓库中的 `outliner_icon_runtime/` 整个目录复制到自身插件根目录，然后使用 `from .outliner_icon_runtime import OutlinerIconBridge`。该目录已经包含 Python 实现、预编译 DLL 与随包图标；`native/`、`CMakeLists.txt` 和示例插件都不需要复制。

### 接入方职责

1. 复制完整的 `outliner_icon_runtime/` 文件夹，并创建一个桥接实例。默认使用该文件夹内的相对 DLL 路径；也可以显式指定 DLL 路径。
2. 在第一次调用 `bind` 或 `rebind` 前，注册全部唯一、非空的资源键和存在的图片路径。
3. 使用自己的数据模型持久化“对象对应哪个资源键”。
4. 在 `load_post` 中枚举这些对象并调用 `rebind`。
5. 在删除已绑定对象前调用 `clear`，插件卸载时调用 `close`。

对象地址仅在当前 Blender 进程中有效。加载 `.blend` 后不得复用旧指针，必须重新绑定。

### Hook 地址解析

桥接层先计算运行中 `blender.exe` 的 SHA-256，并查询运行时包内的 `known_builds.json`。命中精确哈希时，DLL 直接使用该条目的 RVA，不需要 PDB 或 DIA。未命中时才调用现有 PDB/DIA 解析路径；该路径要求 `blender.exe` 同目录存在匹配的 `blender.pdb`，且系统具备 Microsoft DIA。

未知构建在没有 PDB/DIA 时会明确安装失败，不会猜测地址或尝试 Hook。

### 已验证构建与维护

当前地址表包含 Blender 4.1.1、4.2.9、4.3.2、4.4.3、4.5.3、5.0.1、5.1.0、5.1.2、5.2.0 的 Windows x64 精确构建。版本号不是匹配条件，实际匹配条件是 `blender.exe` SHA-256。

新增构建时，先在具备 PDB/DIA 的开发环境中通过 `outliner_icon_hook_target_rva()` 取得 RVA，再将构建名称、可执行文件 SHA-256、RVA 写入 `known_builds.json`。只应加入已验证 Hook 可安装的构建。

### 性能与缓存

每个 `OutlinerIconBridge` 实例首次 `install()` 会计算一次 `blender.exe` SHA-256、加载 DLL 并创建预览资源；Blender 5.2.0 后台实测首次绑定约 `669 ms`。安装成功后桥接层复用已就绪状态，不会在后续 `bind()` 中重复计算 SHA-256；19 次后续 `bind()` 合计约 `0.010 ms`。GUI 重绘时间取决于 Blender 场景和界面状态。

### Python API

| 方法 | 输入 | 结果 |
| --- | --- | --- |
| `register_asset(key, image_path)` | 非空 `str`、存在的文件 | 保存运行时资源定义。 |
| `install()` | 无 | 原生 Hook 安装成功时返回 `True`。 |
| `bind(obj, key)` | Blender 对象、已注册资源键 | 将对象当前指针绑定到预览图标，成功时返回 `True`。 |
| `clear(obj)` | Blender 对象 | 删除该对象的映射。 |
| `rebind((obj, key)...)` | 对象与资源键的可迭代对 | 清理本桥接实例的旧映射，重建传入映射，并重绘 Outliner。 |
| `close()` | 无 | 清理本桥接实例的映射和预览集合。 |
| `diagnostics()` | 无 | 返回 `ready`、`error`、`mappings`、`calls`、`overrides`。 |

DLL 不存在、未知构建的 PDB/DIA 解析失败或 Blender 未分配预览图标 ID 时，`bind` 返回 `False`。资源键不存在或图片路径不存在属于调用参数错误，分别抛出 `KeyError` 或 `FileNotFoundError`。

### 原生 ABI

导出声明位于 `native/include/outliner_icon_hook_api.h`。稳定且必需的函数是 `outliner_icon_hook_install`、`outliner_icon_hook_install_at_rva`、`outliner_icon_hook_set`、`outliner_icon_hook_clear`。诊断函数和 `outliner_icon_hook_clear_all` 可供工具使用；接入插件不得调用 `clear_all`，因为 DLL 的原生映射在同一 Blender 进程内共享。

---

## English

### Scope

`OutlinerIconBridge` is a Python adapter over native ABI version `2`. It takes Blender objects and image paths, obtains Blender dynamic preview IDs, and sends only `Object* -> icon_id` mappings to the DLL. It does not create objects, modify object properties, add UI, or own a load handler.

Copy the complete `outliner_icon_runtime/` directory into the consumer add-on root, then import it with `from .outliner_icon_runtime import OutlinerIconBridge`. The directory already contains the Python implementation, prebuilt DLL, and bundled icons; `native/`, `CMakeLists.txt`, and the example add-on are not required by consumers.

### Consumer responsibilities

1. Copy the complete `outliner_icon_runtime/` directory and construct one bridge. Its relative DLL path works by default; an explicit DLL path is also supported.
2. Register all unique non-empty asset keys and existing image paths before the first call to `bind` or `rebind`.
3. Persist the consumer's object-to-asset relationship in its own data model.
4. On `load_post`, enumerate those objects and call `rebind`.
5. Call `clear` before an owned object is deleted, and `close` on add-on unload.

The object address is process-local. It is invalid after a `.blend` load, so a stored pointer must never be reused as persistent data.

### Hook address resolution

The bridge first calculates the SHA-256 of the running `blender.exe` and queries `known_builds.json` in the runtime package. An exact hash match makes the DLL install directly at that entry's RVA, without a PDB or DIA. Only an unknown build uses the existing PDB/DIA path, which requires a matching adjacent `blender.pdb` and Microsoft DIA.

An unknown build without PDB/DIA fails clearly; the runtime never guesses an address or attempts a hook.

### Verified builds and maintenance

The current table contains exact Windows x64 builds for Blender 4.1.1, 4.2.9, 4.3.2, 4.4.3, 4.5.3, 5.0.1, 5.1.0, 5.1.2, and 5.2.0. A version number is not a match condition; the actual match condition is the `blender.exe` SHA-256.

To add a build, use a development environment with PDB/DIA to obtain its RVA through `outliner_icon_hook_target_rva()`, then add the build name, executable SHA-256, and RVA to `known_builds.json`. Only add a build after its hook installation has been verified.

### Performance and caching

The first `install()` for an `OutlinerIconBridge` instance calculates `blender.exe` SHA-256 once, loads the DLL, and creates preview resources; the first bind measured about `669 ms` in Blender 5.2.0 background mode. After successful installation the bridge reuses its ready state and does not recalculate SHA-256 on later `bind()` calls; 19 further calls took about `0.010 ms` total. GUI redraw time depends on Blender's scene and UI state.

### Python API

| Method | Input | Result |
| --- | --- | --- |
| `register_asset(key, image_path)` | non-empty `str`, existing file | Stores a runtime asset definition. |
| `install()` | none | `True` when the native hook is installed. |
| `bind(obj, key)` | Blender object, registered key | `True` after mapping its current pointer to the preview icon. |
| `clear(obj)` | Blender object | Removes that object's mapping. |
| `rebind((obj, key)...)` | iterable of pairs | Clears this bridge's old mappings, recreates all supplied ones, redraws Outliners. |
| `close()` | none | Removes this bridge's mappings and preview collection. |
| `diagnostics()` | none | Returns `ready`, `error`, `mappings`, `calls`, and `overrides`. |

`bind` returns `False` when the DLL is unavailable, an unknown build's PDB/DIA lookup fails, or Blender has not assigned a preview icon ID. A missing key or missing image path is an input error and raises `KeyError` or `FileNotFoundError`.

### Native ABI

The exported declarations live in `native/include/outliner_icon_hook_api.h`. The stable required functions are `outliner_icon_hook_install`, `outliner_icon_hook_install_at_rva`, `outliner_icon_hook_set`, and `outliner_icon_hook_clear`. The diagnostics exports and `outliner_icon_hook_clear_all` are available for tooling; consumers should not call `clear_all` because its native map is shared by every bridge in the Blender process.
