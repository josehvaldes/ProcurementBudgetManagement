"""Dependency Injection Container."""
from invoice_lifecycle_api.application.interfaces.service_interfaces import MessagingServiceInterface, StorageServiceInterface, TableServiceInterface
from invoice_lifecycle_api.infrastructure.azure_credential_manager import AzureCredentialManager, get_credential_manager
from invoice_lifecycle_api.infrastructure.messaging.servicebus_messaging_service import ServiceBusMessagingService
from invoice_lifecycle_api.infrastructure.repositories.in_memory_invoice_storage import InMemoryInvoiceStorageService
from invoice_lifecycle_api.infrastructure.repositories.in_memory_table_repository_service import InMemoryTableRepositoryService
from invoice_lifecycle_api.infrastructure.repositories.invoice_storage_service import InvoiceStorageService
from invoice_lifecycle_api.infrastructure.repositories.table_storage_service import TableStorageService
from invoice_lifecycle_api.application.services.event_choreographer import EventChoreographer
from shared.config.settings import settings


class DIContainer:
    """Simple dependency injection container."""
    
    def __init__(self):
        self._services = {}
        self._singletons = {}
        self._setup_services()

    def _setup_services(self):
        
        print("Setting up Singleton DI Container services...")
        azure_credential_manager = get_credential_manager()
        self._singletons[AzureCredentialManager] = azure_credential_manager
        self._singletons[MessagingServiceInterface] = ServiceBusMessagingService()

        if settings.repository_type == "in_memory": 
            self._singletons[TableServiceInterface] = InMemoryTableRepositoryService()
            self._singletons[StorageServiceInterface] = InMemoryInvoiceStorageService()
        else:
            self._singletons[TableServiceInterface] = TableStorageService()
            self._singletons[StorageServiceInterface] = InvoiceStorageService()

        

    def get_service(self, service_type, *args, **kwargs):
        
        # Return cached singleton if exists
        if service_type in self._singletons:
            return self._singletons[service_type]
        
        """Get a service instance by type."""
        if service_type in self._services:
            service_class = self._services[service_type]
            return service_class(*args, **kwargs)
        raise ValueError(f"Service {service_type} not registered")

# Global container instance
_container = DIContainer()

async def close_all_services() -> None:
    """Close all services that require cleanup."""
    for service in _container._singletons.values():
        if hasattr(service, "close") and callable(service.close):
            await service.close()

    for service in _container._services.values():
        if hasattr(service, "close") and callable(service.close):
            await service.close()


def get_repository_service() -> TableServiceInterface:
    """Dependency injection function for product service."""
    return _container.get_service(TableServiceInterface)

def get_invoice_storage_service():
    """Dependency injection function for invoice storage service."""
    return _container.get_service(StorageServiceInterface)

def get_event_choreographer_service():
    """Dependency injection function for event choreographer service."""
    table_repository = _container.get_service(TableServiceInterface)
    invoice_storage = _container.get_service(StorageServiceInterface)
    messaging_service = _container.get_service(MessagingServiceInterface)
    return EventChoreographer(table_repository, invoice_storage, messaging_service)