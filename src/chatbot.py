import argparse
import os
import time
from typing import Any, Optional

from dotenv import load_dotenv


BASELINE_SYSTEM_PROMPT = """
Bạn là chatbot chăm sóc khách hàng của shop thời trang.
Trả lời trực tiếp, lịch sự và ngắn gọn.
Không được khẳng định đã kiểm tra đơn hàng, tồn kho hoặc tạo phiếu đổi hàng.
""".strip()


class BaselineChatbot:
    def __init__(self, llm: Optional[Any] = None):
        self.llm = llm

    def answer(self, user_query: str) -> dict:
        start_time = time.time()

        if self.llm is not None:
            result = self.llm.generate(
                user_query,
                system_prompt=BASELINE_SYSTEM_PROMPT,
            )
            return {
                "content": result.get("content", ""),
                "latency_ms": result.get("latency_ms", 0),
                "usage": result.get("usage", {}),
                "provider": result.get("provider", "unknown"),
                "model": getattr(self.llm, "model_name", "unknown"),
            }

        content = (
            "Shop đã nhận yêu cầu đổi size của bạn. Bạn vui lòng cung cấp mã đơn "
            "hàng và giữ sản phẩm còn nguyên trạng để shop chuyển bộ phận xử lý "
            "kiểm tra điều kiện đổi hàng, tồn kho size mới và hướng dẫn bước tiếp theo."
        )
        latency_ms = int((time.time() - start_time) * 1000)
        estimated_tokens = max(1, len(user_query.split()) + len(content.split()))

        return {
            "content": content,
            "latency_ms": latency_ms,
            "usage": {
                "prompt_tokens": len(user_query.split()),
                "completion_tokens": len(content.split()),
                "total_tokens": estimated_tokens,
            },
            "provider": "offline_baseline",
            "model": "rule_free_direct_reply",
        }


def build_provider_from_env() -> Optional[Any]:
    load_dotenv()
    provider = os.getenv("DEFAULT_PROVIDER", "").lower()

    if provider == "openai":
        from src.core.openai_provider import OpenAIProvider

        return OpenAIProvider(
            model_name=os.getenv("OPENAI_MODEL", "gpt-4o"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    if provider in {"gemini", "google"}:
        from src.core.gemini_provider import GeminiProvider

        return GeminiProvider(
            model_name=os.getenv(
                "GEMINI_MODEL",
                os.getenv("DEFAULT_MODEL", "gemini-1.5-flash"),
            ),
            api_key=os.getenv("GEMINI_API_KEY"),
        )

    if provider == "local":
        from src.core.local_provider import LocalProvider

        return LocalProvider(
            model_path=os.getenv(
                "LOCAL_MODEL_PATH",
                "./models/Phi-3-mini-4k-instruct-q4.gguf",
            )
        )

    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the baseline retail chatbot.")
    parser.add_argument("query", nargs="*", help="Customer question")
    parser.add_argument(
        "--use-env-llm",
        action="store_true",
        help="Use DEFAULT_PROVIDER from .env instead of offline fallback.",
    )
    args = parser.parse_args()

    user_query = " ".join(args.query).strip()
    if not user_query:
        user_query = input("Customer: ").strip()

    llm = build_provider_from_env() if args.use_env_llm else None
    chatbot = BaselineChatbot(llm=llm)
    result = chatbot.answer(user_query)
    print(result["content"])


if __name__ == "__main__":
    main()
