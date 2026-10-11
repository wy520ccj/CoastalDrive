"""车辆数值进程的有界双向共享槽；管道不再逐车复制完整状态。"""

import struct
import time
from multiprocessing.shared_memory import SharedMemory

from physics_wire import write_numeric

SLOTS = 4
CAPACITY = 131072
_size = struct.Struct('<Q')
_stride = CAPACITY + _size.size


class PhysicsChannel:
    def __init__(self, name, slot, outgoing, incoming, *, child=False):
        self.memory = SharedMemory(name=name)
        self.slot = slot
        self.outgoing = outgoing
        self.incoming = incoming
        self.child = child
        self.write_index = 0
        self.read_index = 0
        self.ready = False
        self.peer = None

    def _wait(self, semaphore, timeout=30.):
        if semaphore.acquire(False):
            return
        if timeout is None and self.peer is None:
            semaphore.acquire()
            return
        deadline = time.monotonic() + timeout if timeout is not None else None
        while True:
            if self.peer is not None and not self.peer.is_alive():
                raise EOFError('车辆数值进程已退出')
            remaining = deadline - time.monotonic() if deadline is not None else 1.
            if remaining <= 0:
                raise TimeoutError('车辆数值进程共享槽等待超时')
            if semaphore.acquire(timeout=min(.1 if deadline is not None else 1., remaining)):
                return

    @staticmethod
    def allocation_size(workers):
        return workers * 2 * SLOTS * _stride

    def _offset(self, index, direction):
        return ((self.slot * 2 + direction) * SLOTS + index % SLOTS) * _stride

    def send_bytes(self, packet):
        if len(packet) > CAPACITY:
            raise BufferError('车辆数值包超过共享槽容量')
        free, ready = self.outgoing
        self._wait(free)
        offset = self._offset(self.write_index, int(self.child))
        _size.pack_into(self.memory.buf, offset, len(packet))
        self.memory.buf[offset + _size.size:offset + _size.size + len(packet)] = packet
        self.write_index += 1
        ready.release()

    def send_numeric(self, header, record):
        if len(header) > CAPACITY:
            raise BufferError('车辆数值包头超过共享槽容量')
        free, ready = self.outgoing
        self._wait(free)
        offset = self._offset(self.write_index, int(self.child))
        start = offset + _size.size
        sent = False
        try:
            self.memory.buf[start:start + len(header)] = header
            with self.memory.buf[start + len(header):start + CAPACITY] as target:
                length = write_numeric(record, target)
            _size.pack_into(self.memory.buf, offset, len(header) + length)
            sent = True
        finally:
            if not sent:
                free.release()
        self.write_index += 1
        ready.release()

    def poll(self, timeout=0.):
        if not self.ready:
            self.ready = (self.incoming[1].acquire(False) if timeout == 0.
                          else self.incoming[1].acquire(timeout=timeout))
        return self.ready

    def receive_view(self):
        if not self.ready:
            # 菜单/暂停可无限期空闲；父进程等待已提交的求解才需要超时。
            self._wait(self.incoming[1], None if self.child else 30.)
        self.ready = False
        offset = self._offset(self.read_index, int(not self.child))
        size, = _size.unpack_from(self.memory.buf, offset)
        if size > CAPACITY:
            raise ValueError('车辆共享槽长度无效')
        return self.memory.buf[offset + _size.size:offset + _size.size + size]

    def release_view(self, packet):
        packet.release()
        self.read_index += 1
        self.incoming[0].release()

    def recv_bytes(self):
        packet = self.receive_view()
        try:
            return bytes(packet)
        finally:
            self.release_view(packet)

    def close(self):
        self.memory.close()
