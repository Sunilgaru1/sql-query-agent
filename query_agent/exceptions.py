class AgentError(Exception):
    """Base error for the Text-to-SQL agent."""


class UnsafeSQLError(AgentError):
    """Raised when generated SQL fails the security gateway."""


class ConfigurationError(AgentError):
    """Raised when required environment configuration is missing."""


class QueryRepairExhaustedError(AgentError):
    """Raised after the self-correction loop hits the retry limit."""
