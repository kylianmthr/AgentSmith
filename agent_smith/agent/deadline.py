import signal


class TaskDeadlineExceeded(TimeoutError):
    """Report that the global task deadline expired."""


class TaskDeadline:
    """Arm and cancel a process-wide real-time deadline."""

    def __init__(self, seconds: float) -> None:
        """Store a positive deadline duration."""

        if seconds <= 0:
            raise ValueError("Task deadline must be positive")
        self.seconds = seconds
        self._active = False
        self._previous_handler = None

    def _handle_timeout(self, _signum, _frame) -> None:
        """Interrupt the current operation when the deadline expires."""

        raise TaskDeadlineExceeded(
            f"Task exceeded its internal {self.seconds:g}-second deadline"
        )

    def start(self) -> None:
        """Start the deadline timer."""

        if self._active:
            raise RuntimeError("Task deadline is already active")
        self._previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, self._handle_timeout)
        try:
            signal.setitimer(signal.ITIMER_REAL, self.seconds)
        except BaseException:
            signal.signal(signal.SIGALRM, self._previous_handler)
            self._previous_handler = None
            raise
        self._active = True

    def cancel(self) -> None:
        """Cancel the timer and restore the previous signal handler."""

        if not self._active:
            return
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, self._previous_handler)
        self._previous_handler = None
        self._active = False
