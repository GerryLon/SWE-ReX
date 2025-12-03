import asyncio
import logging
from abc import ABC, abstractmethod

from swerex.deployment.hooks.abstract import DeploymentHook
from swerex.runtime.abstract import AbstractRuntime, IsAliveResponse

__all__ = ["AbstractDeployment"]


class AbstractDeployment(ABC):
    def __init__(self, *args, **kwargs):
        self.logger: logging.Logger

    @abstractmethod
    def add_hook(self, hook: DeploymentHook): ...

    @abstractmethod
    async def is_alive(self, *, timeout: float | None = None) -> IsAliveResponse:
        """Checks if the runtime is alive. The return value can be
        tested with bool().

        Raises:
            DeploymentNotStartedError: If the deployment was not started.
        """

    @abstractmethod
    async def start(self, *args, **kwargs):
        """Starts the runtime."""

    @abstractmethod
    async def stop(self, *args, **kwargs):
        """Stops the runtime."""

    @property
    @abstractmethod
    def runtime(self) -> AbstractRuntime:
        """Returns the runtime if running.

        Raises:
            DeploymentNotStartedError: If the deployment was not started.
        """

    def __del__(self):
        """Stops the runtime when the object is deleted."""
        # Check if Python is shutting down
        # During shutdown, sys.meta_path and other globals may be None
        import sys
        if sys.meta_path is None or sys is None:
            # Python is shutting down, skip cleanup to avoid errors
            return
        
        # Need to be check whether we are in an async event loop or not
        # https://stackoverflow.com/questions/54770360/
        msg = "Ensuring deployment is stopped because object is deleted"
        try:
            self.logger.debug(msg)
        except Exception:
            print(msg)
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # 没有事件循环，无法执行异步清理
            try:
                self.logger.warning("No event loop available in __del__, skipping cleanup")
            except Exception:
                print("No event loop available in __del__, skipping cleanup")
            return
        
        if loop.is_running():
            # 事件循环正在运行，创建任务但不等待
            # 注意：这不保证任务会执行完成
            try:
                task = loop.create_task(self.stop())
                # 添加回调来记录任务完成情况
                def _log_task_done(t):
                    import sys
                    if sys.meta_path is None:
                        return  # Python is shutting down
                    try:
                        if t.exception():
                            try:
                                self.logger.error(f"Error in __del__ cleanup task: {t.exception()}")
                            except Exception:
                                print(f"Error in __del__ cleanup task: {t.exception()}")
                    except Exception:
                        pass
                task.add_done_callback(_log_task_done)
            except Exception as e:
                import sys
                if sys.meta_path is None:
                    return  # Python is shutting down
                try:
                    self.logger.error(f"Failed to create cleanup task in __del__: {e}")
                except Exception:
                    print(f"Failed to create cleanup task in __del__: {e}")
        else:
            # 事件循环未运行，尝试同步执行但添加超时保护
            try:
                # 使用 asyncio.wait_for 添加超时保护（默认 30 秒）
                loop.run_until_complete(
                    asyncio.wait_for(self.stop(), timeout=30.0)
                )
            except asyncio.TimeoutError:
                import sys
                if sys.meta_path is None:
                    return  # Python is shutting down
                try:
                    self.logger.warning("Timeout during __del__ cleanup (30s), forcing exit")
                except Exception:
                    print("Timeout during __del__ cleanup (30s), forcing exit")
            except Exception as e:
                import sys
                if sys.meta_path is None:
                    return  # Python is shutting down
                try:
                    self.logger.error(f"Error during __del__ cleanup: {e}")
                except Exception:
                    print(f"Error during __del__ cleanup: {e}")
