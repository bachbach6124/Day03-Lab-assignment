import json
import re
from typing import List, Dict, Any, Optional
from src.core.llm_provider import LLMProvider
from src.agent.prompts import build_react_prompt
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker

class ReActAgent:
    """
    A ReAct-style Agent that follows the Thought-Action-Observation loop.
    """
    
    def __init__(
        self,
        llm: LLMProvider,
        tools: List[Dict[str, Any]],
        max_steps: int = 5,
        version: str = "v1",
    ):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.version = version
        self.history = []
        self.last_run_stats = self._new_run_stats()

    def get_system_prompt(self) -> str:
        tool_descriptions = "\n".join(
            [f"- {tool['name']}: {tool['description']}" for tool in self.tools]
        )
        return build_react_prompt(tool_descriptions, version=self.version)

    def run(self, user_input: str) -> str:
        """
        Run the ReAct loop until the model produces a final answer or max_steps is reached.
        """
        self.last_run_stats = self._new_run_stats()
        logger.log_event(
            "AGENT_START",
            {
                "input": user_input,
                "model": self.llm.model_name,
                "max_steps": self.max_steps,
                "tools": self._available_tool_names(),
                "version": self.version,
            },
        )
        
        conversation_trace = f"User request:\n{user_input}"

        for step in range(1, self.max_steps + 1):
            result = self.llm.generate(
                conversation_trace,
                system_prompt=self.get_system_prompt(),
            )
            self._track_llm_metric(result)
            usage = result.get("usage", {})
            self.last_run_stats["tokens"] += usage.get("total_tokens", 0)
            self.last_run_stats["cost"] += self._estimate_cost(usage.get("total_tokens", 0))
            self.last_run_stats["latency_ms"] += result.get("latency_ms", 0)

            content = result.get("content", "") or ""
            self.history.append({"step": step, "llm_response": content})
            logger.log_event(
                "LLM_RESPONSE",
                {
                    "step": step,
                    "content": content,
                    "provider": result.get("provider"),
                    "usage": result.get("usage", {}),
                    "latency_ms": result.get("latency_ms"),
                },
            )

            final_answer = self._parse_final_answer(content)
            if final_answer:
                logger.log_event(
                    "AGENT_END",
                    {"status": "success", "steps": step, "final_answer": final_answer},
                )
                self.last_run_stats["loop_count"] = step
                self.last_run_stats["final_answer"] = final_answer
                return final_answer

            action = self._parse_action(content)
            if not action:
                self.last_run_stats["parser_errors"] += 1
                observation = {
                    "error": "PARSER_ERROR",
                    "message": "Could not parse Action. Use: Action: tool_name({\"key\": \"value\"})",
                }
                logger.log_event(
                    "PARSER_ERROR",
                    {"step": step, "content": content, "observation": observation},
                )
                conversation_trace = self._append_observation(
                    conversation_trace,
                    content,
                    observation,
                )
                continue

            logger.log_event(
                "TOOL_CALL",
                {
                    "step": step,
                    "tool_name": action["tool_name"],
                    "args": action["args"],
                },
            )
            observation = self._execute_tool(action["tool_name"], action["args"])
            self.last_run_stats["tools_used"].append(action["tool_name"])
            if observation.get("error") in {"TOOL_EXECUTION_ERROR", "TOOL_NOT_FOUND"}:
                self.last_run_stats["tool_errors"] += 1
            logger.log_event(
                "TOOL_OBSERVATION",
                {
                    "step": step,
                    "tool_name": action["tool_name"],
                    "observation": observation,
                },
            )
            conversation_trace = self._append_observation(
                conversation_trace,
                content,
                observation,
            )
            
        message = (
            "Dạ xin lỗi, hiện tại hệ thống chưa hoàn tất xử lý yêu cầu trong "
            "giới hạn số bước. Shop sẽ cần kiểm tra thêm thông tin trước khi phản hồi chính xác ạ."
        )
        logger.log_event(
            "TIMEOUT",
            {"max_steps": self.max_steps, "message": message},
        )
        self.last_run_stats["timeout_errors"] += 1
        self.last_run_stats["loop_count"] = self.max_steps
        self.last_run_stats["final_answer"] = message
        logger.log_event(
            "AGENT_END",
            {"status": "timeout", "steps": self.max_steps},
        )
        return message

    def _parse_final_answer(self, content: str) -> Optional[str]:
        match = re.search(r"Final Answer\s*:\s*(.+)", content, re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        answer = match.group(1).strip()
        return answer or None

    def _parse_action(self, content: str) -> Optional[Dict[str, Any]]:
        cleaned = self._strip_code_fences(content)
        match = re.search(
            r"Action\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((\s*\{.*\}\s*)\)",
            cleaned,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None

        tool_name = match.group(1)
        args_text = match.group(2)
        try:
            args = json.loads(args_text)
        except json.JSONDecodeError as exc:
            logger.log_event(
                "PARSER_ERROR",
                {
                    "tool_name": tool_name,
                    "args_text": args_text,
                    "message": str(exc),
                },
            )
            return None

        if not isinstance(args, dict):
            logger.log_event(
                "PARSER_ERROR",
                {
                    "tool_name": tool_name,
                    "args_text": args_text,
                    "message": "Action arguments must be a JSON object.",
                },
            )
            return None

        return {"tool_name": tool_name, "args": args}

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute tools using the agreed interface: tool["func"](args: dict) -> dict.
        """
        for tool in self.tools:
            if tool["name"] != tool_name:
                continue

            try:
                result = tool["func"](args)
            except Exception as exc:
                observation = {
                    "error": "TOOL_EXECUTION_ERROR",
                    "message": str(exc),
                    "tool_name": tool_name,
                }
                logger.log_event("TOOL_ERROR", observation)
                return observation

            if isinstance(result, dict):
                return result
            return {"result": result}

        observation = {
            "error": "TOOL_NOT_FOUND",
            "message": f"Tool {tool_name} not found.",
            "available_tools": self._available_tool_names(),
        }
        logger.log_event("TOOL_ERROR", observation)
        return observation

    def _append_observation(
        self,
        conversation_trace: str,
        llm_content: str,
        observation: Dict[str, Any],
    ) -> str:
        return (
            f"{conversation_trace}\n\n"
            f"{llm_content.strip()}\n"
            f"Observation: {self._format_observation(observation)}"
        )

    def _format_observation(self, observation: Dict[str, Any]) -> str:
        return json.dumps(observation, ensure_ascii=False)

    def _available_tool_names(self) -> List[str]:
        return [tool["name"] for tool in self.tools]

    def _track_llm_metric(self, result: Dict[str, Any]) -> None:
        tracker.track_request(
            provider=result.get("provider", "unknown"),
            model=self.llm.model_name,
            usage=result.get("usage", {}),
            latency_ms=result.get("latency_ms", 0),
        )

    def _strip_code_fences(self, content: str) -> str:
        return re.sub(r"```(?:json|python|text)?\s*|\s*```", "", content, flags=re.IGNORECASE)

    def _new_run_stats(self) -> Dict[str, Any]:
        return {
            "tokens": 0,
            "cost": 0.0,
            "latency_ms": 0,
            "loop_count": 0,
            "tools_used": [],
            "parser_errors": 0,
            "tool_errors": 0,
            "timeout_errors": 0,
            "final_answer": "",
        }

    def _estimate_cost(self, total_tokens: int) -> float:
        return round((total_tokens / 1000) * 0.01, 6)
