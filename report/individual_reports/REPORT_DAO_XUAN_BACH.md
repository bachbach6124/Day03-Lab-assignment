# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Đào Xuân Bách
- **Student ID**: 2A202600640
- **Date**: 2026-06-01
- **Project**: Retail size exchange / return ReAct Agent

---

## I. Technical Contribution (15 Points)

### 1. Contribution Summary

Trong lab này, phần đóng góp kỹ thuật tập trung vào việc biến một chatbot trả lời trực tiếp thành một ReAct Agent có thể kiểm chứng nghiệp vụ bằng tool trace và evaluation metrics.

| Module / File | Contribution |
| :--- | :--- |
| `src/agent/agent.py` | Triển khai/củng cố ReAct loop: nhận output từ LLM, parse `Action`, gọi tool, append `Observation`, dừng khi có `Final Answer` hoặc vượt `max_steps`. |
| `src/agent/prompts.py` | Xây dựng prompt cho Agent v1 và v2. v2 thêm guardrails: chỉ tạo ticket sau khi policy và stock đã được xác nhận. |
| `src/tools/retail_tools.py` | Xây dựng bộ tool nghiệp vụ và search tool: search policy docs, kiểm tra order/policy, kiểm tra tồn kho, tạo ticket đổi hàng. |
| `src/tools/mock_data/policy_docs.json` | Thêm policy corpus cục bộ để agent có thể dùng `search_policy_docs` như một RAG-lite search tool. |
| `src/evaluate.py` | Cải thiện evaluation để đo đúng hành vi agent: outcome match, expected tools, missing tools, tool sequence, failure type. |
| `src/analyze_logs.py` | Tổng hợp metrics từ JSONL logs: success rate, latency, token count, estimated cost, loop count, parser/tool/timeout errors. |
| `tests/test_retail_workflow.py` | Bổ sung test cho retail workflow, parser/action behavior, TC03 out-of-stock, expected tool verification và agent history. |
| `streamlit_app.py` | Tạo demo UI để so sánh chatbot vs agent, hiển thị answer, metrics, reasoning trace, checklist và saved logs. |

### 2. Code Quality Evidence

Hệ thống được tách theo các module rõ ràng:

- Agent loop không hard-code logic nghiệp vụ; nó gọi tool thông qua registry.
- Retail tools nằm riêng trong `src/tools/retail_tools.py`.
- `search_policy_docs` giúp agent retrieve policy context trước khi kiểm tra order và tạo ticket.
- LLM providers được tách qua interface `LLMProvider`, hỗ trợ OpenAI, Gemini, local model và scripted offline provider.
- Evaluation và log analysis tách khỏi UI, giúp chạy test tự động.
- Telemetry ghi lại token, cost estimate, latency, loop count, parser errors, tool errors và timeout errors.

### 3. Verification Result

Các lệnh đã chạy:

```bash
python3 -m pytest -q
python3 -m src.evaluate --offline-agents
python3 -m src.analyze_logs
```

Kết quả test:

```text
10 passed, 32 warnings
```

Kết quả evaluation:

| System | Success Rate | Avg Latency | Total Tokens | Est. Cost | Avg Loop | Parser / Tool / Timeout Errors |
| :--- | ---: | ---: | ---: | ---: | ---: | :--- |
| Chatbot baseline | 0.0% | 0.0ms | 327 | $0.003270 | 1.00 | 0 / 0 / 0 |
| Agent v1 | 100.0% | 1.0ms | 7409 | $0.074090 | 3.60 | 0 / 0 / 0 |
| Agent v2 | 100.0% | 0.2ms | 9624 | $0.096240 | 3.60 | 0 / 0 / 0 |

### 4. Scoring Alignment

Rubric yêu cầu phần technical contribution phải có module cụ thể và bằng chứng code quality. Phần này đáp ứng bằng cách liệt kê đúng file, trách nhiệm của từng file, kết quả test và metrics sau evaluation.

---

## II. Debugging Case Study (10 Points)

### 1. Problem: False Pass in Negative Cases

Case quan trọng nhất trong quá trình debug là `TC03 - Hết hàng size L`.

Mục tiêu của TC03:

1. Khách có đơn hàng hợp lệ.
2. Đơn vẫn còn trong thời hạn đổi trả.
3. Size khách muốn đổi là size L.
4. Kho không còn size L.
5. Agent phải kiểm tra kho rồi mới từ chối tạo ticket.

Nếu evaluation chỉ kiểm tra "có tạo ticket hay không", TC03 có thể pass giả. Một agent không kiểm kho và cũng không tạo ticket vẫn có thể được tính đúng, dù nó chưa chứng minh được lý do nghiệp vụ.

### 2. Failure Signal from Telemetry / Logs

Sau khi chạy:

```bash
python3 -m src.evaluate --offline-agents
```

Evaluation log cho TC03 của Agent v2 có dạng:

