"""One active hint and one coalesced pending hint, independent of audio input."""
from collections import deque
import math
import threading
import time
from request_control import RequestControl, RequestCancelled, RequestDeadline


class HintJob:
    def __init__(self, generation, work, clock):
        self.generation = generation
        self.work = work
        self.control = RequestControl(clock=clock)
        self.queued_at = clock()
        self.done = threading.Event()
        self.value = None
        self.error = None

    def cancel(self):
        self.control.cancel()
        self.done.set()

    def result(self):
        if not self.done.wait(max(0, self.control.deadline - self.control.clock()) + .1):
            self.cancel()
            raise RequestDeadline()
        self.control.check()
        if self.error:
            raise self.error
        return self.value


class HintQueue:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.condition = threading.Condition()
        self.active = None
        self.pending = None
        self.latest_generation = 0
        self.closed = False
        self.samples = deque(maxlen=128)
        self.cancelled_count = 0
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def _cancel(self, job):
        if job and not job.control.cancelled.is_set():
            self.cancelled_count += 1
            job.cancel()

    def submit(self, generation, work):
        if isinstance(generation, bool) or not isinstance(generation, int) or not 0 < generation < 2**53:
            raise ValueError('Invalid hint generation')
        job = HintJob(generation, work, self.clock)
        with self.condition:
            if self.closed or generation <= self.latest_generation:
                raise RequestCancelled()
            self.latest_generation = generation
            self._cancel(self.active)
            self._cancel(self.pending)
            self.pending = job
            self.condition.notify()
        return job

    def cancel(self, generation):
        if isinstance(generation, bool) or not isinstance(generation, int) or not 0 < generation < 2**53:
            raise ValueError('Invalid hint generation')
        with self.condition:
            # Remember cancellation even if its POST arrived before submission.
            # A late cancel for an older request cannot cancel its replacement.
            self.latest_generation = max(self.latest_generation, generation)
            for job in (self.active, self.pending):
                if job and job.generation == generation:
                    self._cancel(job)

    def cancel_all(self):
        with self.condition:
            self._cancel(self.active)
            self._cancel(self.pending)

    def reset(self):
        with self.condition:
            self._cancel(self.active)
            self._cancel(self.pending)
            self.pending = None
            self.latest_generation = 0

    def close(self):
        with self.condition:
            self.closed = True
            self._cancel(self.active)
            self._cancel(self.pending)
            self.condition.notify()

    def _run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.closed or self.pending is not None)
                if self.closed:
                    return
                job = self.pending
                self.pending = None
                self.active = job
            started = self.clock()
            state = 'completed'
            try:
                job.control.check()
                value = job.work(job.control)
                with self.condition:
                    job.control.check()
                    job.value = value
            except (RequestCancelled, RequestDeadline) as error:
                state = 'cancelled'
                job.error = error
            except Exception as error:
                state = 'failed'
                job.error = error
            finally:
                with self.condition:
                    self.samples.append({'queue_ms': max(0, started-job.queued_at)*1000,
                                         'request_ms': max(0, self.clock()-started)*1000,
                                         'state': state})
                    job.done.set()
                    self.active = None

    def snapshot(self):
        with self.condition:
            def summary(field):
                values = sorted(s[field] for s in self.samples)
                if not values:
                    return {'samples': 0, 'p50': None, 'p95': None}
                return {'samples': len(values),
                        'p50': round(values[math.ceil(.50*len(values))-1], 1),
                        'p95': round(values[math.ceil(.95*len(values))-1], 1)}
            return {'capacity': 1, 'active': self.active is not None,
                    'pending': self.pending is not None, 'cancelled': self.cancelled_count,
                    'queue_ms': summary('queue_ms'), 'request_ms': summary('request_ms')}
