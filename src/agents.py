import logging
from smolagents import CodeAgent, InferenceClientModel, MCPClient, LiteLLMModel
from config import MODEL_NAME, API_KEY, MCP_SERVERS

logger = logging.getLogger(__name__)

def create_pipeline_agent(tools=None):
    """Create a smolagents CodeAgent for pipeline analysis"""
    if tools is None:
        tools = []
    try:
        # Initialize model based on model name
        if "llama" in MODEL_NAME.lower():
            # For Ollama models, use InferenceClientModel with default settings
            model = InferenceClientModel(model_id=MODEL_NAME)
        elif "gpt" in MODEL_NAME.lower():
            model = LiteLLMModel(model_id=MODEL_NAME, api_key=API_KEY)
        elif "gemini" in MODEL_NAME.lower():
            from smolagents import LiteLLMModel
            # Handle both "gemini-pro" and "gemini/gemini-pro" formats
            if MODEL_NAME.startswith("gemini/"):
                model = LiteLLMModel(model_id=MODEL_NAME, api_key=API_KEY)
            else:
                model = LiteLLMModel(model_id=f"gemini/{MODEL_NAME}", api_key=API_KEY)
        elif "claude" in MODEL_NAME.lower():
            model = LiteLLMModel(model_id=MODEL_NAME, api_key=API_KEY)
        else:
            # Default to inference client
            model = InferenceClientModel()
        
        # Create agent with provided tools
        agent = CodeAgent(
            model=model,
            tools=tools
        )
        
        return agent
    except Exception as e:
        logger.error(f"Failed to create pipeline agent: {e}")
        return None



def parse_agent_decision(result):
    """Parse the agent's decision from the response"""
    response = str(result).lower()
    
    # Look for explicit decision statements first
    if "decision:" in response:
        decision_line = [line for line in response.split('\n') if "decision:" in line.lower()]
        if decision_line:
            decision_text = decision_line[0].lower()
            if "reject" in decision_text:
                return "reject", "Rejected by AI agent analysis"
            elif "approve" in decision_text:
                return "approve", "Approved by AI agent analysis"
    
    # Look for final answer patterns
    if "final answer:" in response:
        final_answer = response.split("final answer:")[-1].strip()
        if "reject" in final_answer:
            return "reject", "Rejected by AI agent analysis"
        elif "approve" in final_answer:
            return "approve", "Approved by AI agent analysis"
    
    # Look for decision patterns in the response
    if "decision:" in response:
        decision_section = response.split("decision:")[-1].split('\n')[0].strip()
        if "reject" in decision_section:
            return "reject", "Rejected by AI agent analysis"
        elif "approve" in decision_section:
            return "approve", "Approved by AI agent analysis"
    
    # Fallback: look for the first occurrence of approve/reject
    if "reject" in response:
        return "reject", "Rejected by AI agent analysis"
    elif "approve" in response:
        return "approve", "Approved by AI agent analysis"
    
    # Default to reject if no clear decision found
    return "reject", "No clear decision found, defaulting to reject"

def analyze_approval_task(pipeline_run_name, pipeline_name, description):
    """
    Analyze an ApprovalTask using smolagents and return decision
    """
    try:
        # Initialize MCP client to get tools
        mcp_config = {
            "url": MCP_SERVERS["kubernetes"]["url"],
            "transport": "streamable-http"
        }
        
        with MCPClient(mcp_config) as tools:
            logger.info(f"✅ MCP connection successful! Available tools: {len(tools)}")
            
            # Create the agent with the available tools
            agent = create_pipeline_agent(tools=tools)
            if not agent:
                return "reject", "Failed to create agent"

            # Define the prompt for the agent
            prompt = f"""You are a SRE who analyzes Tekton PipelineRuns.

Your job is to:
1. Check for existing load on the cluster
2. Check whether we can deploy the pipeline without affecting the existing load
3. Check what has changed in the pipelinerun since the last run
4. 
Analyze this ApprovalTask and make a decision:

PipelineRun: {pipeline_run_name}
Pipeline: {pipeline_name}
Description: {description}

You have access to a set of tools to fetch real-time Kubernetes data. 
Use them to gather information about the pipeline, pipeline run, and related resources.

Available tools: {', '.join([tool.name for tool in tools])}

Perform a comprehensive analysis using the available tools to fetch live data.

Consider:
- Resource usage and efficiency from real data
- Description content and context
- Actual taskruns and their status
- Related events and pod status
- Any other relevant information

IMPORTANT: Start your response with "Decision: [approve/reject]" and then provide detailed reasoning."""
            
            logger.info(f"Running agent analysis with tools for pipeline: {pipeline_run_name}")
            result = agent.run(prompt)
        
        # Parse the result using improved logic
        decision, message = parse_agent_decision(result)
        
        logger.info(f"Agent decision: {decision} - {message}")
        return decision, message
        
    except Exception as e:
        logger.error(f"Error in agent analysis: {e}")
        return "reject", f"Error in analysis: {str(e)}" 