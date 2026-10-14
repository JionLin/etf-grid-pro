#!/bin/bash

# ETF网格交易策略设计工具 - Docker容器启动脚本

set -e

echo "🚀 启动ETF网格交易策略设计工具..."

# 环境变量默认值
FLASK_ENV=${FLASK_ENV:-production}
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-5001}

# 创建必要目录
mkdir -p /app/logs /app/cache

# 检查环境变量
if [ -z "$TUSHARE_TOKEN" ] || [ "$TUSHARE_TOKEN" = "your_tushare_token_here" ]; then
    echo "⚠️  警告: TUSHARE_TOKEN未正确配置，某些功能可能无法使用"
fi

if [ -z "$MYSQL_USER" ] || [ -z "$MYSQL_PASSWORD" ]; then
    echo "⚠️  警告: MYSQL_USER / MYSQL_PASSWORD 未配置，行情和档案无法写入 MySQL"
fi

# 根据环境选择启动方式
if [ "$FLASK_ENV" = "development" ]; then
    echo "🔧 开发环境模式启动..."
    exec python backend/app.py
elif [ "$FLASK_ENV" = "production" ]; then
    echo "🏭 生产环境模式启动..."
    
    # 切换到backend目录以解决模块导入问题
    cd /app/backend
    
    # 检查Gunicorn配置文件
    if [ -f "/app/gunicorn.conf.py" ]; then
        echo "📋 使用Gunicorn配置文件启动..."
        exec gunicorn --config /app/gunicorn.conf.py app:app
    else
        echo "📋 使用默认Gunicorn配置启动..."
        exec gunicorn \
            --bind ${HOST}:${PORT} \
            --workers ${WORKERS:-4} \
            --worker-class gevent \
            --worker-connections 1000 \
            --timeout ${TIMEOUT:-30} \
            --keepalive 2 \
            --max-requests 1000 \
            --max-requests-jitter 100 \
            --preload \
            --access-logfile /app/logs/access.log \
            --error-logfile /app/logs/error.log \
            --log-level ${LOG_LEVEL:-info} \
            app:app
    fi
else
    echo "🔧 直接启动Flask应用..."
    exec python backend/app.py
fi
