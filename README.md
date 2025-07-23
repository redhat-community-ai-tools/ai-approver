# AI Approver Agent

This repository contains an AI agent designed to automate the approval or rejection of `ApprovalTask` for Tekton.

The agent runs as a standalone service, continuously monitoring the cluster for relevant tasks and making decisions based on a configurable set of rules and logic.

## Overview

In many CI/CD pipelines, there are stages that require manual sign-off before proceeding. This could be for security, compliance, or quality assurance reasons. The `openshift-pipelines/manual-approval-gate` project provides an `ApprovalTask` custom resource for Tekton, which provides a mechanism to pause a pipeline and wait for this manual intervention.

This project provides an intelligent agent that automates this approval process. The agent can be configured to act in one of two modes:

1.  **Co-Approver:** The AI acts as one of several required approvers. For example, it might perform a series of automated checks and provide a preliminary approval, with a final human sign-off still required.
2.  **Full Approver:** The AI is given sole authority to approve or reject a task. This is suitable for high-confidence, low-risk scenarios where full automation is desired.

## How It Works

The AI Approver is a long-running service that:

1.  **Monitors** the Kubernetes API for `ApprovalTask` resources in a `pending` state.
2.  **Evaluates** each task based on its internal logic. This logic is highly customizable and can include:
    *   Calling out to external services (e.g., security scanners, code quality analysis tools, testing frameworks).
    *   Querying a Large Language Model (LLM) with context from the pipeline and the associated code changes.
    *   Checking against a predefined set of rules defined in its configuration.
3.  **Acts** on the task by patching the `ApprovalTask` resource with an `approve` or `reject` status and a corresponding message. This action unblocks the waiting Tekton pipeline, allowing it to either proceed or fail.

## Project Structure

This repository contains the Python agent and its supporting configuration.

-   **`python-agent/src/main.py`**: The entrypoint for the agent, containing the main reconciliation loop.
-   **`requirements.txt`**: The Python dependencies for the agent.
-   **`Containerfile`**: The recipe for building the agent's container image.
-   **`config/`**: Contains example Kubernetes manifests for deploying the agent.

## Getting Started

### Prerequisites

-   A running Kubernetes cluster.
-   Tekton Pipelines installed on the cluster.
-   The `ApprovalTask` CRD from the [openshift-pipelines/manual-approval-gate](https://github.com/openshift-pipelines/manual-approval-gate) project must be installed on the cluster.
-   A container registry (like Docker Hub, GCR, or Quay.io) to store the agent's image.

### Configuration

1.  Edit `python-agent/config.yaml` to define the agent's behavior. You will need to specify:
    -   The Kubernetes namespace(s) the agent should monitor.
    -   The name of the user or ServiceAccount the agent will use for approvals.
    -   The logic or rules for making approval/rejection decisions.

### Building and Deploying the Agent

  **Deploy the agent to your Kubernetes cluster:**
    You will need to create a Kubernetes Deployment (and likely a ServiceAccount, Role, and RoleBinding) to run the agent. The Deployment should use the image you just built and pushed. Ensure the ServiceAccount has the necessary permissions to `get`, `list`, `watch`, and `patch` `approvaltasks` resources.

    Example deployment manifests can be found in the `config/` directory. You will need to customize them for your environment.

    ```sh
    ko apply -f config/
    ```

Once deployed, the agent will start monitoring for `ApprovalTask` resources and acting on them according to its configuration.



#### Running locally
Assuming you have GEMINI_API_KEY setup in environment.
```
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
export MODEL_NAME=gemini-2.5-pro-preview-05-06
kopf run src/main.py
```
