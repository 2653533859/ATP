"""真机 M1 动作矩阵：tap / 精确断言 / back / swipe / content-desc / wait_for。"""

import sys, time

sys.path.insert(0, "backend")

SERIAL = "b01ac8cb"
import uiautomator2 as u2
from app.services.android_agent.device_adapter import (
    UiautomatorTransport,
    AndroidDeviceAdapter,
    UiTarget,
    DeviceAdapterError,
)

d = u2.connect(SERIAL)
w, h = d.window_size()
PKG = "com.android.calculator2"
adapter = AndroidDeviceAdapter(UiautomatorTransport(d), package=PKG, width=int(w), height=int(h))


def allow():
    return None


def tap_any(target):
    adapter.tap(target, assert_write_allowed=allow)
    time.sleep(0.3)


results = {}

# 冷启动并关闭隐私弹窗
d.app_stop(PKG)
time.sleep(0.6)
d.app_start(PKG, wait=True)
time.sleep(1.8)
nodes = adapter.observe()
if any(n.text == "同意" for n in nodes):
    tap_any(UiTarget(resource_id="android:id/button1", text="同意"))
    nodes = adapter.observe()
results["dialog_dismissed"] = not any(n.text == "同意" for n in nodes)

# 先清零，避免上一轮残留
tap_any(UiTarget(resource_id=f"{PKG}:id/clr", text="C"))
nodes = adapter.observe()
display_before = [n.text for n in nodes if n.text and n.text.isdigit() and len(n.text) <= 3]
results["cleared"] = display_before

# 7 + 8 = ，数字用 resource_id、运算符用 content-desc（真机只有 desc）
tap_any(UiTarget(resource_id=f"{PKG}:id/digit_7", text="7"))
tap_any(UiTarget(resource_id=f"{PKG}:id/op_add", content_desc="加"))
tap_any(UiTarget(resource_id=f"{PKG}:id/digit_8", text="8"))
tap_any(UiTarget(resource_id=f"{PKG}:id/eq", content_desc="等于"))

nodes = adapter.observe()
all_texts = [n.text for n in nodes if n.text]
results["screen_texts"] = all_texts
results["assert_15"] = any(n.text == "15" for n in nodes)
results["assert_absent_correctly_false"] = not any(n.text == "999999" for n in nodes)

# 精确断言：结果元素唯一匹配
matches = [n for n in nodes if n.text == "15"]
results["exact_match_count"] = len(matches)

# back 键
adapter.press_back(assert_write_allowed=allow)
time.sleep(1.0)
results["foreground_after_back"] = d.app_current().get("package")

# swipe
d.app_start(PKG, wait=True)
time.sleep(1.2)
adapter.swipe("up", 0.3, assert_write_allowed=allow)
adapter.swipe("down", 0.3, assert_write_allowed=allow)
results["swipe"] = "ok"

# wait_for 成功与超时
found = adapter.wait_for(UiTarget(resource_id=f"{PKG}:id/digit_7", text="7"), timeout_ms=5000)
results["wait_for_found"] = bool(found)
try:
    adapter.wait_for(UiTarget(resource_id=f"{PKG}:id/nope"), timeout_ms=1200)
    results["wait_timeout_raised"] = False
except DeviceAdapterError as exc:
    results["wait_timeout_raised"] = exc.args[0] == "condition_timeout"

# 空目标必须拒绝
try:
    UiTarget()
    results["empty_target_rejected"] = False
except DeviceAdapterError as exc:
    results["empty_target_rejected"] = exc.args[0] == "empty_target"

for k, v in results.items():
    print(f"{k}: {v}")

passed = all(
    [
        results["dialog_dismissed"],
        results["assert_15"],
        results["assert_absent_correctly_false"],
        results["exact_match_count"] == 1,
        results["foreground_after_back"] == "com.oppo.launcher",
        results["wait_for_found"],
        results["wait_timeout_raised"],
        results["empty_target_rejected"],
    ]
)
print("ACTION MATRIX:", "PASS" if passed else "FAIL")
sys.exit(0 if passed else 1)
