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
This module contains the functions needed for resource estimation with the double factorization
method.
"""

from pennylane import numpy as np


def estimation_cost(norm, error):
    r"""Return the number of calls to the unitary needed to achieve the desired error in phase
    estimation.

    Args:
        norm (float): 1-norm of a second-quantized Hamiltonian
        error (float): target error in the algorithm

    Returns:
        int: number of calls to unitary

    **Example**

    >>> cost = estimation_cost(72.49779513025341, 0.001)
    >>> print(cost)
    113880
    """
    return int(np.ceil(np.pi * norm / (2 * error)))


def qrom_cost(constants):
    r"""Return the number of Toffoli gates and the expansion factor needed to implement a QROM.

    The complexity of a QROM computation in the most general form is given by
    [`arXiv:2011.03494 <https://arxiv.org/abs/2011.03494>`_]

    .. math::

        cost = \left \lceil \frac{a + b}{k} \right \rceil + \left \lceil \frac{c}{k} \right \rceil +
        d \left ( k + e \right ),

    where :math:`a, b, c, d, e` are constants that depend on the nature of the QROM implementation
    and the expansion factor :math:`k` is an integer power of two, :math:`k = 2^n`, that minimizes
    the cost. This function computes the optimum :math:`k` and the minimum cost for a QROM
    specification.

    To obtain the optimum values of :math:`k`, we first assume that the cost function is continues
    and use differentiation to obtain the value of :math:`k` that minimizes the cost. This value of
    :math:`k` is not necessarily an integer power of 2. We then obtain the value of :math:`n` as
    :math:`n = \log_2(k)` and compute the cost for
    :math:`n_{int}= \left \{\left \lceil n \right \rceil, \left \lfloor n \right \rfloor \right \}`.
    The value of :math:`n_{int}` that gives the smaller cost is used to compute the optimim
    :math:`k`.

    Args:
        constants (tuple[float]): constants determining a QROM

    Returns:
        tuple(int, int): the cost and the expansion factor for the QROM

    **Example**
    >>> constants = (151.0, 7.0, 151.0, 30.0, -1.0)
    >>> cost_qrom(constants)
    168, 4
    """
    a, b, c, d, e = constants
    n = np.log2(((a + b + c) / d) ** 0.5)
    k = np.array([2 ** np.floor(n), 2 ** np.ceil(n)])
    cost = np.ceil((a + b) / k) + np.ceil(c / k) + d * (k + e)

    return int(cost[np.argmin(cost)]), int(k[np.argmin(cost)])


def unitary_cost(n, rank_r, rank_m, br=7, aleph=10, beth=20):
    r"""Return the number of Toffoli gates needed to implement the qubitization unitary operator.

    The expression for computing the cost is taken from
    [`arXiv:2011.03494 <https://arxiv.org/abs/2011.03494>`_].

    Args:
        n (int): number of molecular orbitals
        rank_r (int): the rank of the first factorization step
        rank_m (int): the average rank of the second factorization step
        br (int): number of bits for ancilla qubit rotation
        aleph (int): number of bits for the keep register
        beth (int): number of bits for the rotation angles

    Returns:
        int: the number of Toffoli gates to implement the qubitization unitary

    **Example**

    >>> n = 14
    >>> rank_r = 26
    >>> rank_m = 5.5
    >>> br = 7
    >>> aleph = 10
    >>> beth = 20
    >>> unitary_cost(n, norm, error, rank_r, rank_m, br, aleph, beth)
    2007
    """
    eta = np.array([np.log2(n) for n in range(1, rank_r + 1) if rank_r % n == 0])
    eta = int(np.max([n for n in eta if n % 1 == 0]))

    nxi = np.ceil(np.log2(rank_m))
    nlxi = np.ceil(np.log2(rank_r * rank_m + n / 2))
    nl = np.ceil(np.log2(rank_r + 1))

    bp1 = nl + aleph
    bp2 = nxi + aleph + 2
    bo = nxi + nlxi + br + 1

    rank_rm = rank_r * rank_m

    cost = 9 * nl - 6 * eta + 12 * br + 34 * nxi + 8 * nlxi + 9 * aleph + 3 * n * beth - 6 * n - 43

    cost += qrom_cost((rank_r, 1, 0, bp1, -1))[0]
    cost += qrom_cost((rank_r, 1, 0, bo, -1))[0]
    cost += qrom_cost((rank_r, 1, 0, 1, 0))[0] * 2
    cost += qrom_cost((rank_rm, n / 2, rank_rm, n * beth, 0))[0]
    cost += qrom_cost((rank_rm, n / 2, rank_rm, 2, 0))[0] * 2
    cost += qrom_cost((rank_rm, n / 2, rank_rm, 2 * bp2, -1))[0]

    return int(cost)


def gate_cost(n, norm, error, rank_r, rank_m, br=7, aleph=10, beth=20):
    r"""Return the number of Toffoli gates needed to implement the double factorization method.

    Args:
        n (int): number of molecular orbitals
        norm (float): 1-norm of a second-quantized Hamiltonian
        error (float): target error in the algorithm
        rank_r (int): the rank of the first factorization step
        rank_m (int): the average rank of the second factorization step
        br (int): number of bits for ancilla qubit rotation
        aleph (int): number of bits for the keep register
        beth (int): number of bits for the rotation angles

    Returns:
        int: the number of Toffoli gates for the double factorization method

    **Example**

    >>> n = 14
    >>> norm = 52.98761457453095
    >>> error = 0.001
    >>> rank_r = 26
    >>> rank_m = 5.5
    >>> br = 7
    >>> aleph = 10
    >>> beth = 20
    >>> gate_cost(n, norm, error, rank_r, rank_m, br, aleph, beth)
    167048631
    """
    e_cost = estimation_cost(norm, error)
    u_cost = unitary_cost(n, rank_r, rank_m, br, aleph, beth)

    return int(e_cost * u_cost)


def qubit_cost(n, norm, error, rank_r, rank_m, br=7, aleph=10, beth=20):
    r"""Return the number of ancilla qubits needed to implement the double factorization method.

    Args:
        n (int): number of molecular orbitals
        norm (float): 1-norm of a second-quantized Hamiltonian
        error (float): target error in the algorithm
        rank_r (int): the rank of the first factorization step
        rank_m (int): the average rank of the second factorization step
        br (int): number of bits for ancilla qubit rotation
        aleph (int): number of bits for the keep register
        beth (int): number of bits for the rotation angles

    Returns:
        int: the number of ancilla qubits for the double factorization method

    **Example**

    >>> n = 14
    >>> norm = 52.98761457453095
    >>> error = 0.001
    >>> rank_r = 26
    >>> rank_m = 5.5
    >>> br = 7
    >>> aleph = 10
    >>> beth = 20
    >>> qubit_cost(n, norm, error, rank_r, rank_m, br, aleph, beth)
    292
    """
    nxi = np.ceil(np.log2(rank_m))
    nlxi = np.ceil(np.log2(rank_r * rank_m + n / 2))
    nl = np.ceil(np.log2(rank_r + 1))

    bp2 = nxi + aleph + 2
    bo = nxi + nlxi + br + 1
    kr = qrom_cost((rank_r * rank_m, n / 2, rank_r * rank_m, n * beth, 0))[1]

    e_cost = estimation_cost(norm, error)

    cost = n + 2 * nl + nxi + 3 * aleph + beth + bo + bp2
    cost += kr * n * beth / 2 + 2 * np.ceil(np.log2(e_cost + 1)) + 7

    return int(cost)
