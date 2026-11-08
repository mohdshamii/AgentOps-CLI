"""
AgentOpsCLI custom typed error hierarchy.
"""

class AgentOpsError(Exception):
    """Base exception for all AgentOpsCLI errors."""
    pass


class ConfigurationError(AgentOpsError):
    """Configuration validation or loading error."""
    pass


class ProviderError(AgentOpsError):
    """Error communicating with an LLM provider."""
    pass


class AuthenticationError(ProviderError):
    """Missing or invalid credentials for a provider."""
    pass


class RateLimitError(ProviderError):
    """Rate limit exceeded on provider API."""
    pass


class ContextLengthExceededError(ProviderError):
    """Token context limit exceeded."""
    pass


class ToolExecutionError(AgentOpsError):
    """Error executing a tool."""
    pass


class SecurityViolationError(AgentOpsError):
    """Path traversal or unauthorized security escape violation."""
    pass

