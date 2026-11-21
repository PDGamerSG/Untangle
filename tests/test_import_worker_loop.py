"""Persistent worker loop: keeps polling, reconnects after failures and stops cleanly."""

from __future__ import annotations

import threading

from untangle.repositories.worker import serve


class FakeGraph:
    def __init__(self):
        self.closed = False

    def ensure_schema(self):
        return {}

    def close(self):
        self.closed = True


def test_loop_processes_queue_then_waits_until_stopped():
    stop = threading.Event()
    graphs, results = [], iter([True, True, False])

    def connect(require):
        graphs.append(FakeGraph())
        return graphs[-1]

    def process(graph):
        value = next(results, False)
        if not value:
            stop.set()
        return value

    assert serve(connect, stop, poll_seconds=0, process=process) == 2
    assert len(graphs) == 1 and graphs[0].closed


def test_loop_reconnects_after_a_failed_poll():
    stop = threading.Event()
    graphs, calls = [], []

    def connect(require):
        graphs.append(FakeGraph())
        return graphs[-1]

    def process(graph):
        calls.append(graph)
        if len(calls) == 1:
            raise OSError("connection reset")
        stop.set()
        return True

    assert serve(connect, stop, poll_seconds=0, process=process) == 1
    assert len(graphs) == 2
    assert graphs[0].closed and graphs[1].closed


def test_loop_survives_an_unreachable_database_until_stopped():
    stop = threading.Event()
    attempts = []

    def connect(require):
        attempts.append(1)
        if len(attempts) == 3:
            stop.set()
        raise RuntimeError("database paused")

    assert serve(connect, stop, poll_seconds=0, process=lambda graph: True) == 0
    assert len(attempts) == 3
