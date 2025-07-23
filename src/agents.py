import logging
from smolagents import CodeAgent, InferenceClientModel
from config import MODEL_NAME, API_KEY, MCP_SERVERS

logger = logging.getLogger(__name__)

def create_pipeline_agent():
    """Create a smolagents CodeAgent for pipeline analysis"""
    try:
        # Initialize model based on model name
        if "llama" in MODEL_NAME.lower():
            # For Ollama models, use InferenceClientModel with default settings
            model = InferenceClientModel(model_id=MODEL_NAME)
        elif "gpt" in MODEL_NAME.lower():
            from smolagents import LiteLLMModel
            model = LiteLLMModel(model_id=MODEL_NAME, api_key=API_KEY)
        elif "gemini" in MODEL_NAME.lower():
            from smolagents import LiteLLMModel
            # Handle both "gemini-pro" and "gemini/gemini-pro" formats
            if MODEL_NAME.startswith("gemini/"):
                model = LiteLLMModel(model_id=MODEL_NAME, api_key=API_KEY)
            else:
                model = LiteLLMModel(model_id=f"gemini/{MODEL_NAME}", api_key=API_KEY)
        elif "claude" in MODEL_NAME.lower():
            from smolagents import LiteLLMModel
            model = LiteLLMModel(model_id=MODEL_NAME, api_key=API_KEY)
        else:
            # Default to inference client
            model = InferenceClientModel()
        
        # Create agent with MCP tools
        agent = CodeAgent(
            model=model,
            tools=[]  # We'll add MCP tools later
        )
        
        return agent
    except Exception as e:
        logger.error(f"Failed to create pipeline agent: {e}")
        return None

def analyze_approval_task(pipeline_run_name, task_run_name, pipeline_name, description):
    """
    Analyze an ApprovalTask using smolagents and return decision
    """
    try:
        agent = create_pipeline_agent()
        if not agent:
            return "reject", "Failed to create agent"
        
        # Create analysis prompt with system instructions
        prompt = f"""You are a Pipeline Expert Agent that analyzes Tekton pipeline configurations.

Your job is to:
1. Analyze pipeline configurations for potential issues
2. Check for security concerns
3. Evaluate pipeline efficiency
4. Make approve/reject decisions based on analysis

Always provide clear reasoning for your decisions.

Analyze this ApprovalTask and make a decision:

PipelineRun: {pipeline_run_name}
TaskRun: {task_run_name}
Pipeline: {pipeline_name}
Description: {description}

Based on this information, should this pipeline be approved or rejected?
Consider:
- Pipeline safety and security
- Resource usage
- Potential risks
- Description content

Respond with either 'approve' or 'reject' and provide a brief reason."""
        
        logger.info(f"Running agent analysis for pipeline: {pipeline_run_name}")
        result = agent.run(prompt)
        
        # Parse the result
        response = str(result).lower()
        if "approve" in response:
            decision = "approve"
            message = "Approved by AI agent analysis"
        else:
            decision = "reject"
            message = "Rejected by AI agent analysis"
        
        logger.info(f"Agent decision: {decision} - {message}")
        return decision, message
        
    except Exception as e:
        logger.error(f"Error in agent analysis: {e}")
        return "reject", f"Error in analysis: {str(e)}" 