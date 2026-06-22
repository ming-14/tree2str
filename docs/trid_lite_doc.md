# TrID 库使用文档

`trid.py` 是 [TrID](https://mark0.net) 的 Python 精简库版本，用于通过定义包（.trd 文件）识别文件类型。

## 安装依赖

```bash
# 基础功能无需额外依赖
# 可选加速: 安装 stringzilla 可大幅提升字符串匹配性能
pip install stringzilla
```

## 匹配策略

`tridAnalyze` 对**每个定义**依次执行以下两种匹配，分数累加：

### 1. 二进制模式匹配（Patterns）

| 特性 | 说明 |
|---|---|
| 匹配位置 | 文件开头 `2048` 字节内，按定义中指定的固定偏移 |
| 匹配方式 | 精确字节匹配，**所有 patterns 必须全部命中**，任一不匹配则跳过该定义 |
| 分数规则 | 偏移 `0` 的模式 → `长度 × 1000` 分；其他偏移 → `长度 × 1` 分 |

### 2. 字符串匹配（Strings）

| 特性 | 说明 |
|---|---|
| 匹配位置 | 整个文件任意位置 |
| 匹配方式 | 子串搜索，**所有 strings 必须全部命中** |
| 分数规则 | 每个命中字符串 → `长度 × 500` 分 |

> 模式匹配优先执行，模式失败的定义会直接跳过（不检查字符串），这是 TrID 原版行为。

## API 参考

### 常量

| 常量 | 值 | 说明 |
|---|---|---|
| `PROGRAM_VER` | `"2.48"` | 库版本号 |
| `HEADER_FRONT_SIZE` | `2048` | 模式匹配读取的文件头大小（字节） |
| `MAX_FILE_SIZE` | `10 MB` | 读取文件大小上限 |
| `STRINGZILLA_AVAILABLE` | `True/False` | 是否可用 stringzilla 加速 |

---

### `trdpkg2defs(filename, usecache=False)`

加载 TrID 定义包文件（`.trd`）。

**参数：**

| 参数 | 类型 | 说明 |
|---|---|---|
| `filename` | `str` / `Path` | `.trd` 定义包文件路径 |
| `usecache` | `bool` | 是否启用 pickle 缓存加速后续加载 |

**返回：** `TrIDDefsBlock` 对象

**异常：** `TrIDError` — 文件无法读取、格式无效或长度不匹配时抛出

**示例：**

```python
# 加载定义包（不缓存）
TDB = trid.trdpkg2defs("triddefs.trd")

# 启用缓存（会在同目录生成 .triddefs.trd.cache 文件）
TDB = trid.trdpkg2defs("triddefs.trd", usecache=True)
```

---

### `tridAnalyze(filename, TDB)`

使用已加载的定义包分析指定文件（全量匹配，最高准确度）。

**参数：**

| 参数 | 类型 | 说明 |
|---|---|---|
| `filename` | `str` | 要分析的文件路径 |
| `TDB` | `TrIDDefsBlock` | `trdpkg2defs()` 返回的定义块 |

**返回：** `list[TrIDResult]` — 按分数降序排列，空列表表示未能识别

**示例：**

```python
TDB = trid.trdpkg2defs("triddefs.trd")
results = trid.tridAnalyze("unknown_file.bin", TDB)

if not results:
    print("无法识别该文件类型")
else:
    best = results[0]
    print(f"{best.perc:.1f}%  {best.triddef.filetype} (.{best.triddef.ext})")
```

---

### `get_files(filenames, recursive=False)`

将文件路径、通配符模式、目录展开为平坦的文件列表。

**参数：**

| 参数 | 类型 | 说明 |
|---|---|---|
| `filenames` | `Iterable[str]` | 文件路径、glob 通配符或目录路径 |
| `recursive` | `bool` | 是否递归子目录 |

**返回：** `list[str]` — 去重后的文件路径列表

**示例：**

```python
# 通配符
files = trid.get_files(["*.exe", "*.dll"])

# 目录（非递归）
files = trid.get_files(["downloads/"])

# 目录（递归）
files = trid.get_files(["downloads/"], recursive=True)

# 混合使用
files = trid.get_files(["*.exe", "samples/"])
```

---

### `LoadDataFromFile(filename)`

读取文件的相关部分用于字符串分析。小文件读取全部内容，大文件（>10MB）只读取头部和尾部。

**返回：** `bytes` — 转换为大写的文件数据

---

### `errprint(msg)`

向 `stderr` 打印错误信息。

---

## 数据类

### `TrIDDef`

单个文件类型定义，包含以下属性：

| 属性 | 类型 | 说明 |
|---|---|---|
| `filetype` | `str` | 文件类型名称，如 "Windows Executable" |
| `ext` | `str` | 关联扩展名，如 "exe/dll" |
| `mime` | `str` | MIME 类型 |
| `patterns` | `list[tuple]` | 二进制模式列表 `[(偏移, 字节串), ...]` |
| `strings` | `list[bytes]` | 文本字符串列表 |
| `rem` | `str` | 备注说明 |
| `refurl` | `str` | 参考 URL |
| `user` / `email` / `home` | `str` | 定义作者信息 |
| `filename` | `str` | 定义文件名称 |

### `TrIDResult`

单个文件的分析结果：

| 属性 | 类型 | 说明 |
|---|---|---|
| `perc` | `float` | 匹配置信度百分比（0~100） |
| `pts` | `int` | 原始匹配分数 |
| `patt` | `int` | 匹配的模式数 |
| `str` | `int` | 匹配的字符串数 |
| `triddef` | `TrIDDef` | 对应的定义对象 |

### `TrIDDefsBlock`

定义包容器：

| 属性 | 类型 | 说明 |
|---|---|---|
| `version` | `int` | 缓存版本号 |
| `defs_num` | `int` | 定义总数 |
| `defs_group` | `dict` | 按首字节分组的定义字典（key: -1~255） |

---

## 完整示例

```python
import os
import trid

def main():
    # 加载定义包
    TDB = trid.trdpkg2defs("triddefs.trd", usecache=True)

    # 获取待分析文件列表
    files = trid.get_files(["*.exe", "*.bin", "samples/"], recursive=True)

    for f in files:
        results = trid.tridAnalyze(f, TDB)
        print(f"\nFile: {f}")
        if not results:
            print("  Unknown!")
            continue
        for i, res in enumerate(results[:3], 1):
            print(f"  #{i}: {res.perc:5.1f}%  .{res.triddef.ext:<10s}  "
                  f"{res.triddef.filetype}")

if __name__ == "__main__":
    main()
```

## 常见问题

**Q: 如何获得 `.trd` 定义包？**

A: 从 [Mark0.net](https://mark0.net/download/triddefs.zip) 下载 `triddefs.zip`，解压后得到 `triddefs.trd`。
