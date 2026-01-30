"""
图执行与队列管理

职责：
- 执行 LangGraph 工作流
- 管理事件队列的消费
- 流式发送答案（打字机效果）
"""

import asyncio
import logging
from typing import AsyncGenerator, TYPE_CHECKING

from api.streaming import SSEEventBuilder, StateUpdateProcessor

if TYPE_CHECKING:
    from infra.database import DatabaseManager
    from infra.task_manager import TaskManager
    from agent.graph import PesticideAgent, AgentState

logger = logging.getLogger(__name__)


async def execute_with_checkpointer_and_queue(
    agent: "PesticideAgent",
    db: "DatabaseManager",
    initial_state: "AgentState",
    config: dict,
    processor: StateUpdateProcessor,
    session_id: str,
    task_manager: "TaskManager",
    step_queue: asyncio.Queue,
) -> AsyncGenerator[str, None]:
    """
    使用 checkpointer 执行图，同时监听事件队列

    使用并行消费模式：
    - 后台协程消费 step_queue 中的子图事件
    - 后台协程执行主图并处理状态更新
    - 主循环从 output_queue 读取事件并 yield

    Args:
        agent: Agent 实例
        db: 数据库管理器
        initial_state: 初始状态
        config: 图配置
        processor: 状态更新处理器
        session_id: 会话 ID
        task_manager: 任务管理器
        step_queue: 步骤事件队列

    Yields:
        SSE 事件字符串
    """
    output_queue: asyncio.Queue[str] = asyncio.Queue()
    graph_done = asyncio.Event()
    cancelled = False

    async def consume_step_queue():
        """后台协程：持续消费 step_queue 并推送到 output_queue"""
        nonlocal cancelled
        while not graph_done.is_set() or not step_queue.empty():
            try:
                step = await asyncio.wait_for(step_queue.get(), timeout=0.1)
                step_type = step.get("type", "unknown")
                if step_type != "answer":
                    sse_event = SSEEventBuilder.step_event(step)
                    await output_queue.put(sse_event)
                    if step_type == "thought":
                        processor.thinking_parts.append(step.get("content", ""))
                    processor.all_steps.append(step)
            except asyncio.TimeoutError:
                if graph_done.is_set() and step_queue.empty():
                    break
            except asyncio.CancelledError:
                break
        await output_queue.put("__queue_consumer_done__")

    async def run_graph():
        """后台协程：执行主图并推送事件到 output_queue"""
        nonlocal cancelled
        try:
            async with db.get_checkpointer() as checkpointer:
                graph = agent.get_compiled_graph(checkpointer=checkpointer, async_mode=True)

                async for event in graph.astream(initial_state, config=config):
                    if await task_manager.check_cancel_flag(session_id):
                        await output_queue.put("__cancelled__")
                        cancelled = True
                        return

                    for node_name, state_update in event.items():
                        if await task_manager.check_cancel_flag(session_id):
                            await output_queue.put("__cancelled__")
                            cancelled = True
                            return

                        for sse_event in processor.process_state_update(state_update):
                            await output_queue.put(sse_event)

        except ImportError:
            # 回退到无 checkpointer 模式
            graph = agent.get_compiled_graph(async_mode=True)
            async for event in graph.astream(initial_state, config=config):
                if await task_manager.check_cancel_flag(session_id):
                    await output_queue.put("__cancelled__")
                    cancelled = True
                    return

                for node_name, state_update in event.items():
                    for sse_event in processor.process_state_update(state_update):
                        await output_queue.put(sse_event)

        finally:
            graph_done.set()
            await output_queue.put("__graph_done__")

    # 启动两个后台任务
    queue_consumer_task = asyncio.create_task(consume_step_queue())
    graph_task = asyncio.create_task(run_graph())

    try:
        graph_finished = False
        queue_consumer_finished = False

        while not (graph_finished and queue_consumer_finished):
            try:
                event = await asyncio.wait_for(output_queue.get(), timeout=0.5)

                if event == "__graph_done__":
                    graph_finished = True
                    continue
                elif event == "__queue_consumer_done__":
                    queue_consumer_finished = True
                    continue
                elif event == "__cancelled__":
                    yield "__cancelled__"
                    return
                else:
                    yield event

            except asyncio.TimeoutError:
                if await task_manager.check_cancel_flag(session_id):
                    yield "__cancelled__"
                    return
                if graph_task.done() and queue_consumer_task.done():
                    break

    finally:
        graph_done.set()
        if not graph_task.done():
            graph_task.cancel()
            try:
                await graph_task
            except asyncio.CancelledError:
                pass
        if not queue_consumer_task.done():
            queue_consumer_task.cancel()
            try:
                await queue_consumer_task
            except asyncio.CancelledError:
                pass


