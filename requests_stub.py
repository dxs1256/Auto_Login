"""requests_stub.py —— 供本地测试用的最小 requests 桩。

本地验证环境没有安装 requests（pip 安装受沙箱限制），
而 verify_e5.py 全程 mock 网络，只需要模块能 import、异常类型可用。
在 CI 里是用真的 requests，这里只是本地跑测的替代。
"""

import types
import sys


class RequestException(Exception):
    pass


class ConnectionError(RequestException):  # noqa: A001 - 对齐 requests 命名
    pass


class Timeout(RequestException):
    pass


def request(*args, **kwargs):
    raise RequestException("requests_stub: 网络调用未 mock，不应走到这里")


def get(*args, **kwargs):
    return request(*args, **kwargs)


def post(*args, **kwargs):
    return request(*args, **kwargs)


def install():
    """把桩注册成 sys.modules['requests']"""
    mod = types.ModuleType("requests")
    mod.RequestException = RequestException
    mod.ConnectionError = ConnectionError
    mod.Timeout = Timeout
    mod.request = request
    mod.get = get
    mod.post = post
    mod.__version__ = "0.0.0-stub"
    sys.modules["requests"] = mod
    return mod
