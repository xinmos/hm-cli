# 代码规范

## 1. 文件头部

- 文件第一行必须是代码（import/定义），**禁止顶部写文档字符串**
- 模块文档放 README

```python
# ❌ 禁止
"""模块说明"""
import os

# ✅ 正确
import os
import subprocess
```

## 2. Import 规范

分组（每组空一行）：
1. 标准库 (`os`, `sys`, `typing`)
2. 第三方库 (`orjson`, `langchain`)
3. 本地项目 (`hermes.config`)

每组内按字母排序，优先用 `from x import y`。

```python
import os
import sys
from typing import Any, Dict

import orjson
from langchain_openai import ChatOpenAI

from hermes.config import Config
```

- 循环引用时才允许函数内 import

## 3. 技术栈

| 用途 | 必选 |
|------|------|
| JSON | `orjson`（性能更好，支持 bytes）|
| Python 执行 | `uv run python` |

```bash
# ✅ 正确
uv run python -c "print('OK')"
uv run python script.py

# ❌ 禁止裸命令
python script.py
python3 script.py
```

## 4. 注释规范

**需要注释：**
- 复杂算法/业务逻辑（解释**为什么**这么做）
- 非直观的代码（如魔法数字、workaround）
- 仅当函数/类命名无法自解释时才加 docstring

**禁止注释：**
- 解释显而易见的代码行为
- 每行代码都加注释
- 简单函数的 docstring（函数名已说明用途）

```python
# ❌ 禁止 - 解释显而易见的内容
i += 1  # 增加计数

# ✅ 正确 - 解释复杂逻辑
# 使用滑动窗口避免重复计算，时间复杂度从 O(n^2) 降到 O(n)
window_sum = sum(nums[:k])
```
