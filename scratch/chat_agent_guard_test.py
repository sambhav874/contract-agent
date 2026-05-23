import sys
sys.path.insert(0, '.')

from app.agents.chat_agent import (
    classify_intent, ResponseMode, _is_compound_question,
    _serialize_structured_data, _extract_thinking, _hallucination_guard_check,
    ChatAgent
)
import ast

print('=== TEST 4: Re-run with refined guard ===')

# 1. Intent classification
test_queries = [
    ('explain the penalty clause', ResponseMode.TEXT_ONLY),
    ('show me kpi dashboard', ResponseMode.DATA_VIZ),
    ('draw a process flow', ResponseMode.DIAGRAM),
    ('what can you do', ResponseMode.INTROSPECTION),
    ('show me the breach dashboard', ResponseMode.DATA_VIZ),
    ('what is the contract structure', ResponseMode.TEXT_ONLY),
]
for query, expected_mode in test_queries:
    mode = classify_intent(query)
    assert mode == expected_mode, f'Expected {expected_mode} for "{query}", got {mode}'
print('  Intent classification (6 queries): OK')

# 2. Compound question detection
compound = [
    'What is the penalty clause and show me a chart?',
    'Explain Article IV and also give me breach status?',
    'Show dashboard. What is force majeure?',
]
for q in compound:
    assert _is_compound_question(q), f'Expected compound: {q}'
non_compound = ['What is the penalty?', 'Show dashboard', 'Explain Article IV']
for q in non_compound:
    assert not _is_compound_question(q), f'Expected non-compound: {q}'
print('  Compound question detection: OK')

# 3. Structured data serialization
kpis = [
    {'kpi_id': 'KPI-01', 'name': 'On-time Delivery', 'value_min': 95.0, 'unit': '%',
     'operator': '>=', 'party': 'Supplier', 'consequence_value': 500.0, 'consequence_unit': 'USD',
     'remediation': 'Root cause analysis', 'remediation_sla': '48h', 'trigger_condition': 'value < 95'}
]
breaches = [
    {'kpi_id': 'KPI-01', 'is_breach': True, 'penalty_amount': 500.0, 'actual_value': 92.0,
     'threshold_value': 95.0, 'operator': '>=', 'status': 'Open', 'sample_count': 1,
     'remediation': 'RCA required', 'remediation_sla': '48h', 'penalty_triggered': 'Late delivery'}
]
actuals = [
    {'kpi_id': 'KPI-01', 'value': 92.0, 'unit': '%', 'timestamp': '2024-01-15T10:00:00Z', 'source': 'ERP'}
]
result = _serialize_structured_data(kpis, breaches, actuals)
assert 'On-time Delivery' in result
assert '500.0' in result
assert '92.0' in result
print('  Full structured data: OK')

# 4. Thinking extraction
thought, plan, answer = _extract_thinking('No tags here, plain answer.')
assert answer == 'No tags here, plain answer.'
assert not thought and not plan

thought, plan, answer = _extract_thinking('<thought>Need to find penalty clause</thought>Answer is in Article IV.')
assert thought == 'Need to find penalty clause'
assert 'Article IV' in answer

thought, plan, answer = _extract_thinking('<thought>Think</thought><plan>Plan</plan><answer>Final answer</answer>')
assert thought == 'Think'
assert plan == 'Plan'
assert 'Final answer' in answer
print('  Thinking extraction: OK')

# 5. Hallucination guard
assert _hallucination_guard_check('Some text', ResponseMode.TEXT_ONLY)
assert _hallucination_guard_check('The penalty is $500', ResponseMode.DATA_VIZ)  # prose, no code block
assert _hallucination_guard_check('The penalty is $500', ResponseMode.DIAGRAM)  # prose, no code block
# HTML code block with value but no structured data ref
assert not _hallucination_guard_check('```html\n<div>$500</div>\n```', ResponseMode.DATA_VIZ)
# SVG code block with value and structured data ref
assert _hallucination_guard_check('```svg\n<path>$500</path>\n```\nSTRUCTURED DATA', ResponseMode.DIAGRAM)
print('  Hallucination guard: OK')

# 6. ChatAgent
t = ChatAgent('test-contract-123')
tools = t._tools()
assert len(tools) == 1
assert len(tools[0].function_declarations) == 3
print('  ChatAgent tools: OK')

# 7. Syntax
with open('app/agents/chat_agent.py', 'rb') as f:
    ast.parse(f.read())
print('  Syntax: OK')

print()
print('=== ALL TESTS PASSED ===')
