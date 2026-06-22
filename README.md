# tree2str

Windows 桌面工具：递归扫描目录构建文件树，按扩展名收集文本内容，可选 TrID 文件类型识别，输出 JSON。

## 功能特性

- **递归扫描目录** — BFS 多线程扫描，构建完整文件树（含文件大小、修改时间）
- **按扩展名收集内容** — 勾选需要收集文本内容的扩展名，自动识别文本类型扩展名
- **无扩展名文件支持** — 弹窗查看与选择无扩展名文件，支持 Everything 风格搜索语法
- **TrID 文件类型识别** — 可选基于二进制特征的文件格式识别（内置 Python 移植版 TrID 引擎）
- **配置持久化** — 扩展名选择、TrID 开关等配置自动保存，下次启动恢复
- **JSON 输出** — 结果输出为结构化 JSON 文件

## 搜索语法

无扩展名文件弹窗支持类 Everything 搜索语法：

| 语法 | 示例 | 说明 |
|------|------|------|
| 关键词 AND | `src core` | 路径同时包含 "src" 和 "core" |
| OR | `readme \| dialogs` | 路径包含 "readme" 或 "dialogs" |
| NOT | `!dll` | 排除路径含 "dll" 的文件 |
| 精确短语 | `"My Guide"` | 精确匹配含空格的短语 |
| 通配符 | `*.py`, `dialogs.p?` | `*` 任意字符，`?` 单字符 |
| `name:` / `n:` | `name:scanner` | 仅搜索文件名 |
| `path:` / `p:` | `path:src` | 搜索完整路径 |
| `size:` / `s:` | `size:>1mb` | 按大小筛选，支持范围 `size:10kb..1mb` 和常量 `size:tiny` |
| `dm:` | `dm:>2025-06-01` | 按修改时间筛选 |
| `case:` | `case:README` | 大小写敏感匹配 |
| `regex:` | `regex:.*\.py$` | 正则表达式匹配 |

## 快速开始

### 环境要求

- Python 3.8+
- Windows

### 运行

```bash
python run.py
```

可选指定配置文件：

```bash
python run.py path/to/config.json
```

### 可选加速

```bash
pip install stringzilla
```

安装 [stringzilla](https://github.com/ashvardanian/stringzilla) 可大幅提升 TrID 字符串匹配性能。

## 项目结构

```
tree2str/
├── run.py                    # 入口：sys.path 配置 + 控制台最小化
├── src/
│   ├── main.py               # 日志配置 + 参数解析 + 启动窗口
│   ├── core/                 # 核心逻辑层（无 UI 依赖）
│   │   ├── scanner.py        #   BFS 多线程目录扫描
│   │   ├── tree.py           #   多线程文件内容填充 + TrID 分析
│   │   ├── trid.py           #   TrID 定义包查找/加载
│   │   └── pipeline.py       #   处理流水线（填充 → JSON 输出）
│   ├── ui/                   # 界面层
│   │   ├── app.py            #   主窗口
│   │   ├── config.py         #   配置管理
│   │   ├── cursor.py         #   系统光标忙状态管理
│   │   └── dialogs.py        #   搜索组件 + 无扩展名文件弹窗
│   ├── lib/
│   │   └── trid_lite.py      #   TrID Python 移植版
│   └── data/
│       └── triddefs.trd      #   TrID 定义包
├── test/                     # 测试（pytest）
│   ├── core/
│   │   ├── test_scanner.py
│   │   └── test_tree.py
│   └── ui/
│       └── test_dialogs.py
└── doc/
    ├── 架构规范.md
    ├── 搜索功能帮助.md
    └── trid_lite_doc.md
```

## 测试

```bash
# 运行全部测试
pytest test/

# 搜索功能测试
pytest test/ui/test_dialogs.py -v

# 扫描器测试
pytest test/core/test_scanner.py -v

# 目录树填充测试
pytest test/core/test_tree.py -v
```

共计 97 个测试，覆盖搜索语法解析、目录扫描、文件树填充三大模块。

## 输出格式

JSON 输出结构：

```json
{
  "files": {
    "main.py": {
      "content": "文件文本内容",
      "size": 1234,
      "mtime": "2025-06-01T12:00:00",
      "trid": ["Python Script (.py) - 95.2%"]
    }
  },
  "dirs": {
    "src": {
      "files": { "...": "..." },
      "dirs": { "...": "..." }
    }
  }
}
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 语言 | Python 3.8 |
| GUI | Tkinter (ttk) |
| 文件类型识别 | TrID (trid_lite.py) |
| 配置存储 | JSON |
| 并发 | threading + ThreadPoolExecutor |
