"""ex2: gather vs TaskGroup vs manual wait. (Read docs/02 first.)

Same 1000 sleeps, three orchestration styles. The OUTPUT SHAPE differs:
  - gather: returns an ordered list (input order, re-sorted)
  - TaskGroup: structured; the block awaits everything on exit
  - manual create_task + wait: you manage the task list yourself
"""

import asyncio


async def one(i: int) -> int:
    await asyncio.sleep(0.01)   # a small "I/O wait"
    return i * 2


async def with_gather():
    # results come back IN INPUT ORDER, regardless of who finished first
    results = await asyncio.gather(*(one(i) for i in range(5)))
    return results


async def with_task_group():
    # The TaskGroup block AWAITS all of its tasks on exit. You must NOT read
    # t.result() inside the block (the task may still be running -> InvalidStateError).
    # Collect the refs inside, read them AFTER the block exits.
    tasks = []
    async with asyncio.TaskGroup() as tg:
        for i in range(5):
            tasks.append(tg.create_task(one(i)))
    out = [t.result() for t in tasks]     # safe: the block already awaited them
    out.sort()                              # deterministic order
    return out


async def with_manual_wait():
    tasks = [asyncio.create_task(one(i)) for i in range(5)]
    done, _ = await asyncio.wait(tasks)        # wait() returns sets; collect from `done`
    out = sorted(t.result() for t in done)
    return out


async def main():
    print("gather    :", await with_gather())
    print("taskgroup :", await with_task_group())
    print("manual wait:", await with_manual_wait())
    print("\nAll three produce the same set. gather = ordered convenience; TaskGroup = structured scoping;")
    print("manual wait = you own the task list. For the dup tool, TaskGroup + a Semaphore is the cleanest.")


if __name__ == "__main__":
    asyncio.run(main())
