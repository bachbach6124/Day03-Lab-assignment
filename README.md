# Lab 3: Chatbot vs ReAct Agent (Industry Edition)

Welcome to Phase 3 of the Agentic AI course! This lab focuses on moving from a simple LLM Chatbot to a sophisticated **ReAct Agent** with industry-standard monitoring.

## 🚀 Getting Started

### 1. Download the Project
Use one of the following options to download this lab assignment.

**Option A: Clone with Git**
```bash
git clone https://github.com/bachbach6124/Day03-Lab-assignment.git
cd Day03-Lab-assignment
```

**Option B: Download ZIP from GitHub**
1. Open: https://github.com/bachbach6124/Day03-Lab-assignment
2. Click **Code** -> **Download ZIP**.
3. Extract the ZIP file.
4. Open the extracted `Day03-Lab-assignment` folder in your terminal or code editor.

### 2. Setup Environment
Copy the `.env.example` to `.env` and fill in your API keys:
```bash
cp .env.example .env
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Directory Structure
- `src/tools/`: Extension point for your custom tools.

### 5. Run the Local Web Demo
```bash
streamlit run streamlit_app.py
```

After entering a customer question and clicking **Run comparison**, the app shows:
- Baseline chatbot answer, latency, token count, and model/provider.
- ReAct agent answer, latency, token count, estimated cost, loop count, parser/tool/timeout errors, provider, and tools used.
- Reasoning trace with each LLM step, parsed action, and tool observation.
- Current run logs as JSON and saved local log files from `logs/`.

For preset cases, the app also shows an evaluation checklist for outcome match, expected tool order, missing tools, and final pass/fail.

## 🏠 Running with Local Models (CPU)

If you don't want to use OpenAI or Gemini, you can run open-source models (like Phi-3) directly on your CPU using `llama-cpp-python`.

### 1. Download the Model
Download the **Phi-3-mini-4k-instruct-q4.gguf** (approx 2.2GB) from Hugging Face:
- [Phi-3-mini-4k-instruct-GGUF](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf)
- Direct Download: [phi-3-mini-4k-instruct-q4.gguf](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf)

### 2. Place Model in Project
Create a `models/` folder in the root and move the downloaded `.gguf` file there.

### 3. Update `.env`
Change your `DEFAULT_PROVIDER` and set the path:
```env
DEFAULT_PROVIDER=local
LOCAL_MODEL_PATH=./models/Phi-3-mini-4k-instruct-q4.gguf
```

## 🎯 Lab Objectives

1.  **Baseline Chatbot**: Observe the limitations of a standard LLM when faced with multi-step reasoning.
2.  **ReAct Loop**: Implement the `Thought-Action-Observation` cycle in `src/agent/agent.py`.
3.  **Provider Switching**: Swap between OpenAI and Gemini seamlessly using the `LLMProvider` interface.
4.  **Failure Analysis**: Use the structured logs in `logs/` to identify why the agent fails (hallucinations, parsing errors).
5.  **Grading & Bonus**: Follow the [SCORING.md](file:///Users/tindt/personal/ai-thuc-chien/day03-lab-agent/SCORING.md) to maximize your points and explore bonus metrics.

## 🛠️ How to Use This Baseline
The code is designed as a **Production Prototype**. It includes:
- **Telemetry**: Every action is logged in JSON format for later analysis.
- **Robust Provider Pattern**: Easily extendable to any LLM API.
- **Clean Skeletons**: Focus on the logic that matters—the agent's reasoning process.

---

*Happy Coding! Let's build agents that actually work.*
