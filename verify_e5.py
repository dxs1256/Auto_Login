#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_e5.py —— e5.py 判据回归测试（不需要真实凭据/网络）

核心验收：审计日志的"查询失败"绝不能被显示成"无记录"。
2026-11-21 的线上运行就是这样：429 重试耗尽后 act 保持初始值"无记录"，
日报看起来正常，实际是查询失败。
"""

import sys
import types

# 本地环境可能没装 requests；测试全程 mock 网络，用桩顶上即可。
try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    import requests_stub
    requests_stub.install()

import e5

PASS = 0
FAIL = 0


def check(name, actual, expected):
    global PASS, FAIL
    ok = actual == expected
    print("{} {}  实际={!r} 期望={!r}".format("✅" if ok else "❌", name, actual, expected))
    if ok:
        PASS += 1
    else:
        FAIL += 1


class FakeResp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload
        self.text = ""
        self.headers = {}

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def patch_request(handler):
    """替换 e5._request，让每次调用走 handler(url) -> FakeResp"""
    def fake_request(method, url, **kwargs):
        return handler(url)
    return fake_request


ORG_OK = FakeResp(200, {"value": [{"displayName": "哒哒哒科技公司", "createdDateTime": "2025-11-15T00:00:00Z"}]})


def run_case(name, audit_resp, expect_state, expect_act_substr, expect_warn_icon):
    """跑 get_extra_info 的一个场景"""
    def handler(url):
        if "organization" in url:
            return ORG_OK
        return audit_resp

    orig = e5._request
    e5._request = patch_request(handler)
    try:
        info = e5.get_extra_info("fake-token")
    finally:
        e5._request = orig

    check("{} → act_state".format(name), info["act_state"], expect_state)
    check("{} → act 含 {!r}".format(name, expect_act_substr), expect_act_substr in info["act"], True)

    # 日报渲染：fail 状态必须带 ⚠️
    if expect_warn_icon:
        act_icon = {"ok": "", "fail": "⚠️ ", "unknown": "⚠️ "}.get(info["act_state"], "⚠️ ")
        check("{} → 日报带 ⚠️".format(name), act_icon, "⚠️ ")
    else:
        act_icon = {"ok": "", "fail": "⚠️ ", "unknown": "⚠️ "}.get(info["act_state"], "⚠️ ")
        check("{} → 日报不带 ⚠️".format(name), act_icon, "")


print("—— 审计日志四种状态必须可区分 ——")

# 1. 真正查到记录
run_case(
    "有记录",
    FakeResp(200, {"value": [{"activityDateTime": "2026-11-20T12:26:18.1234567Z"}]}),
    "ok",
    "2026-11-20 12:26:18 (UTC)",
    False,
)

# 2. 查询成功但确实为空
run_case("成功但为空", FakeResp(200, {"value": []}), "ok", "无记录（查询成功）", False)

# 3. 429 限流（2026-11-21 线上实际发生的情况）
run_case("429 限流", FakeResp(429), "fail", "限流 429", True)

# 4. 403 权限不足
run_case("403 权限不足", FakeResp(403), "fail", "权限不足", True)

# 5. 其他 5xx
run_case("500 服务端错误", FakeResp(500), "fail", "HTTP 500", True)

# 6. 记录缺时间字段
run_case("记录缺时间", FakeResp(200, {"value": [{"activityDateTime": None}]}), "fail", "缺少时间字段", True)


print("\n—— 关键回归：429 绝不能显示成 '无记录' ——")
orig = e5._request
e5._request = patch_request(lambda url: ORG_OK if "organization" in url else FakeResp(429))
try:
    info = e5.get_extra_info("fake-token")
finally:
    e5._request = orig

check("429 → act 不等于裸 '无记录'", info["act"] == "无记录", False)
check("429 → act 明确写出失败", "429" in info["act"], True)
check("429 → act_state=fail", info["act_state"], "fail")

print("\n—— 网络异常也要落到 fail ——")
orig = e5._request


def raise_net(method, url, **kwargs):
    if "organization" in url:
        return ORG_OK
    import requests as _rq
    raise _rq.RequestException("boom")


e5._request = raise_net
try:
    info = e5.get_extra_info("fake-token")
finally:
    e5._request = orig
check("网络异常 → act_state=fail", info["act_state"], "fail")
check("网络异常 → act 含 '查询异常'", "查询异常" in info["act"], True)

print("\n—— _request 429 退避：重试后仍 429 应原样返回 ——")
calls = {"n": 0}


class _Seq:
    def __init__(self):
        self.status_code = 429
        self.headers = {"Retry-After": "1"}
        self.text = ""

    def json(self):
        raise ValueError()


def seq_request(method, url, **kwargs):
    calls["n"] += 1
    return _Seq()


orig_req = e5.requests.request
e5.requests.request = seq_request
orig_sleep = e5.time.sleep
e5.time.sleep = lambda s: None  # 不真的等
try:
    resp = e5._request("GET", "https://example.invalid/x")
finally:
    e5.requests.request = orig_req
    e5.time.sleep = orig_sleep

check("429 总请求次数", calls["n"], e5.MAX_RETRY + 1)
check("429 耗尽后返回 429", resp.status_code, 429)

print("\n结果: 通过 {} 项，失败 {} 项".format(PASS, FAIL))
sys.exit(0 if FAIL == 0 else 1)
