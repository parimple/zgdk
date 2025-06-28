"""Dependency injection container for service management."""

import logging
from typing import Any, Dict, Type, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from core.containers.unit_of_work import UnitOfWork

T = TypeVar("T")


class ServiceContainer:
    """Simple dependency injection container for managing services and their dependencies."""

    def __init__(self) -> None:
        self._services: Dict[Type, Any] = {}
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, callable] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_singleton(self, interface: Type[T], implementation: T) -> None:
        """Register a singleton service instance."""
        self._singletons[interface] = implementation
        self.logger.debug(
            f"Registered singleton: {interface.__name__} -> {implementation.__class__.__name__}"
        )

    def register_factory(self, interface: Type[T], factory: callable) -> None:
        """Register a factory function for creating service instances."""
        self._factories[interface] = factory
        self.logger.debug(f"Registered factory: {interface.__name__}")

    def register_transient(
        self, interface: Type[T], implementation_class: Type[T]
    ) -> None:
        """Register a transient service class (new instance each time)."""
        self._services[interface] = implementation_class
        self.logger.debug(
            f"Registered transient: {interface.__name__} -> {implementation_class.__name__}"
        )

    def get_service(self, interface: Type[T]) -> T:
        """Get service instance by interface type."""
        try:
            # Check singletons first
            if interface in self._singletons:
                return self._singletons[interface]

            # Check factories
            if interface in self._factories:
                instance = self._factories[interface]()
                self.logger.debug(f"Created instance via factory: {interface.__name__}")
                return instance

            # Check transient services
            if interface in self._services:
                implementation_class = self._services[interface]
                instance = implementation_class()
                self.logger.debug(f"Created transient instance: {interface.__name__}")
                return instance

            raise ValueError(f"Service not registered: {interface.__name__}")

        except Exception as e:
            self.logger.error(f"Error getting service {interface.__name__}: {e}")
            raise

    def create_unit_of_work(self, session: AsyncSession) -> UnitOfWork:
        """Create a new Unit of Work instance with the provided session."""
        return UnitOfWork(session)

    def has_service(self, interface: Type[T]) -> bool:
        """Check if a service is registered."""
        return (
            interface in self._singletons
            or interface in self._factories
            or interface in self._services
        )

    def clear(self) -> None:
        """Clear all registered services."""
        self._services.clear()
        self._singletons.clear()
        self._factories.clear()
        self.logger.debug("Service container cleared")

    def get_registered_services(self) -> Dict[str, str]:
        """Get a summary of all registered services for debugging."""
        services = {}

        for interface, implementation in self._singletons.items():
            services[
                interface.__name__
            ] = f"Singleton: {implementation.__class__.__name__}"

        for interface in self._factories.keys():
            services[interface.__name__] = "Factory"

        for interface, implementation_class in self._services.items():
            services[interface.__name__] = f"Transient: {implementation_class.__name__}"

        return services
