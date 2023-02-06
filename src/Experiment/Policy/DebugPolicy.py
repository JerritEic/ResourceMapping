import time

from src.Experiment.Policy.Policy import Policy, PolicyAction


# Performs preconfigured policy actions after a preconfigured amount of time
class DebugPolicy(Policy):
    def __init__(self, actions):
        # actions should be a list of dicts with 'action' and 'time'
        self.actions = actions
        self.start_time = -1

    # Sets the 'start time' to current time
    def _zero_start_time(self):
        self.start_time = time.time()

    def check(self, nodes) -> [PolicyAction]:
        if self.start_time == -1:
            self._zero_start_time()
        actions_to_perform = []
        # check if enough time has elapsed
        for action in self.actions:
            if 'done' not in action and action['time'] >= time.time() - self.start_time:
                # do the action
                actions_to_perform.append(action['action'])
                action['done'] = True
        return actions_to_perform
