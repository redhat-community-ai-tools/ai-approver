import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration (standardized environment variables)
MODEL_NAME = os.getenv("MODEL_NAME", "llama3.1")  # Model name (llama3.1, gpt-4, gemini-pro, etc.)
API_KEY = os.getenv("API_KEY", "")  # API key for the model provider

# MCP Server Configuration
MCP_SERVERS = {
    "kubernetes": {
        "url": os.getenv("K8S_MCP_URL", "http://localhost:8080"),
        "timeout": 30
    }
}

# Smolagents Configuration
AGENTS = {
    "pipeline_expert": {
        "enabled": True,
        "name": "Pipeline Expert",
        "role": "Expert in analyzing Tekton pipeline configurations and identifying potential issues",
        "tools": ["k8s_mcp_query"]
    },
    "coordinator": {
        "enabled": True,
        "name": "Decision Coordinator", 
        "role": "Coordinates analysis and makes final approve/reject decisions",
        "tools": ["analyze_pipeline_data"]
    }
}

# Decision Configuration
DECISION = {
    "approval_threshold": 0.7,
    "fallback_decision": "reject"
}

# ApprovalTask Configuration
APPROVAL_TASK = {
    "label_prefix": "tekton.dev/",
    "required_labels": ["pipelineRun", "customRun", "pipeline"]
}

# CRD Configuration
GROUP = "openshift-pipelines.org"
VERSION = "v1alpha1"
PLURAL = "approvaltasks"
AI_APPROVER_NAME = "kubernetes-admin"
ANNOTATION_REVIEWED_AT = "ai-approver.openshift-pipelines.org/reviewed-at" 