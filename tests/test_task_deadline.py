import signal

import pytest

from agent_smith.agent.deadline import TaskDeadline, TaskDeadlineExceeded


def test_task_deadline_rejects_non_positive_duration() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        TaskDeadline(0)


def test_task_deadline_handler_raises_clear_error() -> None:
    deadline = TaskDeadline(115)

    with pytest.raises(TaskDeadlineExceeded, match="115-second"):
        deadline._handle_timeout(None, None)


def test_task_deadline_arms_and_cancels_timer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_handler = object()
    handlers = []
    timers = []

    monkeypatch.setattr(signal, "getsignal", lambda _signal: previous_handler)
    monkeypatch.setattr(
        signal,
        "signal",
        lambda signal_number, handler: handlers.append(
            (signal_number, handler)
        ),
    )
    monkeypatch.setattr(
        signal,
        "setitimer",
        lambda timer, seconds: timers.append((timer, seconds)),
    )

    deadline = TaskDeadline(115)
    deadline.start()
    deadline.cancel()
    deadline.cancel()

    assert handlers[0][0] == signal.SIGALRM
    assert handlers[0][1] == deadline._handle_timeout
    assert handlers[-1] == (signal.SIGALRM, previous_handler)
    assert timers == [
        (signal.ITIMER_REAL, 115),
        (signal.ITIMER_REAL, 0),
    ]
