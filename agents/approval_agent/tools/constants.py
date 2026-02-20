

_static_approval_policy = None

def get_static_approval_policy():
    """Reads the approval policy from a YAML file and caches it in memory."""
    global _static_approval_policy
    if _static_approval_policy is None:
        try:
            with open("agents/approval_agent/tools/approval_policy.yaml", "r") as f:
                _static_approval_policy = f.read()
        except Exception as e:
            _static_approval_policy = None

    return _static_approval_policy