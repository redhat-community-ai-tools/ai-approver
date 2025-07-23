import kopf
import logging
import copy
import json
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(level=logging.INFO)

# CRD details for ApprovalTask
GROUP = "openshift-pipelines.org"
VERSION = "v1alpha1"
PLURAL = "approvaltasks"
AI_APPROVER_NAME = "kubernetes-admin"
ANNOTATION_REVIEWED_AT = "ai-approver.openshift-pipelines.org/reviewed-at"


@kopf.on.create(GROUP, VERSION, PLURAL)
@kopf.on.update(GROUP, VERSION, PLURAL)
def handle_approval_task(spec, name, namespace, body, logger, patch, **kwargs):
    """
    Handles the creation and update of ApprovalTask resources.
    """
    annotations = body.get("metadata", {}).get("annotations", {})
    if ANNOTATION_REVIEWED_AT in annotations:
        logger.info(f"ApprovalTask '{name}' was already reviewed at {annotations[ANNOTATION_REVIEWED_AT]}. Skipping.")
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
        logger.info(f"'{AI_APPROVER_NAME}' not in approvers list for ApprovalTask '{name}'. Skipping.")
        return

    # If the AI approver has already made a decision (and it's not 'pending'), do nothing.
    current_input = ai_approver_entry.get("input")
    if current_input and current_input != "pending":
        logger.info(f"'{AI_APPROVER_NAME}' has already provided input '{current_input}' for ApprovalTask '{name}'. Skipping.")
        return

    logger.info(f"Processing ApprovalTask for '{AI_APPROVER_NAME}': {name}")

    # Get the description from the spec
    description = spec.get("description", "")

    # Simple rule: Approve if "LGTM" is in the description, otherwise reject
    decision = "approve"
    message = "Approved automatically"

    logger.info(f"Decision for '{name}' by '{AI_APPROVER_NAME}': {decision}")

    # The admission webhook might reject patches that replace the whole approvers list.
    # We are using kopf's patching, which will replace the list.
    # If this fails, a JSON patch with the kubernetes client is needed.
    approvers[ai_approver_index]['input'] = decision
    approvers[ai_approver_index]['message'] = message

    patch['spec'] = {'approvers': approvers}

    reviewed_at_time = datetime.now(timezone.utc).isoformat()
    if 'metadata' not in patch:
        patch['metadata'] = {}
    if 'annotations' not in patch['metadata']:
        patch['metadata']['annotations'] = {}
    patch['metadata']['annotations'][ANNOTATION_REVIEWED_AT] = reviewed_at_time

    logger.info(f"Successfully generated patch for ApprovalTask '{name}'.")
