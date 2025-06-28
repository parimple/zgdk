"""Database-related exceptions."""

from typing import Any, Optional

from .base import BotError


class DatabaseError(BotError):
    """Base exception for database errors."""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        table: Optional[str] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize database error."""
        details = {}
        if operation:
            details["operation"] = operation
        if table:
            details["table"] = table

        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            details=details,
            user_message=user_message or "Błąd bazy danych.",
        )


class EntityNotFoundError(DatabaseError):
    """Raised when an entity is not found in the database."""

    def __init__(
        self,
        entity_type: str,
        entity_id: Any,
        user_message: Optional[str] = None,
    ):
        """Initialize entity not found error."""
        super().__init__(
            message=f"{entity_type} with id {entity_id} not found",
            operation="SELECT",
            table=entity_type.lower(),
            user_message=user_message or f"Nie znaleziono {entity_type}.",
        )
        self.entity_type = entity_type
        self.entity_id = entity_id


class IntegrityError(DatabaseError):
    """Raised when a database integrity constraint is violated."""

    def __init__(
        self,
        constraint: str,
        message: Optional[str] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize integrity error."""
        super().__init__(
            message=message or f"Integrity constraint violated: {constraint}",
            operation="INSERT/UPDATE",
            user_message=user_message or "Naruszenie integralności danych.",
        )
        self.constraint = constraint


class ConnectionError(DatabaseError):
    """Raised when database connection fails."""

    def __init__(
        self,
        message: Optional[str] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize connection error."""
        super().__init__(
            message=message or "Failed to connect to database",
            user_message=user_message or "Błąd połączenia z bazą danych.",
        )
