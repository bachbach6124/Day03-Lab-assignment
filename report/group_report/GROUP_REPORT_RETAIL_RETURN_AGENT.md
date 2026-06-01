# Group Report: Lab 3 - Production-Grade Agentic System

- **Team Name**: [Điền tên nhóm]
- **Team Members**: [Điền danh sách thành viên]
- **Deployment Date**: 2026-06-01

---

## 1. Executive Summary

Nhóm xây dựng hệ thống hỗ trợ đổi size/đổi trả cho shop thời trang, so sánh giữa một baseline chatbot trả lời trực tiếp và ReAct Agent có khả năng gọi tool để kiểm tra dữ liệu thật. Agent sử dụng vòng lặp `Thought -> Action -> Observation -> Final Answer` để kiểm tra điều kiện đổi trả, tồn kho và tạo phiếu đổi hàng khi đủ điều kiện.

Kết quả chạy evaluation offline ngày 2026-06-01:

| System | Passed / Total | Success Rate | Total Tokens | Avg Loop |
| :--- | ---: | ---: | ---: | ---: |
| Chatbot baseline | 0 / 5 | 0.0% | 327 | 1.00 |
| Agent v1 | 5 / 5 | 100.0% | 4133 | 2.60 |
| Agent v2 | 5 / 5 | 100.0% | 5504 | 2.60 |

**Key Outcome**: ReAct Agent đạt 100% trên bộ 5 test cases vì có khả năng verify bằng tool. Baseline chatbot trả lời lịch sự nhưng không gọi tool, không kiểm tra policy, không kiểm kho và không tạo ticket, nên fail theo tiêu chí production tool-verification.

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation

Luồng xử lý chính nằm trong `src/agent/agent.py`:

1. Agent nhận user query và system prompt chứa danh sách tool.
2. LLM sinh một trong hai dạng output:
   - `Action: tool_name({"key": "value"})`
   - `Final Answer: ...`
3. Nếu có `Action`, code parse JSON arguments và gọi Python function tương ứng.
4. Tool trả về `Observation` dạng JSON.
5. Observation được append vào conversation trace để LLM quyết định bước tiếp theo.
6. Agent dừng khi có `Final Answer` hoặc khi vượt `max_steps`.

Agent v1 và v2 dùng chung core loop nhưng khác prompt. Agent v2 thêm guardrails: chỉ tạo ticket khi đã quan sát `policy_valid=true` từ `check_order_status` và `status="available"` từ `check_warehouse_stock`.

### 2.2 Tool Definitions (Inventory)

| Tool Name | Input Format | Use Case |
| :--- | :--- | :--- |
| `check_order_status` | JSON: `customer_id`, `product_id` | Kiểm tra đơn hàng có tồn tại không, đã giao chưa, còn trong thời hạn đổi trả không và sản phẩm có được đổi trả không. |
| `check_warehouse_stock` | JSON: `product_id`, `size` | Kiểm tra tồn kho size khách muốn đổi. |
| `create_return_ticket` | JSON: `order_id`, `action_type`, `detail` | Tạo phiếu đổi hàng khi policy hợp lệ và còn hàng. |

### 2.3 LLM Providers Used

- **Primary for reproducible evaluation**: `ScriptedRetailReActProvider` offline trong `src/agent/run_agent.py`.
- **Supported providers**: OpenAI, Gemini và local GGUF model thông qua interface `LLMProvider`.
- **Demo UI**: `streamlit_app.py` cho phép chọn `.env LLM` hoặc `offline scripted`.

---

## 3. Telemetry & Performance Dashboard

Evaluation được chạy bằng:

```bash
python3 -m src.evaluate --offline-agents
python3 -m src.analyze_logs
```

Kết quả:

| System | Success Rate | Avg Latency | Total Tokens | Avg Loop | Parser Errors | Tool Errors | Timeout |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Chatbot baseline | 0.0% | 0.0ms | 327 | 1.00 | 0 | 0 | 0 |
| Agent v1 | 100.0% | 0.8ms | 4133 | 2.60 | 0 | 0 | 0 |
| Agent v2 | 100.0% | 0.0ms | 5504 | 2.60 | 0 | 0 | 0 |

Estimated cost:

| System | Estimated Cost |
| :--- | ---: |
| Chatbot baseline | $0.003270 |
| Agent v1 | $0.041330 |
| Agent v2 | $0.055040 |

Insight: Agent tốn nhiều token hơn baseline vì mỗi task cần nhiều vòng reasoning và tool observations. Đổi lại, Agent có độ tin cậy cao hơn vì quyết định dựa trên dữ liệu trả về từ tool thay vì trả lời theo suy đoán.

---

## 4. Root Cause Analysis (RCA) - Failure Traces

### Case Study: Baseline Chatbot Fails Tool Verification

