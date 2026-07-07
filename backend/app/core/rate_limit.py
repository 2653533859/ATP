"""
API 限流配置

使用 slowapi 基于客户端 IP 进行请求限流。
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
