# Individual Report: Lab 3 - Chatbot vs ReAct Agent

**Student Name:** Nguyễn Công Thành
**Student ID:** 2A202600696
**Date:** 2026-06-01

---

# I. Technical Contribution (15 Points)

## Modules Implemented

* `src/tools/retail_tools.py`
* `src/tools/__init__.py`
* `src/tools/mock_data/orders.json`
* `src/tools/mock_data/products.json`
* `src/tools/mock_data/warehouse_stock.json`
* `src/tools/mock_data/return_tickets.json`
* `src/tools/mock_data/test_cases.json`
* `src/chatbot.py`
* `src/evaluate.py`
* `src/analyze_logs.py`

## Code Highlights

My primary contribution was implementing the retail tool environment and evaluation pipeline used by the ReAct agent.

I implemented three business tools using the required interface:

```python
tool_name(args: dict) -> dict
```

### check_order_status

This tool verifies:

* Whether the order exists.
* Whether the product is eligible for exchange.
* Whether the order is still within the 7-day exchange window.
* The current delivery status.

The tool returns structured information that the agent can use in later reasoning steps.

### check_warehouse_stock

This tool checks inventory availability based on:

* Product ID
* Requested size

The returned observation allows the agent to determine whether an exchange can proceed.

### create_return_ticket

This tool creates a return/exchange ticket and stores the result in the mock ticket database.

The returned ticket ID is used in the final customer response.

In addition to tool implementation, I created mock datasets covering both successful and failure scenarios, including:

* Valid exchange requests
* Expired exchange windows
* Missing orders
* Final-sale products
* Out-of-stock products

I also implemented:

* `src/chatbot.py` as a baseline chatbot without tool usage.
* `src/evaluate.py` for automated testing of all required test cases.
* `src/analyze_logs.py` for calculating success rate, latency, token usage, average reasoning loops, parser errors, tool errors, and timeout statistics.

## Documentation

The implemented tools act as the environment layer of the ReAct architecture.

The interaction flow is:

1. The agent generates a **Thought** describing the next reasoning step.
2. The agent generates an **Action** specifying which tool should be called.
3. The selected tool executes using structured arguments.
4. The tool returns an **Observation**.
5. The observation is added back into the conversation context.
6. The agent generates the next Thought based on the returned observation.

For a successful exchange request, the expected reasoning sequence is:

```text
Thought: Verify exchange eligibility.
Action: check_order_status

Observation: Order valid and policy active.

Thought: Verify inventory availability.
Action: check_warehouse_stock

Observation: Size L available.

Thought: Create exchange request.
Action: create_return_ticket

Observation: Ticket created.

Final Answer: Exchange request completed successfully.
```

This workflow demonstrates how external tools allow the agent to perform business actions instead of only generating text responses.

---

# II. Debugging Case Study (10 Points)

## Problem Description

One important failure case occurred during evaluation of the baseline chatbot on test case `TC01`.

The customer requested a valid size exchange that should have been approved according to business policy. However, the chatbot failed to complete the task and only produced a generic customer-service response.

As a result, the evaluation marked the case as unsuccessful.

## Log Source

`logs/chatbot_baseline.jsonl`

```json
{
  "case_id": "TC01",
  "case_name": "Valid Size Exchange",
  "system": "Chatbot Baseline",
  "expected_success": true,
  "predicted_success": false,
  "success": false,
  "tools_used": [],
  "failure_type": "baseline_no_tool_verification"
}
```

## Diagnosis

After reviewing the execution logs, I found that the failure was not caused by a coding bug or tool malfunction.

The root cause was the architectural limitation of the baseline chatbot.

Because the chatbot had no access to external tools, it could not:

* Verify the order.
* Check the exchange policy.
* Confirm warehouse stock.
* Create a return ticket.

The chatbot could only generate a plausible natural-language response without validating any business information.

This demonstrated that language generation alone is insufficient for tasks that require interaction with external systems.

## Solution

To solve this problem, I integrated the retail tools into the ReAct workflow.

For the same test case, Agent v2 executed the following actions:

1. `check_order_status`
2. `check_warehouse_stock`
3. `create_return_ticket`

Each tool returned observations that guided the next reasoning step.

After confirming policy eligibility and stock availability, the agent successfully created exchange ticket `TK-8831` and returned a correct final answer.

This case demonstrated the advantage of tool-augmented reasoning compared to direct chatbot responses.

---

# III. Personal Insights: Chatbot vs ReAct (10 Points)

## Reasoning

The biggest difference I observed is that the ReAct agent performs explicit multi-step reasoning before producing an answer.

A traditional chatbot tends to answer immediately based on the user's request.

In contrast, the ReAct agent first identifies what information is missing, then gathers that information through tool calls before making a decision.

The Thought block helps the model decompose a complex business task into smaller and more manageable steps.

For example, instead of directly approving an exchange request, the agent first verifies policy eligibility, then checks inventory availability, and only then creates a return ticket.

This process produces more reliable and explainable decisions.

## Reliability

Although the ReAct agent is more capable, it also introduces additional failure points.

The agent depends on:

* Correct provider configuration
* Correct prompt design
* Valid Action formatting
* Successful tool execution
* Correct observation handling

A failure in any of these components can prevent successful task completion.

In contrast, the chatbot baseline is simpler and therefore less likely to encounter parser or tool-related failures.

However, the chatbot cannot reliably complete tasks that require external verification or business actions.

In the evaluation results, the Chatbot Baseline achieved 80% success while Agent v1 and Agent v2 achieved 100%, demonstrating the benefit of tool-assisted reasoning for task completion.

## Observation

One of the most important lessons from the lab is that observations directly influence future reasoning.

The agent does not make decisions solely based on its internal knowledge.

Instead, each observation determines the next action.

For example:

* If `check_order_status` returns `policy_valid = true`, the agent proceeds to inventory checking.
* If inventory is available, the agent creates a return ticket.
* If the policy is expired, the agent immediately stops and rejects the request.

This feedback loop between Action and Observation is the key mechanism that enables ReAct agents to interact effectively with external environments.

---

# IV. Future Improvements (5 Points)

## Scalability

For production deployment, local JSON files should be replaced with dedicated backend services and databases.

Tool calls should communicate with:

* Order Service
* Product Service
* Inventory Service
* Return Management Service

To support larger workloads, asynchronous task queues and service-based architecture could be introduced to improve scalability.

## Safety

Additional safeguards should be implemented before executing business actions:

* Customer ownership verification
* Duplicate ticket detection
* Product condition validation
* Human approval for sensitive actions

A supervisor or auditing component could also monitor agent actions before execution.

## Performance

Several optimizations could improve system performance:

* Cache frequently accessed product and inventory data.
* Reduce repeated tool calls.
* Add schema validation for tool arguments.
* Implement structured tracing for debugging.
* Use vector-based tool retrieval when the number of available tools becomes large.

These improvements would increase reliability while reducing latency and operational cost.
