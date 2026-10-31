# SPDX-License-Identifier: GPL-3.0-only
import os

def configure_process_lifetime():
    """Close tool descendants when VS Code's Stop button terminates this runner."""
    if os.name != 'nt':
        return
    import ctypes
    from ctypes import wintypes

    class Limits(ctypes.Structure):
        _fields_ = [('processTime', ctypes.c_int64), ('jobTime', ctypes.c_int64),
            ('flags', wintypes.DWORD), ('minWorkingSet', ctypes.c_size_t),
            ('maxWorkingSet', ctypes.c_size_t), ('activeProcesses', wintypes.DWORD),
            ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
            ('scheduling', wintypes.DWORD)]

    class JobInfo(ctypes.Structure):
        _fields_ = [('limits', Limits), ('ioCounters', ctypes.c_uint64 * 6),
            ('processMemory', ctypes.c_size_t), ('jobMemory', ctypes.c_size_t),
            ('peakProcessMemory', ctypes.c_size_t), ('peakJobMemory', ctypes.c_size_t)]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    info = JobInfo()
    info.limits.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
        error = ctypes.get_last_error()
        kernel.CloseHandle(handle)
        raise ctypes.WinError(error)
    if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
        error = ctypes.get_last_error()
        kernel.CloseHandle(handle)
        raise ctypes.WinError(error)
    # Keep the non-inheritable handle until Windows closes it on process exit.
    # The child Arduino CLI and its serial-monitor process inherit job membership.
    return handle
