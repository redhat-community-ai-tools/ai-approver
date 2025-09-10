import kopf
import logging
from datetime import datetime, timezone
from agents import analyze_approval_task
from kubernetes import client, config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CRD details for ApprovalTask
GROUP = "openshift-pipelines.org"
VERSION = "v1alpha1"
PLURAL = "approvaltasks"
AI_APPROVER_NAME = "kubernetes-admin"
ANNOTATION_REVIEWED_AT = "ai-approver.openshift-pipelines.org/reviewed-at"

# Initialize Kubernetes client
try:
    config.load_incluster_config()  # Try in-cluster config first
    logger.info("Using in-cluster Kubernetes config")
except:
    try:
        config.load_kube_config()  # Fall back to local kubeconfig
        logger.info("Using local kubeconfig")
    except Exception as e:
        logger.warning(f"Could not load Kubernetes config: {e}")

def fetch_pipeline_run_spec(pipeline_run_name, namespace):
    """
    Fetch the PipelineRun spec from Kubernetes using the client.
    Returns the pipelineSpec if found, None otherwise.
    """
    # Validate input parameters
    if not pipeline_run_name or not pipeline_run_name.strip():
        logger.warning("Empty or invalid PipelineRun name provided")
        return None
    
    try:
        # Create a custom API client for Tekton resources
        api_client = client.ApiClient()
        
        # Use the custom resource API to fetch PipelineRun
        custom_api = client.CustomObjectsApi(api_client)
        
        pipeline_run = custom_api.get_namespaced_custom_object(
            group="tekton.dev",
            version="v1",
            namespace=namespace,
            plural="pipelineruns",
            name=pipeline_run_name
        )
        
        # Extract the pipelineSpec from the PipelineRun
        spec = pipeline_run.get("spec", {})
        pipeline_spec = spec.get("pipelineSpec", {})
        
        # If no inline pipelineSpec, check the status section first
        if not pipeline_spec:
            status = pipeline_run.get("status", {})
            pipeline_spec = status.get("pipelineSpec", {})
            if pipeline_spec:
                logger.info(f"Found pipelineSpec in status section for PipelineRun '{pipeline_run_name}'")
        
        # If still no pipelineSpec, check if it references an external Pipeline
        if not pipeline_spec:
            pipeline_ref = spec.get("pipelineRef", {})
            if pipeline_ref:
                pipeline_name = pipeline_ref.get("name")
                if pipeline_name:
                    logger.info(f"PipelineRun '{pipeline_run_name}' references Pipeline '{pipeline_name}', fetching Pipeline spec")
                    pipeline_spec = fetch_pipeline_spec(pipeline_name, namespace)
                else:
                    logger.warning(f"PipelineRun '{pipeline_run_name}' has pipelineRef but no name")
            else:
                logger.warning(f"PipelineRun '{pipeline_run_name}' has no pipelineSpec in spec, status, or pipelineRef")
        
        # Return None if pipelineSpec is still empty
        if not pipeline_spec:
            return None
        
        logger.info(f"Successfully fetched PipelineRun '{pipeline_run_name}' from namespace '{namespace}'")
        return pipeline_spec
        
    except client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning(f"PipelineRun '{pipeline_run_name}' not found in namespace '{namespace}'")
        else:
            logger.error(f"Error fetching PipelineRun '{pipeline_run_name}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching PipelineRun '{pipeline_run_name}': {e}")
        return None

def fetch_pipeline_spec(pipeline_name, namespace):
    """
    Fetch the Pipeline spec from Kubernetes using the client.
    Returns the pipeline spec if found, None otherwise.
    """
    try:
        # Create a custom API client for Tekton resources
        api_client = client.ApiClient()
        
        # Use the custom resource API to fetch Pipeline
        custom_api = client.CustomObjectsApi(api_client)
        
        pipeline = custom_api.get_namespaced_custom_object(
            group="tekton.dev",
            version="v1",
            namespace=namespace,
            plural="pipelines",
            name=pipeline_name
        )
        
        # Extract the spec from the Pipeline
        pipeline_spec = pipeline.get("spec", {})
        
        if not pipeline_spec:
            logger.warning(f"Pipeline '{pipeline_name}' has no spec")
            return None
        
        logger.info(f"Successfully fetched Pipeline '{pipeline_name}' from namespace '{namespace}'")
        return pipeline_spec
        
    except client.exceptions.ApiException as e:
        if e.status == 404:
            logger.warning(f"Pipeline '{pipeline_name}' not found in namespace '{namespace}'")
        else:
            logger.error(f"Error fetching Pipeline '{pipeline_name}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching Pipeline '{pipeline_name}': {e}")
        return None


