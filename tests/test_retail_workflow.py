from src.agent.agent import ReActAgent
from src.agent.run_agent import build_agent
from src.core.llm_provider import LLMProvider
from src.evaluate import assess_case_result, run_agent_case
from src.tools.retail_tools import check_order_status, check_warehouse_stock, load_json


class DummyProvider(LLMProvider):
    def __init__(self):
        super().__init__(model_name="dummy")

    def generate(self, prompt: str, system_prompt: str | None = None) -> dict:
        return {
            "content": "Final Answer: done",
            "usage": {"total_tokens": 0},
            "latency_ms": 0,
            "provider": "dummy",
        }

    def stream(self, prompt: str, system_prompt: str | None = None):
        yield "Final Answer: done"


def test_check_order_status_valid_and_expired_cases():
    valid = check_order_status({"customer_id": "USER_48291", "product_id": "AT104"})
    expired = check_order_status({"customer_id": "USER_48291", "product_id": "AT103"})

    assert valid["policy_valid"] is True
    assert valid["order_id"] == "DH-66304"
    assert expired["policy_valid"] is False
    assert expired["reason"] == "Expired 7-day exchange window"


def test_check_warehouse_stock_reports_out_of_stock_size_l():
    result = check_warehouse_stock({"product_id": "AT104", "size": "L"})

    assert result["status"] == "out_of_stock"
    assert result["stock_quantity"] == 0


def test_parse_action_accepts_json_object_inside_code_fence():
    agent = ReActAgent(llm=DummyProvider(), tools=[])
    content = """
```text
Thought: kiểm tra kho.
Action: check_warehouse_stock({"product_id": "AT104", "size": "L"})
```
"""

    assert agent._parse_action(content) == {
        "tool_name": "check_warehouse_stock",
        "args": {"product_id": "AT104", "size": "L"},
    }


def test_parse_action_rejects_non_json_arguments():
    agent = ReActAgent(llm=DummyProvider(), tools=[])

    assert agent._parse_action("Action: check_order_status(customer_id='USER_48291')") is None


def test_tc03_mock_data_represents_valid_order_with_size_l_out_of_stock():
    case = next(case for case in load_json("test_cases.json") if case["case_id"] == "TC03")

    assert case["product_id"] == "AT104"
    assert check_order_status(
        {"customer_id": case["customer_id"], "product_id": case["product_id"]}
    )["policy_valid"] is True
    assert check_warehouse_stock(
        {"product_id": case["product_id"], "size": case["target_size"]}
    )["status"] == "out_of_stock"


def test_evaluation_fails_tc03_when_stock_check_is_missing():
    case = next(case for case in load_json("test_cases.json") if case["case_id"] == "TC03")

    assessment = assess_case_result(case, ["check_order_status"])

    assert assessment["outcome_matches"] is True
    assert assessment["success"] is False
    assert assessment["missing_expected_tools"] == ["check_warehouse_stock"]


def test_scripted_agent_handles_tc03_with_stock_check_and_no_ticket():
    case = next(case for case in load_json("test_cases.json") if case["case_id"] == "TC03")

    result = run_agent_case(case, "v2", use_env_llm=False)

    assert result["success"] is True
    assert result["predicted_success"] is False
    assert result["tools_used"] == ["check_order_status", "check_warehouse_stock"]
    assert result["failure_type"] is None


def test_agent_history_includes_action_and_observation_for_web_logs():
    agent = build_agent(version="v2", use_env_llm=False)

    agent.run("Mình muốn đổi áo polo mã AT104 từ size M sang size L.")

    assert any("action" in item for item in agent.history)
    assert any(
        item.get("observation", {}).get("status") == "out_of_stock"
        for item in agent.history
    )
