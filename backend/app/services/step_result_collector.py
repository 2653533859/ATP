import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_STEP_BATCH_SIZE = 5
DEFAULT_STEP_FLUSH_INTERVAL = 1.0


class StepResultBatchCollector:
    """用例步骤执行结果批处理缓冲写入器。

    解决高频高并发测试下每个步骤均同步执行 `db.commit()` 导致的数据库行锁争用与 I/O 阻塞。
    在缓冲步骤结果的同时，支持按数量阈值（batch_size）与时间窗口（flush_interval）分批提交，
    并在上下文管理器退出（__aexit__）时确保全部未提交步骤兜底持久化。
    """

    def __init__(
        self,
        db: Any,
        *,
        batch_size: int = DEFAULT_STEP_BATCH_SIZE,
        flush_interval: float = DEFAULT_STEP_FLUSH_INTERVAL,
    ) -> None:
        self.db = db
        self.batch_size = max(1, batch_size)
        self.flush_interval = max(0.1, flush_interval)
        self._pending_count: int = 0
        self._last_flush_time: float = time.monotonic()

    async def add(self, step_result: Any, *, flush: bool = False) -> None:
        """向数据库会话添加步骤结果，并在满足阈值时执行批处理提交。

        :param step_result: StepResult 模型实例或测试替身
        :param flush: 是否强制立即提交（例如 AI 自愈需要立即生成 step_result.id）
        """
        if hasattr(self.db, "add"):
            added_list = getattr(self.db, "added", None)
            if added_list is None or step_result not in added_list:
                self.db.add(step_result)
        self._pending_count += 1

        elapsed = time.monotonic() - self._last_flush_time
        if flush or self._pending_count >= self.batch_size or elapsed >= self.flush_interval:
            await self.flush()

    async def flush(self) -> None:
        """将当前缓冲区内所有待提交的步骤结果一次性提交至数据库。"""
        if self._pending_count <= 0:
            return

        try:
            if hasattr(self.db, "commit"):
                commit_result = self.db.commit()
                if hasattr(commit_result, "__await__"):
                    await commit_result
            self._pending_count = 0
            self._last_flush_time = time.monotonic()
        except Exception:
            logger.exception("Failed to flush batched StepResults to database")
            raise

    async def __aenter__(self) -> "StepResultBatchCollector":
        self._last_flush_time = time.monotonic()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # 无论正常退出还是发生异常，均确保已缓冲但尚未提交的 StepResult 强刷入库
        try:
            await self.flush()
        except Exception:
            if exc_type is None:
                raise
            logger.exception("Error flushing remaining StepResults during exception exit")
