import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration (standardized environment variables)
MODEL_NAME = os.getenv(
    "MODEL_NAME", "llama3.1"
)  # Model name (llama3.1, gpt-4, gemini-pro, etc.)
API_KEY = os.getenv("API_KEY", "")  # API key for the model provider

# MCP Server Configuration
MCP_SERVERS = {
    "github": {
        "command": "docker",
        "args": ["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", "-e", "GITHUB_TOOLSETS=repos", "ghcr.io/github/github-mcp-server:latest", "stdio"],
        "env": {
            "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", ""),
            "GITHUB_TOOLSETS": "repos"  # Only repos toolset for commit analysis
        }
    },
    "kubernetes": {
        "url": "http://localhost:7007/mcp"
    }
}

# Smolagents Configuration
AGENTS = {
    "pipeline_expert": {
        "enabled": True,
        "name": "Pipeline Expert",
        "role": "Expert in analyzing Tekton pipeline configurations and identifying potential issues",
        "tools": ["k8s_mcp_query"],
    },
    "coordinator": {
        "enabled": True,
        "name": "Decision Coordinator",
        "role": "Coordinates analysis and makes final approve/reject decisions",
        "tools": ["analyze_pipeline_data"],
    },
}

# Decision Configuration
DECISION = {"approval_threshold": 0.7, "fallback_decision": "reject"}

# ApprovalTask Configuration
APPROVAL_TASK = {
    "label_prefix": "tekton.dev/",
    "required_labels": ["pipelineRun", "customRun", "pipeline"],
}

# CRD Configuration
GROUP = "openshift-pipelines.org"
VERSION = "v1alpha1"
PLURAL = "approvaltasks"
AI_APPROVER_NAME = "kubernetes-admin"
ANNOTATION_REVIEWED_AT = "ai-approver.openshift-pipelines.org/reviewed-at"

# Prompt Configuration
PROMPT_CONFIG = {
    "base_prompt": """You are a Senior DevOps Engineer who analyzes Tekton PipelineRuns and their associated code changes.

Your job is to:
1. Analyze the code changes in the last commit of the PipelineRun
2. Check for security vulnerabilities, code quality issues, and best practices
3. Evaluate the impact of changes on the pipeline and deployment
4. Check cluster resource availability and current load before approving
5. Make approve/reject decisions based on comprehensive analysis

Analyze this ApprovalTask and make a decision:

PipelineRun: {pipeline_run_name}
Pipeline: {pipeline_name}
Description: {description}

You have access to both GitHub and Kubernetes tools:
- GitHub tools: list_commits, get_commit (for analyzing code changes)
- Kubernetes tools: resources_list, resources_get (for fetching PipelineRun details and cluster resources)

Available tools: {tool_list}

CRITICAL CLUSTER RESOURCE CHECKS - PERFORM THESE BEFORE APPROVING:
1. Check current PipelineRun count in the cluster to assess load
2. Check current Pod count and resource usage
3. Verify cluster capacity and resource availability
4. Consider the impact of additional PipelineRuns on cluster performance

Use the resources_list and resources_get tools to check:
- PipelineRuns: resources_list(apiVersion="tekton.dev/v1", kind="PipelineRun", namespace="default")
- Pods: resources_list(apiVersion="v1", kind="Pod", namespace="default")
- Specific resources: resources_get(apiVersion="tekton.dev/v1", kind="PipelineRun", name="pipeline-name", namespace="default")

IMPORTANT: Use list_commits with page=1, perPage=1 to get only the latest commit efficiently. CRITICAL: list_commits returns a JSON STRING, not a parsed object. You MUST use json.loads() to parse the response before accessing any data. Always check if the commits list is empty before accessing commits[0] to avoid "list index out of range" errors. Focus on analyzing ONLY the diff between the last two commits. Do not fetch unnecessary data like entire file contents, multiple commits, or repository metadata. Get the specific changes and analyze those.
""",
    "considerations": [
        "Code quality and best practices in the changes",
        "Security vulnerabilities in the modified code",
        "Breaking changes or potential deployment issues",
        "Test coverage and quality of tests",
        "Documentation and commit message quality",
        "Compliance with coding standards and conventions",
        "Dependencies and their security status",
        "Performance impact of the changes",
        "Current cluster resource utilization and capacity",
        "Number of existing PipelineRuns and their impact on cluster load",
        "Pod resource consumption and availability",
        "Potential resource contention with existing workloads",
    ],
    "rules": [
        {
            "field": "description",
            "contains": "security",
            "instruction": "This involves security changes. Perform extra scrutiny for potential vulnerabilities and security best practices.",
        },
        {
            "field": "pipeline_name",
            "contains": "production",
            "instruction": "This is a production pipeline. Be extra careful and scrutinize code quality, security, and potential impact on stability.",
        },
        {
            "field": "description",
            "contains": "critical",
            "instruction": "The description mentions this is a critical task. Verify the code changes thoroughly and ensure proper testing.",
        },
        {
            "field": "description",
            "contains": "hotfix",
            "instruction": "This is a hotfix. Ensure the changes are minimal, well-tested, and don't introduce new issues.",
        },
        {
            "field": "pipeline_name",
            "contains": "load-test",
            "instruction": "This is a load testing pipeline. Check cluster capacity and existing load before approving. Consider resource impact on other workloads.",
        },
        {
            "field": "description",
            "contains": "deployment",
            "instruction": "This involves deployment changes. Check current cluster resource utilization and ensure sufficient capacity for the deployment.",
        },
    ],
    "output_format_instruction": """
IMPORTANT: Use the final_answer() function to provide your decision. Format your response as:
<code>
final_answer("Decision: [approve/reject]

**Reasoning:**
[Your detailed reasoning here]")
</code>""",
}
