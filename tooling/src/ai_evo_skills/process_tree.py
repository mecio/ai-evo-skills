"""Linux step-scoped process supervision, including detached orphan descendants."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import signal
import time


class ProcessTreeError(RuntimeError):
    pass


def _children(pid: int) -> set[int]:
    children: set[int] = set()
    for task in Path(f'/proc/{pid}/task').glob('*'):
        try:
            children.update(map(int, (task / 'children').read_text().split()))
        except (FileNotFoundError, ProcessLookupError):
            pass
    return children


def _birth(pid: int) -> str | None:
    try:
        # comm can contain spaces and closing parentheses; fields after its last
        # closing parenthesis start with state (field 3), then ppid (field 4).
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    except (FileNotFoundError, ProcessLookupError):
        return None


class ProcessTree:
    """Used by the dedicated CLI execution process, not a concurrent task runner.

    Linux reparents orphan descendants to this subreaper even if they call setsid
    or double-fork. pidfds keep cleanup tied to process identities, not reused PIDs.
    Children already present before the step, and their subtrees, are excluded.
    """

    def __init__(self) -> None:
        self.owner = os.getpid()
        self.handles: dict[int, tuple[str, int]] = {}
        self.existing = {pid: _birth(pid) for pid in _children(self.owner)}
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.previous = ctypes.c_int()
        try:
            probe = os.pidfd_open(self.owner)
            os.close(probe)
        except (AttributeError, OSError) as exc:
            raise ProcessTreeError('execution supervision requires Linux pidfd support (kernel 5.3+)') from exc
        if self.libc.prctl(37, ctypes.byref(self.previous), 0, 0, 0) != 0:
            raise ProcessTreeError('cannot read Linux child-subreaper state')
        if self.libc.prctl(36, 1, 0, 0, 0) != 0:
            raise ProcessTreeError('cannot enable Linux child-subreaper supervision')

    def refresh(self) -> None:
        pending, seen = [self.owner], set()
        while pending:
            parent = pending.pop()
            if parent in seen:
                continue
            seen.add(parent)
            for pid in _children(parent):
                birth = _birth(pid)
                if birth is None or (pid in self.existing and self.existing[pid] == birth):
                    continue
                pending.append(pid)
                if pid in self.handles and self.handles[pid][0] != birth:
                    self._drop(pid)
                if pid not in self.handles:
                    try:
                        fd = os.pidfd_open(pid)
                    except ProcessLookupError:
                        continue
                    # The process may have disappeared and its PID been reused
                    # between reading procfs and opening the identity handle.
                    if _birth(pid) != birth:
                        os.close(fd)
                        continue
                    self.handles[pid] = (birth, fd)

    def _drop(self, pid: int) -> None:
        _, fd = self.handles.pop(pid)
        os.close(fd)

    def _signal(self, pid: int, signum: int) -> None:
        try:
            signal.pidfd_send_signal(self.handles[pid][1], signum)
        except ProcessLookupError:
            pass

    def _reap(self, leader) -> None:
        leader.poll()  # Let Popen retain the leader's actual exit status.
        for pid, (birth, _) in list(self.handles.items()):
            if pid != leader.pid:
                try:
                    os.waitpid(pid, os.WNOHANG)
                except ChildProcessError:
                    pass  # Still owned by a living intermediate parent.
            if _birth(pid) != birth:
                self._drop(pid)

    def _empty(self, leader) -> bool:
        if self.handles:
            return False
        # A parent can exit between reading its parent's children list and its
        # own procfs entry. Scan again to find newly adopted orphans.
        time.sleep(0.01)
        self.refresh()
        self._reap(leader)
        return not self.handles

    def stop(self, leader) -> None:
        # Repeated discovery covers children forked during TERM handling. Orphans
        # stay attached to the subreaper even after intermediate parents exit.
        deadline, notified = time.monotonic() + 2, set()
        while True:
            self.refresh()
            self._reap(leader)
            if self._empty(leader):
                return
            for pid, (birth, _) in self.handles.items():
                if (pid, birth) not in notified:
                    self._signal(pid, signal.SIGTERM)
                    notified.add((pid, birth))
            if time.monotonic() >= deadline:
                break
            time.sleep(0.02)
        deadline = time.monotonic() + 2
        while True:
            self.refresh()
            for pid in self.handles:
                self._signal(pid, signal.SIGKILL)
            self._reap(leader)
            if self._empty(leader):
                return
            if time.monotonic() >= deadline:
                raise ProcessTreeError('could not reap all delegated descendants after SIGKILL')
            time.sleep(0.02)

    def close(self) -> None:
        for pid in list(self.handles):
            self._drop(pid)
        if self.libc.prctl(36, self.previous.value, 0, 0, 0) != 0:
            raise ProcessTreeError('cannot restore Linux child-subreaper state')
