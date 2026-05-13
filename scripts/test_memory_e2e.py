"""
端到端测试脚本：模拟真实多会话编码场景，验证记忆系统效果。

运行方式:
    uv run python scripts/test_memory_e2e.py

测试场景:
    场景 A: 多会话记忆检索（模拟 agentmemory 的 JWT → N+1 → Rate Limiting 流程）
    场景 B: 隐私脱敏验证
    场景 C: 去重验证
    场景 D: 知识图谱实体关联
    场景 E: 记忆衰减和淘汰
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hermes.core.memory.memory_manager import MemoryManager
from hermes.core.memory.models import MemoryConfig


def green(s: str) -> str:
    return f"\033[32m{s}\033[0m"


def red(s: str) -> str:
    return f"\033[31m{s}\033[0m"


def bold(s: str) -> str:
    return f"\033[1m{s}\033[0m"


def section(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {bold(title)}")
    print(f"{'='*70}")


def check(condition: bool, label: str) -> bool:
    global passed_checks, failed_checks
    if condition:
        passed_checks += 1
        status = green("✓ PASS")
    else:
        failed_checks += 1
        status = red("✗ FAIL")
    print(f"  {status}: {label}")
    return condition


passed_checks = 0
failed_checks = 0
failed = 0


def record(mgr: MemoryManager, sid: str, ui: str, ar: str = "done") -> None:
    ep = mgr.record_interaction(sid, ui, ar)
    if ep:
        pass  # counted separately


# ──────────────────────────────────────────────────────────────
# 场景 A: 模拟 agentmemory 的多会话编码流程
# ──────────────────────────────────────────────────────────────
section("场景 A: 多会话记忆检索")

tmpdir = Path(tempfile.mkdtemp())
config = MemoryConfig(
    episodes_path=str(tmpdir / "episodes.json"),
    importance_threshold=1,
)
kg_path = tmpdir / "knowledge_graph.json"
mgr = MemoryManager(episodes_path=tmpdir / "episodes.json", config=config, knowledge_graph_path=kg_path)

print("\n📝 Session 1: 搭建 JWT 认证系统")
print("-" * 40)
record(mgr, "s1", "配置 JWT 认证中间件，使用 jose 库替代 jsonwebtoken 以支持 Edge runtime")
record(mgr, "s1", "在 src/middleware/auth.ts 中实现 token 验证逻辑")
record(mgr, "s1", "jose 库的 sign 方法需要指定 alg 参数为 RS256")
record(mgr, "s1", "编写 auth 模块的单元测试，覆盖 token 过期和无效签名场景")
record(mgr, "s1", "修复测试中 mock jose 的 import 路径错误")

print("\n📝 Session 2: 修复数据库 N+1 查询问题")
print("-" * 40)
record(mgr, "s2", "发现用户列表接口存在 N+1 查询问题，每次请求查询 200+ 次数据库")
record(mgr, "s2", "使用 Prisma 的 include 优化 User 和 Post 的关联查询")
record(mgr, "s2", "在 src/services/user.service.ts 中添加批量查询方法")
record(mgr, "s2", "添加数据库查询性能测试，确保 N+1 修复后查询数降到 5 次以内")

print("\n📝 Session 3: 添加 API 频率限制")
print("-" * 40)
record(mgr, "s3", "为 API 接口添加频率限制，使用 Redis 滑动窗口算法")
record(mgr, "s3", "在 src/middleware/rate-limiter.ts 实现基于用户 ID 的限流")
record(mgr, "s3", "对 auth 相关的端点设置更严格的限制：每分钟 10 次")
record(mgr, "s3", "添加限流中间件的集成测试")

print(f"\n  已记录 13 条交互\n")

# ── 测试检索效果 ──
print(bold("🔍 检索测试: '数据库查询性能优化'"))
result = mgr.retrieve_context("数据库查询性能优化", max_episodes=3)
print(f"  返回结果:\n{result}")
check(
    len(result) > 0 and ("N+1" in result or "查询" in result),
    "检索到 N+1 查询相关记录",
)

print(f"\n{bold('🔍 检索测试: JWT 认证中间件')}")
result = mgr.retrieve_context("JWT 认证中间件", max_episodes=3)
print(f"  返回结果:\n{result}")
check(
    len(result) > 0 and ("JWT" in result or "auth" in result or "jose" in result),
    "检索到 JWT/auth 相关记录",
)

print(f"\n{bold('🔍 检索测试: 限流和频率控制')}")
result = mgr.retrieve_context("限流和频率控制", max_episodes=3)
print(f"  返回结果:\n{result}")
check(
    len(result) > 0 and ("限流" in result or "rate" in result or "Redis" in result),
    "检索到限流相关记录",
)

print(f"\n{bold('🔍 检索测试: 无关联查询应返回空')}")
result = mgr.retrieve_context("前端 CSS 动画效果", max_episodes=3)
check(result == "", "无关联查询正确返回空字符串")


# ──────────────────────────────────────────────────────────────
# 场景 B: 隐私脱敏
# ──────────────────────────────────────────────────────────────
section("场景 B: 隐私脱敏验证")

tmpdir2 = Path(tempfile.mkdtemp())
mgr2 = MemoryManager(
    episodes_path=tmpdir2 / "episodes.json",
    config=MemoryConfig(episodes_path=str(tmpdir2 / "episodes.json"), importance_threshold=1),
)

print("\n📝 记录包含敏感信息的交互")
ep = mgr2.record_interaction(
    "s1",
    "用这个 API key: sk-ant-api03-abc123def45678901234567890",
    "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0 已配置",
)
assert ep is not None

# 重新加载检查存储的数据
from hermes.core.memory.episode_store import EpisodeStore
store = EpisodeStore(tmpdir2 / "episodes.json")
stored = store.get_all()
print(f"  存储的 summary: {stored[0].summary}")
print(f"  存储的 user_input: {stored[0].raw_data.get('user_input', '')}")

check("sk-ant" not in stored[0].summary, "Summary 中 API key 已脱敏")
check("sk-ant" not in str(stored[0].raw_data), "Raw data 中 API key 已脱敏")
check("eyJhbGci" not in stored[0].summary, "Summary 中 JWT token 已脱敏")
check("REDACTED" in str(stored[0].raw_data), "脱敏标记存在")


# ──────────────────────────────────────────────────────────────
# 场景 C: 去重
# ──────────────────────────────────────────────────────────────
section("场景 C: 去重验证")

tmpdir3 = Path(tempfile.mkdtemp())
mgr3 = MemoryManager(
    episodes_path=tmpdir3 / "episodes.json",
    config=MemoryConfig(episodes_path=str(tmpdir3 / "episodes.json"), importance_threshold=1),
)

print("\n📝 连续记录相同输入")
ep1 = mgr3.record_interaction("s1", "配置 JWT 中间件参数", "完成")
ep2 = mgr3.record_interaction("s1", "配置 JWT 中间件参数", "完成")  # 5 分钟内相同输入
ep3 = mgr3.record_interaction("s1", "修改 JWT 过期时间为 24 小时", "完成")

check(ep1 is not None, "第一次记录成功")
check(ep2 is None, "重复输入被去重跳过（5 分钟窗口）")
check(ep3 is not None, "不同输入正常记录")


# ──────────────────────────────────────────────────────────────
# 场景 D: 知识图谱实体关联
# ──────────────────────────────────────────────────────────────
section("场景 D: 知识图谱实体关联")

from hermes.core.memory.knowledge_graph import KnowledgeGraph

tmpdir4 = Path(tempfile.mkdtemp())
kg = KnowledgeGraph(tmpdir4 / "kg.json")

from hermes.core.memory.models import EntityRef

print("\n📝 添加实体共现关系（模拟同一 episode 中操作的文件）")
kg.add_entities([
    EntityRef("file", "/src/middleware/auth.ts", "auth.ts"),
    EntityRef("file", "/src/middleware/rate-limiter.ts", "rate-limiter.ts"),
    EntityRef("file", "/src/services/user.service.ts", "user.service.ts"),
], "ep1")

kg.add_entities([
    EntityRef("file", "/src/middleware/auth.ts", "auth.ts"),
    EntityRef("file", "/tests/auth.test.ts", "auth.test.ts"),
], "ep2")

print(f"\n{bold('🔍 查询 auth.ts 的关联实体')}")
related = kg.query_related_entities("auth.ts")
for node, edge in related:
    print(f"  → {node.name} (confidence: {edge.confidence:.2f}, type: {edge.relation_type})")

check(len(related) > 0, "auth.ts 能找到关联实体")
check(any(n.name == "rate-limiter.ts" for n, _ in related), "关联到 rate-limiter.ts")
check(any(n.name == "auth.test.ts" for n, _ in related), "关联到 auth.test.ts（第二次添加）")

node = kg.get_node("file", "auth.ts")
check(node is not None, "直接查找 auth.ts 节点")
check(node is not None and node.confidence > 0.3, "auth.ts 节点置信度 > 0.3（被多次引用）")


# ──────────────────────────────────────────────────────────────
# 场景 E: 记忆衰减和淘汰
# ──────────────────────────────────────────────────────────────
section("场景 E: 记忆衰减和淘汰")

tmpdir5 = Path(tempfile.mkdtemp())
store2 = EpisodeStore(
    tmpdir5 / "decay.json",
    decay_rate=0.5,  # 加速衰减（每天 50%）
    min_retention_score=0.1,
)

from hermes.core.memory.models import Episode as E, EventType as ET

# 插入一条"旧"记忆
old_ep = E(
    id="old1", timestamp=datetime.now() - timedelta(days=30),
    event_type=ET.USER_MESSAGE, session_id="s1",
    summary="旧的不再使用的配置", raw_data={}, entities=[],
    importance=1, retention_score=0.15,
)
# 插入一条新记忆
new_ep = E(
    id="new1", timestamp=datetime.now(),
    event_type=ET.USER_MESSAGE, session_id="s2",
    summary="新的重要配置", raw_data={}, entities=[],
    importance=9, retention_score=1.0,
)
store2.append(old_ep)
store2.append(new_ep)
print(f"\n  淘汰前: {len(store2.get_all())} 条记录")

removed = store2.prune_decayed(datetime.now())
print(f"  淘汰了 {removed} 条记录")
remaining = store2.get_all()
print(f"  淘汰后: {len(remaining)} 条记录")
for ep in remaining:
    print(f"    - [{ep.retention_score:.2f}] {ep.summary}")

check(removed >= 1, "低分旧记忆被淘汰")
check(len(remaining) >= 1, f"保留至少一条 (实际: {len(remaining)})")

# 测试访问 boost
print(f"\n{bold('📈 访问 boost 测试')}")
store2.record_access("new1", datetime.now())
updated = [e for e in store2.get_all() if e.id == "new1"][0]
print(f"  访问前 retention_score: 1.0, 访问后: {updated.retention_score:.3f}")
check(updated.access_count == 1, "access_count 递增")
check(updated.retention_score > 0.8, "retention_score 保持高位（被访问强化）")


# ──────────────────────────────────────────────────────────────
# 结果汇总
# ──────────────────────────────────────────────────────────────
section("结果汇总")
total = passed_checks + failed_checks
print(f"  通过: {passed_checks}/{total}")
if failed_checks > 0:
    print(f"  {red(f'失败: {failed_checks}/{total}')}")
else:
    print(f"  {green('全部通过! 🎉')}")
