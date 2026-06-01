# Evaluation Metrics for Lab 3: Agentic reasoning

In this lab, we don't just ask "Does it work?". We ask **"How well does it perform?"**.

## Key Industry Metrics

### 1. Token Efficiency (Token count)
- **Prompt vs. Completion**: Are your system prompts too verbose? Is the agent generating unnecessary "chatter" before the tool call?
- **Cost Analysis**: Lower token count = Lower cost = Higher ROI.

### 2. Latency (Response time)
- **Time-to-First-Token (TTFT)**: How quickly does the LLM start responding?
- **Total Duration**: For a ReAct agent, this includes all loops + tool execution times.
- **Goal**: In "production", users expect responses within 200ms-2s.

### 3. Loop count (Steps)
- **Multi-step Reasoning**: How many `Thought->Action` cycles did the agent need to solve the task?
- **Termination Quality**: Does the agent correctly identify when to call "Final Answer", or does it get stuck in an "endless loop"?

### 4. Failure Analysis (Error codes)
- **JSON Parser Error**: The LLM outputted `Action` in a format that your code couldn't parse.
- **Hallucination Error**: The LLM hallucinated a tool that doesn't exist.
- **Timeout**: The agent exceeded the `max_steps`.
- **Missing Expected Tools**: The final outcome may look correct, but the agent skipped a required verification step. For example, a negative case should not pass only because no ticket was created if the expected path required checking warehouse stock.

## Case Design Notes

- **TC03 - Hết hàng size L** uses product `AT104`, a valid delivered order within the 7-day exchange window, with warehouse stock for size `L` set to `0`. This keeps the test focused on stock checking instead of accidentally testing the expired-window policy for `AT103`.
- Prompt v2 is evaluated mainly for stronger safety and guardrails. If v1 and v2 both reach 100% success on the small offline suite, report that v2 improves policy/tool-call discipline rather than claiming a success-rate lift.

## How to use the Logs
All these metrics are automatically captured in `logs/` directory. Use a script to parse these JSON files and calculate the **Aggregate Reliability** of your agent version 1 vs version 2.

The Streamlit app also exposes logs locally after a comparison run:

- **Reasoning trace**: model response, parsed action, and tool observation per step.
- **Current run logs**: raw JSON payload for the baseline and agent run.
- **Saved local log files**: tail view of files under `logs/`, including evaluation JSONL files and manual traces.
