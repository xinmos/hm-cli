---
name: skill_permissions_system
description: Skill 工具权限系统实现，使 skill 的 allowed-tools 声明能够实际生效
type: project
---

# Skill 工具权限系统

## 实现时间
2026-04-16

## 核心功能

实现了 skill 的 `allowed-tools` 声明到实际权限控制的映射：

1. **权限解析**：解析 `allowed-tools: Bash(agent-browser:*), Bash(npx agent-browser:*)` 这样的声明
2. **模式匹配**：支持通配符匹配（如 `agent-browser:*` 匹配所有以 agent-browser 开头的命令）
3. **自动批准**：当命令匹配 skill 的 allowed-tools 时，自动批准执行（无需安全确认）

## 核心组件

### 1. hermes/core/skill_permissions.py

- **ToolPermission**：单个权限模式（如 `Bash(agent-browser:*)`）
- **SkillToolPermissionChecker**：检查命令是否被 skill 允许

### 2. hermes/infra/langchain/tools.py

修改 `bash` 工具：
1. 首先检查当前激活的 skill
2. 如果命令匹配 skill 的 allowed-tools，自动批准
3. 否则走正常安全检查流程

### 3. hermes/infra/persistence/file_skill_repo.py

- 添加 `_active_skill` 字段跟踪当前激活的 skill
- 添加 `get_active_skill()` / `set_active_skill()` 方法

### 4. hermes/app/ports.py

在 `SkillRepository` 协议中添加 `get_active_skill()` 方法

## 使用示例

### Skill 定义 (.hermes/skills/agent-browser/SKILL.md)

```yaml
---
name: agent-browser
description: Browser automation...
allowed-tools: Bash(agent-browser:*), Bash(npx agent-browser:*)
---
```

### 权限检查逻辑

```python
# 当 agent-browser skill 激活时
skill_repo.set_active_skill("agent-browser")

# 以下命令自动批准（无需确认）
bash("agent-browser navigate https://example.com")  # ✅ 匹配 agent-browser:*
bash("npx agent-browser click button")            # ✅ 匹配 npx agent-browser:*

# 以下命令仍需安全检查
bash("ls -la")        # ❌ 不匹配，走正常安全检查
bash("rm -rf /")      # ❌ 不匹配，且高危，直接拒绝
```

## 安全设计

1. **Skill 激活机制**：必须显式激活 skill 才能使用其权限
2. **最小权限原则**：只授予 skill 明确声明的权限
3. **双重保护**：
   - 匹配 allowed-tools 的命令自动批准
   - 不匹配的命令仍走正常安全检查流程
4. **高危命令保护**：即使是 allowed-tools 中的命令，如果是高危操作（如 rm -rf /），仍会被拒绝

## 相关文件

- `hermes/core/skill_permissions.py` - 权限检查核心逻辑
- `hermes/infra/langchain/tools.py` - 工具集成
- `hermes/infra/persistence/file_skill_repo.py` - Skill 存储和激活
- `hermes/app/ports.py` - 协议定义

## Why

解决 skill 的 `allowed-tools` 声明不生效的问题。之前 skill 可以声明 `allowed-tools: Bash(agent-browser:*)`，但系统并没有实际使用这个声明来控制权限，所有 bash 命令都经过统一的安全检查，没有考虑当前激活的 skill。

## How to apply

1. Skill 作者：在 SKILL.md 中声明 `allowed-tools: Bash(命令模式)`
2. 系统：自动解析并使用这些权限声明
3. 运行时：当命令匹配 allowed-tools 时自动批准，否则走安全检查
