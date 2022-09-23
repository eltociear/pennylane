# Device API

This module contains the new device API for PennyLane. The goal is to address several of the following short-comings with the existing device structures:

* Nested inheritence hierarchiesfor existing devices.
* Inflexible extensions for new features and implementation updates.
* Lack of support for parallel executions on single or multiple devices.

To alleviate such issues, and provide support for future devices more easily, we define a new device API for PennyLane.

## Required feature-set and design considerations

We have identified the following list of features that new and existing devices should provide, support and enable:

* Devices maintain and can return a configuration data-structure that returns all settings, properties and metadata about the device.
* The purpose of any given device is to consume single or multiple `QuantumScript` objects, and supported classical pre- and post-processing of the results.
* A device supports validation of a given `QuantumScript` against its supported gate-set and features.
* A device supports transpilation of a `QuantumScript` object to its native gate-set. This is failure checked with the previous validation step.
* A device can register classical pre- and post-processing steps for the results of a given `QuantumScript` circuit execution.
* A device can register native, and custom, gradient methods.
* A device can return the result of forward and/or backward execution, given an appropriate `QuantumScript` and inputs.
* If supported, a device can also allow return of the VJP for a given set of inputs.
* A device can return all supported quantum and classical operations.
* Default support should exist for virtual devices with the following functionalities:
    * Computing marginal probabilities.
    * Generating and retuning samples from the quantum state.
    * Return probabilities from given a `QuantumScript`.
* 