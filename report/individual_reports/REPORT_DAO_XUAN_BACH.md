# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Nguyễn Công Thành
- **Student ID**: [Điền mã sinh viên]
- **Date**: 2026-06-01

---

## I. Technical Contribution (15 Points)

### Modules Implemented / Improved

Trong lab này, phần đóng góp kỹ thuật chính tập trung vào việc biến baseline chatbot thành một workflow có thể đánh giá được bằng trace và tool verification:

| Module | Contribution |
| :--- | :--- |
| `src/agent/agent.py` | Triển khai/củng cố ReAct loop: parse `Action`, gọi tool, append `Observation`, lưu `history`, track tokens/cost/latency/errors. |
| `src/agent/prompts.py` | Xây dựng prompt cho Agent v1 và Agent v2. Agent v2 có guardrails trước khi tạo ticket. |
| `src/tools/retail_tools.py` | Xây dựng tool nghiệp vụ: kiểm tra order policy, kiểm kho, tạo return/exchange ticket. |
| `src/evaluate.py` | Cải thiện evaluation để không chỉ check outcome mà còn check `expected_tools`, missing tools và tool sequence. |
| `tests/test_retail_workflow.py` | Bổ sung tests cho retail tools, parser, TC03 out-of-stock case, evaluation logic và agent history. |
| `streamlit_app.py` | Tạo demo UI để so sánh baseline chatbot với ReAct Agent, hiển thị metrics, reasoning trace, checklist và saved logs. |

### Code Highlights

ReAct Agent dùng format:

```text
Thought: ...
Action: tool_name({"key": "value"})
```

hoặc:

```text
Final Answer: ...
```

Khi LLM sinh `Action`, code parse arguments JSON rồi gọi tool tương ứng. Sau khi tool chạy, kết quả được ghi lại thành `Observation` và đưa lại vào prompt cho bước tiếp theo.

Phần evaluation được cải thiện bằng function `assess_case_result`, giúp phát hiện các case "pass giả". Trước đây nếu một negative case không tạo ticket thì có thể được tính pass, dù agent chưa gọi đủ tool cần thiết. Sau cải tiến, case chỉ pass khi:

1. Outcome đúng (`create_return_ticket` có/không có đúng kỳ vọng).
2. Không thiếu expected tools.
3. Tool sequence đúng thứ tự mong muốn.

### Verification

Các lệnh đã chạy:

```bash
python3 -m pytest -q
python3 -m src.evaluate --offline-agents
python3 -m src.analyze_logs
```

Kết quả test:

```text
9 passed
```

Kết quả evaluation:

| System | Success Rate | Total Tokens | Avg Loop |
| :--- | ---: | ---: | ---: |
| Chatbot baseline | 0.0% | 327 | 1.00 |
| Agent v1 | 100.0% | 4133 | 2.60 |
| Agent v2 | 100.0% | 5504 | 2.60 |

---

## II. Debugging Case Study (10 Points)

### Problem Description

Một vấn đề quan trọng trong quá trình làm lab là case `TC03 - Hết hàng size L`. Mục tiêu của case này là kiểm tra agent xử lý tình huống đơn hàng hợp lệ nhưng size cần đổi đã hết hàng. Agent phải:

1. Gọi `check_order_status`.
2. Thấy `policy_valid=true`.
3. Gọi `check_warehouse_stock`.
4. Thấy `status="out_of_stock"`.
5. Không tạo ticket.
6. Trả lời khách rằng size đã hết hàng và đề xuất chờ restock/chọn mẫu khác.

Nếu evaluation chỉ kiểm tra "agent có tạo ticket không", TC03 có thể pass ngay cả khi agent không kiểm kho. Đây là pass giả vì thiếu tool verification.

### Log Source

Log sau khi chạy `python3 -m src.evaluate --offline-agents` cho TC03:

```json
{
  "case_id": "TC03",
  "case_name": "Hết hàng size L",
  "system": "Agent v2",
  "expected_success": false,
  "predicted_success": false,
  "success": true,
  "tools_used": ["check_order_status", "check_warehouse_stock"],
  "expected_tools": ["check_order_status", "check_warehouse_stock"],
  "missing_expected_tools": [],
  "tool_sequence_ok": true,
  "outcome_matches": true,
  "final_answer": "Dạ shop đã kiểm tra đơn hàng hợp lệ nhưng size bạn muốn đổi hiện chưa còn hàng..."
}
```

### Diagnosis

Root cause nằm ở thiết kế evaluation và test data. Với một negative case, việc không tạo ticket là cần thiết nhưng chưa đủ. Agent vẫn phải chứng minh rằng nó đã kiểm tra đúng nguyên nhân thất bại. TC03 phải fail nếu thiếu `check_warehouse_stock`.

Ngoài ra, dữ liệu test cần mô phỏng đúng nghiệp vụ: sản phẩm `AT104` là đơn còn trong hạn đổi trả, nhưng size `L` hết hàng. Như vậy agent buộc phải đi qua cả policy check và stock check.

