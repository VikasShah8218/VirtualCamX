"""Child-process helpers.

On Windows every child (FFmpeg, MediaMTX) is put into a Job Object with
KILL_ON_JOB_CLOSE, so if vcam_server dies for any reason the OS kills all children and
no orphan FFmpeg keeps publishing.
"""
import asyncio
import logging
import os
import subprocess
import sys

logger = logging.getLogger("vcam.proc")

_job_handle = None


def _windows_job():
    global _job_handle
    if _job_handle is not None or sys.platform != "win32":
        return _job_handle
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        job = kernel32.CreateJobObjectW(None, None)
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
        if not ok:
            logger.warning("SetInformationJobObject failed: %s", ctypes.get_last_error())
            return None
        _job_handle = (kernel32, job)
    except Exception:
        logger.exception("could not create Windows job object")
        _job_handle = None
    return _job_handle


def _assign_to_job(pid: int) -> None:
    job = _windows_job()
    if not job:
        return
    kernel32, handle = job
    from ctypes import wintypes

    kernel32.OpenProcess.restype = wintypes.HANDLE
    ph = kernel32.OpenProcess(0x0001 | 0x0100, False, pid)  # PROCESS_TERMINATE | PROCESS_SET_QUOTA
    if ph:
        kernel32.AssignProcessToJobObject(handle, ph)
        kernel32.CloseHandle(ph)


async def start_process(argv: list[str], cwd: str | None = None, merge_output: bool = False) -> asyncio.subprocess.Process:
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.PIPE,
        # merge_output: stdout is a pipe and stderr goes into it (read proc.stdout);
        # otherwise stdout is discarded and stderr is a pipe (FFmpeg logs to stderr)
        stdout=asyncio.subprocess.PIPE if merge_output else asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.STDOUT if merge_output else asyncio.subprocess.PIPE,
        cwd=cwd,
        **kwargs,
    )
    _assign_to_job(proc.pid)
    return proc


async def stop_process(proc: asyncio.subprocess.Process, graceful_input: bytes | None = b"q", timeout: float = 3.0) -> None:
    """Ask the process to quit (FFmpeg reads 'q' on stdin), then kill it."""
    if proc.returncode is not None:
        return
    try:
        if graceful_input and proc.stdin and not proc.stdin.is_closing():
            proc.stdin.write(graceful_input)
            await proc.stdin.drain()
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout)
        return
    except asyncio.TimeoutError:
        pass
    try:
        proc.kill()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(proc.wait(), timeout=5)
    except asyncio.TimeoutError:
        logger.error("process %s did not exit after kill", proc.pid)


async def run_capture(argv: list[str], timeout: float = 30.0) -> tuple[int, str, str]:
    """Run a short command and capture stdout/stderr (used for ffprobe, ffmpeg -filters...)."""
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    proc = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, stdin=asyncio.subprocess.DEVNULL, **kwargs
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, "", "timeout"
    return proc.returncode or 0, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


def ensure_dir(path) -> None:
    os.makedirs(path, exist_ok=True)
