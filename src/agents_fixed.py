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
    """Parse the agent's decision from the response"""
    response = str(result).lower()

    # Look for explicit decision statements first
    if "decision:" in response:
        decision_line = [
            line for line in response.split("\n") if "decision:" in line.lower()
        ]
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
        decision_section = response.split("decision:")[-1].split("\n")[0].strip()
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
                    required_k8s_tools = ["resources_get"]
                    
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
                        # Use the provided pipeline spec (real data)
                        commit_info = extract_git_info_from_pipeline_spec(pipeline_spec)
                        logger.info(f"Using provided pipeline spec")
                    else:
                        # Try to fetch PipelineRun spec using Kubernetes MCP server
                        try:
                            # Use the Kubernetes MCP server to fetch the PipelineRun
                            # This will be handled by the agent using the resources_get tool
                            logger.info(f"PipelineRun spec not provided, agent will fetch it using Kubernetes MCP server")
                            
                            # For now, use sample data as fallback
                            sample_pipeline_spec = {
                                "tasks": [
                                    {
                                        "taskRef": {"name": "git-clone"},
                                        "params": [
                                            {"name": "url", "value": "https://github.com/khrm/pipeline"},
                                            {"name": "revision", "value": "managedBy"}
                                        ]
                                    }
                                ]
                            }
                            commit_info = extract_git_info_from_pipeline_spec(sample_pipeline_spec)
                            logger.info(f"Using sample pipeline spec as fallback")
                        except Exception as e:
                            logger.warning(f"Failed to fetch PipelineRun spec: {e}")
                            # Use sample data as final fallback
                            sample_pipeline_spec = {
                                "tasks": [
                                    {
                                        "taskRef": {"name": "git-clone"},
                                        "params": [
                                            {"name": "url", "value": "https://github.com/khrm/pipeline"},
                                            {"name": "revision", "value": "managedBy"}
                                        ]
                                    }
                                ]
                            }
                            commit_info = extract_git_info_from_pipeline_spec(sample_pipeline_spec)
                            logger.info(f"Using sample pipeline spec as final fallback")
                    
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
                    if commit_info['commit_sha']:
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
                        # If we only have branch/revision info, analyze the latest changes
                        # Create the prompt with proper string formatting
                        owner = commit_info['repository_owner']
                        repo = commit_info['repository_name']
                        branch = commit_info['branch']
                        
                        prompt_parts.append(f"""
REPOSITORY INFORMATION TO ANALYZE:
Repository: {owner}/{repo}
Branch/Revision: {branch}
Git URL: {commit_info['git_url']}

IMPORTANT: If you need the actual PipelineRun spec (not provided), use the Kubernetes MCP server:
- Use resources_get tool to fetch the PipelineRun: {pipeline_run_name}
- This will give you the real pipelineSpec with actual git-clone task parameters

Use the GitHub tools to:
1. Get the latest commit from the branch/revision: {branch}
2. Parse the JSON response to extract the commit SHA
3. Get the commit details using the SHA
4. Analyze ONLY the diff content for code quality, security, and best practices
5. Focus on the specific changes, not the entire codebase

CRITICAL WORKFLOW - FOLLOW EXACTLY:
```python
import json

# Step 1: Get commits (returns JSON STRING)
commits_str = list_commits(owner="{owner}", repo="{repo}", sha="{branch}", page=1, perPage=1)
print(f"Raw commits result type: {{type(commits_str)}}")

# Step 2: Parse JSON STRING to get list
commits_data = json.loads(commits_str)
print(f"Parsed commits type: {{type(commits_data)}}")
print(f"Number of commits: {{len(commits_data)}}")

# Step 3: Check if we have commits
if len(commits_data) == 0:
    print(f"No commits found on branch '{branch}'. Trying main branch...")
    commits_str = list_commits(owner="{owner}", repo="{repo}", sha="main", page=1, perPage=1)
    commits_data = json.loads(commits_str)
    if len(commits_data) == 0:
        print("No commits found on main branch either.")
        exit(1)

# Step 4: Get commit SHA (commits_data is now a parsed list)
latest_commit_sha = commits_data[0]['sha']
print(f"Latest commit SHA: {{latest_commit_sha}}")

# Step 5: Get commit details (also returns JSON STRING)
commit_details_str = get_commit(owner="{owner}", repo="{repo}", sha=latest_commit_sha)
print(f"Commit details type: {{type(commit_details_str)}}")

# Step 6: Parse commit details
commit_data = json.loads(commit_details_str)
print(f"Parsed commit data keys: {{list(commit_data.keys())}}")

# Step 7: Analyze the commit
print(f"Commit message: {{commit_data['commit']['message']}}")
if 'files' in commit_data:
    print(f"Files changed: {{len(commit_data['files'])}}")
```

IMPORTANT: Use these exact values:
- owner: {owner}
- repo: {repo}  
- branch: {branch}

ERROR HANDLING: If the branch '{branch}' doesn't exist or has no commits, try the 'main' branch as a fallback.
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
                # Use the provided pipeline spec (real data)
                commit_info = extract_git_info_from_pipeline_spec(pipeline_spec)
            else:
                # For demo purposes, create a sample pipeline spec that would come from a real PipelineRun
                sample_pipeline_spec = {
                    "tasks": [
                        {
                            "taskRef": {"name": "git-clone"},
                            "params": [
                                {"name": "url", "value": "https://github.com/khrm/pipeline"},
                                {"name": "revision", "value": "main"}
                            ]
                        }
                    ]
                }
                commit_info = extract_git_info_from_pipeline_spec(sample_pipeline_spec)
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
