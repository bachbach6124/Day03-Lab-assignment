import argparse
import json
import time
from pathlib import Path

from src.agent.run_agent import build_agent
from src.chatbot import BaselineChatbot, build_provider_from_env
from src.tools.retail_tools import (
    load_json,
    save_json,
)


ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT_DIR / "logs"
BASELINE_LOG = LOG_DIR / "chatbot_baseline.jsonl"
AGENT_V1_LOG = LOG_DIR / "agent_v1.jsonl"
AGENT_V2_LOG = LOG_DIR / "agent_v2.jsonl"
SUMMARY_LOG = LOG_DIR / "evaluation_summary.json"


def write_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def clear_logs() -> None:
    for path in [BASELINE_LOG, AGENT_V1_LOG, AGENT_V2_LOG, SUMMARY_LOG]:
        if path.exists():
            path.unlink()


def run_chatbot_case(case: dict, use_env_llm: bool = False) -> dict:
    chatbot = BaselineChatbot(llm=build_provider_from_env() if use_env_llm else None)
    started = time.time()
    response = chatbot.answer(case["user_query"])
    latency_ms = response.get("latency_ms") or int((time.time() - started) * 1000)
    predicted_success = False

    return {
        "case_id": case["case_id"],
        "case_name": case["case_name"],
        "system": "Chatbot baseline",
        "expected_success": case["expected_success"],
        "predicted_success": predicted_success,
        "success": predicted_success == case["expected_success"],
        "latency_ms": latency_ms,
        "tokens": response.get("usage", {}).get("total_tokens", 0),
        "cost": estimate_cost(response.get("usage", {}).get("total_tokens", 0)),
        "loop_count": 1,
        "tools_used": [],
        "failure_type": None if predicted_success == case["expected_success"] else "baseline_no_tool_verification",
        "parser_errors": 0,
        "tool_errors": 0,
        "timeout_errors": 0,
        "response": response.get("content", ""),
    }


def run_agent_case(case: dict, version: str, use_env_llm: bool = True) -> dict:
    system_name = f"Agent {version}"
    started = time.time()
    agent = build_agent(version=version, use_env_llm=use_env_llm)
    final_answer = ""
    provider_error = None

    try:
        final_answer = agent.run(case["user_query"])
    except Exception as exc:
        provider_error = str(exc)
        final_answer = f"Provider error: {exc}"

    stats = agent.last_run_stats
    tools_used = stats.get("tools_used", [])
    predicted_success = "create_return_ticket" in tools_used
    success = predicted_success == case["expected_success"]
    latency_ms = stats.get("latency_ms") or int((time.time() - started) * 1000)
    failure_type = classify_failure(case, tools_used, provider_error)

    return {
        "case_id": case["case_id"],
        "case_name": case["case_name"],
        "system": system_name,
        "expected_success": case["expected_success"],
        "predicted_success": predicted_success,
        "success": success,
        "latency_ms": latency_ms,
        "tokens": stats.get("tokens", 0),
        "cost": round(stats.get("cost", 0.0), 6),
        "loop_count": stats.get("loop_count", len(tools_used)),
        "tools_used": tools_used,
        "expected_tools": case["expected_tools"],
        "failure_type": None if success else failure_type or "unexpected_result",
        "parser_errors": stats.get("parser_errors", 0),
        "tool_errors": stats.get("tool_errors", 0),
        "timeout_errors": stats.get("timeout_errors", 0),
        "final_answer": final_answer,
        "provider_error": provider_error,
    }


def classify_failure(case: dict, tools_used: list[str], provider_error: str | None = None) -> str | None:
    if provider_error:
        return "provider_error"
    if "create_return_ticket" in tools_used and not case["expected_success"]:
        return "created_ticket_for_negative_case"
    if case["expected_success"] and "create_return_ticket" not in tools_used:
        return "ticket_not_created"
    missing_tools = [tool for tool in case["expected_tools"] if tool not in tools_used]
    if missing_tools:
        return "missing_expected_tools"
    return None


def estimate_cost(total_tokens: int) -> float:
    return round((total_tokens / 1000) * 0.01, 6)


def summarize(results: list[dict]) -> dict:
    by_system: dict[str, list[dict]] = {}
    for item in results:
        by_system.setdefault(item["system"], []).append(item)

    summary = {}
    for system, items in by_system.items():
        total = len(items)
        passed = sum(1 for item in items if item["success"])
        summary[system] = {
            "total_cases": total,
            "passed_cases": passed,
            "success_rate": round(passed / total, 4) if total else 0,
            "average_latency_ms": round(
                sum(item["latency_ms"] for item in items) / total,
                2,
            )
            if total
            else 0,
            "total_tokens": sum(item["tokens"] for item in items),
            "estimated_cost": round(sum(item["cost"] for item in items), 6),
            "average_loop_count": round(
                sum(item["loop_count"] for item in items) / total,
                2,
            )
            if total
            else 0,
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retail return systems.")
    parser.add_argument(
        "--use-env-llm",
        action="store_true",
        help="Use DEFAULT_PROVIDER for chatbot baseline too. Agents use DEFAULT_PROVIDER by default.",
    )
    parser.add_argument(
        "--offline-agents",
        action="store_true",
        help="Use the reliable offline scripted provider for Agent v1/v2 instead of DEFAULT_PROVIDER.",
    )
    parser.add_argument(
        "--keep-logs",
        action="store_true",
        help="Append to existing logs instead of clearing them first.",
    )
    args = parser.parse_args()

    if not args.keep_logs:
        clear_logs()

    cases = load_json("test_cases.json")
    original_tickets = load_json("return_tickets.json")
    results = []

    try:
        for case in cases:
            baseline_result = run_chatbot_case(case, use_env_llm=args.use_env_llm)
            results.append(baseline_result)
            write_jsonl(BASELINE_LOG, baseline_result)

            agent_v1_result = run_agent_case(case, "v1", use_env_llm=not args.offline_agents)
            results.append(agent_v1_result)
            write_jsonl(AGENT_V1_LOG, agent_v1_result)

            agent_v2_result = run_agent_case(case, "v2", use_env_llm=not args.offline_agents)
            results.append(agent_v2_result)
            write_jsonl(AGENT_V2_LOG, agent_v2_result)
    finally:
        save_json("return_tickets.json", original_tickets)

    summary = summarize(results)
    write_summary(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def write_summary(summary: dict) -> None:
    SUMMARY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_LOG.open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)
        file.write("\n")


if __name__ == "__main__":
    main()
