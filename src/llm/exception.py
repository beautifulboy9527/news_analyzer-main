"""
Custom exceptions for the LLM module.
"""

class LLMError(Exception):
    """Base exception class for LLM-related errors."""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def __str__(self):
        if self.status_code:
            return f"[Code: {self.status_code}] {self.message}"
        return self.message

# Add more specific exceptions inheriting from LLMError later if needed
# class RateLimitError(LLMError): ...
# class AuthenticationError(LLMError): ...
# class InvalidRequestError(LLMError): ... 