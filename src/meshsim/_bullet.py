"""PyBullet import and client creation without its banner lines."""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
from contextlib import contextmanager


def _flush_c_stdio() -> None:
    # C stdio buffers output when stdout is not a terminal; flush it while it still points at devnull.
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c") or None)
        libc.fflush(None)
    except (OSError, AttributeError):
        pass


@contextmanager
def quiet_output():
    """Silence C-level writes to stdout and stderr (PyBullet prints on import and connect)."""
    # Use the process-level descriptors: sys.stdout may be a Python object without one (pytest, notebooks).
    streams = [1, 2]
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (AttributeError, OSError, ValueError):
            pass
    saved = [os.dup(fd) for fd in streams]
    try:
        with open(os.devnull, "w") as devnull:
            for fd in streams:
                os.dup2(devnull.fileno(), fd)
            try:
                yield
            finally:
                _flush_c_stdio()
    finally:
        for fd, copy in zip(streams, saved, strict=True):
            os.dup2(copy, fd)
            os.close(copy)


with quiet_output():
    import pybullet as p
    from pybullet_utils.bullet_client import BulletClient


def new_client() -> BulletClient:
    with quiet_output():
        return BulletClient(connection_mode=p.DIRECT)


__all__ = ["BulletClient", "new_client", "p"]
