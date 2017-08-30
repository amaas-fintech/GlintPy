import boto3
import json

class JSONifyMixin(object):
    def to_json(self):
        return json.dumps(self._config)

    def to_dict(self):
        return self._config

class StateMachine(JSONifyMixin):
    def __init__(self, start_at, comment='', timeout_seconds=None,
                 version=None, states={}):
        self._config = {'StartAt': start_at,
                        'States': states}

        if comment:
            self._config['Comment'] = comment

        if timeout_seconds:
            self._config['TimeoutSeconds'] = timeout_seconds

        if version:
            self._config['Version'] = version

    def create_state_machine(self, name, definition, role_arn):
        client = boto3.client('stepfunctions', region_name='ap-northeast-1')
        response = client.create_state_machine(name=name,
                                               definition=definition,
                                               roleArn=role_arn)
        return response.get('stateMachineArn', '')

    def add_state(self, state):
        if isinstance(state, State):
            if not self._config.get('States'):
                # StartAt must be same as the first state's name
                if list(state.to_dict().keys())[0] != self._config.get('StartAt'):
                    raise KeyError('Invalide StartAt key')
                else:
                    self._config['States'].update(state.to_dict())
            else:
                self._config['States'].update(state.to_dict())
        else:
            raise TypeError('Invalid State object.')


class State(object):
    def __init__(self, name):
        self._config = {name: {'Type': self.__class__.__name__}}

class Task(JSONifyMixin, State):
    def __init__(self, name, state_resource, state_next='',
                 state_comment='', timeout_seconds=None,
                 heartbeat_seconds=None, result_path=None, retry=[], catch=[]):
        super().__init__(name)

        if state_resource:
            self._config[name]['Resource'] = state_resource

        if state_comment:
            self._config[name]['Comment'] = state_comment

        if state_next:
            self._config[name]['Next'] = state_next
        else:
            self._config[name]['End'] = True

        if timeout_seconds:
            self._config['TimeoutSeconds'] = timeout_seconds

        if heartbeat_seconds:
            self._config['HeartbeatSeconds'] = heartbeat_seconds

        if result_path:
            self._config['ResultPath'] = result_path

        if retry:
            self._config['Retry'] = retry

        if catch:
            self._config['Catch'] = catch


class Parallel(JSONifyMixin, State):
    def __init__(self, name, branches, state_next=''):
        if not isinstance(branches, list):
            raise TypeError('Invalid argument type, a list is expected.')

        super().__init__(name)
        self._ref = name
        self._config[name].update({'Branches': [branch.to_dict() for branch in branches]})

        if state_next:
            self._config[name]['Next'] = state_next
        else:
            self._config[name]['End'] = True

    def add_branch(self, branch):
        if isinstance(branch, Branch):
            self._config[self._ref]['Branches'].append(branch.to_dict())
        else:
            raise TypeError('Invalid Branch object.')

class Branch(JSONifyMixin):
    def __init__(self, start_at, init_state):
        self._config = {'StartAt': start_at,
                        'States': init_state.to_dict()}

    def add_state(self, state):
        if isinstance(state, State):
            self._config['States'].update(state.to_dict())
        else:
            raise TypeError('Invalid State object.')

class Choice(JSONifyMixin, State):
    def __init__(self, name, choices, default=''):
        if not isinstance(choices, list):
            raise TypeError('Invalid argument type, a list is expected.')

        super().__init__(name)
        self._ref = name

        if default:
            self._config[name]['Default'] = default

        self._config[name]['Choices'] = [item.to_dict() for item in choices]

    def add_option(self, choice_option):
        self._config[self._ref]['Choices'].append(choice_option.to_dict())

class ChoiceOption(JSONifyMixin):
    def __init__(self, operation=None, state_next=None, variable=None):
        if not isinstance(operation, dict):
            raise TypeError('Invalid argument type, a dict is expected.')
        
        self._config = {}

        if operation:
            self._config.update(operation)

        if state_next:
            self._config.update({'Next': state_next})

        if variable:
            self._config.update({'Variable': variable})

class Wait(JSONifyMixin, State):
    def __init__(self, name, time_wait, state_next):
        super().__init__(name)

        if isinstance(time_wait, (int, float)):
            self._config[name]['Seconds'] = time_wait
        else:
            self._config[name]['Timestamp'] = time_wait

        self._config[name]['Next'] = state_next

class Pass(JSONifyMixin, State):
    def __init__(self, name, state_next=None, result=None, result_path=None):
        super().__init__(name)

        if state_next:
            self._config[name]['Next'] = state_next

        if result:
            self._config[name]['Result'] = result

        if result_path:
            self._config[name]['ResultPath'] = result_path

class Succeed(JSONifyMixin, State):
    def __init__(self, name):
        super().__init__(name)

class Fail(JSONifyMixin, State):
    def __init__(self, name, cause='', error=''):
        super().__init__(name)

        if cause:
            self._config['Cause'] = cause

        if error:
            self._config['Error'] = error

if __name__ == '__main__':
    sm = StateMachine(start_at='TestLambdaTask', comment='Comment')
    sm.add_state(Task(name='TestLambdaTask',  state_resource='arn:aws:lambda:us-east-1:123456789012:function:asdfsd'))
    Task(name='TestLambdaTask',  state_resource='arn:aws:lambda:us-east-1:123456789012:function:asdfsd')
    parallel = Parallel(name='TestLambdaParallel', 
                        branches=[Branch('TestStart',
                                         Task(name='TestLambdaTask',
                                              state_resource='arn:aws:lambda:us-east-1:123456789012:function:asdfsd'))])

    sm.add_state(parallel)
    print(sm.to_dict())