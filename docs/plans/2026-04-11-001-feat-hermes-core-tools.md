# Hermes Agent 核心工具扩展计划

## 设计理念

**Bash 优先（像 Claude Code）**：通过 `run_command` 让模型直接使用熟悉的 Unix 命令（`cat`, `grep`, `find`, `ls` 等）来探索文件系统，而不是封装成专用工具。这样模型可以：
- 用 `cat file.py | head -50` 查看文件
- 用 `grep -r "pattern" . --include="*.py"` 搜索代码
- 用 `ls -la` 查看目录
- 组合管道完成复杂任务

专用工具只保留必要的：**view_file**（带行号）和 **edit_file**（带备份和语法检查）

---

## 当前状态
- ✅ CLI 基础框架（Rich UI + 历史记录）
- ✅ Agent 对话能力（流式响应）
- ✅ **Bash 优先工具集** - 类似 Claude Code
  - `run_command` - 执行 shell 命令（cat/grep/ls/cd 等）
  - `view_file` - 查看文件（带行号，支持范围）
  - `edit_file` - 精确编辑文件（带备份）
  - `run_python` - 执行 Python 代码
- ❌ Phase 2: 扩展工具
- ❌ Phase 3: Agent 能力增强

---

## 核心工具 Roadmap

### Phase 1: Bash 优先核心工具 ✅ 已完成
目标：让 Agent 通过 Unix 命令自由探索和操作

- [x] `run_command` - 执行任意 shell 命令
  - 安全模式：自动批准 cat/ls/grep 等，危险命令检测
  - 支持管道、重定向
  - 超时控制 + 输出截断
- [x] `view_file` - 查看文件内容（带行号，支持范围）
- [x] `edit_file` - 基于字符串替换的精确编辑（带备份）
- [x] `run_python` - 执行 Python 代码

**示例交互**：
```
User: "查看 cli.py 的前 30 行"
Agent: $ cat cli.py | head -30
       [显示输出...]

User: "搜索项目中所有使用了 ChatOpenAI 的地方"
Agent: $ grep -r "ChatOpenAI" . --include="*.py"
       [显示结果...]

User: "列出 hermes 目录结构"
Agent: $ ls -la hermes/
       [显示结果...]
```

### Phase 2: 扩展工具（可选）
目标：补充 Bash 不方便完成的任务

- [ ] `write_file` - 创建新文件（大内容时比 echo 方便）
- [ ] `undo_edit` - 撤销最近编辑（恢复 .bak 文件）
- [ ] `run_test` - 运行测试并解析结果
- [ ] `git_diff` - 查看变更（比 git diff 更智能的解析）

### Phase 3: Agent 能力增强
目标：提升任务执行效率和可靠性

- [ ] 工具结果缓存（避免重复 cat 同一个文件）
- [ ] 自动任务分解（复杂需求拆分子任务）
- [ ] 上下文压缩（长对话历史摘要）
- [ ] 错误恢复（命令失败重试策略）

---

## 技术实现

### Bash 工具集
```python
# hermes/tools/bash.py
from langchain_core.tools import tool

@tool
def run_command(command: str, cwd: str = None, timeout: int = 30) -> str:
    """执行 shell 命令（cat, grep, ls, find 等）"""
    # 安全检查：自动批准列表 + 危险模式检测
    # 使用 subprocess.run(shell=True) 支持管道
    ...

@tool  
def view_file(file_path: str, view_range: list = None) -> str:
    """查看文件（带行号，可选范围）"""
    # 类似 cat -n，但支持 [start, end] 范围
    ...

@tool
def edit_file(file_path: str, old_string: str, new_string: str) -> str:
    """精确编辑文件（old_string 必须完全匹配）"""
    # 自动创建 .bak 备份
    # Python 文件 AST 语法检查
    ...
```

### 安全机制
```python
# 自动批准（无需确认）
AUTO_APPROVED = ["^ls", "^cat", "^grep", "^head", "^tail", "^cd", "^pwd", "^echo"]

# 危险模式（必须拦截）
DANGEROUS = ["rm -rf", "git push --force", "sudo", "curl.*|.*bash"]
```

---

## 下一步行动

1. **测试当前工具集** - 验证 Bash 优先设计是否流畅
2. **Phase 2 扩展** - 按需添加 write_file, undo_edit 等
3. **Agent 增强** - 缓存、任务分解等高级功能

---

**更新记录**:
- 2026-04-11: 改为 Bash 优先设计，移除 read_file/list_dir/search_files，添加 run_command/view_file/edit_file