async def execute_without_checkpointer_and_queue(
    agent: "PesticideAgent",
    initial_state: "AgentState",
    config: dict,
    processor: StateUpdateProcessor,
    session_id: str,
    task_manager: "TaskManager",
    step_queue: asyncio.Queue,
) -> AsyncGenerator[str, None]:
    """
    不使用 checkpointer 执行图，同时监听事件队列

    Args:
        agent: Agent 实例
        initial_state: 初始状态
        config: 图配置
        processor: 状态更新处理器
        session_id: 会话 ID
        task_manager: 任务管理器
        step_queue: 步骤事件队列

    Yields:
        SSE 事件字符串
    """
    output_queue: asyncio.Queue[str] = asyncio.Queue()
    graph_done = asyncio.Event()
    cancelled = False

    async def consume_step_queue():
        """后台协程：持续消费 step_queue 并推送到 output_queue"""
        nonlocal cancelled
        while not graph_done.is_set() or not step_queue.empty():
            try:
                step = await asyncio.wait_for(step_queue.get(), timeout=0.1)
                step_type = step.get("type", "unknown")
                if step_type != "answer":
                    sse_event = SSEEventBuilder.step_event(step)
                    await output_queue.put(sse_event)
                    if step_type == "thought":
                        processor.thinking_parts.append(step.get("content", ""))
                    processor.all_steps.append(step)
            except asyncio.TimeoutError:
                if graph_done.is_set() and step_queue.empty():
                    break
            except asyncio.CancelledError:
                break
        await output_queue.put("__queue_consumer_done__")

    async def run_graph():
        """后台协程：执行主图并推送事件到 output_queue"""
        nonlocal cancelled
        try:
            graph = agent.get_compiled_graph(async_mode=True)
            async for event in graph.astream(initial_state, config=config):
                if await task_manager.check_cancel_flag(session_id):
                    await output_queue.put("__cancelled__")
                    cancelled = True
                    return

                for node_name, state_update in event.items():
                    if await task_manager.check_cancel_flag(session_id):
                        await output_queue.put("__cancelled__")
                        cancelled = True
                        return

                    for sse_event in processor.process_state_update(state_update):
                        await output_queue.put(sse_event)
        finally:
            graph_done.set()
            await output_queue.put("__graph_done__")

    # 启动两个后台任务
    queue_consumer_task = asyncio.create_task(consume_step_queue())
    graph_task = asyncio.create_task(run_graph())

    try:
        graph_finished = False
        queue_consumer_finished = False

        while not (graph_finished and queue_consumer_finished):
            try:
                event = await asyncio.wait_for(output_queue.get(), timeout=0.5)

                if event == "__graph_done__":
                    graph_finished = True
                    continue
                elif event == "__queue_consumer_done__":
                    queue_consumer_finished = True
                    continue
                elif event == "__cancelled__":
                    yield "__cancelled__"
                    return
                else:
                    yield event

            except asyncio.TimeoutError:
                if await task_manager.check_cancel_flag(session_id):
                    yield "__cancelled__"
                    return
                if graph_task.done() and queue_consumer_task.done():
                    break

    finally:
        graph_done.set()
        if not graph_task.done():
            graph_task.cancel()
            try:
                await graph_task
            except asyncio.CancelledError:
                pass
        if not queue_consumer_task.done():
            queue_consumer_task.cancel()
            try:
                await queue_consumer_task
            except asyncio.CancelledError:
                pass


async def stream_answer(
    answer: str,
    session_id: str,
    task_manager: "TaskManager",
    chunk_size: int = 5,
) -> AsyncGenerator[str, None]:
    """
    流式发送答案（打字机效果）

    Args:
        answer: 完整答案
        session_id: 会话 ID
        task_manager: 任务管理器
        chunk_size: 每次发送的字符数

    Yields:
        SSE 事件字符串
    """
    for i in range(0, len(answer), chunk_size):
        if await task_manager.check_cancel_flag(session_id):
            yield "__cancelled__"
            return

        chunk = answer[i : i + chunk_size]
        yield SSEEventBuilder.answer_chunk_event(chunk, i // chunk_size)
        await asyncio.sleep(0.015)


__all__ = [
    "execute_with_checkpointer_and_queue",
    "execute_without_checkpointer_and_queue",
    "stream_answer",
]
