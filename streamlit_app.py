import copy
import json
import re
from pathlib import Path
from typing import Any, Optional

import streamlit as st

from src.agent.run_agent import (
    ScriptedRetailReActProvider,
    build_agent,
    enrich_demo_query,
)
from src.chatbot import BaselineChatbot
from src.evaluate import assess_case_result
from src.tools import TOOLS


ROOT_DIR = Path(__file__).resolve().parent
TEST_CASES_PATH = ROOT_DIR / "src" / "tools" / "mock_data" / "test_cases.json"
RETURN_TICKETS_PATH = ROOT_DIR / "src" / "tools" / "mock_data" / "return_tickets.json"
LOG_DIR = ROOT_DIR / "logs"


def load_test_cases() -> list[dict[str, Any]]:
    with TEST_CASES_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def restore_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def run_baseline(query: str) -> dict[str, Any]:
    chatbot = BaselineChatbot()
    return chatbot.answer(query)


def run_agent_with_fallback(
    query: str,
    version: str,
    use_env_llm: bool,
) -> tuple[str, dict[str, Any], list[dict[str, Any]], str, Optional[str]]:
    fallback_warning = None
    enriched_query = enrich_demo_query(query)
    tickets_snapshot = read_text(RETURN_TICKETS_PATH)

    try:
        agent = build_agent(version=version, use_env_llm=use_env_llm)
        answer = agent.run(enriched_query)
        provider_label = getattr(agent.llm, "model_name", "unknown")
        if use_env_llm and isinstance(agent.llm, ScriptedRetailReActProvider):
            fallback_warning = (
                "Không tìm thấy provider hợp lệ trong .env nên app đã dùng offline "
                "scripted provider cho lượt chạy này."
            )
        return (
            answer,
            copy.deepcopy(agent.last_run_stats),
            copy.deepcopy(agent.history),
            provider_label,
            fallback_warning,
        )
    except Exception as exc:
        fallback_warning = (
            "Không chạy được provider từ .env nên app đã chuyển sang offline scripted "
            f"provider. Chi tiết: {exc}"
        )
        offline_agent = build_agent(version=version, use_env_llm=False)
        offline_agent.llm = ScriptedRetailReActProvider(version)
        answer = offline_agent.run(enriched_query)
        provider_label = getattr(offline_agent.llm, "model_name", "scripted_offline")
        return (
            answer,
            copy.deepcopy(offline_agent.last_run_stats),
            copy.deepcopy(offline_agent.history),
            provider_label,
            fallback_warning,
        )
    finally:
        restore_text(RETURN_TICKETS_PATH, tickets_snapshot)


def parse_action(content: str) -> Optional[dict[str, Any]]:
    cleaned = re.sub(r"```(?:json|python|text)?\s*|\s*```", "", content, flags=re.IGNORECASE)
    match = re.search(
        r"Action\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((\s*\{.*\}\s*)\)",
        cleaned,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None

    try:
        args = json.loads(match.group(2))
    except json.JSONDecodeError:
        args = {"raw": match.group(2)}
    return {"tool_name": match.group(1), "args": args}


def list_local_log_files() -> list[Path]:
    if not LOG_DIR.exists():
        return []

    patterns = ["*.jsonl", "*.json", "*.log"]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(LOG_DIR.rglob(pattern))
    return sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)


def read_tail(path: Path, max_lines: int = 80) -> str:
    lines = read_text(path).splitlines()
    return "\n".join(lines[-max_lines:])


def metric_value(stats: dict[str, Any], key: str, default: Any = 0) -> Any:
    value = stats.get(key, default)
    return value if value not in (None, "") else default


def render_response_card(title: str, result: dict[str, Any]) -> None:
    st.subheader(title)
    st.write(result.get("content") or result.get("answer") or "")

    usage = result.get("usage", {})
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Latency", f"{result.get('latency_ms', 0)} ms")
    col_b.metric("Tokens", usage.get("total_tokens", 0))
    col_c.metric("Model", result.get("model", result.get("provider", "unknown")))


def render_agent_metrics(stats: dict[str, Any], provider_label: str) -> None:
    st.subheader("Agent details")
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Loops", metric_value(stats, "loop_count"))
    col_b.metric("Latency", f"{metric_value(stats, 'latency_ms')} ms")
    col_c.metric("Tokens", metric_value(stats, "tokens"))
    col_d.metric("Cost est.", f"${metric_value(stats, 'cost', 0.0):.6f}")

    col_e, col_f, col_g, col_h = st.columns(4)
    col_e.metric("Parser errors", metric_value(stats, "parser_errors"))
    col_f.metric("Tool errors", metric_value(stats, "tool_errors"))
    col_g.metric("Timeouts", metric_value(stats, "timeout_errors"))
    col_h.metric("Provider", provider_label)

    tools_used = stats.get("tools_used", [])
    if tools_used:
        st.caption("Tools used: " + " -> ".join(tools_used))
    else:
        st.caption("Tools used: none")


def render_case_checklist(case: dict[str, Any], stats: dict[str, Any]) -> None:
    assessment = assess_case_result(case, stats.get("tools_used", []))
    st.subheader("Evaluation checklist")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Outcome match", "yes" if assessment["outcome_matches"] else "no")
    col_b.metric("Tool order", "yes" if assessment["tool_sequence_ok"] else "no")
    col_c.metric("Case pass", "yes" if assessment["success"] else "no")

    if assessment["missing_expected_tools"]:
        st.warning(
            "Missing expected tools: "
            + " -> ".join(assessment["missing_expected_tools"])
        )
    else:
        st.caption("All expected tools were called.")


