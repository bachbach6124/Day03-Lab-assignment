import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Generator, Optional

from src.agent.agent import ReActAgent
from src.chatbot import build_provider_from_env
from src.core.llm_provider import LLMProvider
from src.tools import TOOLS


ROOT_DIR = Path(__file__).resolve().parents[2]
TRACE_DIR = ROOT_DIR / "logs" / "traces"


class ScriptedRetailReActProvider(LLMProvider):
    """Deterministic ReAct provider for reliable local demos and evaluation."""

    def __init__(self, version: str = "v1"):
        super().__init__(model_name=f"scripted-react-{version}")
        self.version = version

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        content = self._next_response(prompt)
        latency_ms = int((time.time() - start_time) * 1000)
        prompt_tokens = len((system_prompt or "").split()) + len(prompt.split())
        completion_tokens = len(content.split())
        return {
            "content": content,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "latency_ms": latency_ms,
            "provider": "scripted_offline",
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        yield self.generate(prompt, system_prompt=system_prompt)["content"]

    def _next_response(self, prompt: str) -> str:
        if "Observation:" not in prompt:
            return self._order_action(prompt)

        observations = self._observations(prompt)
        last_observation = observations[-1] if observations else {}

        if last_observation.get("error") == "PARSER_ERROR":
            return self._order_action(prompt)

        if "order_id" in last_observation or "policy_valid" in last_observation:
            if last_observation.get("policy_valid") is True:
                target_size = self._target_size(prompt)
                product_id = self._product_id(prompt)
                return (
                    "Thought: Đơn hàng hợp lệ, cần kiểm tra tồn kho size khách muốn đổi.\n"
                    f'Action: check_warehouse_stock({{"product_id": "{product_id}", "size": "{target_size}"}})'
                )
            return self._policy_final_answer(last_observation)

        if last_observation.get("status") in {"available", "out_of_stock", "not_found"}:
            if last_observation.get("status") == "available":
                order_id = self._latest_value(observations, "order_id")
                current_size = self._latest_value(observations, "current_size") or "M"
                target_size = self._target_size(prompt)
                return (
                    "Thought: Size cần đổi còn hàng, có thể tạo phiếu đổi hàng.\n"
                    "Action: create_return_ticket("
                    f'{{"order_id": "{order_id}", "action_type": "EXCHANGE", '
                    f'"detail": "Đổi từ size {current_size} lên size {target_size} do chật"}})'
                )
            return self._stock_final_answer(last_observation)

        if last_observation.get("ticket_id"):
            return (
                "Final Answer: Dạ shop đã kiểm tra đơn hàng hợp lệ và size cần đổi còn hàng. "
                f"Shop đã tạo phiếu đổi hàng {last_observation['ticket_id']}; shipper sẽ thu hồi hàng cũ khi giao hàng mới. "
                f"Thời gian xử lý dự kiến {last_observation.get('estimated_process_time', '2-3 ngày')} ạ."
            )

        return (
            "Final Answer: Dạ shop chưa đủ dữ liệu để xử lý tự động. "
            "Bạn vui lòng cung cấp thêm mã đơn hàng hoặc số điện thoại đặt hàng ạ."
        )

    def _order_action(self, prompt: str) -> str:
        product_id = self._product_id(prompt)
        customer_id = self._customer_id(prompt)
        return (
            "Thought: Cần kiểm tra đơn hàng và điều kiện đổi trả trước.\n"
            f'Action: check_order_status({{"customer_id": "{customer_id}", "product_id": "{product_id}"}})'
        )

    def _policy_final_answer(self, observation: dict) -> str:
        reason = observation.get("reason", "đơn hàng không đủ điều kiện đổi trả")
        if observation.get("error") == "order_not_found":
            return (
                "Final Answer: Dạ shop chưa tìm thấy đơn hàng tương ứng. "
                "Bạn vui lòng gửi thêm mã đơn hàng hoặc số điện thoại đặt hàng để shop kiểm tra lại ạ."
            )
        return f"Final Answer: Dạ shop đã kiểm tra và hiện chưa thể hỗ trợ đổi hàng vì: {reason}."

    def _stock_final_answer(self, observation: dict) -> str:
        if self.version == "v2":
            return (
                "Final Answer: Dạ shop đã kiểm tra đơn hàng hợp lệ nhưng size bạn muốn đổi hiện chưa còn hàng. "
                "Shop có thể ghi nhận để báo lại khi có restock hoặc hỗ trợ bạn chọn size/mẫu khác ạ."
            )
        return "Final Answer: Dạ size bạn muốn đổi hiện chưa còn hàng, shop chưa thể tạo phiếu đổi lúc này ạ."

    def _observations(self, prompt: str) -> list[dict]:
        rows = []
        for match in re.finditer(r"Observation:\s*(\{.*?\})(?=\n|$)", prompt):
            try:
                rows.append(json.loads(match.group(1)))
            except json.JSONDecodeError:
                continue
        return rows

    def _product_id(self, prompt: str) -> str:
        match = re.search(r"\bAT\d{3}\b", prompt.upper())
        return match.group(0) if match else "AT102"

    def _target_size(self, prompt: str) -> str:
        patterns = [
            r"sang size\s+([A-Z]{1,2})",
            r"lên size\s+([A-Z]{1,2})",
            r"size\s+([A-Z]{1,2})\s*$",
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return "L"

    def _customer_id(self, prompt: str) -> str:
        match = re.search(r"\bUSER_\d+\b", prompt.upper())
        return match.group(0) if match else "USER_48291"

    def _latest_value(self, observations: list[dict], key: str) -> Any:
        for observation in reversed(observations):
            if key in observation:
                return observation[key]
        return None


def build_agent(version: str, use_env_llm: bool = True) -> ReActAgent:
    llm = build_provider_from_env() if use_env_llm else ScriptedRetailReActProvider(version)
    if llm is None:
        llm = ScriptedRetailReActProvider(version)
    max_steps = 6 if version == "v2" else 5
    return ReActAgent(llm=llm, tools=TOOLS, max_steps=max_steps, version=version)


def write_trace(version: str, query: str, answer: str, stats: dict) -> None:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    path = TRACE_DIR / f"agent_{version}_manual.jsonl"
    payload = {
        "timestamp": time.time(),
        "system": f"Agent {version}",
        "query": query,
        "final_answer": answer,
        **stats,
    }
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the retail ReAct agent.")
    parser.add_argument("query", nargs="*", help="Customer question")
    parser.add_argument("--version", choices=["v1", "v2"], default="v2")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use the reliable offline scripted provider instead of DEFAULT_PROVIDER from .env.",
    )
    args = parser.parse_args()

    query = " ".join(args.query).strip()
    if not query:
        query = input("Customer: ").strip()

    agent_input = enrich_demo_query(query)
    agent = build_agent(version=args.version, use_env_llm=not args.offline)
    try:
        answer = agent.run(agent_input)
    except Exception as exc:
        answer = f"Dạ hiện agent chưa gọi được LLM/provider: {exc}"

    write_trace(args.version, query, answer, agent.last_run_stats)
    print(answer)


def enrich_demo_query(query: str) -> str:
    if re.search(r"\bUSER_\d+\b", query.upper()):
        return query
    return f"{query}\n\nKnown lab demo customer_id: USER_48291"


if __name__ == "__main__":
    main()
