import asyncio
from collections import deque
from functools import wraps
from threading import Condition, Lock, Thread
from typing import Any, AsyncIterator, Callable, Deque, Dict, Generic, Iterable, Iterator, Optional, Tuple, TypeVar

T = TypeVar("T")


class SyncIteratorWrapper(Generic[T]):
    def __init__(
            self,
            to_wrap: Callable[..., Iterator[T]],
            args: Iterable[Any],
            kwargs: Dict[str, Any],
            poll_interval: float = 0.1
    ):
        self.wrapped: Callable[..., Iterator[T]] = to_wrap
        self.args: Tuple[Any, ...] = tuple(args)
        self.kwargs: Dict[str, Any] = kwargs
        self.thread: Optional[Thread] = None
        self.condition: Optional[Condition] = None
        self.result_queue: Deque[T] = deque()
        self.poll_interval: float = poll_interval

    def __getattr__(self, item):
        return getattr(self.wrapped, item)

    def __iter__(self):
        return self.wrapped(*self.args, **self.kwargs)

    def _run(self):
        for result in self.wrapped(*self.args, **self.kwargs):
            with self.condition:
                self.result_queue.append(result)

    def __aiter__(self):
        if self.thread is None:
            self.condition: Condition = Condition(Lock())
            self.thread = Thread(target=self._run)
            self.thread.start()
        return self

    async def __anext__(self):
        while True:
            with self.condition:
                if self.result_queue:
                    return self.result_queue.popleft()
                elif self.thread is None or not self.thread.is_alive():
                    # The thread finished and there are no more results
                    self.thread = None
                    raise StopAsyncIteration
            await asyncio.sleep(self.poll_interval)


def iterator_to_async(to_wrap: Callable[..., Iterator[T]]) -> Callable[..., AsyncIterator[T]]:
    """Decorator to automatically convert a synchronous function that returns an iterator to be asynchronous"""
    @wraps(to_wrap)
    def wrapper(*args, **kwargs):
        return SyncIteratorWrapper(to_wrap, args, kwargs)
    return wrapper
