# Copyright 2018-2021 Xanadu Quantum Technologies Inc.# Licensed under the Apache License, Version 2.0 (the "License");# you may not use this file except in compliance with the License.# You may obtain a copy of the License at#     http://www.apache.org/licenses/LICENSE-2.0# Unless required by applicable law or agreed to in writing, software# distributed under the License is distributed on an "AS IS" BASIS,# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.# See the License for the specific language governing permissions and# limitations under the License.r"""Contains the SwapTest template."""from pennylane.operation import Operationfrom pennylane.measure import samplefrom pennylane.wires import Wiresclass SwapTest(Operation):    """A class that implements the SwapTest"""    def __init__(self, q_reg1, q_reg2, ancilla, do_queue=True, id=None):        wires = Wires(q_reg1 + q_reg2 + ancilla)        if len(q_reg1) != len(q_reg2):            raise ValueError(f"The two quantum registers must be the same size to compare them via SWAPTest, "                             f"got: {q_reg1}, {q_reg2}")        super().__init__(q_reg1, q_reg2, wires=wires, do_queue=do_queue, id=id)    def expand(self):        return