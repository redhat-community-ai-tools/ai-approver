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
    "kubernetes": {
        "url": os.getenv("K8S_MCP_URL", "http://localhost:7007/mcp"),
        "timeout": 30,
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
    "base_prompt": """You are a SRE who analyzes Tekton PipelineRuns.

Your job is to:
1. Check for existing load on the cluster
2. Check whether we can deploy the pipeline without affecting the existing load
3. Check what has changed in the pipelinerun since the last run.

Analyze this ApprovalTask and make a decision:

PipelineRun: {pipeline_run_name}
Pipeline: {pipeline_name}
Description: {description}

You have access to a set of tools to fetch real-time Kubernetes data. 
Use them to gather information about the pipeline, pipeline run, and related resources.

Available tools: {tool_list}

Perform a comprehensive analysis using the available tools to fetch live data.
""",
    "considerations": [
        "Resource usage and efficiency from real data",
        "Description content and context",
        "Actual taskruns and their status",
        "Related events and pod status",
        "Any other relevant information",
    ],
    "rules": [
        {
            "field": "image",
            "contains": ":latest",
            "instruction": "The use of ':latest' tag in container images is not allowed. Reject this pipeline.",
        },
        {
            "field": "pipeline_name",
            "contains": "production",
            "instruction": "This is a production pipeline. Be extra careful and scrutinize resource usage and potential impact on stability.",
        },
        {
            "field": "description",
            "contains": "critical",
            "instruction": "The description mentions this is a critical task. Verify the changes thoroughly.",
        },
    ],
    "output_format_instruction": """
IMPORTANT: Start your response with "Decision: [approve/reject]" and then provide detailed reasoning.""",
}
