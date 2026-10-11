"""共享槽的原生写入、循环复用和真实子进程退出边界。"""

import time
from multiprocessing import get_context
from multiprocessing.shared_memory import SharedMemory

import pytest

from physics_channel import CAPACITY, SLOTS, PhysicsChannel
from physics_wire import from_bytes
from physics_workers import PhysicsWorkers
from vehicle_state import WheelDynamicsState


def test_bounded_slots_wrap_preserve_packets_and_recover_from_encode_error():
    context = get_context('spawn')
    outgoing = context.Semaphore(SLOTS), context.Semaphore(0)
    incoming = context.Semaphore(SLOTS), context.Semaphore(0)
    memory = SharedMemory(create=True, size=PhysicsChannel.allocation_size(1))
    parent = PhysicsChannel(memory.name, 0, outgoing, incoming)
    child = PhysicsChannel(memory.name, 0, incoming, outgoing, child=True)
    try:
        for round_ in range(3):
            for i in range(SLOTS):
                parent.send_bytes(bytes([round_, i]))
            assert not outgoing[0].acquire(False)
            for i in range(SLOTS):
                assert child.poll() and child.poll()
                assert child.recv_bytes() == bytes([round_, i])
            assert not child.poll()
        with pytest.raises(TypeError):
            parent.send_numeric(b'\2', object())
        with pytest.raises(BufferError):
            parent.send_numeric(b'\2', 'x' * CAPACITY)
        with pytest.raises(BufferError):
            parent.send_numeric(b'x' * (CAPACITY + 1), None)
        with pytest.raises(BufferError):
            parent.send_bytes(b'x' * (CAPACITY + 1))
        record = WheelDynamicsState(omega=-0., fx=125.5)
        for _ in range(SLOTS):
            parent.send_numeric(b'\2', record)
        for _ in range(SLOTS):
            packet = child.receive_view()
            try:
                assert packet[0] == 2
                assert from_bytes(packet[1:]) == record
            finally:
                child.release_view(packet)
        child.send_bytes(b'response')
        assert parent.recv_bytes() == b'response'
    finally:
        child.close()
        parent.close()
        memory.close()
        memory.unlink()


def test_dead_worker_is_reported_and_shared_memory_is_released():
    pool = PhysicsWorkers(1)
    pool._start()
    name = pool.channel_memories[0].name
    process, connection = pool.processes[0]
    process.terminate()
    process.join(5)
    try:
        with pytest.raises(EOFError, match='已退出'):
            connection.receive_view()
    finally:
        pool.close()
    with pytest.raises(FileNotFoundError):
        SharedMemory(name=name)


def test_idle_worker_survives_long_menu_pause_and_closes_cleanly():
    pool = PhysicsWorkers(1)
    pool._start()
    process, _connection = pool.processes[0]
    try:
        time.sleep(31.)
        assert process.is_alive()
    finally:
        pool.close()
