# Developers:   Yang Hu, et al.
# Email:    huyang0905@gmail.com

import os
import gc
import sys
import time
import psutil
import threading
import traceback
import resource
from io import StringIO


def run_program_to(code, front_code, end_code, entry_code, timeout):
    from basic_framework.holes import Holes

    thd = threading.Thread(target=run_core,
                           args=(code, front_code, end_code, entry_code))

    Holes.is_stop = False
    Holes.real_output = ""
    thd.start()
    thd.join(timeout=timeout)
    Holes.is_stop = True
    while thd.is_alive():
        time.sleep(0.2)
    Holes.is_stop = False
    return Holes.real_output


def run_core(code, front_code, end_code, entry_code):
    from basic_framework.f1x import DepthTrace
    from basic_framework.holes import Holes

    backup_stdout = sys.stdout
    sys.stdout = StringIO()

    hole_hdr_code = "from basic_framework.holes import *\n"

    if "print(" not in entry_code:
        entry_code = "print(" + entry_code.strip() + ")\n"

    final_code = hole_hdr_code + "\n\n" + \
                 front_code + "\n\n" + \
                 code + "\n\n" + \
                 end_code + "\n\n" + \
                 entry_code
    try:
        exec(final_code, globals())
    except DepthTrace.MaxDepthException:
        print("Reach max depth.", file=sys.stderr)
    except Holes.NoCandidateException:
        pass
    except Exception as e:
        pass

    real_output = sys.stdout.getvalue()

    if sys.stdout != backup_stdout:
        sys.stdout.close()
        sys.stdout = backup_stdout

    Holes.real_output = real_output


def fast_eval(expr, var_dict):
    if "lambda" not in expr:
        exp_as_func = eval('lambda var_dict: ' + expr)
        return exp_as_func(var_dict)
    return eval(expr)


class MemoryGuarder:
    def __init__(self):
        self.mc = 0
        self.bound = 4 # GB
        self.set_max_runtime(self.bound*1024*1024*1024)

    def set_max_runtime(self, maxsize):
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        resource.setrlimit(resource.RLIMIT_AS, (maxsize, hard))