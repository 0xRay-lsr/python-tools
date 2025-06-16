import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from typing import Any, List, TypeVar, Generic, Callable, Dict, Optional, Union

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 定义泛型类型
T = TypeVar('T')  # 任务类型
R = TypeVar('R')  # 结果类型


class TaskStatus:
    """任务状态枚举"""
    PENDING = "等待中"
    RUNNING = "执行中"
    COMPLETED = "已完成"
    FAILED = "失败"
    TIMEOUT = "超时"
    RETRYING = "重试中"


class TaskResult(Generic[R]):
    """任务结果包装类"""
    def __init__(self, task_id: int, original_task: Any):
        self.task_id = task_id
        self.original_task = original_task
        self.result: Optional[R] = None
        self.status = TaskStatus.PENDING
        self.error_message: Optional[str] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.retry_count = 0

    @property
    def execution_time(self) -> Optional[float]:
        """获取任务执行时间（秒）"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    def __str__(self) -> str:
        return (f"任务ID: {self.task_id}, 状态: {self.status}, "
                f"重试次数: {self.retry_count}, 执行时间: {self.execution_time or '未完成'}")


class MultiThreadProcessorWithResult(Generic[T, R]):
    """
    多线程任务处理器，支持结果收集、自动重试、超时控制和进度跟踪

    特性:
    - 类型安全的泛型实现
    - 详细的任务状态跟踪
    - 自动重试机制
    - 超时控制
    - 进度报告
    - 结构化的结果收集
    """
    def __init__(self, max_workers: int = 5, retry: int = 2, timeout: float = 10.0):
        """
        初始化多线程处理器

        参数:
            max_workers: 最大工作线程数
            retry: 任务失败后的最大重试次数
            timeout: 单个任务的超时时间（秒）
        """
        self.max_workers = max_workers
        self.retry = retry
        self.timeout = timeout
        self.lock = threading.Lock()
        self.task_results: Dict[int, TaskResult[R]] = {}
        self.total_tasks = 0
        self.completed_tasks = 0

    def run(self, tasks: List[T]) -> List[Optional[R]]:
        """
        执行多线程任务，返回所有任务的结果

        参数:
            tasks: 待执行的任务列表

        返回:
            任务结果列表，与输入任务顺序一致
        """
        self.total_tasks = len(tasks)
        self.completed_tasks = 0
        results: List[Optional[R]] = []

        # 初始化任务结果跟踪
        self.task_results = {
            i: TaskResult(i, task) for i, task in enumerate(tasks)
        }

        logger.info(f"开始处理 {self.total_tasks} 个任务，最大线程数: {self.max_workers}")
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_task_id: Dict[Future, int] = {
                executor.submit(self._run_with_retry, task_id): task_id 
                for task_id, task in enumerate(tasks)
            }

            # 处理完成的任务
            for future in as_completed(future_to_task_id):
                task_id = future_to_task_id[future]
                task_result = self.task_results[task_id]

                try:
                    result = future.result(timeout=self.timeout)
                    task_result.result = result
                    task_result.status = TaskStatus.COMPLETED
                    results.append(result)
                except TimeoutError:
                    logger.warning(f"[超时] 任务 {task_id} 执行超时")
                    task_result.status = TaskStatus.TIMEOUT
                    task_result.error_message = "任务执行超时"
                    results.append(None)
                except Exception as e:
                    logger.error(f"[失败] 任务 {task_id} 异常: {str(e)}")
                    task_result.status = TaskStatus.FAILED
                    task_result.error_message = str(e)
                    results.append(None)
                finally:
                    task_result.end_time = time.time()
                    with self.lock:
                        self.completed_tasks += 1
                        self._report_progress()

        total_time = time.time() - start_time
        logger.info(f"所有任务处理完成，总耗时: {total_time:.2f}秒")
        return results

    def _run_with_retry(self, task_id: int) -> R:
        """
        执行任务并实现自动重试机制

        参数:
            task_id: 任务ID

        返回:
            任务处理结果

        异常:
            如果重试后仍然失败，则抛出最后一次的异常
        """
        task_result = self.task_results[task_id]
        task = task_result.original_task
        task_result.start_time = time.time()
        task_result.status = TaskStatus.RUNNING

        for attempt in range(self.retry + 1):  # +1 是因为第一次不算重试
            try:
                if attempt > 0:
                    task_result.status = TaskStatus.RETRYING
                    task_result.retry_count = attempt
                    logger.info(f"[重试] 任务 {task_id} 第 {attempt} 次重试")

                return self.process(task)

            except Exception as e:
                if attempt < self.retry:
                    logger.warning(f"[重试] 任务 {task_id} 第 {attempt+1} 次失败，原因：{str(e)}")
                    # 可以在这里添加重试延迟
                    time.sleep(0.1 * (attempt + 1))  # 指数退避策略
                else:
                    logger.error(f"[失败] 任务 {task_id} 已重试 {self.retry} 次仍然失败")
                    raise

    def process(self, task: T) -> R:
        """
        处理单个任务的方法，子类应该重写此方法

        参数:
            task: 要处理的任务

        返回:
            任务处理结果
        """
        logger.info(f"任务 {task} 正在处理...")
        return task  # type: ignore

    def _report_progress(self) -> None:
        """报告当前进度"""
        progress = (self.completed_tasks / self.total_tasks) * 100 if self.total_tasks > 0 else 0
        logger.info(f"进度: {progress:.1f}% ({self.completed_tasks}/{self.total_tasks})")

    def get_task_status(self) -> Dict[int, TaskResult[R]]:
        """获取所有任务的状态"""
        return self.task_results.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """获取任务执行统计信息"""
        if not self.task_results:
            return {"status": "未执行任务"}

        statuses = {}
        for result in self.task_results.values():
            statuses[result.status] = statuses.get(result.status, 0) + 1

        total_time = max((r.end_time or 0) for r in self.task_results.values()) - \
                    min((r.start_time or float('inf')) for r in self.task_results.values())

        return {
            "总任务数": self.total_tasks,
            "已完成": self.completed_tasks,
            "状态统计": statuses,
            "总耗时(秒)": total_time if total_time != float('inf') else 0
        }


class MyTaskProcessor(MultiThreadProcessorWithResult[Callable[[], R], R]):
    """示例任务处理器，处理可调用对象并返回其结果"""

    def process(self, task: Callable[[], R]) -> R:
        """
        处理可调用任务

        参数:
            task: 可调用对象，无参数

        返回:
            调用task()的结果
        """
        logger.info("任务开始处理...")
        return task()


def task_process() -> str:
    """示例任务函数"""
    logger.info("执行任务中...")
    # 模拟耗时操作
    time.sleep(0.5)
    return "我是task返回值"


def task_with_error() -> str:
    """会抛出异常的示例任务函数"""
    logger.info("执行可能失败的任务...")
    if random.random() < 0.7:  # 70%概率失败
        raise ValueError("随机错误")
    return "任务成功"


if __name__ == '__main__':
    import random

    # 创建一些示例任务
    tasks = [task_process, task_process]

    # 添加一些可能失败的任务
    for _ in range(3):
        tasks.append(task_with_error)

    # 创建处理器并执行任务
    processor = MyTaskProcessor(max_workers=3, retry=2, timeout=5.0)
    logger.info("开始执行任务...")

    # 执行任务并获取结果
    task_results = processor.run(tasks)

    # 打印结果
    logger.info("\n--- 任务结果 ---")
    for i, result in enumerate(task_results):
        logger.info(f"任务 {i} 结果: {result}")

    # 打印任务统计信息
    logger.info("\n--- 任务统计 ---")
    stats = processor.get_statistics()
    for key, value in stats.items():
        logger.info(f"{key}: {value}")

    # 打印详细的任务状态
    logger.info("\n--- 详细任务状态 ---")
    for task_id, task_result in processor.get_task_status().items():
        logger.info(f"{task_result}")
