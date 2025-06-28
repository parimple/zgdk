"""
Intelligent error handling using PydanticAI.
"""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent


class ErrorCategory(str, Enum):
    """Categories of errors."""
    PERMISSION = "permission"
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    RATE_LIMIT = "rate_limit"
    PAYMENT = "payment"
    CONFIGURATION = "configuration"
    NETWORK = "network"
    DATABASE = "database"
    UNKNOWN = "unknown"


class ErrorResponse(BaseModel):
    """Structured error response."""
    error_message: str
    user_message: str
    suggestion: Optional[str] = None
    help_command: Optional[str] = None
    error_category: ErrorCategory
    technical_details: Optional[str] = None
    
    def to_discord_message(self) -> str:
        """Format for Discord message."""
        parts = [f"❌ **{self.user_message}**"]
        
        if self.suggestion:
            parts.append(f"\n💡 **Suggestion:** {self.suggestion}")
        
        if self.help_command:
            parts.append(f"\n📖 Use `{self.help_command}` for more help")
        
        return '\n'.join(parts)


class IntelligentErrorHandler:
    """Generate helpful error messages with AI assistance."""
    
    # Common error mappings
    ERROR_MAPPINGS = {
        "InsufficientFunds": (
            ErrorCategory.PAYMENT,
            "You don't have enough credits for this action.",
            "Check your balance with `/balance`"
        ),
        "MissingPermissions": (
            ErrorCategory.PERMISSION,
            "You don't have permission to use this command.",
            "This command requires special roles or permissions."
        ),
        "MemberNotFound": (
            ErrorCategory.NOT_FOUND,
            "Could not find the specified member.",
            "Make sure you're mentioning or providing a valid user ID."
        ),
        "InvalidColor": (
            ErrorCategory.VALIDATION,
            "Invalid color format provided.",
            "Use hex format (#RRGGBB), RGB (rgb(r,g,b)), or color names."
        ),
        "CommandOnCooldown": (
            ErrorCategory.RATE_LIMIT,
            "This command is on cooldown.",
            "Please wait before using this command again."
        ),
    }
    
    def __init__(self, use_ai: bool = True):
        """Initialize error handler."""
        self.use_ai = use_ai
        
        if use_ai:
            self.agent = Agent(
                'openai:gpt-3.5-turbo',
                system_prompt="""You are a helpful Discord bot error handler.
                Generate user-friendly error messages that:
                1. Explain what went wrong in simple terms
                2. Provide actionable suggestions to fix it
                3. Include relevant command examples
                4. Stay under 100 words
                5. Use a friendly, helpful tone
                
                Focus on being helpful rather than technical.
                If suggesting commands, use Discord slash command format (/command).
                """
            )
    
    async def handle_error(
        self,
        error: Exception,
        command: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ErrorResponse:
        """Generate appropriate error response."""
        error_type = type(error).__name__
        error_str = str(error)
        
        # First check known error mappings
        if error_type in self.ERROR_MAPPINGS:
            category, message, suggestion = self.ERROR_MAPPINGS[error_type]
            return ErrorResponse(
                error_message=error_str,
                user_message=message,
                suggestion=suggestion,
                help_command=f"/help {command}" if command else "/help",
                error_category=category,
                technical_details=error_type
            )
        
        # Try to categorize by error message content
        category = self._categorize_error(error_str)
        
        # If AI is enabled, get enhanced error message
        if self.use_ai:
            return await self._generate_ai_response(
                error, command, context, category
            )
        
        # Fallback to generic message
        return self._generate_fallback_response(
            error, command, category
        )
    
    def _categorize_error(self, error_message: str) -> ErrorCategory:
        """Categorize error based on message content."""
        lower_msg = error_message.lower()
        
        if any(word in lower_msg for word in ['permission', 'forbidden', 'unauthorized']):
            return ErrorCategory.PERMISSION
        elif any(word in lower_msg for word in ['not found', 'unknown', 'missing']):
            return ErrorCategory.NOT_FOUND
        elif any(word in lower_msg for word in ['invalid', 'format', 'type']):
            return ErrorCategory.VALIDATION
        elif any(word in lower_msg for word in ['cooldown', 'rate limit', 'too fast']):
            return ErrorCategory.RATE_LIMIT
        elif any(word in lower_msg for word in ['payment', 'funds', 'credits', 'balance']):
            return ErrorCategory.PAYMENT
        elif any(word in lower_msg for word in ['database', 'connection', 'query']):
            return ErrorCategory.DATABASE
        elif any(word in lower_msg for word in ['network', 'timeout', 'unreachable']):
            return ErrorCategory.NETWORK
        
        return ErrorCategory.UNKNOWN
    
    async def _generate_ai_response(
        self,
        error: Exception,
        command: Optional[str],
        context: Optional[Dict[str, Any]],
        category: ErrorCategory
    ) -> ErrorResponse:
        """Generate AI-enhanced error response."""
        try:
            # Prepare context for AI
            error_info = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "command": command,
                "category": category.value,
                "context": context or {}
            }
            
            # Get AI response
            prompt = f"""Generate a helpful error message for this Discord bot error:
            {error_info}
            
            Return a JSON with:
            - user_message: Simple explanation (required)
            - suggestion: How to fix it (optional)
            - help_command: Relevant help command (optional)
            """
            
            result = await self.agent.run(prompt, result_type=Dict)
            ai_data = result.data
            
            return ErrorResponse(
                error_message=str(error),
                user_message=ai_data.get("user_message", "An error occurred."),
                suggestion=ai_data.get("suggestion"),
                help_command=ai_data.get("help_command", f"/help {command}" if command else None),
                error_category=category,
                technical_details=type(error).__name__
            )
            
        except Exception:
            # If AI fails, use fallback
            return self._generate_fallback_response(error, command, category)
    
    def _generate_fallback_response(
        self,
        error: Exception,
        command: Optional[str],
        category: ErrorCategory
    ) -> ErrorResponse:
        """Generate fallback error response without AI."""
        # Category-specific messages
        category_messages = {
            ErrorCategory.PERMISSION: (
                "You don't have permission to do that.",
                "Make sure you have the required role or permissions."
            ),
            ErrorCategory.VALIDATION: (
                "Invalid input provided.",
                "Check the command format and try again."
            ),
            ErrorCategory.NOT_FOUND: (
                "Could not find what you're looking for.",
                "Double-check your input and try again."
            ),
            ErrorCategory.RATE_LIMIT: (
                "Slow down! You're using commands too quickly.",
                "Wait a moment before trying again."
            ),
            ErrorCategory.PAYMENT: (
                "There was an issue with the transaction.",
                "Check your balance or contact support."
            ),
            ErrorCategory.DATABASE: (
                "Database error occurred.",
                "This is temporary - please try again later."
            ),
            ErrorCategory.NETWORK: (
                "Network connection issue.",
                "Check your connection and try again."
            ),
            ErrorCategory.UNKNOWN: (
                "An unexpected error occurred.",
                "Try again or contact support if it persists."
            )
        }
        
        message, suggestion = category_messages.get(
            category,
            ("An error occurred.", "Please try again.")
        )
        
        return ErrorResponse(
            error_message=str(error),
            user_message=message,
            suggestion=suggestion,
            help_command=f"/help {command}" if command else "/help",
            error_category=category,
            technical_details=type(error).__name__
        )
    
    async def generate_command_help(
        self,
        command: str,
        error: Optional[Exception] = None
    ) -> str:
        """Generate helpful command usage information."""
        if not self.use_ai:
            return f"Use `/help {command}` for more information."
        
        try:
            prompt = f"""Generate a brief help message for the Discord command '{command}'.
            Include:
            1. What the command does
            2. Basic usage syntax
            3. One example
            
            Keep it under 50 words."""
            
            if error:
                prompt += f"\nThe user encountered this error: {error}"
            
            result = await self.agent.run(prompt)
            return result.data
            
        except Exception:
            return f"Use `/help {command}` for more information."


# Convenience function
async def handle_command_error(
    error: Exception,
    command: Optional[str] = None,
    context: Optional[Dict] = None,
    use_ai: bool = True
) -> ErrorResponse:
    """Quick error handling function."""
    handler = IntelligentErrorHandler(use_ai=use_ai)
    return await handler.handle_error(error, command, context)