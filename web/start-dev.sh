#!/bin/bash

# Hermes Web 开发启动脚本

echo "🚀 启动 Hermes Web 开发环境..."
echo ""

# 检查端口占用
function check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 获取项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/.hermes/logs"
BACKEND_LOG="$LOG_DIR/web-backend.log"
FRONTEND_LOG="$LOG_DIR/web-frontend.log"

cd "$PROJECT_ROOT"
mkdir -p "$LOG_DIR"

# 启动后端
echo "📦 启动后端服务..."
cd web/backend

if check_port 8000; then
    echo "⚠️ 端口 8000 已被占用，可能是后端已在运行"
else
    # 使用 nohup 在后台运行
    nohup bash -c "cd '$PROJECT_ROOT' && uv run python -m uvicorn web.backend.main:app --reload --port 8000 --host 0.0.0.0" > "$BACKEND_LOG" 2>&1 &
    echo "✅ 后端服务已启动 (PID: $!)"
    echo "📄 日志文件: .hermes/logs/web-backend.log"
fi

cd "$PROJECT_ROOT"

# 等待后端启动
echo "⏳ 等待后端启动..."
sleep 3

# 检查后端是否成功启动
if check_port 8000; then
    echo "✅ 后端服务运行正常 (http://localhost:8000)"
else
    echo "❌ 后端服务启动失败，请检查日志: .hermes/logs/web-backend.log"
fi

echo ""

# 启动前端
echo "🎨 启动前端服务..."
cd web/frontend

if check_port 3000; then
    echo "⚠️ 端口 3000 已被占用，可能是前端已在运行"
else
    echo "📦 安装依赖..."
    npm install

    echo "🚀 启动 Next.js 开发服务器..."
    nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
    echo "✅ 前端服务已启动 (PID: $!)"
    echo "📄 日志文件: .hermes/logs/web-frontend.log"
fi

cd "$PROJECT_ROOT"

# 等待前端启动
echo "⏳ 等待前端启动..."
sleep 5

# 检查前端是否成功启动
if check_port 3000; then
    echo "✅ 前端服务运行正常 (http://localhost:3000)"
else
    echo "❌ 前端服务启动失败，请检查日志: .hermes/logs/web-frontend.log"
fi

echo ""
echo "═══════════════════════════════════════════"
echo "🎉 Hermes Web 开发环境已启动！"
echo "═══════════════════════════════════════════"
echo ""
echo "🔗 访问地址:"
echo "   前端界面: http://localhost:3000"
echo "   后端 API: http://localhost:8000"
echo "   API 文档: http://localhost:8000/docs"
echo ""
echo "📋 常用命令:"
echo "   查看后端日志: tail -f .hermes/logs/web-backend.log"
echo "   查看前端日志: tail -f .hermes/logs/web-frontend.log"
echo "   停止所有服务: pkill -f 'uvicorn web.backend.main:app' && pkill -f 'next dev'"
echo ""
echo "═══════════════════════════════════════════"
