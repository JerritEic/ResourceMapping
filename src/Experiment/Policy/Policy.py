import logging

from src.NetProtocol.Message import Message
from src.NetworkGraph.NetworkGraph import NetworkNode
from src.app.Component import Component


# Performs actions based on decisions of a policy
class PolicyAction:
    name = "None"
    needs_input = False
    output = None

    def perform_action(self, action_input=None) -> bool:
        pass


# Execute a series of policy actions, piping output to next input. These can be nested
class PolicyActionChain(PolicyAction):
    name = "PolicyActionChain"

    def __init__(self, policy_actions: list[PolicyAction]):
        self.policy_actions = policy_actions

    def perform_action(self, action_input=None) -> bool:
        prev_output = action_input
        num_policies = len(self.policy_actions)
        res = True
        for i in range(num_policies):
            # Set current
            curr_action = self.policy_actions[i]

            if prev_output is None and curr_action.needs_input:
                logging.error(f"{curr_action.name} needs an input and none was provided!")

            curr_action.output = prev_output  # output = input by default
            res = res and curr_action.perform_action(prev_output)

            # Update previous
            prev_output = curr_action.output
        self.output = prev_output  # Output of whole chain is the output of the last action
        return res  # return False if any actions in the chain failed


# Policy actions
# Start/Modify/Move/Stop a component
# Start/Modify/Stop hardware


# Start a component
class StartComponentAction(PolicyAction):
    name = "StartComponent"

    def __init__(self, start_component_message: Message, target_node: NetworkNode, message_handler):
        self.target_node = target_node
        self.start_component_message = start_component_message
        self.message_handler = message_handler

    def perform_action(self, action_input=None) -> bool:
        future = self.target_node.conn_handler.send_message_and_wait_response(self.start_component_message,
                                                                              yield_message=True)
        comp_name = self.start_component_message.content.request['components']
        if not self.message_handler.wait_for_responses([future], 5):
            logging.error(f"Timeout on starting component: {comp_name}")
            return False
        resp = future.get_message().content.request['results']
        if resp[0] == -1:
            logging.error(f"Failed to start {comp_name}.")
            return False
        else:
            self.target_node.add_known_component(Component(pid=resp[0], name=comp_name))
            return True


class StopComponentAction(PolicyAction):
    name = "StopComponent"

    def __init__(self, stop_component_message: Message, target_node: NetworkNode):
        self.target_node = target_node
        self.stop_component_message = stop_component_message

    def perform_action(self, action_input=None) -> bool:
        # Don't wait for a response
        self.target_node.conn_handler.send_message(self.stop_component_message)
        return True



# Given an input of a list of MessageEvent, waits for all to be set, with some timeout
class WaitForResponses(PolicyAction):
    name = "WaitForOutput"
    needs_input = True

    def __init__(self, timeout=10):
        self.timeout = timeout

    def perform_action(self, action_input=None) -> bool:
        pass


# Policy No-Op, prints what it's input was, or nothing
class DebugPolicyAction(PolicyAction):
    name = "DebugPolicyAction"

    def __init__(self, to_print=None):
        self.to_print = to_print

    def perform_action(self, action_input=None) -> bool:
        if action_input is not None or self.to_print is not None:
            logging.info(f"DebugPolicyAction - {self.to_print} - {action_input}")
        return True


# Decides how components are distributed over a network graph of hardware resources
class Policy:
    def check(self, nodes) -> [PolicyAction]:
        pass
