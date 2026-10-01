#!/bin/bash

# ETF网格交易策略设计工具一键启动脚本

echo "🚀 启动ETF网格交易策略设计工具..."
echo "=================================="

# 0. 环境预检：检查 .env 配置文件
if [ ! -f ".env" ]; then
    echo "❌ 错误: 未检测到 .env 配置文件！"
    echo "=================================="
    echo "💡 快速初始化指南："
    echo "  1. 复制配置文件模板:  cp .env.example .env"
    echo "  2. 编辑 .env 文件填入你的 Tushare Token (免费注册获取: https://tushare.pro/register)"
    echo "=================================="
    exit 1
fi

# 检查指定端口是否处于监听状态
check_port() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        lsof -i :"$port" -sTCP:LISTEN >/dev/null 2>&1
        return $?
    fi
    if command -v nc >/dev/null 2>&1; then
        nc -z 127.0.0.1 "$port" >/dev/null 2>&1
        return $?
    fi
    return 1
}

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "🛑 正在停止服务..."
    if [ -n "$FRONTEND_PID" ]; then
        kill -TERM "$FRONTEND_PID" 2>/dev/null
    fi
    if [ -n "$BACKEND_PID" ]; then
        kill -TERM "$BACKEND_PID" 2>/dev/null
    fi
    pkill -f "python.*backend/app.py" 2>/dev/null
    pkill -f "vite" 2>/dev/null
    exit 0
}

trap cleanup INT TERM

# 1. 检查后端服务 (端口 5001)
if check_port 5001; then
    echo "✅ 后端服务已在运行 (端口 5001 活跃)"
else
    echo "📦 启动后端服务..."
    uv run python backend/app.py &
    BACKEND_PID=$!
    backend_ready=0
    for i in {1..12}; do
        if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
            echo "❌ 后端服务启动失败，进程已异常退出！"
            echo "💡 请检查 .env 中的 TUSHARE_TOKEN 是否有效，或执行: uv run python backend/app.py 查看完整报错。"
            cleanup
            exit 1
        fi
        if check_port 5001; then
            backend_ready=1
            break
        fi
        sleep 0.5
    done
    if [ $backend_ready -eq 0 ]; then
        echo "⚠️  后端服务启动超时 (端口 5001 未响应)"
    else
        echo "✅ 后端服务启动就绪 (端口 5001)"
    fi
fi

# 2. 检查前端依赖与服务 (端口 3000)
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 检测到前端未安装依赖，正在自动执行 npm install..."
    (cd frontend && npm install)
    if [ $? -ne 0 ]; then
        echo "❌ 前端依赖安装失败，请检查网络或 Node/npm 环境。"
        cleanup
        exit 1
    fi
    echo "✅ 前端依赖安装完成！"
fi

if check_port 3000; then
    echo "✅ 前端服务已在运行 (端口 3000 活跃)"
else
    echo "📦 启动前端服务..."
    (cd frontend && npm run dev) &
    FRONTEND_PID=$!
    frontend_ready=0
    for i in {1..15}; do
        if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
            echo "❌ 前端服务启动失败，进程已异常退出！"
            echo "💡 请进入 frontend 目录执行: npm run dev 查看完整报错。"
            cleanup
            exit 1
        fi
        if check_port 3000; then
            frontend_ready=1
            break
        fi
        sleep 0.5
    done
    if [ $frontend_ready -eq 0 ]; then
        echo "⚠️  前端服务启动超时 (端口 3000 未响应)"
    else
        echo "✅ 前端服务启动就绪 (端口 3000)"
    fi
fi

echo ""
echo "🎉 服务启动完成！"
echo "=================="
echo "🌐 前端应用: http://localhost:3000"
echo "🔧 后端API: http://localhost:5001"
echo ""
echo "💡 使用提示："
echo "  - 在浏览器中打开前端地址开始使用"
echo "  - 确保已正确配置 .env 文件中的 TUSHARE_TOKEN"
echo "  - 推荐使用热门ETF代码：510300, 510500, 159915 等"
echo ""
echo "⚠️  按 Ctrl+C 停止服务"
echo ""

wait
