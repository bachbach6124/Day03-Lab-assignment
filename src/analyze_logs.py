import argparse
import json
from collections import Counter
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT_DIR / "logs"
LOG_FILES = {
    "Chatbot baseline": LOG_DIR / "chatbot_baseline.jsonl",
    "Agent v1": LOG_DIR / "agent_v1.jsonl",
    "Agent v2": LOG_DIR / "agent_v2.jsonl",
}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []

    rows = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def calculate_metrics(rows: list[dict]) -> dict:
    if not rows:
        return {
            "success_rate": 0.0,
            "average_latency_ms": 0.0,
            "total_tokens": 0,
            "estimated_cost": 0.0,
            "average_loop_count": 0.0,
            "failure_types": {},
            "parser_errors": 0,
            "tool_errors": 0,
            "timeout_errors": 0,
        }

    total = len(rows)
    failure_types = Counter(
        row.get("failure_type")
        for row in rows
        if row.get("failure_type")
    )

    return {
        "success_rate": sum(1 for row in rows if row.get("success")) / total,
        "average_latency_ms": sum(row.get("latency_ms", 0) for row in rows) / total,
        "total_tokens": sum(row.get("tokens", 0) for row in rows),
        "estimated_cost": sum(row.get("cost", 0.0) for row in rows),
        "average_loop_count": sum(row.get("loop_count", 0) for row in rows) / total,
        "failure_types": dict(failure_types),
        "parser_errors": sum(row.get("parser_errors", 0) for row in rows),
        "tool_errors": sum(row.get("tool_errors", 0) for row in rows),
        "timeout_errors": sum(row.get("timeout_errors", 0) for row in rows),
    }


def format_metrics_table(metrics_by_system: dict[str, dict]) -> str:
    header = (
        f"{'System':<18} {'Success Rate':>12} {'Avg Latency':>12} "
        f"{'Total Tokens':>13} {'Avg Loop':>9} {'Parser Errors':>14} "
        f"{'Tool Errors':>11} {'Timeout':>8}"
    )
    lines = [header, "-" * len(header)]

    for system, metrics in metrics_by_system.items():
        lines.append(
            f"{system:<18} "
            f"{metrics['success_rate'] * 100:>11.1f}% "
            f"{metrics['average_latency_ms']:>10.1f}ms "
            f"{metrics['total_tokens']:>13} "
            f"{metrics['average_loop_count']:>9.2f} "
            f"{metrics['parser_errors']:>14} "
            f"{metrics['tool_errors']:>11} "
            f"{metrics['timeout_errors']:>8}"
        )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze retail return evaluation logs.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print metrics as JSON instead of a table.",
    )
    args = parser.parse_args()

    metrics_by_system = {
        system: calculate_metrics(read_jsonl(path))
        for system, path in LOG_FILES.items()
    }

    if args.json:
        print(json.dumps(metrics_by_system, ensure_ascii=False, indent=2))
        return

    print(format_metrics_table(metrics_by_system))
    for system, metrics in metrics_by_system.items():
        if metrics["failure_types"]:
            print(f"{system} failure types: {metrics['failure_types']}")


if __name__ == "__main__":
    main()
