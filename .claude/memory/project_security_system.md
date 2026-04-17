---
name: project_security_system
description: 项目安全分级系统实现记录
type: project
---

# 安全分级系统

## 实现时间
2026-04-16

## 核心功能

实现了三级安全机制：

1. **REJECTED** (高危命令) → 直接拒绝执行
2. **NEEDS_CONFIRMATION** (潜在危险) → 需要用户确认
3. **APPROVED** (安全命令) → 自动执行，无需确认

## 各工具安全策略

| 工具   | 策略                                           |
|--------|------------------------------------------------|
| bash   | 分级检查：高危拒绝/危险需确认/安全自动批准     |
| read   | 只读操作，自动批准                             |
| write  | 写操作，需要确认                               |
| edit   | 编辑操作，需要确认                             |
| load_skill | 只读操作，自动批准                         |

## 安全命令列表 (自动批准)

ls, cat, grep, find, pwd, head, tail, wc, cd, echo, test, [, rg, sort, uniq, read, load_skill

## 需要确认的命令

rm, rmdir, mv (到 /dev/null 或 .bak), >, >>

## 被拒绝的高危命令

rm -rf /, rm -rf ~, sudo, su, shutdown, reboot, 管道到 bash/sh, mkfs, fdisk, dd, format

## 相关文件

- `hermes/infra/langchain/tools.py` - 工具实现
- `hermes/security.py` - 安全分级逻辑

## Why
解决每次工具执行都需要手动确认的问题，提高开发效率同时保持安全性。

## How to apply
- 只读操作（read, load_skill）自动批准
- 安全命令（ls, cat, grep等）自动批准
- 危险操作（rm, >等）需要确认
- 高危命令（rm -rf /等）直接拒绝
