"""相机结果或错误回包发送完毕后，才让出下一追赶拍。"""

import pickle
from threading import Event, Thread

import pytest

from session import Session
from session_clock import SessionClock
from session_process import _camera_loop


@pytest.mark.parametrize('failure', ('none', 'query', 'send'))
def test_catchup_waits_for_complete_camera_reply_and_errors_release_it(monkeypatch, failure):
    session = Session(track='test')
    session.start(countdown=False)
    clock = SessionClock(session)
    session._clock = clock
    sending, finish_send, ticked = Event(), Event(), Event()
    errors, payloads = [], []

    class Connection:
        first = True
        closed = False

        def recv(self):
            if self.first:
                self.first = False
                return (0., 0., 1.), (0., -3., 1.), 0.
            return None

        def send_bytes(self, payload):
            payloads.append(payload)
            sending.set()
            assert finish_send.wait(2.)
            if failure == 'send':
                raise BrokenPipeError('测试回包端关闭')

        def close(self):
            self.closed = True

    def query(start, end):
        if failure == 'query':
            raise ValueError('测试真实查询失败')
        return end

    connection = Connection()
    monkeypatch.setattr(session.simulation, 'camera_position', query)

    def camera():
        try:
            _camera_loop(connection, session)
        except BrokenPipeError as error:
            errors.append(error)

    def tick():
        clock.tick()
        ticked.set()

    camera_thread, tick_thread = Thread(target=camera), Thread(target=tick)
    try:
        camera_thread.start()
        assert sending.wait(1.)
        assert not clock.camera_idle.is_set()
        tick_thread.start()
        assert not ticked.wait(.05)
        finish_send.set()
        camera_thread.join(2.)
        tick_thread.join(2.)
        assert not camera_thread.is_alive() and not tick_thread.is_alive()
        assert ticked.is_set() and clock.camera_idle.is_set() and connection.closed
        success, result, _traceback = pickle.loads(payloads[0][1:])
        assert success == (failure != 'query')
        if failure == 'query':
            assert isinstance(result, ValueError)
        else:
            assert result == (0., -3., 1.)
        assert len(errors) == int(failure == 'send')
    finally:
        finish_send.set()
        clock.camera_idle.set()
        camera_thread.join(2.)
        if tick_thread.ident is not None:
            tick_thread.join(2.)
        session._clock = None
        session.simulation._query_lock = None
        session.close()
