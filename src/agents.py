import logging
from smolagents import CodeAgent, InferenceClientModel, MCPClient, LiteLLMModel
from mcp import StdioServerParameters
from config import MODEL_NAME, API_KEY, MCP_SERVERS, PROMPT_CONFIG

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
        
        # Create agent with provided tools and authorized imports
        agent = CodeAgent(
            model=model,
            tools=tools,
            additional_authorized_imports=['json']
        )
        
        return agent
    except Exception as e:
        logger.error(f"Failed to create pipeline agent: {e}")
        return None


def parse_git_url(git_url):
    """
    Parse GitHub URL to extract owner and repository name
    Examples:
    - https://github.com/khrm/pipeline -> owner: khrm, repo: pipeline
    - git@github.com:khrm/pipeline.git -> owner: khrm, repo: pipeline
    """
    import re
    
    # Handle HTTPS URLs
    https_match = re.match(r'https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$', git_url)
    if https_match:
        return https_match.group(1), https_match.group(2)
    
    # Handle SSH URLs
    ssh_match = re.match(r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?/?$', git_url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)
    
    # Fallback
    logger.warning(f"Could not parse git URL: {git_url}")
    return "unknown", "unknown"

def extract_git_info_from_pipeline_spec(pipeline_spec):
    """
    Extract git information from Pipeline spec by finding the git-clone task
    This is a more realistic implementation that would parse the actual PipelineRun
    """
    git_info = {
        "commit_sha": None,
        "repository_owner": None,
        "repository_name": None,
        "branch": None,
        "git_url": None
    }
    
    # Look for git-clone task in the pipeline
    tasks = pipeline_spec.get("tasks", [])
    for task in tasks:
        task_ref = task.get("taskRef", {})
        if task_ref.get("name") == "git-clone":
            # Extract parameters from git-clone task
            params = task.get("params", [])
            for param in params:
                if param.get("name") == "url":
                    git_url = param.get("value", "")
                    git_info["git_url"] = git_url
                    owner, repo = parse_git_url(git_url)
                    git_info["repository_owner"] = owner
                    git_info["repository_name"] = repo
                elif param.get("name") == "revision":
                    git_info["branch"] = param.get("value", "")
            break
    
    return git_info


def parse_agent_decision(result):
    """Parse the agent's decision and reasoning from the response"""
    response = str(result)
    response_lower = response.lower()

    # Extract the full reasoning from the agent's response
    reasoning = ""
    
    # Look for final answer patterns first (most reliable)
    if "final answer:" in response_lower:
        final_answer_section = response.split("Final answer:")[-1].strip()
        if final_answer_section:
            reasoning = final_answer_section
    elif "decision:" in response_lower:
        # Extract everything after "Decision:" including reasoning
        decision_section = response.split("Decision:")[-1].strip()
        if decision_section:
            reasoning = decision_section

    # Determine the decision
    decision = "reject"  # default
    if "approve" in response_lower:
        decision = "approve"
    elif "reject" in response_lower:
        decision = "reject"

    # Clean up the reasoning
    if reasoning:
        # Remove any code block markers
        reasoning = reasoning.replace("<code>", "").replace("</code>", "")
        # Remove final_answer function wrapper if present
        if reasoning.startswith('final_answer("') and reasoning.endswith('")'):
            reasoning = reasoning[13:-2]  # Remove final_answer(" and ")
        # Clean up any extra whitespace
        reasoning = reasoning.strip()
        
        # If reasoning is too long, truncate it
        if len(reasoning) > 1000:
            reasoning = reasoning[:997] + "..."
    else:
        # Fallback to generic message if no reasoning found
        if decision == "approve":
            reasoning = "Approved by AI agent analysis"
        else:
            reasoning = "Rejected by AI agent analysis"

    return decision, reasoning


def analyze_approval_task(pipeline_run_name, pipeline_name, description, pipeline_spec=None):
    """
    Analyze an ApprovalTask using smolagents and return decision
    """
    try:
        # Initialize both MCP clients
        github_config = MCP_SERVERS["github"]
        k8s_config = MCP_SERVERS["kubernetes"]
        
        github_server_parameters = StdioServerParameters(
            command=github_config["command"],
            args=github_config["args"],
            env=github_config["env"]
        )
        
        try:
            # Connect to both MCP servers
            # GitHub MCP server (stdio)
            with MCPClient(github_server_parameters) as github_tools:
                
                # Kubernetes MCP server (HTTP)
                k8s_mcp_config = {
                    "url": k8s_config["url"],
                    "transport": "streamable-http",
                }
                
                with MCPClient(k8s_mcp_config) as k8s_tools:
                    # Filter tools to only the ones we need
                    required_github_tools = ["list_commits", "get_commit"]
                    required_k8s_tools = ["resources_get", "resources_list"]
                    
                    filtered_github_tools = [tool for tool in github_tools if tool.name in required_github_tools]
                    filtered_k8s_tools = [tool for tool in k8s_tools if tool.name in required_k8s_tools]
                    
                    # Combine the filtered tools
                    all_tools = filtered_github_tools + filtered_k8s_tools
                    
                    logger.info(f"✅ MCP connections successful!")
                    logger.info(f"   GitHub tools: {len(filtered_github_tools)} ({[t.name for t in filtered_github_tools]})")
                    logger.info(f"   Kubernetes tools: {len(filtered_k8s_tools)} ({[t.name for t in filtered_k8s_tools]})")
                    logger.info(f"   Total tools: {len(all_tools)}")

                    # Create the agent with the filtered tools
                    agent = create_pipeline_agent(tools=all_tools)
                    if not agent:
                        return "reject", "Failed to create agent"
                    
                    # Extract commit information from PipelineRun
                    if pipeline_spec:
                        # Use the provided pipeline spec (fetched by main.py using Kubernetes client)
                        commit_info = extract_git_info_from_pipeline_spec(pipeline_spec)
                        logger.info(f"Using pipeline spec fetched by Kubernetes client")
                    else:
                        # No pipeline spec available - initialize with empty commit info
                        logger.info(f"No pipeline spec available, proceeding with empty commit info")
                        commit_info = {
                            "commit_sha": None,
                            "repository_owner": None,
                            "repository_name": None,
                            "branch": None,
                            "git_url": None
                        }
                    
                    logger.info(f"Extracted commit info: {commit_info}")

                    # Build the prompt from PROMPT_CONFIG
                    tool_list = ", ".join([tool.name for tool in all_tools])

                    prompt_parts = []

                    # Base prompt
                    base_prompt = PROMPT_CONFIG.get("base_prompt", "")
                    if base_prompt:
                        prompt_parts.append(
                            base_prompt.format(
                                pipeline_run_name=pipeline_run_name,
                                pipeline_name=pipeline_name,
                                description=description,
                                tool_list=tool_list,
                            )
                        )

                    # Add commit information to the prompt
                    if commit_info['repository_owner'] and commit_info['repository_name']:
                        # If we have a specific commit SHA, analyze that commit
                        prompt_parts.append(f"""
COMMIT INFORMATION TO ANALYZE:
Repository: {commit_info['repository_owner']}/{commit_info['repository_name']}
Commit SHA: {commit_info['commit_sha']}
Branch: {commit_info['branch']}
Git URL: {commit_info['git_url']}

Use the GitHub tools to:
1. Get the commit details using the commit SHA: {commit_info['commit_sha']}
2. Parse the JSON response to extract the commit information
3. Analyze ONLY the diff content for code quality, security, and best practices
4. Focus on the specific changes, not the entire codebase

Example workflow:
```python
import json
commit_details = get_commit(owner="{commit_info['repository_owner']}", repo="{commit_info['repository_name']}", sha="{commit_info['commit_sha']}")
commit_data = json.loads(commit_details)
# Now analyze commit_data['files'] for the diff patches
```

IMPORTANT: Use these exact values:
- owner: {commit_info['repository_owner']}
- repo: {commit_info['repository_name']}  
- sha: {commit_info['commit_sha']}
""")
                    else:
                        # No commit info available - proceed with basic analysis
                        prompt_parts.append(f"""
NO PIPELINE SPEC AVAILABLE:
The PipelineRun spec was not available, so we cannot extract git information for code analysis.

PipelineRun: {pipeline_run_name}
Pipeline: {pipeline_name}

Since no git information is available, please:
1. Check cluster resources using Kubernetes MCP tools
2. Analyze based on the description and pipeline information only
3. Make a decision based on available information

Use the Kubernetes tools to check:
- Current PipelineRun count: resources_list(apiVersion="tekton.dev/v1", kind="PipelineRun", namespace="default")
- Current Pod count: resources_list(apiVersion="v1", kind="Pod", namespace="default")
- Cluster resource availability

Note: Without git information, this is a limited analysis based on cluster state and description only.
""")

                    # Add conditional instructions from rules
                    custom_instructions = []
                    for rule in PROMPT_CONFIG.get("rules", []):
                        field_name = rule.get("field")
                        contains_value = rule.get("contains")
                        instruction = rule.get("instruction")

                        field_value = ""
                        if field_name == "pipeline_name":
                            field_value = pipeline_name
                        elif field_name == "description":
                            field_value = description

                        if (
                            contains_value
                            and instruction
                            and contains_value.lower() in field_value.lower()
                        ):
                            custom_instructions.append(instruction)

                    if custom_instructions:
                        prompt_parts.append(
                            "\nAdditionally, pay close attention to the following:"
                        )
                        for instr in custom_instructions:
                            prompt_parts.append(f"- {instr}")

                    # Add considerations
                    if PROMPT_CONFIG.get("considerations"):
                        prompt_parts.append("\nConsider:")
                        for consideration in PROMPT_CONFIG["considerations"]:
                            prompt_parts.append(f"- {consideration}")

                    # Add output format instruction
                    output_instruction = PROMPT_CONFIG.get("output_format_instruction", "")
                    if output_instruction:
                        prompt_parts.append(output_instruction)

                    prompt = "\n".join(prompt_parts)

                    logger.info(
                        f"Running agent analysis with MCP tools for pipeline: {pipeline_run_name}"
                    )
                    result = agent.run(prompt)

                    # Parse the result using improved logic
                    decision, message = parse_agent_decision(result)

                    logger.info(f"Agent decision: {decision} - {message}")
                    return decision, message

        except Exception as mcp_error:
            logger.warning(f"MCP connection failed: {mcp_error}")
            logger.info("Falling back to basic analysis without MCP tools")
            
            # Fallback: Create agent without MCP tools
            agent = create_pipeline_agent(tools=[])
            if not agent:
                return "reject", "Failed to create agent"

            # Extract commit information from PipelineRun using the actual function
            if pipeline_spec:
                # Use the provided pipeline spec (fetched by main.py using Kubernetes client)
                commit_info = extract_git_info_from_pipeline_spec(pipeline_spec)
            else:
                # No pipeline spec available - initialize with empty commit info
                commit_info = {
                    "commit_sha": None,
                    "repository_owner": None,
                    "repository_name": None,
                    "branch": None,
                    "git_url": None
                }
            logger.info(f"Extracted commit info: {commit_info}")

            # Build basic prompt without MCP tools
            prompt_parts = []

            # Base prompt
            base_prompt = PROMPT_CONFIG.get("base_prompt", "")
            if base_prompt:
                prompt_parts.append(
                    base_prompt.format(
                        pipeline_run_name=pipeline_run_name,
                        pipeline_name=pipeline_name,
                        description=description,
                        tool_list="No GitHub MCP tools available (fallback mode)",
                    )
                )

            # Add commit information to the prompt
            owner = commit_info['repository_owner']
            repo = commit_info['repository_name']
            branch = commit_info['branch']
            
            prompt_parts.append(f"""
REPOSITORY INFORMATION (Limited Analysis):
Repository: {owner}/{repo}
Branch/Revision: {branch}
Git URL: {commit_info['git_url']}

Note: GitHub MCP tools are not available, so this is a basic analysis based on the description and pipeline information only.
""")

            # Add conditional instructions from rules
            custom_instructions = []
            for rule in PROMPT_CONFIG.get("rules", []):
                field_name = rule.get("field")
                contains_value = rule.get("contains")
                instruction = rule.get("instruction")

                field_value = ""
                if field_name == "pipeline_name":
                    field_value = pipeline_name
                elif field_name == "description":
                    field_value = description

                if (
                    contains_value
                    and instruction
                    and contains_value.lower() in field_value.lower()
                ):
                    custom_instructions.append(instruction)

            if custom_instructions:
                prompt_parts.append(
                    "\nAdditionally, pay close attention to the following:"
                )
                for instr in custom_instructions:
                    prompt_parts.append(f"- {instr}")

            # Add considerations
            if PROMPT_CONFIG.get("considerations"):
                prompt_parts.append("\nConsider:")
                for consideration in PROMPT_CONFIG["considerations"]:
                    prompt_parts.append(f"- {consideration}")

            # Add output format instruction
            output_instruction = PROMPT_CONFIG.get("output_format_instruction", "")
            if output_instruction:
                prompt_parts.append(output_instruction)

            prompt = "\n".join(prompt_parts)

            logger.info(
                f"Running basic agent analysis (fallback mode) for pipeline: {pipeline_run_name}"
            )
            result = agent.run(prompt)
            
            # Parse the result using improved logic
            decision, message = parse_agent_decision(result)
            
            logger.info(f"Agent decision: {decision} - {message}")
            return decision, message
        
    except Exception as e:
        logger.error(f"Error in agent analysis: {e}")
        return "reject", f"Error in analysis: {str(e)}"
