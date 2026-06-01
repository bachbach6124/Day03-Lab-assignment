# Plan Tạo File Chia Task Cho Người 2

## Summary

Tạo một file Markdown mới để share cho Nguyễn Công Thành, mô tả rõ phần việc của Người 2 trong lab **AI Trợ Lý Hỗ Trợ Đổi Trả Hàng**. File này sẽ nằm riêng trong repo, không sửa template report có sẵn để tránh conflict.

File đề xuất:

```text
TEAM_TASK_SPLIT_RETAIL_RETURN_AGENT.md
```

Nội dung file sẽ viết bằng tiếng Việt, đủ để Người 2 đọc và bắt tay làm ngay.

## Nội Dung File Markdown

File sẽ gồm các phần chính:

- Thông tin nhóm:
  - Đào Xuân Bách - `2A202600640`
  - Nguyễn Công Thành - `2A202600696`
  - Project: `AI Trợ Lý Hỗ Trợ Đổi Trả Hàng`

- Tổng quan scenario:
  - User muốn đổi áo thun mã `AT102` từ size M sang size L.
  - Agent cần kiểm tra đơn hàng, kiểm tra kho, tạo phiếu đổi hàng.
  - Đây là bài toán retail/customer support multi-step.

- Chia việc tránh conflict:
  - Bách sở hữu `src/agent/agent.py`, `src/agent/prompts.py`.
  - Thành sở hữu `src/tools/retail_tools.py`, `src/tools/__init__.py`, `src/chatbot.py`, `src/evaluate.py`, `src/analyze_logs.py`, report group/cá nhân của Thành.

- Task chi tiết của Nguyễn Công Thành:
  - Implement retail tools:
    - `check_order_status`
    - `check_warehouse_stock`
    - `create_return_ticket`
  - Tạo mock data đơn hàng/kho.
  - Làm chatbot baseline.
  - Làm evaluation runner.
  - Làm log analyzer.
  - Tổng hợp bảng Chatbot vs Agent v1 vs Agent v2.
  - Viết phần report liên quan tools/evaluation/failure analysis.

- Tool interface thống nhất:
  - Mỗi tool nhận `args: dict`.
  - Mỗi tool trả về `dict`.
  - `TOOLS` là list dictionary gồm `name`, `description`, `func`.

Ví dụ interface:

```python
TOOLS = [
    {
        "name": "check_order_status",
        "description": "Check whether a customer's order is eligible for return or exchange. Input JSON: customer_id, product_id.",
        "func": check_order_status,
    }
]
```

- Test cases Thành cần chuẩn bị:
  - Đổi size hợp lệ.
  - Quá hạn 7 ngày.
  - Hết hàng size L.
  - Không tìm thấy đơn hàng.
  - Sản phẩm không đủ điều kiện đổi trả.

- Log/evaluation Thành cần tổng hợp:
  - success rate
  - latency trung bình
  - token usage
  - estimated cost
  - loop count
  - parser/tool/failure errors
  - so sánh chatbot baseline với agent

## Markdown Sẽ Được Tạo

Khi triển khai, tạo file `TEAM_TASK_SPLIT_RETAIL_RETURN_AGENT.md` ở root repo với nội dung hoàn chỉnh gồm:

```md
# Team Task Split - Retail Return Agent

## Thông Tin Nhóm

- Đào Xuân Bách - 2A202600640
- Nguyễn Công Thành - 2A202600696

Project: AI Trợ Lý Hỗ Trợ Đổi Trả Hàng

## Scenario Chính

User request:

"Mình mới nhận cái áo thun mã AT102 hôm qua nhưng mặc bị chật quá, giờ mình muốn đổi từ size M lên size L thì làm thế nào shop?"

Agent cần thực hiện 3 bước:

1. Kiểm tra đơn hàng và chính sách đổi trả.
2. Kiểm tra tồn kho size L.
3. Tạo phiếu đổi hàng và phản hồi khách.

## Chia Việc Để Tránh Conflict

### Đào Xuân Bách

Sở hữu các file:

- src/agent/agent.py
- src/agent/prompts.py

Phụ trách:

- ReAct loop.
- Action parser.
- Tool execution.
- Runtime JSON logs.
- Token/latency/cost tracking.
- Error handling.
- Agent v1 và Agent v2.

### Nguyễn Công Thành

Sở hữu các file:

- src/tools/retail_tools.py
- src/tools/__init__.py
- src/chatbot.py
- src/evaluate.py
- src/analyze_logs.py
- report/group_report/GROUP_REPORT_RETAIL_RETURN_AGENT.md
- report/individual_reports/REPORT_NGUYEN_CONG_THANH.md

Phụ trách:

- Retail tools.
- Mock data.
- Chatbot baseline.
- Test cases.
- Evaluation runner.
- Log analyzer.
- Metrics table.
- Report phần tools/evaluation/failure analysis.

## Tool Interface Thống Nhất

Các tool trong src/tools/retail_tools.py dùng format:

```python
def tool_name(args: dict) -> dict:
    ...
