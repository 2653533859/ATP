"""Structured execution error codes (E2xxx / P1xxx) and Chinese repair suggestions for APP/UI runners."""

from __future__ import annotations

from typing import Any

E2001_ELEMENT_NOT_FOUND = "E2001_ELEMENT_NOT_FOUND"
E2002_WAIT_TIMEOUT = "E2002_WAIT_TIMEOUT"
E2003_ASSERT_TEXT_FAILED = "E2003_ASSERT_TEXT_FAILED"
E2004_ASSERT_IMAGE_FAILED = "E2004_ASSERT_IMAGE_FAILED"
E2005_IMAGE_NOT_MATCHED = "E2005_IMAGE_NOT_MATCHED"
E2006_OCR_NO_RESULT = "E2006_OCR_NO_RESULT"
E2007_INPUT_FAILED = "E2007_INPUT_FAILED"
E2008_APP_CONTROL_FAILED = "E2008_APP_CONTROL_FAILED"
E2009_CLICK_NO_EFFECT = "E2009_CLICK_NO_EFFECT"
E2010_IMAGE_AMBIGUOUS = "E2010_IMAGE_AMBIGUOUS"
E2011_IMAGE_TEMPLATE_INVALID = "E2011_IMAGE_TEMPLATE_INVALID"
E2012_IMAGE_UNSTABLE = "E2012_IMAGE_UNSTABLE"
E2013_IMAGE_MATCH_UNSUPPORTED = "E2013_IMAGE_MATCH_UNSUPPORTED"
E2101_DEVICE_CONNECTION_LOST = "E2101_DEVICE_CONNECTION_LOST"
E2102_WDA_SESSION_ERROR = "E2102_WDA_SESSION_ERROR"
E2201_INVALID_ARGS = "E2201_INVALID_ARGS"
E2999_EXECUTION_ERROR = "E2999_EXECUTION_ERROR"

ERROR_SUGGESTIONS: dict[str, str] = {
    E2001_ELEMENT_NOT_FOUND: "检查定位器是否正确、页面是否已加载；可在录制模式重新抓取该元素，或配置备选定位器。",
    E2002_WAIT_TIMEOUT: "确认页面跳转是否完成，适当增大步骤超时时间，或在该步骤前增加等待。",
    E2003_ASSERT_TEXT_FAILED: "核对期望文本与页面实际文案是否一致；页面加载较慢时在断言前增加等待。",
    E2004_ASSERT_IMAGE_FAILED: "确认模板图与当前页面一致；分辨率、主题或文案变化会影响匹配，必要时重新截取模板图。",
    E2005_IMAGE_NOT_MATCHED: "确认目标已出现在屏幕上，或重新截取更清晰、特征更独特的模板图。",
    E2006_OCR_NO_RESULT: "检查识别区域坐标与提取规则是否正确，确认区域内存在清晰文本。",
    E2007_INPUT_FAILED: "确认目标为可输入控件且已获得焦点；可先点击输入框再输入，或检查输入法状态。",
    E2008_APP_CONTROL_FAILED: "检查应用包名 / Bundle ID 是否正确、应用是否已安装在该设备上。",
    E2009_CLICK_NO_EFFECT: "检查元素是否可点击或被遮挡，必要时改用坐标点击或严格图像点击。",
    E2010_IMAGE_AMBIGUOUS: "屏幕上存在多个相似候选目标，请限定搜索区域或截取更具唯一特征的模板。",
    E2011_IMAGE_TEMPLATE_INVALID: "模板图片过小、纯色或缺少有效轮廓特征，请重新截取完整清晰的目标。",
    E2012_IMAGE_UNSTABLE: "目标在超时预算内未连续两帧稳定，请等待页面动画结束或适当增大超时时间。",
    E2013_IMAGE_MATCH_UNSUPPORTED: "当前运行节点缺少 strict-v1 图像匹配依赖（OpenCV/NumPy）或截图比例不兼容。",
    E2101_DEVICE_CONNECTION_LOST: "检查 USB/网络连接与 adb devices 状态，必要时重连设备或恢复租约。",
    E2102_WDA_SESSION_ERROR: "确认 WebDriverAgent / Appium 正在运行且端口映射正常，必要时重启 WDA 后重试。",
    E2201_INVALID_ARGS: "检查步骤参数配置或模板 SHA-256 绑定是否已失效。",
    E2999_EXECUTION_ERROR: "请结合步骤错误信息与设备日志排查，必要时重试或检查设备状态。",
}