```json
{
  "case_id": "TC03",
  "case_name": "Hết hàng size L",
  "system": "Agent v2",
  "expected_success": false,
  "predicted_success": false,
  "success": true,
  "tools_used": ["search_policy_docs", "check_order_status", "check_warehouse_stock"],
  "expected_tools": ["search_policy_docs", "check_order_status", "check_warehouse_stock"],
  "missing_expected_tools": [],
  "tool_sequence_ok": true,
  "outcome_matches": true
}
```

Trace quan trọng:

```text
Action: search_policy_docs({"query": "stock required before exchange ticket", "top_k": 2})
Observation: {"matches": [{"id": "POLICY_STOCK_REQUIRED"}]}

Action: check_order_status({"customer_id": "USER_48291", "product_id": "AT104"})
Observation: {"policy_valid": true, "reason": "Within 7-day exchange window"}

Action: check_warehouse_stock({"product_id": "AT104", "size": "L"})
Observation: {"status": "out_of_stock", "stock_quantity": 0}

Final Answer: size L hết hàng, không tạo phiếu đổi.
```

### 3. Root Cause

Root cause không nằm ở tool, mà nằm ở cách đánh giá ban đầu:

- Với positive case, việc tạo ticket là dấu hiệu khá rõ.
- Với negative case, việc không tạo ticket là cần thiết nhưng chưa đủ.
- Agent vẫn phải gọi đúng tool để chứng minh nguyên nhân từ chối.

TC03 đặc biệt quan trọng vì nó tách riêng hai điều kiện:

- policy hợp lệ,
- stock không hợp lệ.

Nếu test data dùng một đơn hết hạn, agent có thể từ chối ngay sau policy check và không bao giờ cần kiểm kho. Vì vậy TC03 phải dùng product `AT104`, một đơn hợp lệ nhưng size `L` có `stock_quantity=0`.

### 4. Fix Implemented

Các thay đổi/cải tiến đã được thực hiện:

- TC03 được thiết kế lại để dùng `AT104`: đơn hợp lệ, trong 7 ngày, nhưng size L hết hàng.
- `warehouse_stock.json` có record cho `AT104`, size `L`, quantity `0`.
- Thêm `policy_docs.json` và `search_policy_docs` để agent retrieve policy context trước khi đi vào workflow.
- `assess_case_result` trong `src/evaluate.py` kiểm tra:
  - `outcome_matches`,
  - `missing_expected_tools`,
  - `tool_sequence_ok`.
- `classify_failure` phân loại các lỗi như:
  - `ticket_not_created`,
  - `created_ticket_for_negative_case`,
  - `missing_expected_tools`,
  - `expected_tool_order_mismatch`,
  - `provider_error`.
- Tests được thêm để đảm bảo TC03 fail nếu thiếu stock check.

### 5. Result After Fix

Agent v1 và v2 đều pass TC03 đúng nghĩa:

- gọi `check_order_status`,
- trước đó gọi `search_policy_docs` để lấy policy stock/exchange liên quan,
- thấy policy hợp lệ,
- gọi `check_warehouse_stock`,
- thấy size L hết hàng,
- không gọi `create_return_ticket`,
- trả lời khách với lý do đúng.

Đây là ví dụ rõ nhất cho yêu cầu của rubric: lỗi và quá trình sửa phải được phân tích bằng telemetry/logs, không chỉ bằng cảm giác rằng câu trả lời "nghe có vẻ đúng".

---

## III. Personal Insights: Chatbot vs ReAct Agent (10 Points)

### 1. Chatbot Is Language-First

Baseline chatbot phù hợp khi nhiệm vụ là FAQ hoặc tư vấn chung. Nó có thể viết câu trả lời tự nhiên, lịch sự và có vẻ hợp lý. Tuy nhiên, trong workflow đổi trả, câu trả lời hay không đủ để tạo niềm tin.

Ví dụ, khi khách hỏi đổi size, hệ thống phải biết:

- đơn có tồn tại không,
- sản phẩm có thuộc khách đó không,
- còn trong hạn 7 ngày không,
- có phải final sale không,
- size mới còn hàng không,
- ticket có được tạo thật không.

Chatbot baseline không có kênh để kiểm tra những điều này. Vì vậy nó fail 0/5 trong evaluation dù không có parser/tool/timeout error.

### 2. ReAct Agent Is Action-and-Evidence-First

ReAct Agent khác chatbot ở chỗ nó không chỉ trả lời; nó hành động theo từng bước và dùng kết quả từ môi trường để quyết định bước tiếp theo.

Cấu trúc `Thought -> Action -> Observation` giúp agent:

- chia task phức tạp thành các bước nhỏ,
- gọi tool đúng thời điểm,
- thay đổi quyết định dựa trên dữ liệu thật,
- tạo final answer có căn cứ.

