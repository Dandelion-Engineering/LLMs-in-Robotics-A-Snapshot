"""Read-only Windows process and TCP ownership proof for a registered Popen.

No process discovery, guessed ownership, elevation, or executable-name fallback.
The executable digest identifies the expected on-disk binary, not a memory-image
attestation. Each admission rechecks its file identity and the live process.
"""
from __future__ import annotations
import ctypes
import copy
from ctypes import wintypes
import hashlib
import os
from pathlib import Path
import socket
import struct
import subprocess
import threading
import time


class OwnerError(ValueError):
    pass


def require(value, reason):
    if not value:
        raise OwnerError(reason)


def file_identity(path):
    path = Path(path).resolve(strict=True)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    after = path.stat()
    fingerprint = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    require(fingerprint(before) == fingerprint(after), 'executable_changed_during_registration')
    return {'path': str(path), 'sha256': digest.hexdigest(), 'bytes': after.st_size,
            'file_identity': list(fingerprint(after))}


class WindowsOwnerAPI:
    def __init__(self):
        require(os.name == 'nt', 'windows_owner_api_required')
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.iphlp = ctypes.WinDLL('iphlpapi', use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        self.kernel.GetProcessTimes.restype = wintypes.BOOL
        self.kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.GetExitCodeProcess.restype = wintypes.BOOL
        self.kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self.iphlp.GetExtendedTcpTable.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL,
                                                  wintypes.ULONG, ctypes.c_int, wintypes.ULONG]
        self.iphlp.GetExtendedTcpTable.restype = wintypes.DWORD

    def process(self, pid):
        handle = self.kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        require(bool(handle), 'process_query_denied_or_missing')
        try:
            created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
            require(self.kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                               ctypes.byref(kernel), ctypes.byref(user)), 'process_times_unavailable')
            exit_code = wintypes.DWORD()
            require(self.kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code)), 'process_liveness_unavailable')
            require(exit_code.value == 259, 'owner_process_exited')
            size = wintypes.DWORD(32768); buffer = ctypes.create_unicode_buffer(size.value)
            require(self.kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)), 'process_executable_unavailable')
            return {'pid': pid, 'process_creation_filetime': (created.dwHighDateTime << 32) | created.dwLowDateTime,
                    'queried_executable_path': str(Path(buffer.value).resolve(strict=True))}
        finally:
            self.kernel.CloseHandle(handle)

    def tcp4(self):
        class Row(ctypes.Structure):
            _fields_ = [(k, wintypes.DWORD) for k in ('state', 'local_addr', 'local_port', 'remote_addr', 'remote_port', 'pid')]
        size = wintypes.DWORD()
        status = self.iphlp.GetExtendedTcpTable(None, ctypes.byref(size), False, 2, 5, 0)
        require(status in (0, 122) and 4 <= size.value <= 16 * 1024 * 1024, 'tcp_table_size_unavailable')
        buffer = ctypes.create_string_buffer(size.value)
        status = self.iphlp.GetExtendedTcpTable(buffer, ctypes.byref(size), False, 2, 5, 0)
        require(status == 0, 'tcp_table_unavailable')
        count = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD))[0]
        require(4 + count * ctypes.sizeof(Row) <= size.value, 'tcp_table_truncated')
        rows = []
        for i in range(count):
            row = Row.from_buffer_copy(buffer, 4 + i * ctypes.sizeof(Row))
            addr = lambda v: socket.inet_ntoa(struct.pack('=I', v))
            rows.append({'state': int(row.state), 'pid': int(row.pid),
                         'local': (addr(row.local_addr), socket.ntohs(row.local_port & 0xffff)),
                         'remote': (addr(row.remote_addr), socket.ntohs(row.remote_port & 0xffff))})
        return rows


class OwnerRegistry:
    def __init__(self, *, api=None, process_type=subprocess.Popen, owner_kind='model_client', clock=time.monotonic, sleep=time.sleep):
        require(owner_kind in ('model_client', 'transport_probe'), 'unknown_owner_kind')
        self.api = api if api is not None else WindowsOwnerAPI()
        self.process_type, self.owner_kind, self.clock, self.sleep = process_type, owner_kind, clock, sleep
        self.lock = threading.RLock()
        self.owner = self.process = None

    def register(self, process, binary_path):
        with self.lock:
            require(self.owner is None, 'duplicate_owner_registration')
            require(isinstance(process, self.process_type) and type(process.pid) is int and process.pid > 0,
                    'actual_popen_process_required')
            require(process.poll() is None, 'owner_process_exited')
            executable = file_identity(binary_path)
            observed = self.api.process(process.pid)
            require(observed['pid'] == process.pid and type(observed['process_creation_filetime']) is int
                    and observed['process_creation_filetime'] > 0, 'invalid_process_identity')
            require(os.path.normcase(observed['queried_executable_path']) == os.path.normcase(executable['path']),
                    'owner_executable_mismatch')
            require(process.poll() is None, 'owner_process_exited')
            self.owner = {'schema': 'campaign002-native-owner-1', 'owner_kind': self.owner_kind, **observed,
                          'executable': executable, 'wall_unix_s': time.time(), 'monotonic_s': self.clock()}
            self.process = process
            return copy.deepcopy(self.owner)

    def _live(self):
        require(self.owner is not None, 'owner_not_registered')
        require(self.process.pid == self.owner['pid'] and self.process.poll() is None, 'owner_process_exited_or_changed')
        current = self.api.process(self.owner['pid'])
        require(all(current.get(k) == self.owner[k] for k in ('pid', 'process_creation_filetime', 'queried_executable_path')),
                'owner_identity_changed_or_pid_reused')
        path = Path(self.owner['executable']['path']); stat = path.stat()
        require([stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns] == self.owner['executable']['file_identity'],
                'owner_executable_file_changed')

    def authenticate(self, client, server):
        client, server = tuple(client), tuple(server)
        require(len(client) == len(server) == 2 and client[0] == server[0] == '127.0.0.1'
                and all(type(x[1]) is int and 0 < x[1] < 65536 for x in (client, server)), 'invalid_ipv4_loopback_tuple')
        with self.lock:
            self._live()
            started = self.clock(); attempts = 0
            while True:
                attempts += 1
                self._live()
                matches = [r for r in self.api.tcp4() if tuple(r['local']) == client and tuple(r['remote']) == server]
                require(len(matches) <= 1, 'ambiguous_tcp_owner')
                if matches:
                    row = matches[0]
                    require(row['pid'] == self.owner['pid'], 'foreign_tcp_owner')
                    require(row['state'] == 5, 'tcp_owner_not_established')
                    self._live()
                    require(self.clock() - started <= .250, 'owner_lookup_deadline')
                    return {'schema': 'campaign002-channel-owner-1', 'owner_pid': self.owner['pid'],
                            'process_creation_filetime': self.owner['process_creation_filetime'],
                            'queried_executable_path': self.owner['queried_executable_path'],
                            'executable_sha256': self.owner['executable']['sha256'],
                            'executable_file_identity': list(self.owner['executable']['file_identity']),
                            'client': list(client), 'server': list(server), 'tcp_state': 5,
                            'lookup_attempts': attempts, 'lookup_elapsed_s': self.clock() - started,
                            'wall_unix_s': time.time(), 'monotonic_s': self.clock()}
                if self.clock() - started >= .250:
                    raise OwnerError('tcp_owner_missing')
                self.sleep(min(.010, max(0, .250 - (self.clock() - started))))
