# Adapted from nature-academic-search 0.3.1 (wp-a), MIT.
"""Use the caller's logging policy; do not attach handlers during import."""
import logging

def setup_logging(level="INFO"):
    return logging.getLogger("literature_workflow.sources")
