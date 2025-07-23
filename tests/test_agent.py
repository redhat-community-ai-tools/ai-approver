#!/usr/bin/env python3
"""
Test script for the AI Approver agent
"""
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agents import analyze_approval_task

def test_agent():
    """Test the agent with sample data"""
    print("Testing AI Approver Agent...")
    
    # Sample ApprovalTask data
    pipeline_run_name = "test-tm584"
    task_run_name = "test-tm584-wait"
    pipeline_name = "test-tm584"
    description = "Approval Task Rocks!!!"
    
    print(f"PipelineRun: {pipeline_run_name}")
    print(f"TaskRun: {task_run_name}")
    print(f"Pipeline: {pipeline_name}")
    print(f"Description: {description}")
    print("-" * 50)
    
    # Run agent analysis
    decision, message = analyze_approval_task(
        pipeline_run_name, 
        task_run_name, 
        pipeline_name, 
        description
    )
    
    print(f"Decision: {decision}")
    print(f"Message: {message}")

if __name__ == "__main__":
    test_agent() 