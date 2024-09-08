import sys
import time
import fuse

from threading import Thread

from remarkable_update_fuse import KillableThread
from remarkable_update_fuse.fuse import lock
from remarkable_update_fuse.fuse import _lock
from remarkable_update_fuse.fuse import FuseArgs

FAILED = False


def assert_value(name, value, expected):
    global FAILED
    print(f"checking {name}: ", end="")

    if value != expected:
        print("fail")
        FAILED = True
        print(f"  {value} != {expected}")
        return

    print("pass")


def assert_true(name, value):
    global FAILED
    print(f"checking {name}: ", end="")

    if not value:
        print("fail")
        FAILED = True
        return

    print("pass")


def assert_subclass(value, cls):
    global FAILED
    print(f"checking {value.__name__} is subclass of {cls.__name__}: ", end="")

    if not issubclass(value, cls):
        print("fail")
        FAILED = True
        return

    print("pass")


assert_subclass(KillableThread, Thread)


def _while_true():
    while True:
        pass


thread = KillableThread(
    target=_while_true,
    name="while-true",
)
thread.start()
assert_true("thread.is_alive()", thread.is_alive())
thread.kill()
time.sleep(0.1)  # Wait for thread to exit
assert_true("not thread.is_alive()", not thread.is_alive())

assert_true("not locked", not _lock.locked())
with lock():
    assert_true("locked", _lock.locked())

assert_true("not locked", not _lock.locked())

assert_value("fuse.fuse_python_api", fuse.fuse_python_api, (0, 2))

assert_value(
    "FuseArgs.__str__",
    str(FuseArgs()),
    """
< None on None:
  {'showhelp': False, 'showversion': False, 'foreground': False}
  -o (none) >
""".strip(),
)

if FAILED:
    sys.exit(1)
