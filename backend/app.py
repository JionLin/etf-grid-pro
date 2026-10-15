"""
ETF网格交易策略分析系统 - Flask应用
基于ATR算法的智能网格交易策略设计及分析系统
重构后的主应用文件，专注于应用初始化
"""

import os
import logging
import argparse
from flask import Flask, send_from_directory, send_file
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# 导入API模块
from api import register_routes, register_middleware, setup_cors, setup_logging

# 导入版本信息
from config import PROJECT_VERSION
from listen_bind import debug_enabled, resolve_listen_host

# 系统版本号
VERSION = PROJECT_VERSION

def create_app():
    """创建Flask应用实例"""
    # 根据环境变量决定静态文件配置
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    
    if FLASK_ENV == 'production':
        # 生产环境：配置静态文件服务
        app = Flask(__name__, 
                   static_folder='../static',
                   static_url_path='/static')
        app.logger.info("生产环境模式：启用静态文件服务")
    else:
        # 开发环境：不处理静态文件（前端独立运行）
        app = Flask(__name__)
        app.logger.info("开发环境模式：仅提供API服务")
    
    # 应用配置。调试器默认关闭，只有显式 FLASK_DEBUG 才打开。
    app.config['ENV'] = FLASK_ENV
    app.config['DEBUG'] = debug_enabled()
    app.config['VERSION'] = VERSION
    
    # 设置日志
    setup_logging(app)
    
    # 配置CORS
    setup_cors(app)
    
    # 注册中间件
    register_middleware(app)
    
    # 注册路由
    register_routes(app)
    
    # 启动前备份 SQLite。测试进程不写备份，避免污染临时库。
    if FLASK_ENV != 'testing' and not os.environ.get('PYTEST_CURRENT_TEST'):
        try:
            from services.data.sqlite_backup import backup_sqlite_database
            backup_path = backup_sqlite_database()
            if backup_path is not None:
                app.logger.info(f"SQLite 已备份到 {backup_path}")
        except Exception as ex:
            app.logger.warning(f"SQLite 启动备份失败 (非阻塞): {ex}")

    # 启动后台数据新鲜度自检与增量自愈守护线程 (测试环境除外)
    if FLASK_ENV != 'testing' and not os.environ.get('PYTEST_CURRENT_TEST'):
        try:
            from services.data.startup_sync_service import StartupSyncService
            sync_service = StartupSyncService()
            sync_service.start_in_background(delay_seconds=3.0)
        except Exception as ex:
            app.logger.warning(f"启动后台数据自检守护线程失败 (非阻塞): {ex}")
    
    # 只在生产环境添加静态文件路由
    if FLASK_ENV == 'production':
        setup_static_routes(app)
    
    return app

def setup_static_routes(app):
    """设置静态文件路由（仅生产环境）"""
    
    @app.route('/')
    def serve_index():
        """服务前端主页"""
        try:
            return send_file('../static/index.html')
        except FileNotFoundError:
            app.logger.error("静态文件 index.html 不存在")
            return {
                'success': False,
                'error': '前端文件未找到，请检查构建是否完成'
            }, 404
    
    @app.route('/<path:path>')
    def serve_static_files(path):
        """服务静态文件，支持SPA路由"""
        # 如果是API路由，跳过静态文件处理
        if path.startswith('api/'):
            return None
        
        # 定义前端路由路径（这些路径应该返回 index.html）
        frontend_routes = ['analysis', 'dashboard', 'settings', 'help']
        
        # 检查是否是前端路由
        if any(path.startswith(route) for route in frontend_routes):
            try:
                return send_file('../static/index.html')
            except FileNotFoundError:
                app.logger.error("静态文件 index.html 不存在")
                return {
                    'success': False,
                    'error': '前端文件未找到'
                }, 404
        
        # 尝试提供静态文件
        try:
            return send_from_directory('../static', path)
        except FileNotFoundError:
            # 文件不存在时返回index.html（支持其他前端路由）
            try:
                return send_file('../static/index.html')
            except FileNotFoundError:
                app.logger.error("静态文件 index.html 不存在")
                return {
                    'success': False,
                    'error': '前端文件未找到'
                }, 404

# 创建应用实例
app = create_app()

if __name__ == '__main__':
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='ETF网格交易策略分析系统')
    parser.add_argument('--port', type=int, default=None, help='服务器端口号')
    parser.add_argument('--host', type=str, default=None, help='服务器主机地址，默认 127.0.0.1')
    parser.add_argument('--debug', action='store_true', help='显式打开调试器，默认关闭')
    args = parser.parse_args()

    # 优先级：命令行参数 > 环境变量 > 本机回环
    port = args.port or int(os.environ.get('PORT', 5001))
    host = resolve_listen_host(args.host)
    debug = debug_enabled(args.debug)

    app.logger.info(f"启动ETF网格交易策略分析系统，版本: {VERSION}, 端口: {port}")
    app.run(host=host, port=port, debug=debug)
