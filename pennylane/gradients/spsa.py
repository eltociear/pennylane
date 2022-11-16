# Copyright 2018-2022 Xanadu Quantum Technologies Inc.

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
This module contains functions for computing the SPSA gradient
of a quantum tape.
"""
# pylint: disable=protected-access,too-many-arguments,too-many-branches,too-many-statements
import warnings
from collections.abc import Sequence

import numpy as np

import pennylane as qml
from pennylane._device import _get_num_copies

from .gradient_transform import (
    gradient_transform,
    grad_method_validation,
    choose_grad_methods,
    gradient_analysis,
)
from .finite_difference import (
    _all_zero_grad_new,
    _no_trainable_grad_new,
    finite_diff_coeffs,
)
from .general_shift_rules import generate_multishifted_tapes


def _rademacher_sampler(indices, num_params):
    """Sample a random vector with (independent) entries from {+1, -1} with balanced probability.
    That is, each entry follows the
    `Rademacher distribution. <https://en.wikipedia.org/wiki/Rademacher_distribution>`_
    """
    direction = np.zeros(num_params)
    direction[indices] = np.random.choice([-1, 1], size=len(indices))
    return direction


@gradient_transform
def _spsa_new(
    tape,
    argnum=None,
    h=1e-7,
    approx_order=1,
    n=1,
    strategy="forward",
    f0=None,
    validate_params=True,
    shots=None,
    num_samples=1,
    sampler=_rademacher_sampler,
):
    r"""Transform a QNode to compute the SPSA gradient of all gate
    parameters with respect to its inputs. This estimator shifts all parameters
    simultaneously and approximates the gradient based on these shifts and a
    finite-difference method. This function is adapted to the new return system.

    Args:
        tape (pennylane.QNode or .QuantumTape): quantum tape or QNode to differentiate
        argnum (int or list[int] or None): Trainable parameter indices to differentiate
            with respect to. If not provided, the derivatives with respect to all
            trainable parameters are returned.
        h (float or tensor_like[float]): Step size for the finite-difference method
            underlying the SPSA. Can be a tensor-like object
            with as many entries as differentiated *gate* parameters
        approx_order (int): The approximation order of the finite-difference method underlying
            the SPSA gradient.
        n (int): compute the :math:`n`-th derivative
        strategy (str): The strategy of the underlying finite difference method. Must be one of
            ``"forward"``, ``"center"``, or ``"backward"``.
            For the ``"forward"`` strategy, the finite-difference shifts occur at the points
            :math:`x_0, x_0+h, x_0+2h,\dots`, where :math:`h` is the stepsize ``h``.
            The ``"backwards"`` strategy is similar, but in
            reverse: :math:`x_0, x_0-h, x_0-2h, \dots`. Finally, the
            ``"center"`` strategy results in shifts symmetric around the
            unshifted point: :math:`\dots, x_0-2h, x_0-h, x_0, x_0+h, x_0+2h,\dots`.
        f0 (tensor_like[float] or None): Output of the evaluated input tape in ``tape``. If
            provided, and the gradient recipe contains an unshifted term, this value is used,
            saving a quantum evaluation.
        validate_params (bool): Whether to validate the tape parameters or not. If ``True``,
            the ``Operation.grad_method`` attribute and the circuit structure will be analyzed
            to determine if the trainable parameters support the finite-difference method,
            inferring that they support SPSA as well.
            If ``False``, the finite-difference method will be applied to all parameters.
        shots (None, int, list[int], list[ShotTuple]): The device shots that will be used to
            execute the tapes outputted by this transform. Note that this argument doesn't
            influence the shots used for tape execution, but provides information
            to the transform about the device shots and helps in determining if a shot
            sequence was used to define the device shots for the new return types output system.
        num_samples (int): Number of sampled simultaneous perturbation vectors. An estimate for
            the gradient is computed for each vector using the underlying finite-difference
            method, and afterwards all estimates are averaged.

    Returns:
        tensor_like or tuple[tensor_like] or tuple[tuple[tensor_like]] or tuple[list[QuantumTape], function]:

        - If the input is a QNode, an object representing the output Jacobian matrix.
          The type of the object returned is either a tensor, a tuple or a nested tuple depending on the nesting
          structure of the output.

        - If the input is a tape, a tuple containing a list of generated tapes,
          in addition to a post-processing function to be applied to the
          evaluated tapes.

    **Example**


    .. details::
        :title: Usage Details

        This gradient transform can also be applied directly to :class:`QNode <pennylane.QNode>`
        objects:

        >>> @qml.qnode(dev)
        ... def circuit(params):
        ...     qml.RX(params[0], wires=0)
        ...     qml.RY(params[1], wires=0)
        ...     qml.RX(params[2], wires=0)
        ...     return qml.expval(qml.PauliZ(0)), qml.var(qml.PauliZ(0))
        >>> params = np.array([0.1, 0.2, 0.3], requires_grad=True)
        >>> qml.gradients.spsa(circuit)(params)
        #TODO

        This quantum gradient transform can also be applied to low-level
        :class:`~.QuantumTape` objects. This will result in no implicit quantum
        device evaluation. Instead, the processed tapes, and post-processing
        function, which together define the gradient are directly returned:

        >>> with qml.tape.QuantumTape() as tape:
        ...     qml.RX(params[0], wires=0)
        ...     qml.RY(params[1], wires=0)
        ...     qml.RX(params[2], wires=0)
        ...     qml.expval(qml.PauliZ(0))
        ...     qml.var(qml.PauliZ(0))
        >>> gradient_tapes, fn = qml.gradients.finite_diff(tape)
        >>> gradient_tapes
        #TODO

        This can be useful if the underlying circuits representing the gradient
        computation need to be analyzed.

        The output tapes can then be evaluated and post-processed to retrieve
        the gradient:

        >>> dev = qml.device("default.qubit", wires=2)
        >>> fn(qml.execute(gradient_tapes, dev, None))
        #TODO

        Devices that have a shot vector defined can also be used for execution, provided
        the ``shots`` argument was passed to the transform:

        >>> shots = (10, 100, 1000)
        >>> dev = qml.device("default.qubit", wires=2, shots=shots)
        >>> @qml.qnode(dev)
        ... def circuit(params):
        ...     qml.RX(params[0], wires=0)
        ...     qml.RY(params[1], wires=0)
        ...     qml.RX(params[2], wires=0)
        ...     return qml.expval(qml.PauliZ(0)), qml.var(qml.PauliZ(0))
        >>> params = np.array([0.1, 0.2, 0.3], requires_grad=True)
        >>> qml.gradients.finite_diff(circuit, shots=shots, h=10e-2)(params)
        #TODO

        The outermost tuple contains results corresponding to each element of the shot vector.
    """
    if argnum is None and not tape.trainable_params:
        return _no_trainable_grad_new(tape, shots)

    if validate_params:
        if "grad_method" not in tape._par_info[0]:
            gradient_analysis(tape, grad_fn=_spsa_new)
        diff_methods = grad_method_validation("numeric", tape)
    else:
        diff_methods = ["F" for i in tape.trainable_params]

    if all(g == "0" for g in diff_methods):
        return _all_zero_grad_new(tape, shots)

    gradient_tapes = []
    extract_r0 = False

    coeffs, shifts = finite_diff_coeffs(n=n, approx_order=approx_order, strategy=strategy)

    if 0 in shifts:
        # Finite difference formula includes a term with zero shift.

        if f0 is None:
            # Ensure that the unshifted tape is appended to the gradient tapes
            gradient_tapes.append(tape)
            extract_r0 = True

        # Skip the unshifted tape
        shifts = shifts[1:]

    method_map = choose_grad_methods(diff_methods, argnum)

    indices = [
        i for i, _ in enumerate(tape.trainable_params) if (i in method_map and method_map[i] != "0")
    ]

    tapes_per_grad = len(shifts)
    all_coeffs = []
    for rep in range(num_samples):
        direction = sampler(indices, len(tape.trainable_params))
        inv_direction = qml.math.divide(
            1, direction, where=(direction != 0), out=qml.math.zeros_like(direction)
        )
        _shifts = qml.math.tensordot(h * shifts, direction, axes=0)
        all_coeffs.append(qml.math.tensordot(coeffs / h**n, inv_direction, axes=0))
        g_tapes = generate_multishifted_tapes(tape, indices, _shifts)
        gradient_tapes.extend(g_tapes)

    def _single_shot_batch_result(results):
        """Auxiliary function for post-processing one batch of results corresponding to finite
        shots or a single component of a shot vector"""

        """
        grads = []
        start = 1 if c0 is not None and f0 is None else 0
        r0 = f0 or results[0]

        output_dims = []
        # TODO: Update shape for CV variables
        for m in tape.measurements:
            if m.return_type is qml.measurements.Probability:
                output_dims.append(2 ** len(m.wires))
            else:
                output_dims.append(1)
        """

        r0, results = (results[0], results[1:]) if extract_r0 else (f0, results)
        grads = []
        if len(tape.measurements) == 1:
            for rep, _coeffs in enumerate(all_coeffs):
                res = results[rep * tapes_per_grad : (rep + 1) * tapes_per_grad]
                if r0 is not None:
                    res.insert(0, r0)
                res = qml.math.stack(res)
                grads = qml.math.tensordot(res, _coeffs, axes=[[0], [0]]) + grads
            grads = grads / num_samples
            if len(tape.trainable_params) == 1:
                return grads[0]
            return tuple(grads)
        else:
            grads = []
            for i, _ in enumerate(tape.measurements):
                grad = 0
                for rep, _coeffs in enumerate(all_coeffs):
                    res = [r[i] for r in results[rep * tapes_per_grad : (rep + 1) * tapes_per_grad]]
                    if r0 is not None:
                        res.insert(0, r0)
                    res = qml.math.stack(res)
                    grad = qml.math.tensordot(res, _coeffs, axes=[[0], [0]]) + grad
                grads.append(grad / num_samples)
            grads = tuple(grads)
        return grads

        """
        # Reordering to match the right shape for multiple measurements
        grads_reorder = [[0] * len(tape.trainable_params) for _ in range(len(tape.measurements))]
        for i in range(len(tape.measurements)):
            for j in range(len(tape.trainable_params)):
                grads_reorder[i][j] = grads[j][i]

        # To tuple
        if len(tape.trainable_params) == 1:
            grads_tuple = tuple(elem[0] for elem in grads_reorder)
        else:
            grads_tuple = tuple(tuple(elem) for elem in grads_reorder)
        return grads_tuple
        """

    def processing_fn(results):
        shot_vector = isinstance(shots, Sequence)

        if not shot_vector:
            grads_tuple = _single_shot_batch_result(results)
        else:
            grads_tuple = []
            len_shot_vec = _get_num_copies(shots)
            for idx in range(len_shot_vec):
                res = [tape_res[idx] for tape_res in results]
                g_tuple = _single_shot_batch_result(res)
                grads_tuple.append(g_tuple)
            grads_tuple = tuple(grads_tuple)

        return grads_tuple

    return gradient_tapes, processing_fn


@gradient_transform
def spsa(
    tape,
    argnum=None,
    h=1e-4,
    approx_order=2,
    n=1,
    strategy="center",
    f0=None,
    validate_params=True,
    shots=None,
    num_samples=1,
    sampler=_rademacher_sampler,
):
    r""" """
    if qml.active_return():
        return _spsa_new(
            tape,
            argnum=argnum,
            h=h,
            approx_order=approx_order,
            n=n,
            strategy=strategy,
            f0=f0,
            validate_params=validate_params,
            shots=shots,
            num_samples=num_samples,
            sampler=sampler,
        )

    if argnum is None and not tape.trainable_params:
        warnings.warn(
            "Attempted to compute the gradient of a tape with no trainable parameters. "
            "If this is unintended, please mark trainable parameters in accordance with the "
            "chosen auto differentiation framework, or via the 'tape.trainable_params' property."
        )
        return [], lambda _: qml.math.zeros([tape.output_dim, 0])

    # TODO: Do we need a separate indicator for spsa differentiation or can we reuse "F"?
    if validate_params:
        if "grad_method" not in tape._par_info[0]:
            gradient_analysis(tape, grad_fn=spsa)
        diff_methods = grad_method_validation("numeric", tape)
    else:
        diff_methods = ["F" for i in tape.trainable_params]

    if all(g == "0" for g in diff_methods):
        return [], lambda _: np.zeros([tape.output_dim, len(tape.trainable_params)])

    gradient_tapes = []
    extract_r0 = False

    coeffs, shifts = finite_diff_coeffs(n=n, approx_order=approx_order, strategy=strategy)

    if 0 in shifts:
        # Finite difference formula includes a term with zero shift.

        if f0 is None:
            # Ensure that the unshifted tape is appended to the gradient tapes
            gradient_tapes.append(tape)
            extract_r0 = True

        # Skip the unshifted tape
        shifts = shifts[1:]

    method_map = choose_grad_methods(diff_methods, argnum)

    indices = [
        i for i, _ in enumerate(tape.trainable_params) if (i in method_map and method_map[i] != "0")
    ]

    tapes_per_grad = len(shifts)
    all_coeffs = []
    for rep in range(num_samples):
        direction = sampler(indices, len(tape.trainable_params))
        inv_direction = qml.math.divide(
            1, direction, where=(direction != 0), out=qml.math.zeros_like(direction)
        )
        _shifts = qml.math.tensordot(h * shifts, direction, axes=0)
        all_coeffs.append(qml.math.tensordot(coeffs / h**n, inv_direction, axes=0))
        g_tapes = generate_multishifted_tapes(tape, indices, _shifts)
        gradient_tapes.extend(g_tapes)

    def processing_fn(results):
        # HOTFIX: Apply the same squeezing as in qml.QNode to make the transform output consistent.
        # pylint: disable=protected-access
        if tape._qfunc_output is not None and not isinstance(tape._qfunc_output, Sequence):
            results = [qml.math.squeeze(res) for res in results]

        r0, results = (results[0], results[1:]) if extract_r0 else (f0, results)

        grads = 0
        for rep, _coeffs in enumerate(all_coeffs):
            res = results[rep * tapes_per_grad : (rep + 1) * tapes_per_grad]
            if r0 is not None:
                res.insert(0, r0)
            res = qml.math.stack(res)
            grads = qml.math.tensordot(res, _coeffs, axes=[[0], [0]]) + grads

        grads = grads / num_samples

        # TODO: What about the following step?
        # The following is for backwards compatibility; currently,
        # the device stacks multiple measurement arrays, even if not the same
        # size, resulting in a ragged array.
        # In the future, we might want to change this so that only tuples
        # of arrays are returned.
        for i, g in enumerate(grads):
            if hasattr(g, "dtype") and g.dtype is np.dtype("object"):
                if qml.math.ndim(g) > 0:
                    grads[i] = qml.math.hstack(g)

        return grads

    return gradient_tapes, processing_fn


"""
    This transform can be registered directly as the quantum gradient transform
    to use during autodifferentiation:

    >>> dev = qml.device("default.qubit", wires=2)
    >>> @qml.qnode(dev, interface="autograd", diff_method="finite-diff")
    ... def circuit(params):
    ...     qml.RX(params[0], wires=0)
    ...     qml.RY(params[1], wires=0)
    ...     qml.RX(params[2], wires=0)
    ...     return qml.expval(qml.PauliZ(0))
    >>> params = np.array([0.1, 0.2, 0.3], requires_grad=True)
    >>> qml.jacobian(circuit)(params)
    array([-0.38751725, -0.18884792, -0.38355708])

    When differentiating QNodes with multiple measurements using Autograd or TensorFlow, the outputs of the QNode first
    need to be stacked. The reason is that those two frameworks only allow differentiating functions with array or
    tensor outputs, instead of functions that output sequences. In contrast, Jax and Torch require no additional
    post-processing.

    >>> import jax
    >>> dev = qml.device("default.qubit", wires=2)
    >>> @qml.qnode(dev, interface="jax", diff_method="finite-diff")
    ... def circuit(params):
    ...     qml.RX(params[0], wires=0)
    ...     qml.RY(params[1], wires=0)
    ...     qml.RX(params[2], wires=0)
    ...     return qml.expval(qml.PauliZ(0)), qml.var(qml.PauliZ(0))
    >>> params = jax.numpy.array([0.1, 0.2, 0.3])
    >>> jax.jacobian(circuit)(params)
    (DeviceArray([-0.38751727, -0.18884793, -0.3835571 ], dtype=float32),
    DeviceArray([0.6991687 , 0.34072432, 0.6920237 ], dtype=float32))

"""
