# tree2str

English | [中文](README.zh.md)

A Windows desktop tool that recursively scans directories to build a file tree, collects text content by extension, optionally identifies file types via TrID, and outputs JSON.

## Features

- **Recursive Directory Scanning** — BFS multi-threaded scan, builds a complete file tree (with file size, modification time)
- **Content Collection by Extension** — Select extensions to collect text content from; auto-detects text-type extensions
- **Extensionless File Support** — Popup to view and select extensionless files, with Everything-style search syntax
- **TrID File Type Identification** — Optional binary-signature-based file format recognition (built-in Python port of TrID engine)
- **Config Persistence** — Extension selection, TrID toggle, and other settings are auto-saved and restored on next launch
- **JSON Output** — Results are output as a structured JSON file

## Search Syntax

The extensionless file popup supports Everything-like search syntax:

| Syntax | Example | Description |
|--------|---------|-------------|
| Keywords AND | `src core` | Path contains both "src" and "core" |
| OR | `readme \| dialogs` | Path contains "readme" or "dialogs" |
| NOT | `!dll` | Exclude files whose path contains "dll" |
| Exact phrase | `"My Guide"` | Exact match for a phrase with spaces |
| Wildcards | `*.py`, `dialogs.p?` | `*` any chars, `?` single char |
| `name:` / `n:` | `name:scanner` | Search filename only |
| `path:` / `p:` | `path:src` | Search full path |
| `size:` / `s:` | `size:>1mb` | Filter by size; supports ranges `size:10kb..1mb` and constants `size:tiny` |
| `dm:` | `dm:>2025-06-01` | Filter by modification time |
| `case:` | `case:README` | Case-sensitive matching |
| `regex:` | `regex:.*\.py$` | Regular expression matching |

## Quick Start

### Requirements

- Python 3.8+
- Windows

### Run

```bash
python run.py
```

Optionally specify a config file:

```bash
python run.py path/to/config.json
```

### Optional Speedup

```bash
pip install stringzilla
```

Installing [stringzilla](https://github.com/ashvardanian/stringzilla) significantly improves TrID string matching performance.

## Project Structure

```
tree2str/
├── run.py                    # Entry: sys.path setup + console minimization
├── src/
│   ├── main.py               # Logging config + arg parsing + launch window
│   ├── core/                 # Core logic layer (no UI dependency)
│   │   ├── scanner.py        #   BFS multi-threaded directory scanner
│   │   ├── tree.py           #   Multi-threaded file content fill + TrID analysis
│   │   ├── trid.py           #   TrID definition pack lookup/loading
│   │   └── pipeline.py       #   Processing pipeline (fill → JSON output)
│   ├── ui/                   # UI layer
│   │   ├── app.py            #   Main window
│   │   ├── config.py         #   Config management
│   │   ├── cursor.py         #   System busy cursor management
│   │   └── dialogs.py        #   Search component + extensionless file popup
│   ├── lib/
│   │   └── trid_lite.py      #   TrID Python port
│   └── data/
│       └── triddefs.trd      #   TrID definition pack
├── test/                     # Tests (pytest)
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

## Testing

```bash
# Run all tests
pytest test/

# Search feature tests
pytest test/ui/test_dialogs.py -v

# Scanner tests
pytest test/core/test_scanner.py -v

# Tree fill tests
pytest test/core/test_tree.py -v
```

97 tests in total, covering search syntax parsing, directory scanning, and file tree filling.

## Output Format

JSON output structure:

```json
{
  "files": {
    "main.py": {
      "content": "file text content",
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

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.8 |
| GUI | Tkinter (ttk) |
| File Type ID | TrID (trid_lite.py) |
| Config Storage | JSON |
| Concurrency | threading + ThreadPoolExecutor |