def render_trace(history: list[dict[str, Any]]) -> None:
    with st.expander("Reasoning trace", expanded=True):
        if not history:
            st.info("No trace available yet.")
            return

        for item in history:
            step = item.get("step", "?")
            content = item.get("llm_response", "")
            action = item.get("action") or parse_action(content)
            observation = item.get("observation")

            st.markdown(f"**Step {step}**")
            st.code(content, language="text")
            if action:
                st.caption("Action")
                st.json(action)
            if observation:
                st.caption("Observation")
                st.json(observation)


def render_current_run_logs(
    baseline_result: dict[str, Any],
    agent_answer: str,
    agent_stats: dict[str, Any],
    agent_history: list[dict[str, Any]],
    provider_label: str,
) -> None:
    with st.expander("Current run logs", expanded=False):
        st.json(
            {
                "baseline": baseline_result,
                "agent": {
                    "answer": agent_answer,
                    "provider": provider_label,
                    "stats": agent_stats,
                    "history": agent_history,
                },
            }
        )


def render_saved_logs() -> None:
    with st.expander("Saved local log files", expanded=False):
        log_files = list_local_log_files()
        if not log_files:
            st.info("No files found in logs/ yet.")
            return

        selected = st.selectbox(
            "Log file",
            log_files,
            format_func=lambda path: str(path.relative_to(ROOT_DIR)),
        )
        st.caption(str(selected))
        st.code(read_tail(selected), language="json")


def main() -> None:
    st.set_page_config(
        page_title="Retail Agent Demo",
        page_icon="💬",
        layout="wide",
    )

    st.title("Retail Chatbot vs ReAct Agent")
    st.caption("Demo đổi size/đổi trả: so sánh trả lời trực tiếp với agent có tool calls.")

    test_cases = load_test_cases()
    case_labels = ["Custom question"] + [
        f"{case['case_id']} - {case['case_name']}" for case in test_cases
    ]

    with st.sidebar:
        st.header("Demo settings")
        provider_mode = st.radio(
            "Provider mode",
            [".env LLM", "offline scripted"],
            index=0,
            help=".env LLM dùng DEFAULT_PROVIDER; offline scripted cho kết quả ổn định khi demo.",
        )
        agent_version = st.selectbox("Agent version", ["v2", "v1"], index=0)

        st.divider()
        st.subheader("Demo data")
        st.markdown(
            "- Customer: `USER_48291`\n"
            "- Valid exchange: `AT102` -> size `L`\n"
            "- Expired window: `AT103`\n"
            "- Out of stock: `AT104` -> size `L`\n"
            "- Final sale: `AT999`\n"
            "- Missing order: `AT404`"
        )

        st.divider()
        st.subheader("Available tools")
        for tool in TOOLS:
            st.caption(f"`{tool['name']}`")

    selected_case = st.selectbox("Preset case", case_labels)
    selected_data = None
    if selected_case != "Custom question":
        case_id = selected_case.split(" - ", 1)[0]
        selected_data = next((case for case in test_cases if case["case_id"] == case_id), None)

    default_query = (
        selected_data["user_query"]
        if selected_data
        else "Mình mới nhận cái áo thun mã AT102 hôm qua nhưng mặc bị chật quá, giờ mình muốn đổi từ size M lên size L thì làm thế nào shop?"
    )

    query = st.text_area(
        "Customer question",
        value=default_query,
        height=120,
        placeholder="Nhập câu hỏi khách hàng...",
    )

    if selected_data:
        st.caption(
            f"Expected: {selected_data['expected_behavior']} "
            f"| Tools: {' -> '.join(selected_data['expected_tools'])}"
        )

    run_clicked = st.button("Run comparison", type="primary", use_container_width=True)
    if not run_clicked:
        st.info("Chọn preset hoặc nhập câu hỏi, sau đó bấm Run comparison.")
        return

    if not query.strip():
        st.warning("Vui lòng nhập câu hỏi khách hàng.")
        return

    use_env_llm = provider_mode == ".env LLM"

    with st.spinner("Running baseline chatbot and ReAct agent..."):
        baseline_result = run_baseline(query.strip())
        agent_answer, agent_stats, agent_history, provider_label, warning = run_agent_with_fallback(
            query=query.strip(),
            version=agent_version,
            use_env_llm=use_env_llm,
        )

    if warning:
        st.warning(warning)

    col_chatbot, col_agent = st.columns(2)
    with col_chatbot:
        render_response_card("Baseline Chatbot", baseline_result)

    with col_agent:
        render_response_card(
            "ReAct Agent",
            {
                "content": agent_answer,
                "latency_ms": agent_stats.get("latency_ms", 0),
                "usage": {"total_tokens": agent_stats.get("tokens", 0)},
                "model": provider_label,
            },
        )

    st.divider()
    render_agent_metrics(agent_stats, provider_label)
    if selected_data:
        render_case_checklist(selected_data, agent_stats)
    render_trace(agent_history)
    render_current_run_logs(
        baseline_result,
        agent_answer,
        agent_stats,
        agent_history,
        provider_label,
    )
    render_saved_logs()


if __name__ == "__main__":
    main()
