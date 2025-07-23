#!/usr/bin/env python3
"""
Test script for MCP tools usage
"""
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from smolagents import MCPClient
from config import MCP_SERVERS

def test_mcp_tools():
    """Test how to properly use MCP tools"""
    print("Testing MCP Tools Usage...")
    
    mcp_config = {
        "url": MCP_SERVERS["kubernetes"]["url"],
        "transport": "streamable-http"
    }
    
    try:
        with MCPClient(mcp_config) as tools:
            print(f"✅ Connected to MCP server with {len(tools)} tools")
            
            # Find the resources_get tool
            resources_get_tool = None
            for tool in tools:
                if tool.name == "resources_get":
                    resources_get_tool = tool
                    break
            
            if resources_get_tool:
                print(f"Found resources_get tool: {resources_get_tool}")
                print(f"Tool description: {resources_get_tool.description}")
                
                # Test fetching a PipelineRun
                try:
                    print("\n--- Testing PipelineRun fetch ---")
                    pipeline_run_result = resources_get_tool({
                        "apiVersion": "tekton.dev/v1",
                        "kind": "PipelineRun",
                        "name": "test-tm584"
                    })
                    print(f"✅ PipelineRun fetch successful!")
                    print(f"PipelineRun data: {pipeline_run_result}")
                except Exception as e:
                    print(f"❌ PipelineRun fetch failed: {e}")
                
                # Test fetching a Pipeline
                try:
                    print("\n--- Testing Pipeline fetch ---")
                    pipeline_result = resources_get_tool({
                        "apiVersion": "tekton.dev/v1",
                        "kind": "Pipeline",
                        "name": "test-tm584"
                    })
                    print(f"✅ Pipeline fetch successful!")
                    print(f"Pipeline data: {pipeline_result}")
                except Exception as e:
                    print(f"❌ Pipeline fetch failed: {e}")
                
                # Test fetching a TaskRun
                try:
                    print("\n--- Testing TaskRun fetch ---")
                    task_run_result = resources_get_tool({
                        "apiVersion": "tekton.dev/v1",
                        "kind": "TaskRun",
                        "name": "test-tm584-wait"
                    })
                    print(f"✅ TaskRun fetch successful!")
                    print(f"TaskRun data: {task_run_result}")
                except Exception as e:
                    print(f"❌ TaskRun fetch failed: {e}")
                
                # Test fetching a Pod
                try:
                    print("\n--- Testing Pod fetch ---")
                    pod_result = resources_get_tool({
                        "apiVersion": "v1",
                        "kind": "Pod",
                        "name": "test-tm584-before-pod"
                    })
                    print(f"✅ Pod fetch successful!")
                    print(f"Pod data: {pod_result}")
                except Exception as e:
                    print(f"❌ Pod fetch failed: {e}")
                
            else:
                print("resources_get tool not found")
                
    except Exception as e:
        print(f"❌ MCP test failed: {e}")

if __name__ == "__main__":
    test_mcp_tools() 