class StepExecutionError(RuntimeError):
    """Structured step execution failure carrying error code, context, and side-effect submission flag."""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        context: dict[str, Any] | None = None,
        action_submitted: bool = False,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.context = context or {}
        self.action_submitted = action_submitted


def suggestion_for_error_code(error_code: str) -> str:
    return ERROR_SUGGESTIONS.get(error_code, ERROR_SUGGESTIONS[E2999_EXECUTION_ERROR])


def classify_step_failure(
    error_message: str | None,
    *,
    action: str = "",
    platform: str = "android",
    exc: Exception | None = None,
) -> tuple[str, str]:
    """Classify a step error message / exception into (error_code, chinese_suggestion)."""
    if isinstance(exc, StepExecutionError):
        return exc.error_code, suggestion_for_error_code(exc.error_code)

    text = str(error_message or (str(exc) if exc else "")).strip()
    lower = text.lower()
    act = str(action or "").strip().lower()

    for known_code in ERROR_SUGGESTIONS:
        if known_code in text:
            return known_code, suggestion_for_error_code(known_code)

    if any(k in lower for k in ("wda", "webdriveragent", "session not created", "invalid session")):
        return E2102_WDA_SESSION_ERROR, suggestion_for_error_code(E2102_WDA_SESSION_ERROR)
    if any(k in lower for k in ("device offline", "adb", "connection refused", "disconnect", "掉线", "连接丢失")):
        return E2101_DEVICE_CONNECTION_LOST, suggestion_for_error_code(E2101_DEVICE_CONNECTION_LOST)
    if act in {"click_image", "assert_image", "assert_visual_element"}:
        if "ambiguous" in lower or "歧义" in lower or "多个" in lower:
            return E2010_IMAGE_AMBIGUOUS, suggestion_for_error_code(E2010_IMAGE_AMBIGUOUS)
        if "unstable" in lower or "稳定" in lower:
            return E2012_IMAGE_UNSTABLE, suggestion_for_error_code(E2012_IMAGE_UNSTABLE)
        if act == "assert_image" or act == "assert_visual_element":
            return E2004_ASSERT_IMAGE_FAILED, suggestion_for_error_code(E2004_ASSERT_IMAGE_FAILED)
        return E2005_IMAGE_NOT_MATCHED, suggestion_for_error_code(E2005_IMAGE_NOT_MATCHED)
    if act == "assert_text" or ("断言" in lower and "text" in act):
        return E2003_ASSERT_TEXT_FAILED, suggestion_for_error_code(E2003_ASSERT_TEXT_FAILED)
    if act in {"start_app", "stop_app"}:
        return E2008_APP_CONTROL_FAILED, suggestion_for_error_code(E2008_APP_CONTROL_FAILED)
    if act == "input":
        return E2007_INPUT_FAILED, suggestion_for_error_code(E2007_INPUT_FAILED)
    if any(k in lower for k in ("timeout", "timed out", "超时")):
        return E2002_WAIT_TIMEOUT, suggestion_for_error_code(E2002_WAIT_TIMEOUT)
    if any(k in lower for k in ("not found", "未找到", "no such element", "不存在")):
        return E2001_ELEMENT_NOT_FOUND, suggestion_for_error_code(E2001_ELEMENT_NOT_FOUND)
    if platform == "ios" and "appium" in lower:
        return E2102_WDA_SESSION_ERROR, suggestion_for_error_code(E2102_WDA_SESSION_ERROR)
    return E2999_EXECUTION_ERROR, suggestion_for_error_code(E2999_EXECUTION_ERROR)