- **Input**: `TC01 - Đổi size hợp lệ`
- **Expected Tools**: `check_order_status -> check_warehouse_stock -> create_return_ticket`
- **Baseline Behavior**: Chatbot trả lời rằng shop đã nhận yêu cầu và yêu cầu khách cung cấp thêm thông tin, nhưng không thực sự kiểm tra đơn hàng, không kiểm tra tồn kho và không tạo ticket.
- **Failure Type**: `ticket_not_created`
- **Root Cause**: Baseline chatbot không có ReAct loop và không có cơ chế gọi tool. Nó chỉ sinh câu trả lời text nên không thể verify dữ liệu nghiệp vụ.
- **Fix / Improvement**: ReAct Agent được triển khai để LLM sinh `Action`, code gọi tool thật và đưa `Observation` quay lại prompt. Với TC01, Agent gọi đủ 3 tool và tạo ticket `TK-8831`.

### Case Study: TC03 Out-of-Stock Guardrail

- **Input**: `TC03 - Hết hàng size L`
- **Expected Tools**: `check_order_status -> check_warehouse_stock`
- **Agent Trace**:
  - `check_order_status({"customer_id": "USER_48291", "product_id": "AT104"})`
  - Observation: `policy_valid=true`
  - `check_warehouse_stock({"product_id": "AT104", "size": "L"})`
  - Observation: `status="out_of_stock"`, `stock_quantity=0`
  - Final Answer: báo size L hết hàng và đề xuất chờ restock/chọn mẫu khác.
- **Important Behavior**: Agent không gọi `create_return_ticket` khi stock unavailable.
- **Learning**: Negative cases cũng cần tool verification. Chỉ kiểm tra outcome "có tạo ticket không" là chưa đủ; evaluation phải kiểm tra expected tool sequence.

---

## 5. Ablation Studies & Experiments

### Experiment 1: Prompt v1 vs Prompt v2

| Version | Main Prompt Behavior | Result |
| :--- | :--- | :--- |
| Agent v1 | Hướng dẫn ReAct chung: kiểm tra đơn hàng, kiểm kho, tạo ticket nếu hợp lệ. | 5/5 pass, 4133 tokens. |
| Agent v2 | Thêm guardrails rõ: trước khi tạo ticket phải có `policy_valid=true` và stock `available`; nếu policy fail hoặc hết hàng thì dừng. | 5/5 pass, 5504 tokens. |

Agent v2 không tăng success rate trên bộ test hiện tại vì v1 đã pass 100%, nhưng v2 tốt hơn về safety và production readiness. Trade-off là token count cao hơn do prompt guardrails dài hơn.

### Experiment 2: Chatbot vs Agent

| Case | Chatbot Result | Agent Result | Winner |
| :--- | :--- | :--- | :--- |
| TC01 - Đổi size hợp lệ | Không tạo ticket, thiếu tất cả expected tools. | Kiểm policy, kiểm stock, tạo ticket. | Agent |
| TC02 - Quá hạn 7 ngày | Không kiểm policy bằng tool. | Kiểm order và từ chối vì quá hạn. | Agent |
| TC03 - Hết hàng size L | Không kiểm kho. | Kiểm order, kiểm kho, báo hết hàng. | Agent |
| TC04 - Không tìm thấy đơn | Không verify đơn hàng. | Gọi `check_order_status`, báo không tìm thấy. | Agent |
| TC05 - Final sale | Không verify policy. | Gọi `check_order_status`, từ chối vì final sale. | Agent |

---

## 6. Production Readiness Review

- **Security**: Cần authentication/authorization trước khi cho phép tạo ticket thật, tránh user giả mạo `customer_id`.
- **Guardrails**: Agent đã có `max_steps`, parser error tracking, tool error tracking và timeout tracking. V2 có thêm rule không tạo ticket nếu policy hoặc stock chưa hợp lệ.
- **Data Integrity**: `create_return_ticket` hiện dùng ticket ID cố định `TK-8831` cho lab demo. Production cần unique ID, idempotency key và database transaction.
- **Monitoring**: Log hiện có JSON events, LLM metrics, token/cost estimate, loop count và failure types. Production nên bổ sung dashboard P50/P95/P99 latency, real pricing theo model và alert cho parser/tool error spikes.
- **Scalability**: Có thể mở rộng sang RAG policy docs, real order database, async tool execution và human-in-the-loop approval cho các action nhạy cảm.
- **User Experience**: Streamlit demo cho phép xem baseline vs agent, trace, current run logs và saved logs, phù hợp để live demo với instructor.

---

## 7. Verification Summary

Các lệnh đã chạy:

```bash
python3 -m pytest -q
python3 -m src.evaluate --offline-agents
python3 -m src.analyze_logs
```

Kết quả:

- `pytest`: 9 passed.
- Agent v1: 100% success rate.
- Agent v2: 100% success rate.
- Parser errors: 0.
- Tool errors: 0.
- Timeout errors: 0.

> Note: `pytest` có warning về `datetime.utcnow()` deprecated trong telemetry logger. Warning này không làm test fail, nhưng production nên đổi sang timezone-aware timestamp.
