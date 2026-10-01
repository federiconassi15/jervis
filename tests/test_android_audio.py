import queue
import socket

import pytest

from jervis.audio.android import AndroidAudioSource


class TimeoutSocket:
    def settimeout(self, value):
        self.value = value

    def recv(self, size):
        raise socket.timeout()


def test_read_timeout_becomes_queue_empty():
    source = AndroidAudioSource(adb_path="adb")
    source.sock = TimeoutSocket()
    with pytest.raises(queue.Empty):
        source.read(frames=160, timeout=0.1)
