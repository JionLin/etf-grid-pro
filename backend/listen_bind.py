"""本机开发进程的监听地址和调试器开关。"""
import os
from typing import Optional


def debug_enabled(cli_debug: bool = False) -> bool:
    """调试器默认关闭。FLASK_ENV=development 不再打开 Werkzeug 调试器。

    Args:
        cli_debug: 命令行是否显式要求打开调试器

    Returns:
        bool: 是否打开调试器
    """
    flag = os.environ.get("FLASK_DEBUG", "").strip().lower()
    return bool(cli_debug) or flag in ("1", "true", "yes", "on")


def resolve_listen_host(cli_host: Optional[str] = None) -> str:
    """本机脚本默认只监听回环。容器通过 HOST 或 --host 显式绑定 0.0.0.0。

    Args:
        cli_host: 命令行传入的主机地址

    Returns:
        str: 实际绑定地址
    """
    if cli_host:
        return cli_host
    return os.environ.get("HOST") or "127.0.0.1"
