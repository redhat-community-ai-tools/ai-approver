# AI-Approver for Tekton

An intelligent, event-driven Kubernetes operator that uses an AI agent to automate the approval of Tekton `ApprovalTask` custom resources. It acts as a smart, automated gate in your CI/CD pipelines, capable of making decisions based on real-time data from your cluster and other integrated systems.

## Overview

In many CI/CD pipelines, there are stages that require manual sign-off before proceeding. The `ApprovalTask` CRD for Tekton provides a mechanism to pause a pipeline and wait for this manual intervention. This project provides an intelligent agent that automates this approval process by using a Large Language Model (LLM) to analyze the task and its context.

The agent can be configured to act in one of two modes:

1.  **Co-Approver:** The AI acts as one of several required approvers. It performs automated checks and provides a preliminary approval, with a final human sign-off still required.
2.  **Full Approver:** The AI is given sole authority to approve or reject a task. This is suitable for high-confidence, low-risk scenarios where full automation is desired.

## Architecture

The system is designed as an intelligent, event-driven Kubernetes operator that automates the approval process for CI/CD tasks.

```mermaid
graph TD
    subgraph "Kubernetes Cluster"
        A[ApprovalTask CR] --> C{Controller};
        C --> A;
    end

    subgraph "AI-Approver Core Logic"
        C --> D[AI Agent];
        D --> P[Prompt Engine];
        P --> CFG[config.py];
        D --> T[Tool Abstraction Layer];
        D --> C;
    end

    subgraph "External Tools (MCPs)"
        T --> K8S[Kubernetes MCP];
        T --> GITHUB[GitHub MCP];
        T --> PROM[Prometheus MCP];
        T --> OTHERS[...];
    end

    subgraph "Model Fine tuning"
        A --> RF[Reward Function];
        H[Human Co-Approver] --> RF;
        RF --> SIG[Training Signal];
        SIG --> LLM[Language Model];
        D --> LLM;
    end
```

### How It Works

1.  **Event Trigger**: The workflow begins when a Tekton `ApprovalTask` Custom Resource (CR) is created or updated. This event is detected by the **Controller**.
2.  **Controller (`src/main.py`)**: The Controller, powered by the `kopf` framework, receives the `ApprovalTask` event and initiates the analysis by invoking the **AI Agent**.
3.  **AI Agent (`src/agents.py`)**: The core decision-making component. It uses a **Prompt Engine** to construct a detailed, context-rich prompt for the Language Model (LLM), dynamically built from templates and rules in `src/config.py`.
4.  **Tool Abstraction Layer**: The agent connects to a **Tool Abstraction Layer** that interfaces with multiple **Machine Control Programs (MCPs)**. This allows it to gather real-time data from various sources:
    *   **GitHub MCP**: Provides tools to inspect source code, check pull requests, analyze commit history, and detect security vulnerabilities.
    *   **Kubernetes MCP (Legacy)**: Previously used for querying live data from the Kubernetes API (e.g., check pod status, resource usage).
    *   **Prometheus MCP (Future)**: Will provide tools to query metrics, check for active alerts, and assess system load.
5.  **Analysis and Decision**: The agent uses the selected tools to gather live data, analyzes it, and generates an `approve` or `reject` decision.
6.  **Patching the Resource**: The Controller receives the decision and patches the original `ApprovalTask` CR, updating it with the AI's input.

### Model Finetuning & Improvement Loop

To ensure the AI-Approver's decisions improve over time, a training loop is a core part of the architecture:

*   **Reward Function**: After the AI agent makes a decision, it is compared to the decision of a **Human Co-Approver**.
*   **Training Signal**: Agreement between the AI and the human generates a positive reward, while disagreement generates a corrective signal.
*   **Model Fine-Tuning**: This signal is used to continuously fine-tune the underlying Language Model, reinforcing correct reasoning and ensuring the AI-Approver becomes more accurate and trustworthy over time.

## Getting Started

### Prerequisites

*   Python 3.10+
*   A running Kubernetes cluster.
*   Tekton Pipelines installed on the cluster.
*   The `ApprovalTask` CRD from the [openshift-pipelines/manual-approval-gate](https://github.com/openshift-pipelines/manual-approval-gate) project installed on the cluster.

### Installation & Configuration

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/khrm/ai-approver.git
    cd ai-approver
    ```

2.  **Set up a virtual environment and install dependencies:**
    ```sh
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Configure environment variables:**
    Create a `.env` file by copying the example:
    ```sh
    cp env.example .env
    ```
    Edit the `.env` file to add your credentials:
    ```
    # .env
    MODEL_NAME=gemini/gemini-pro  # Or gpt-4, llama3.1, etc.
    API_KEY=your_llm_api_key_here
    K8S_MCP_URL=http://localhost:7007/mcp # URL of your Kubernetes MCP server
    ```

### Running the Operator

Run the operator locally using `kopf`. It will automatically use your local `kubeconfig` to connect to the cluster.

```sh
kopf run src/main.py --namespace=your-target-namespace
```

The operator will now be watching for `ApprovalTask` resources in the specified namespace.

## Configuration

The agent's behavior is primarily configured in `src/config.py`. The `PROMPT_CONFIG` dictionary allows you to customize the prompts sent to the LLM, including:

*   **`base_prompt`**: The main template for the analysis request.
*   **`considerations`**: A list of points the agent should always consider.
*   **`rules`**: A list of conditional instructions. For example, you can add a rule to automatically reject any pipeline that uses a `:latest` image tag.
*   **`output_format_instruction`**: Defines how the LLM should structure its response to make it easily parsable.

By modifying this configuration, you can tailor the agent's decision-making process to your organization's specific needs and policies.

## GitHub MCP Integration

The AI Approver now uses the [GitHub MCP Server](https://github.com/github/github-mcp-server) to analyze code changes in PipelineRuns. This provides powerful code analysis capabilities including:

- **Code Quality Analysis**: Check for best practices, coding standards, and potential issues
- **Security Vulnerability Detection**: Identify security issues in code changes
- **Commit Analysis**: Review commit messages, changes, and impact
- **Repository Insights**: Access to pull requests, issues, and repository metadata

### Setup GitHub MCP

1. **Create GitHub Personal Access Token**:
   - Go to [GitHub Settings > Personal Access Tokens](https://github.com/settings/tokens)
   - Create a token with `repo`, `read:org`, and `read:user` scopes

2. **Set Environment Variables**:
   ```bash
   export GITHUB_PERSONAL_ACCESS_TOKEN=your_token_here
   export GITHUB_MCP_URL=http://localhost:3001/mcp
   ```

3. **Start GitHub MCP Server**:
   ```bash
   ./scripts/setup_github_mcp.sh
   ```

### PipelineRun Configuration

Your Pipeline should include a `git-clone` task with the repository information:

```yaml
apiVersion: tekton.dev/v1
kind: Pipeline
metadata:
  name: my-pipeline
spec:
  tasks:
  - name: fetch-from-git
    taskRef:
      name: git-clone
    params:
    - name: url
      value: https://github.com/owner/repo.git
    - name: revision
      value: main
```

For detailed setup instructions, see [GitHub MCP Integration Guide](docs/GITHUB_MCP_INTEGRATION.md).