Trong TC01, agent tạo ticket vì đã thấy policy hợp lệ và stock còn hàng. Trong TC03, agent không tạo ticket vì observation cho thấy stock bằng 0. Điểm khác biệt nằm ở `Observation`: agent có bằng chứng để hành động.

### 3. Reliability Requires Evaluation Beyond Final Answer

Bài học lớn nhất là không nên chỉ chấm final answer. Một câu trả lời có thể đúng bề mặt nhưng sai quy trình.

Ví dụ với negative case:

- "Shop không thể đổi size" có thể là câu trả lời đúng.
- Nhưng nếu agent không kiểm kho hoặc không kiểm policy, câu trả lời đó không đáng tin.

Vì vậy evaluation phải đo cả:

- expected tools,
- missing tools,
- tool sequence,
- outcome match,
- failure type.

Đây là điểm biến lab từ "chatbot demo" thành một hệ thống agentic có thể debug và cải tiến.

### 4. Trade-off: Safety vs Cost

Agent v2 dùng 9624 tokens, cao hơn v1 với 7409 tokens. Lý do là prompt v2 có nhiều guardrails hơn, và cả hai agent giờ đều thêm bước `search_policy_docs` trước workflow chính. Trên bộ 5 test cases, cả hai đều đạt 100%, nên không nên nói v2 "tăng accuracy". Cách nói đúng hơn là:

- v2 tăng độ kỷ luật khi gọi tool,
- v2 giảm rủi ro tạo ticket khi chưa đủ observation,
- v2 có production readiness tốt hơn,
- v2 tốn nhiều token hơn.

Trong hệ thống thật, trade-off này hợp lý nếu sai action gây hậu quả lớn hơn chi phí token.

---

## IV. Future Improvements (5 Points)

### 1. Scale to Production RAG

Hiện tại policy đổi trả nằm trong mock data và tool logic. Để scale lên production, hệ thống nên dùng RAG:

- index tài liệu chính sách đổi trả chính thức,
- retrieve policy theo loại sản phẩm, ngày mua, chương trình sale,
- trích dẫn policy trong final answer,
- version policy theo thời gian để tránh áp dụng nhầm luật cũ.

### 2. Multi-Agent Architecture

Nếu workflow mở rộng sang hoàn tiền, đổi sản phẩm khác giá, hoặc khiếu nại vận chuyển, có thể tách thành nhiều agent:

- **Policy Agent**: đọc policy/RAG và xác định điều kiện.
- **Inventory Agent**: kiểm kho theo size, màu, cửa hàng/kho.
- **Ticket Agent**: tạo ticket, đảm bảo idempotency và transaction.
- **Escalation Agent**: chuyển human-in-the-loop khi refund cao hoặc thông tin mâu thuẫn.

Một orchestrator hoặc state machine như LangGraph có thể điều phối các agent này.

### 3. Safety Improvements

- Thêm authentication để xác minh `customer_id`.
- Không cho LLM tự quyết định `customer_id` nếu user chưa xác thực.
- Thêm idempotency key để tránh tạo ticket trùng khi retry.
- Thêm approval step cho refund hoặc đổi sản phẩm giá trị cao.
- Validate tool arguments bằng schema trước khi execute.

### 4. Monitoring Improvements

- Ghi real cost theo model/provider thay vì cost estimate cố định.
- Theo dõi P50/P95/P99 latency.
- Alert khi parser errors, hallucinated tools, tool errors, timeout hoặc missing expected tools tăng.
- Lưu full trace cho failed cases để RCA nhanh.
- So sánh prompt variants bằng ablation dashboard.

---

## Missing Items for Individual Submission

| Missing / Weak Item | Impact | Suggested Fix |
| :--- | :--- | :--- |
| Contribution ownership chưa có commit evidence. | Nếu giảng viên yêu cầu accountability theo Git, report chưa chứng minh bằng commit hash. | Bổ sung commit IDs hoặc PR link nếu có. |
| Offline latency không đại diện production latency. | Metrics latency hiện chứng minh logging, chưa chứng minh performance với API thật. | Chạy thêm một evaluation bằng OpenAI/Gemini/local model nếu có key/model. |
| Live demo evidence không có trong individual report. | Có thể ảnh hưởng bonus nếu cần chứng minh demo. | Bổ sung screenshot/demo note nếu đã demo với instructor. |

---

## Final Reflection

Điểm quan trọng nhất mình học được là ReAct Agent không chỉ là chatbot dài hơn. Nó là một vòng lặp có bằng chứng: suy nghĩ, gọi tool, đọc observation, rồi mới quyết định. Với bài toán đổi trả, sự khác biệt này rất lớn vì hệ thống không được phép đoán tồn kho hoặc đoán chính sách.

Lab cũng cho thấy evaluation phải được thiết kế cẩn thận. Nếu chỉ nhìn final answer, negative cases rất dễ pass giả. Khi thêm expected tools, tool sequence và failure type, mình có thể thấy rõ hệ thống sai ở đâu và sửa đúng chỗ hơn.
