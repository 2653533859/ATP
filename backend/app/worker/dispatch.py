def is_web_lowcode_config(cfg: dict | None) -> bool:
    if not isinstance(cfg, dict):
        return False
    # 只要显式存在 steps 字段，就走低代码执行器（包含空数组场景）
    return "steps" in cfg