@kopf.on.create(GROUP, VERSION, PLURAL)
@kopf.on.update(GROUP, VERSION, PLURAL)
def handle_approval_task(spec, name, namespace, body, logger, patch, **kwargs):
    """
    Handles the creation and update of ApprovalTask resources.
    """
    annotations = body.get("metadata", {}).get("annotations", {})
    if ANNOTATION_REVIEWED_AT in annotations:
        logger.info(
            f"ApprovalTask '{name}' was already reviewed at {annotations[ANNOTATION_REVIEWED_AT]}. Skipping."
        )
        pass
        return

    approvers = spec.get("approvers", [])

    # Find the AI approver in the list of approvers
    ai_approver_entry = None
    ai_approver_index = -1
    for i, approver in enumerate(approvers):
        if approver.get("name") == AI_APPROVER_NAME:
            ai_approver_entry = approver
            ai_approver_index = i
            break

    # If the AI approver is not in the list, there's nothing to do.
    if not ai_approver_entry:
        logger.info(
            f"'{AI_APPROVER_NAME}' not in approvers list for ApprovalTask '{name}'. Skipping."
        )
        return

    # If the AI approver has already made a decision (and it's not 'pending'), do nothing.
    current_input = ai_approver_entry.get("input")
    if current_input and current_input != "pending":
        logger.info(
            f"'{AI_APPROVER_NAME}' has already provided input '{current_input}' for ApprovalTask '{name}'. Skipping."
        )
        return

    logger.info(f"Processing ApprovalTask for '{AI_APPROVER_NAME}': {name}")

    # Extract data from ApprovalTask
    description = spec.get("description", "")
    labels = body.get("metadata", {}).get("labels", {})

    # Extract Tekton labels
    pipeline_run_name = labels.get("tekton.dev/pipelineRun", "")
    pipeline_name = labels.get("tekton.dev/pipeline", "")

    logger.info(
        f"Extracted data - PipelineRun: {pipeline_run_name}, Pipeline: {pipeline_name}"
    )

    # Fetch the PipelineRun spec using Kubernetes client
    pipeline_spec = None
    if pipeline_run_name:
        pipeline_spec = fetch_pipeline_run_spec(pipeline_run_name, namespace)
        if pipeline_spec:
            logger.info(f"Successfully fetched pipeline spec for PipelineRun '{pipeline_run_name}'")
        else:
            logger.warning(f"Could not fetch pipeline spec for PipelineRun '{pipeline_run_name}'")
    else:
        logger.warning("No PipelineRun name found in labels, proceeding without pipeline spec")
    
    decision, message = analyze_approval_task(
        pipeline_run_name, pipeline_name, description, pipeline_spec
    )

    logger.info(f"Decision for '{name}' by '{AI_APPROVER_NAME}': {decision}")

    # The admission webhook might reject patches that replace the whole approvers list.
    # We are using kopf's patching, which will replace the list.
    # If this fails, a JSON patch with the kubernetes client is needed.
    approvers[ai_approver_index]["input"] = decision
    approvers[ai_approver_index]["message"] = message

    patch["spec"] = {"approvers": approvers}

    reviewed_at_time = datetime.now(timezone.utc).isoformat()
    if "metadata" not in patch:
        patch["metadata"] = {}
    if "annotations" not in patch["metadata"]:
        patch["metadata"]["annotations"] = {}
    patch["metadata"]["annotations"][ANNOTATION_REVIEWED_AT] = reviewed_at_time

    logger.info(f"Successfully generated patch for ApprovalTask '{name}'.")