### Solution

Các cải tiến đã thực hiện:

- Cập nhật TC03 dùng `AT104`, một order hợp lệ nhưng size `L` hết hàng.
- Thêm stock record `AT104`, size `L`, `stock_quantity=0`.
- Thêm `assess_case_result` trong `src/evaluate.py` để check:
  - `outcome_matches`
  - `missing_expected_tools`
  - `tool_sequence_ok`
- Thêm tests trong `tests/test_retail_workflow.py`:
  - TC03 mock data phải là order hợp lệ và size L out of stock.
  - Evaluation phải fail nếu thiếu stock check.
  - Scripted agent phải xử lý TC03 bằng `check_order_status -> check_warehouse_stock` và không tạo ticket.

Kết quả sau fix: Agent v2 pass TC03 đúng nghĩa, không chỉ pass vì không tạo ticket.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

### 1. Reasoning

Baseline chatbot chỉ sinh câu trả lời trực tiếp từ prompt. Nó có thể lịch sự và tự nhiên, nhưng không có khả năng kiểm tra dữ liệu thật. Với bài toán đổi trả, câu trả lời đẹp chưa đủ; hệ thống cần biết đơn có tồn tại không, còn trong thời hạn đổi trả không, size cần đổi có còn hàng không và ticket đã được tạo chưa.

ReAct Agent giải quyết vấn đề này bằng cách tách reasoning thành nhiều bước nhỏ. `Thought` giúp model xác định bước tiếp theo, `Action` biến suy nghĩ thành tool call, còn `Observation` đưa kết quả từ môi trường quay lại model. Nhờ vậy câu trả lời cuối cùng có căn cứ hơn.

### 2. Reliability

Agent đáng tin hơn trong các task multi-step vì nó không phải đoán. Ví dụ:

- TC01: Agent kiểm order, kiểm kho rồi tạo ticket.
- TC02: Agent kiểm policy và từ chối vì quá hạn.
- TC03: Agent kiểm policy, kiểm kho và báo hết hàng.
- TC04: Agent báo không tìm thấy đơn sau khi gọi tool.
- TC05: Agent từ chối vì sản phẩm final sale.

Tuy nhiên, Agent cũng có trade-off:

- Tốn nhiều token hơn baseline.
- Cần parser robust vì LLM có thể sinh sai format `Action`.
- Cần `max_steps` để tránh loop.
- Tool descriptions và prompt guardrails ảnh hưởng mạnh đến chất lượng.

### 3. Observation

Observation là điểm khác biệt lớn nhất giữa chatbot và agent. Agent không chỉ dựa vào user query, mà còn thay đổi quyết định dựa trên dữ liệu tool trả về.

Ví dụ TC03:

```text
Observation: {"policy_valid": true}
```

khiến agent tiếp tục kiểm kho.

```text
Observation: {"status": "out_of_stock", "stock_quantity": 0}
```

khiến agent dừng và không tạo ticket.

Điều này cho thấy ReAct Agent phù hợp hơn cho các workflow nghiệp vụ cần kiểm chứng từng bước.

---

## IV. Future Improvements (5 Points)

### Scalability

- Kết nối tool với database thật thay vì JSON mock data.
- Tách tool execution thành service layer hoặc async job queue.
- Dùng RAG để retrieve chính sách đổi trả từ tài liệu nội bộ thay vì hard-code trong mock data.
- Dùng LangGraph hoặc state machine nếu workflow có nhiều nhánh phức tạp hơn.

### Safety

- Thêm authentication để xác minh `customer_id`.
- Không cho LLM tự ý tạo ticket nếu thiếu order ID hoặc user identity.
- Thêm human-in-the-loop approval cho các action nhạy cảm như refund hoặc đổi sản phẩm giá trị cao.
- Thêm idempotency key để tránh tạo trùng ticket khi retry.

### Performance

- Tối ưu prompt v2 để giảm token nhưng vẫn giữ guardrails.
- Log real cost theo pricing của từng provider.
- Theo dõi P50/P95/P99 latency thay vì chỉ average latency.
- Cache kết quả policy/stock trong cùng session nếu user hỏi lại cùng sản phẩm.

### Monitoring

- Alert khi parser errors, tool errors hoặc timeout tăng bất thường.
- Dashboard theo provider/model để so sánh OpenAI, Gemini và local models.
- Lưu full trace cho các failed cases để phục vụ RCA nhanh hơn.

---

## Final Reflection

Lab này cho thấy khác biệt thực tế giữa "chatbot biết nói" và "agent biết hành động". Baseline chatbot phù hợp với FAQ đơn giản, nhưng với workflow đổi trả cần kiểm tra dữ liệu, ReAct Agent đáng tin hơn vì mọi quyết định đều đi qua tool call và observation. Phần quan trọng nhất không chỉ là làm agent chạy được, mà là biết đọc trace, phát hiện pass giả và cải thiện evaluation để đo đúng hành vi cần có.