```

Danh sách tools export ra dạng:

```python
TOOLS = [
    {
        "name": "check_order_status",
        "description": "...",
        "func": check_order_status,
    }
]
```

Agent sẽ gọi tool bằng:

```python
tool["func"](parsed_args)
```

## Retail Tools Cần Làm

### 1. check_order_status

Input:

```json
{
  "customer_id": "USER_48291",
  "product_id": "AT102"
}
```

Output thành công:

```json
{
  "order_id": "DH-99214",
  "delivery_date": "2026-05-31",
  "policy_valid": true,
  "current_size": "M",
  "reason": "Within 7-day exchange window"
}
```

### 2. check_warehouse_stock

Input:

```json
{
  "product_id": "AT102",
  "size": "L"
}
```

Output thành công:

```json
{
  "status": "available",
  "stock_quantity": 14,
  "warehouse": "Kho Tổng"
}
```

### 3. create_return_ticket

Input:

```json
{
  "order_id": "DH-99214",
  "action_type": "EXCHANGE",
  "detail": "Đổi từ size M lên size L do chật"
}
```

Output thành công:

```json
{
  "ticket_id": "TK-8831",
  "shipper_note": "Thu hồi hàng cũ khi giao hàng mới",
  "estimated_process_time": "2-3 ngày"
}
```

## Test Cases Cần Chuẩn Bị

1. Đổi size hợp lệ:
   - Product `AT102`
   - Received yesterday
   - Size L còn hàng
   - Expected: tạo ticket thành công.

2. Quá hạn 7 ngày:
   - Delivery date quá xa.
   - Expected: agent từ chối đổi trả lịch sự.

3. Hết hàng size L:
   - Stock quantity = 0.
   - Expected: agent báo hết hàng và đề xuất chờ/restock.

4. Không tìm thấy đơn hàng:
   - Sai `customer_id` hoặc `product_id`.
   - Expected: agent xin thêm thông tin đơn hàng.

5. Sản phẩm không đủ điều kiện:
   - Product thuộc nhóm không đổi trả.
   - Expected: agent giải thích theo policy.

## Evaluation Cần Tổng Hợp

So sánh 3 hệ thống:

- Chatbot baseline
- Agent v1
- Agent v2

Metrics cần lấy:

- Success rate
- Average latency
- Total tokens
- Estimated cost
- Average loop count
- Failure types
- Parser errors
- Tool hallucination errors
- Timeout/max_steps errors

## Report Thành Cần Viết

Trong group report, Thành phụ trách các phần:

- Tool Definitions
- Chatbot Baseline
- Evaluation & Analysis
- Telemetry Dashboard
- Failure Traces
- Chatbot vs Agent comparison

Trong individual report, Thành tập trung vào:

- Tool design.
- Test case design.
- Log analysis.
- Evaluation result.
- Một debugging case study cụ thể.
```

## Test/Verification

Sau khi tạo file:

- Chạy `ls` để xác nhận file tồn tại.
- Mở file bằng `sed -n '1,240p' TEAM_TASK_SPLIT_RETAIL_RETURN_AGENT.md` để kiểm tra nội dung.
- Không chạy formatter hoặc sửa các file khác.
- Không đụng `.env`, templates, hoặc source code trong bước tạo planning file này.

## Assumptions

- File nên đặt ở root repo để cả hai người dễ thấy khi mở project.
- Nội dung dùng tiếng Việt vì mục đích là share nhanh cho teammate.
- Chưa tạo code implementation trong bước này; chỉ tạo tài liệu chia task.
