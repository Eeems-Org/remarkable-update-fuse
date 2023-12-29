import ctypes
import threading


class KillableThread(threading.Thread):
    def run(self):
        try:
            super().run()

        except SystemExit:
            pass

    def kill(self):
        if not self.is_alive():
            return

        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(self.ident),
            ctypes.py_object(SystemExit),
        )

        if res == 0:
            raise ValueError(f"Invalid thread id: {self.ident}")

        if res == 1:
            return

        # "if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(self.ident),
            None,
        )
        raise SystemError("PyThreadState_SetAsyncExc failed")
