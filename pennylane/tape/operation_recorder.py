# Copyright 2018-2021 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
This module contains the :class:`OperationRecorder`.
"""
# pylint: disable=too-many-arguments
from threading import RLock

from pennylane.queuing import AnnotatedQueue, QueuingManager, process_queue

from .tape import QuantumScript


class OperationRecorder(QuantumScript, AnnotatedQueue):
    """A template and quantum function inspector,
    allowing easy introspection of operators that have been
    applied without requiring a QNode.

    **Example**:

    The OperationRecorder is a context manager. Executing templates
    or quantum functions stores applied operators in the
    recorder, which can then be printed.

    >>> shape = qml.templates.StronglyEntanglingLayers.shape(n_layers=1, n_wires=2)
    >>> weights = np.random.random(shape)
    >>>
    >>> with OperationRecorder() as rec:
    >>>    qml.templates.StronglyEntanglingLayers(weights, wires=[0, 1])


    Alternatively, the :attr:`~.OperationRecorder.queue` attribute can be used
    to directly access the applied :class:`~.Operation` and :class:`~.Observable`
    objects.
    """

    _lock = RLock()
    """threading.RLock: Used to synchronize appending to/popping from global QueueingContext."""

    def __init__(
        self, ops=None, measurements=None, prep=None, name=None, do_queue=False, _update=True
    ):
        self.do_queue = do_queue
        AnnotatedQueue.__init__(self)
        QuantumScript.__init__(self, ops, measurements, prep, name=name, _update=_update)
        self.ops = None
        self.obs = None

    def __enter__(self):
        OperationRecorder._lock.acquire()
        try:
            if self.do_queue:
                QueuingManager.append(self)
            return AnnotatedQueue.__enter__(self)
        except Exception as _:
            OperationRecorder._lock.release()
            raise

    def __exit__(self, exception_type, exception_value, traceback):
        try:
            AnnotatedQueue.__exit__(self, exception_type, exception_value, traceback)
            # After other optimizations in #2963, #2986 and follow-up work, we should check whether
            # calling `_process_queue` only if there is no `exception_type` saves time. This would
            # be done via the following:
            # if exception_type is None:
            #    self._process_queue()
            self._ops, self._measurements, self._prep = process_queue(self)
            self._update()

            for obj, info in self.items():
                QueuingManager.append(obj, **info)

            new_tape = self.expand(depth=5, stop_at=lambda obj: not isinstance(obj, QuantumScript))
            self.ops = new_tape.operations
            self.obs = new_tape.observables
        finally:
            OperationRecorder._lock.release()

    def __str__(self):
        return "\n".join(
            [
                "Operations",
                "==========",
                *[repr(op) for op in self.ops],
                "",
                "Observables",
                "===========",
                *[repr(op) for op in self.obs],
                "",
            ]
        )

    @property
    def queue(self):
        return self.ops + self.obs

    def __getitem__(self, key):
        """
        Overrides the default because OperationRecorder is both a QuantumScript and an AnnotatedQueue.

        If key is an int, the caller is likely indexing the backing QuantumScript. Otherwise, the
        caller is likely indexing the backing AnnotatedQueue.
        """
        if isinstance(key, int):
            return QuantumScript.__getitem__(self, key)
        return AnnotatedQueue.__getitem__(self, key)

    def __setitem__(self, key, val):
        AnnotatedQueue.__setitem__(self, key, val)
