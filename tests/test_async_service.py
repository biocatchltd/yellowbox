from asyncio import gather, sleep
from time import perf_counter

from pytest import mark

from yellowbox import RunMixin, YellowService
from yellowbox.subclasses import AsyncRunMixin


class BaseSleepService(YellowService):
    living_services = 0

    def start(self):
        type(self).living_services += 1

    def stop(self):
        type(self).living_services -= 1

    def is_alive(self) -> bool:
        return True


class SleepService(BaseSleepService, RunMixin, AsyncRunMixin):
    # a silly service that sleeps on startup
    def __init__(self, dc, sleep_time):
        self.sleep_time = sleep_time

    def start(self):
        raise AssertionError("should not be called")

    async def astart(self, retry_spec=None) -> object:
        super().start()
        await sleep(self.sleep_time)

    async def astop(self, *args, **kwargs) -> None:
        super().stop(*args, **kwargs)
        await sleep(self.sleep_time)

    def stop(self):
        raise AssertionError("should not be called")


@mark.asyncio
async def test_async_service():
    service_contexts = [SleepService.arun(None, sleep_time=0.1 * x) for x in range(1, 4)]
    t = perf_counter()
    await gather(*(s.__aenter__() for s in service_contexts))
    assert perf_counter() - t < 0.4
    await gather(*(s.__aexit__(None, None, None) for s in service_contexts))
    assert perf_counter() - t < 0.7

    assert BaseSleepService.living_services == 0
