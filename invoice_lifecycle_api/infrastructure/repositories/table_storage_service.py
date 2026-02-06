from typing import Optional
from azure.data.tables.aio import TableClient
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError

from shared.utils.constants import CompoundKeyStructure
from shared.utils.exceptions import EntityDeleteException, EntityNotFoundException, EntityQueryException, EntityUpsertException, TableStorageException
from shared.utils.logging_config import get_logger
from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager
from invoice_lifecycle_api.application.interfaces.service_interfaces import CompareOperator, JoinOperator, TableServiceInterface


logger = get_logger(__name__)

AZURE_TABLE_METADATA_FIELDS = {'PartitionKey', 'RowKey', 'Timestamp', 'etag', 'odata.etag', 'odata.metadata'}


class TableStorageService(TableServiceInterface):
    """
    Azure Table Storage service for entity persistence operations.
    
    This service manages:
    - Upserting entities to Table Storage
    - Retrieving entities by partition and row keys
    - Querying entities with filters
    - Deleting entities
    - Managing Table Storage client lifecycle
    
    Attributes:
        account_url (str): Azure Storage account URL
        table_name (str): Table name for operations
        standalone (bool): Whether to manage credential lifecycle independently
        table_client (TableClient): Azure Table Storage client
    """

    def __init__(self, storage_account_url: str, table_name: str, standalone: bool = False):
        """
        Initialize Table Storage service.
        
        Args:
            storage_account_url: Azure Storage account URL
            table_name: Name of the table to operate on
            standalone: If True, manages credential manager lifecycle independently
        """
        self.account_url = storage_account_url
        self.table_name = table_name
        self.standalone = standalone

        logger.info(
            "Initializing Table Storage service",
            extra={
                "storage_account_url": storage_account_url,
                "table_name": table_name,
                "standalone": standalone
            }
        )

        credential_manager = get_credential_manager()
        self.table_client = TableClient(
            endpoint=self.account_url,
            table_name=self.table_name,
            credential=credential_manager.get_credential()
        )
        
        logger.info(
            "Table Storage client initialized successfully",
            extra={"table_name": table_name}
        )

    async def upsert_entity(
        self, 
        entity: dict, 
        partition_key: str, 
        row_key: str,
        correlation_id: Optional[str] = None
    ) -> str:
        """
        Upsert an entity to Azure Table Storage.
        
        Args:
            entity: Entity data to upsert
            partition_key: Partition key for the entity
            row_key: Row key for the entity
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Row key of the upserted entity
            
        Raises:
            EntityUpsertException: If upsert operation fails
        """
        logger.info(
            "Upserting entity to Table Storage",
            extra={
                "table_name": self.table_name,
                "partition_key": partition_key,
                "row_key": row_key,
                "correlation_id": correlation_id
            }
        )
        
        try:
            entity["PartitionKey"] = partition_key
            entity["RowKey"] = row_key

            await self.table_client.upsert_entity(entity=entity)
            
            logger.info(
                "Entity upserted successfully",
                extra={
                    "table_name": self.table_name,
                    "partition_key": partition_key,
                    "row_key": row_key,
                    "correlation_id": correlation_id
                }
            )
            
            return row_key
            
        except HttpResponseError as e:
            logger.error(
                "Azure Table Storage HTTP error during upsert",
                extra={
                    "table_name": self.table_name,
                    "partition_key": partition_key,
                    "row_key": row_key,
                    "correlation_id": correlation_id,
                    "error_type": "TableStorageHttpError",
                    "status_code": e.status_code,
                    "error_code": e.error_code,
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise EntityUpsertException(
                f"Failed to upsert entity (PartitionKey: {partition_key}, RowKey: {row_key}): {str(e)}"
            ) from e
            
        except Exception as e:
            logger.error(
                "Unexpected error during entity upsert",
                extra={
                    "table_name": self.table_name,
                    "partition_key": partition_key,
                    "row_key": row_key,
                    "correlation_id": correlation_id,
                    "error_type": "UnexpectedUpsertError",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise EntityUpsertException(
                f"Unexpected error upserting entity (PartitionKey: {partition_key}, RowKey: {row_key}): {str(e)}"
            ) from e

    async def get_entity(
        self, 
        partition_key: str, 
        row_key: str,
        correlation_id: Optional[str] = None
    ) -> Optional[dict]:
        """
        Retrieve entity from Azure Table Storage by partition and row keys.
        
        Args:
            partition_key: Partition key of the entity
            row_key: Row key of the entity
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            Entity data with metadata stripped, or None if not found
        """
        logger.debug(
            "Retrieving entity from Table Storage",
            extra={
                "table_name": self.table_name,
                "partition_key": partition_key,
                "row_key": row_key,
                "correlation_id": correlation_id
            }
        )

        try:
            entity = await self.table_client.get_entity(
                partition_key=partition_key, 
                row_key=row_key
            )
            
            logger.info(
                "Entity retrieved successfully",
                extra={
                    "table_name": self.table_name,
                    "partition_key": partition_key,
                    "row_key": row_key,
                    "correlation_id": correlation_id
                }
            )
            
            return self._strip_metadata(dict(entity))
            
        except ResourceNotFoundError:
            logger.info(
                "Entity not found in Table Storage",
                extra={
                    "table_name": self.table_name,
                    "partition_key": partition_key,
                    "row_key": row_key,
                    "correlation_id": correlation_id
                }
            )
            raise EntityNotFoundException(f"Entity not found (PartitionKey: {partition_key}, RowKey: {row_key})")

        except HttpResponseError as e:
            logger.error(
                "Azure Table Storage HTTP error during entity retrieval",
                extra={
                    "table_name": self.table_name,
                    "partition_key": partition_key,
                    "row_key": row_key,
                    "correlation_id": correlation_id,
                    "error_type": "TableStorageHttpError",
                    "status_code": e.status_code,
                    "error_code": e.error_code,
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise TableStorageException(f"Entity not found (PartitionKey: {partition_key}, RowKey: {row_key})")
            
        except Exception as e:
            logger.error(
                "Unexpected error retrieving entity from Table Storage",
                extra={
                    "table_name": self.table_name,
                    "partition_key": partition_key,
                    "row_key": row_key,
                    "correlation_id": correlation_id,
                    "error_type": "UnexpectedRetrievalError",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise TableStorageException(
                f"Unexpected error retrieving entity (PartitionKey: {partition_key}, RowKey: {row_key}): {str(e)}"
            )

    async def query_compound_key(
        self, 
        partition_key: str, 
        row_key: str,
        correlation_id: Optional[str] = None
    ) -> list[dict]:
        """
        Query entities from Azure Table Storage using compound key range.
        
        Uses PartitionKey equality and RowKey range to retrieve all entities
        with row keys starting with the specified prefix.
        
        Args:
            partition_key: Partition key to query
            row_key: Row key prefix for range query
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            List of entities matching the query (empty if none found)
            
        Raises:
            EntityQueryException: If query operation fails
        """
        filter_query = "PartitionKey eq @partition_key and RowKey ge @lower and RowKey lt @upper"
        parameters = {
            "partition_key": partition_key,
            "lower": f"{row_key}",
            "upper": f"{row_key}{CompoundKeyStructure.UPPER_BOUND.value}"
        }
        
        logger.info(
            "Querying entities with compound key",
            extra={
                "table_name": self.table_name,
                "partition_key": partition_key,
                "row_key_prefix": row_key,
                "filter_query": filter_query,
                "parameters": parameters,
                "correlation_id": correlation_id
            }
        )

        try:
            entities = self.table_client.query_entities(
                query_filter=filter_query,
                parameters=parameters
            )

            results = []
            async for entity in entities:
                results.append(self._strip_metadata(dict(entity)))

            logger.info(
                f"Compound key query completed: {len(results)} entities found",
                extra={
                    "table_name": self.table_name,
                    "partition_key": partition_key,
                    "row_key_prefix": row_key,
                    "result_count": len(results),
                    "correlation_id": correlation_id
                }
            )

            return results
            
        except HttpResponseError as e:
            logger.error(
                "Azure Table Storage HTTP error during compound key query",
                extra={
                    "table_name": self.table_name,
                    "partition_key": partition_key,
                    "row_key_prefix": row_key,
                    "correlation_id": correlation_id,
                    "error_type": "TableStorageHttpError",
                    "status_code": e.status_code,
                    "error_code": e.error_code,
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise EntityQueryException(
                f"Failed to query entities with compound key (PartitionKey: {partition_key}, RowKey prefix: {row_key}): {str(e)}"
            ) from e
            
        except Exception as e:
            logger.error(
                "Unexpected error during compound key query",
                extra={
                    "table_name": self.table_name,
                    "partition_key": partition_key,
                    "row_key_prefix": row_key,
                    "correlation_id": correlation_id,
                    "error_type": "UnexpectedQueryError",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise EntityQueryException(
                f"Unexpected error querying entities with compound key: {str(e)}"
            ) from e

    async def query_entities_with_filters(
        self, 
        filters: list[tuple[str, str, str]], 
        join_operator: JoinOperator = JoinOperator.AND,
        correlation_id: Optional[str] = None
    ) -> list[dict]:
        """
        Query entities from Azure Table Storage using custom filters.
        
        Args:
            filters: List of tuples (field_name, value, comparer)
                    Example: [("State", "PENDING", "eq"), ("Amount", "100", "gt")]
            join_operator: Operator to join filter conditions (AND/OR)
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            List of entities matching the query (empty if none found)
            
        Raises:
            EntityQueryException: If query operation fails
        """
        try:
            parameters = {}
            index = 1
            
            for field, value, comparer in filters:
                param_name = field.lower()
                if param_name in parameters:
                    param_name = f"{param_name}{index}"
                    index += 1
                parameters[param_name] = value
            
            name_filter = f" {join_operator.value} ".join(
                [f"{filter_name} {comparer} @{param_name}"
                 for (filter_name, value, comparer), param_name in zip(filters, parameters)]
            )

            logger.info(
                "Querying entities with custom filters",
                extra={
                    "table_name": self.table_name,
                    "filter_query": name_filter,
                    "parameters": parameters,
                    "join_operator": join_operator.value,
                    "correlation_id": correlation_id
                }
            )

            entities = self.table_client.query_entities(
                query_filter=name_filter,
                parameters=parameters
            )

            results = []
            async for entity in entities:
                results.append(self._strip_metadata(dict(entity)))
                
            logger.info(
                f"Custom filter query completed: {len(results)} entities found",
                extra={
                    "table_name": self.table_name,
                    "filter_query": name_filter,
                    "result_count": len(results),
                    "correlation_id": correlation_id
                }
            )
            
            return results
            
        except HttpResponseError as e:
            logger.error(
                "Azure Table Storage HTTP error during filtered query",
                extra={
                    "table_name": self.table_name,
                    "filters": str(filters),
                    "correlation_id": correlation_id,
                    "error_type": "TableStorageHttpError",
                    "status_code": e.status_code,
                    "error_code": e.error_code,
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise EntityQueryException(
                f"Failed to query entities with filters: {str(e)}"
            ) from e
            
        except Exception as e:
            logger.error(
                "Unexpected error during filtered query",
                extra={
                    "table_name": self.table_name,
                    "filters": str(filters),
                    "correlation_id": correlation_id,
                    "error_type": "UnexpectedQueryError",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise EntityQueryException(
                f"Unexpected error querying entities with filters: {str(e)}"
            ) from e

    async def query_entities(
        self, 
        filters_query: list[tuple[str, str]], 
        join_operator: JoinOperator = JoinOperator.AND, 
        compare_operator: CompareOperator = CompareOperator.EQUAL,
        correlation_id: Optional[str] = None
    ) -> list[dict]:
        """
        Query entities from Azure Table Storage with simplified filter syntax.
        
        Args:
            filters_query: List of tuples (field_name, value)
                          Example: [("State", "PENDING"), ("DepartmentId", "DEPT-001")]
            join_operator: Operator to join filter conditions (AND/OR)
            compare_operator: Comparison operator to use for all filters (default: EQUAL)
            correlation_id: Optional correlation ID for tracing
            
        Returns:
            List of entities matching the query (empty if none found)
            
        Raises:
            EntityQueryException: If query operation fails
        """
        try:
            parameters = {}
            index = 1
            
            for field, value in filters_query:
                # if parameters.get(f"{field.lower()}") is None:
                #     parameters[f"{field.lower()}"] = value
                # else:
                #     parameters[f"{field.lower()}{index}"] = value
                #     index += 1

                param_name = field.lower()
                if param_name in parameters:
                    param_name = f"{param_name}{index}"
                    index += 1
                parameters[param_name] = value

            name_filter = f"{join_operator.value}".join(
                [f"{filter_name} {compare_operator.value} @{param_name}" 
                 for (filter_name, filter_value), param_name in zip(filters_query, parameters)]
            )
            
            logger.info(
                "Querying entities with filters",
                extra={
                    "table_name": self.table_name,
                    "filter_query": name_filter,
                    "parameters": parameters,
                    "join_operator": join_operator.value,
                    "compare_operator": compare_operator.value,
                    "correlation_id": correlation_id
                }
            )

            entities = self.table_client.query_entities(
                query_filter=name_filter,
                parameters=parameters
            )

            results = []
            async for entity in entities:
                results.append(self._strip_metadata(dict(entity)))
                
            logger.info(
                f"Query completed: {len(results)} entities found",
                extra={
                    "table_name": self.table_name,
                    "filter_query": name_filter,
                    "result_count": len(results),
                    "correlation_id": correlation_id
                }
            )
            
            return results
            
        except HttpResponseError as e:
            logger.error(
                "Azure Table Storage HTTP error during entity query",
                extra={
                    "table_name": self.table_name,
                    "filters": str(filters_query),
                    "correlation_id": correlation_id,
                    "error_type": "TableStorageHttpError",
                    "status_code": e.status_code,
                    "error_code": e.error_code,
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise EntityQueryException(
                f"Failed to query entities: {str(e)}"
            ) from e
            
        except Exception as e:
            logger.error(
                "Unexpected error during entity query",
                extra={
                    "table_name": self.table_name,
                    "filters": str(filters_query),
                    "correlation_id": correlation_id,
                    "error_type": "UnexpectedQueryError",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise EntityQueryException(
                f"Unexpected error querying entities: {str(e)}"
            ) from e

    async def delete_entity(
        self, 
        partition_key: str, 
        row_key: str,
        correlation_id: Optional[str] = None
    ) -> None:
        """
        Delete entity from Azure Table Storage.
        
        Args:
            partition_key: Partition key of the entity
            row_key: Row key of the entity
            correlation_id: Optional correlation ID for tracing
            
        Raises:
            EntityDeleteException: If delete operation fails
        """
        logger.info(
            "Deleting entity from Table Storage",
            extra={
                "table_name": self.table_name,
                "partition_key": partition_key,
                "row_key": row_key,
                "correlation_id": correlation_id
            }
        )
        
        try:
            await self.table_client.delete_entity(
                partition_key=partition_key, 
                row_key=row_key
            )
            
            logger.info(
                "Entity deleted successfully",
                extra={
                    "table_name": self.table_name,
                    "partition_key": partition_key,
                    "row_key": row_key,
                    "correlation_id": correlation_id
                }
            )
            
        except ResourceNotFoundError:
            logger.warning(
                "Entity not found for deletion (already deleted or never existed)",
                extra={
                    "table_name": self.table_name,
                    "partition_key": partition_key,
                    "row_key": row_key,
                    "correlation_id": correlation_id
                }
            )
            # Not raising exception for idempotent delete operations
            
        except HttpResponseError as e:
            logger.error(
                "Azure Table Storage HTTP error during entity deletion",
                extra={
                    "table_name": self.table_name,
                    "partition_key": partition_key,
                    "row_key": row_key,
                    "correlation_id": correlation_id,
                    "error_type": "TableStorageHttpError",
                    "status_code": e.status_code,
                    "error_code": e.error_code,
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise EntityDeleteException(
                f"Failed to delete entity (PartitionKey: {partition_key}, RowKey: {row_key}): {str(e)}"
            ) from e
            
        except Exception as e:
            logger.error(
                "Unexpected error during entity deletion",
                extra={
                    "table_name": self.table_name,
                    "partition_key": partition_key,
                    "row_key": row_key,
                    "correlation_id": correlation_id,
                    "error_type": "UnexpectedDeleteError",
                    "error_details": str(e)
                },
                exc_info=True
            )
            raise EntityDeleteException(
                f"Unexpected error deleting entity (PartitionKey: {partition_key}, RowKey: {row_key}): {str(e)}"
            ) from e

    async def close(self) -> None:
        """
        Close Table Storage client and optionally credential manager.
        
        Should be called during application shutdown to release resources.
        If standalone=True, also closes the credential manager.
        """
        logger.info(
            "Closing Table Storage service",
            extra={
                "table_name": self.table_name,
                "standalone": self.standalone
            }
        )
        
        if self.table_client:
            try:
                await self.table_client.close()
                logger.info(
                    "Table Storage client closed successfully",
                    extra={"table_name": self.table_name}
                )
            except Exception as e:
                logger.warning(
                    "Error closing Table Storage client",
                    extra={
                        "table_name": self.table_name,
                        "error_details": str(e)
                    }
                )
        
        if self.standalone:
            try:
                credential_manager = get_credential_manager()
                await credential_manager.close()
                logger.info("Credential manager closed successfully")
            except Exception as e:
                logger.warning(
                    "Error closing credential manager",
                    extra={"error_details": str(e)}
                )

    def _strip_metadata(self, entity: dict) -> dict:
        """
        Remove Azure Table Storage metadata fields from entity.
        
        Args:
            entity: Entity dict including metadata fields
            
        Returns:
            Entity dict with metadata fields removed
        """
        return {k: v for k, v in entity.items() if k not in AZURE_TABLE_METADATA_FIELDS}

    async def __aenter__(self) -> "TableStorageService":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager and close resources."""
        await self.close()