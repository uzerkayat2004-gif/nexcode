import re

with open('nexcode/ui/prompt.py', 'r') as f:
    content = f.read()

# Add init vars
content = content.replace(
    "self._load_history()",
    "self._load_history()\n        self._history_lock: asyncio.Lock | None = None\n        self._background_tasks: set[asyncio.Task] = set()"
)

# Update _write_async
old_write_async = """        async def _write_async() -> None:
            if self.__class__._history_lock is None:
                self.__class__._history_lock = asyncio.Lock()
            async with self.__class__._history_lock:
                await asyncio.to_thread(_write)"""
new_write_async = """        async def _write_async() -> None:
            if self._history_lock is None:
                self._history_lock = asyncio.Lock()
            async with self._history_lock:
                await asyncio.to_thread(_write)"""
content = content.replace(old_write_async, new_write_async)

# Update task creation
old_task = """            if loop.is_running():
                loop.create_task(_write_async())"""
new_task = """            if loop.is_running():
                task = loop.create_task(_write_async())
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)"""
content = content.replace(old_task, new_task)

with open('nexcode/ui/prompt.py', 'w') as f:
    f.write(content)
