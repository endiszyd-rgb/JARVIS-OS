import json
import pytest
from jarvis.tool_registry import ToolSpec
from jarvis.tool_plan import validate_calls

SPEC=ToolSpec('mqtt','status','demo','Synthetic reviewed operation',json.dumps({'type':'object','properties':{'message':{'type':'string'}},'additionalProperties':False}))
BINDINGS={'read_status':SPEC}

def call(**extra):
    return {'id':'call_1','name':'read_status','arguments':{},**extra}


def test_validated_arguments_are_detached_from_model_data():
    raw=call(arguments={'message':'Synthetic'})
    plan=validate_calls([raw],BINDINGS)
    raw['arguments']['message']='Modified after validation'
    assert plan[0].arguments=={'message':'Synthetic'} and plan[0].tool is SPEC
    decoded=plan[0].arguments;decoded['message']='Changed returned copy'
    assert plan[0].arguments=={'message':'Synthetic'}


@pytest.mark.parametrize('raw', [[call(name='open_gate')],[call(role='owner')],
 [call(arguments={'unexpected':True})],[call(arguments={'message':42})],
 [call(),call()],[call(arguments='not JSON')],[call(arguments='[]')],
 [call(arguments={'message':'x'*65536})]])
def test_invalid_or_injected_plans_are_refused(raw):
    with pytest.raises(ValueError):validate_calls(raw,BINDINGS)


def test_previous_call_cannot_be_replayed_in_a_later_round():
    with pytest.raises(ValueError):validate_calls([call()],BINDINGS,previous_ids={'call_1'})


def test_remaining_budget_is_enforced_before_processing_a_batch():
    with pytest.raises(ValueError):validate_calls([call()],BINDINGS,remaining=0)
    assert validate_calls([],BINDINGS,remaining=0)==()


def test_wire_json_arguments_are_checked_against_server_schema():
    assert validate_calls([call(arguments='{"message":"Hello"}')],BINDINGS)[0].arguments=={'message':'Hello'}
