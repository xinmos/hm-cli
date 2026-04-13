# hm-cli 架构重构计划

## 目标

将当前"脚本集合"转变为"可持续演进的控制平面"。核心原则：**把 CLI 降级为 Adapter，把 Runtime 提升为系统真正入口**。

---

## 重构阶段

### Phase 1: 建立装配边界 (高优先级)

建立三层架构：

| 层级 | 路径 | 职责 |
|------|------|------|
| 接口层 | `hermes/interfaces/cli/` | 参数解析、stdin/stdout 交互、UI 渲染 |
| 应用层 | `hermes/app/` | ControlPlane、Runtime、Services |
| 基础设施层 | `hermes/infra/` | LangChainOpenAIBackend、FileSkillRepository、JsonTaskStore |

**产出文件:**
- `hermes/app/ports.py` - 端口接口定义 (AgentBackend, SkillRepository, TaskStore, ToolCatalog, InteractionPort)
- `hermes/app/bootstrap.py` - 唯一装配入口
- `hermes/app/settings.py` - 显式配置数据类 (替代隐式 Config)

---

### Phase 2: 模型 SDK 赶出 Core (高优先级)

- 拆分 `HermesAgent` → `AgentSession` (Core) + `LangChainOpenAIBackend` (Infra)
- 定义 `AgentBackend` Protocol 接口
- `ContextCompressor` 改为依赖注入 LLMClient

---

### Phase 3: 消灭全局单例 (高优先级)

| 当前问题 | 解决方案 |
|----------|----------|
| `get_registry()` 全局单例 | `SkillService` 显式注入 |
| `_confirm_callback` 全局回调 | `InteractionPort` 注入 |
| `TOOLS` 静态列表 | 可组合的 `ToolCatalog` |
| `Config` import 时读环境 | `Settings` 装配时注入 |

---

### Phase 4: 统一 Runtime (高优先级)

创建 `Runtime` 类统一托管：
- `start()` - 启动 scheduler、gateway、channel worker、session store
- `stop()` - 统一关闭后台资源
- `register_signal_handlers()` - 只在 CLI adapter 做系统信号绑定

拆分 `TaskScheduler`:
- `TaskService` - 业务逻辑
- `TaskStore` - 持久化端口
- `SchedulerDriver` - APScheduler 适配

---

### Phase 5: CLI 降级为 Adapter (高优先级)

`cli.py` 只保留：
1. 参数解析
2. 读取输入
3. 调用 `app.handle(command)`
4. 渲染输出

CLI 不再直接：
- 实例化 `HermesAgent`, `TaskScheduler`, `Console`
- 读取 `Path.read_text()`
- 调用 `get_registry()`, `set_confirm_callback()`

顺道修复: `scheduler.py` 中的 `json` → `orjson`

---

### Phase 6: 测试基础设施 (中优先级)

创建 Fake 实现用于单元测试：
- `FakeLLM` - 模拟 LLM 响应
- `InMemoryTaskStore` - 内存任务存储
- `StubSkillRepository` - 存根技能仓库
- `StubInteractionPort` - 存根交互端口

---

## 重构后的依赖方向

```
┌─────────────────────────────────────┐
│       interfaces/cli/cli.py       │  <- 薄入口，只解析和渲染
├─────────────────────────────────────┤
│          app/bootstrap.py           │  <- 唯一装配点
├─────────────────────────────────────┤
│  app/control_plane  app/runtime     │  <- 核心用例
├─────────────────────────────────────┤
│        infra/langchain/             │  <- 技术适配
│        infra/persistence/           │
└─────────────────────────────────────┘
```

**依赖规则:**
1. CLI 只能依赖 `app` 暴露的 use case
2. Core 不 import 具体插件实现
3. 插件之间不允许通过全局变量通信

---

## 关键验证点

- [ ] CLI 不再直接实例化 `HermesAgent`, `TaskScheduler`, `Console`
- [ ] Core 层不 import `ChatOpenAI`, `rich`, `prompt_toolkit`
- [ ] 所有配置通过 `bootstrap` 显式注入
- [ ] 单元测试可用 Fake 实现运行，无需网络/模型
- [ ] `Runtime.stop()` 能干净关闭所有后台资源

---

## 如果只做一件事

**把 CLI 降级为 Adapter，把 Runtime 提升为系统真正入口。**

---

## 参考

- 代码审查报告: `docs/20260413-001-code-review.md`
- 架构原则: AGENTS.md (import 规范、技术栈)
