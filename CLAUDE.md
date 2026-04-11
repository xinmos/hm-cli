# 代码规范

## 1. 文件头部规范

- **禁止在代码文件最上方写文档字符串（docstring）或注释**
- 文件第一行应为实际的代码（import、定义等）
- 模块级文档应放在 README 或专门的文档文件中

### ❌ 禁止示例
```python
"""Hermes 工具系统 - 类似 Claude Code 的 Bash 优先设计"""

import os
...
```

### ✅ 正确示例
```python
import os
import subprocess
...
```

## 2. JSON 处理

- **只使用 `orjson`**，禁止使用标准库 `json`
- `orjson` 性能更好，且支持 bytes 输入

### 使用示例

```python
import orjson

# 序列化
data = {"key": "value"}
json_bytes = orjson.dumps(data)  # 返回 bytes
json_str = json_bytes.decode("utf-8")  # 需要字符串时解码

# 反序列化
parsed = orjson.loads(json_bytes)  # 支持 bytes
parsed = orjson.loads(json_str)    # 也支持 str
```

## 2. Import 规范

### 位置要求

- **所有 import 语句必须放在文件顶部**
- **例外情况**：仅在需要解决循环引用（circular import）时，才允许将 import 放在函数内部

### 分组与排序

按照 PEP 8 标准，import 分为三组，每组之间空一行：

1. **标准库导入**（如 `os`, `sys`, `typing`）
2. **第三方库导入**（如 `orjson`, `langchain`）
3. **本地应用/项目导入**（如 `hermes.config`）

每组内部按字母顺序排序。

### 格式规范

- 优先使用 `from x import y` 形式导入具体类/函数
- 避免使用 `import *`
- 类型提示需要导入时，使用 `from __future__ import annotations` 配合字符串前向引用

### 示例

```python
from __future__ import annotations

import os
import sys
from typing import Any, Dict

import orjson
from langchain_openai import ChatOpenAI
from rich.console import Console

from hermes.config import Config
from hermes.tools import TOOLS
```

### 循环引用例外示例

```python
def some_function():
    # 循环引用: gateway 层导入 model 层，model 层又需要此类型
    from gateway.SomeGateway import SomeGateway
    gateway = SomeGateway()
    ...
```
