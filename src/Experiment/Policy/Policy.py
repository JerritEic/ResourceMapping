import logging

from src.NetworkGraph.NetworkGraph import NetworkNode
from src.app.Component import Component


# Performs actions based on decisions of a policy
class PolicyAction:
    name = "None"
    needs_input = False
    output = None

    def perform_action(self, action_input=None):
        pass


# Execute a series of policy actions, piping output to next input. These can be nested
class PolicyActionChain(PolicyAction):
    name = "PolicyActionChain"

    def __init__(self, policy_actions: list[PolicyAction]):
        self.policy_actions = policy_actions

    def perform_action(self, action_input=None):
        prev_output = action_input
        num_policies = len(self.policy_actions)
        for i in range(num_policies):
            # Set current
            curr_action = self.policy_actions[i]

            if prev_output is None and curr_action.needs_input:
                logging.error(f"{curr_action.name} needs an input and none was provided!")

            curr_action.output = prev_output  # output = input by default
            curr_action.perform_action(prev_output)

            # Update previous
            prev_output = curr_action.output
        self.output = prev_output  # Output of whole chain is the output of the last action


# Policy actions
# Start/Modify/Move/Stop a component
# Start/Modify/Stop hardware


# Move a component from node 1 to node 2.
class MoveComponentAction(PolicyAction):
    name = "MoveComponent"

    def __init__(self, component: Component, node1: NetworkNode, node2: NetworkNode):
        self.node1 = node1
        self.node2 = node2
        self.component = component

    # In future, this could be some sort of VM/Docker image movement to transfer a service to
    # different hardware.
    def perform_action(self, action_input=None):
        # Start component on node2
        # Wait for it to be ready
        # Stop component on node1
        pass


# Given an input of a list of MessageEvent, waits for all to be set, with some timeout
class WaitForResponses(PolicyAction):
    name = "WaitForOutput"
    needs_input = True

    def __init__(self, timeout=10):
        self.timeout = timeout

    def perform_action(self, action_input=None):
        pass


# Policy No-Op, prints what it's input was, or nothing
class DebugPolicyAction(PolicyAction):
    name = "DebugPolicyAction"

    def __init__(self, to_print=None):
        self.to_print = to_print

    def perform_action(self, action_input=None):
        if action_input is not None or self.to_print is not None:
            logging.info(f"DebugPolicyAction - {self.to_print} - {action_input}")


# Decides how components are distributed over a network graph of hardware resources
class Policy:
    def check(self, nodes) -> [PolicyAction]:
        pass
