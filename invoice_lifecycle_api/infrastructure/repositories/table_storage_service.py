import traceback
from enum import Enum
from azure.data.tables.aio import TableClient

from shared.utils.logging_config import get_logger

from invoice_lifecycle_api.infrastructure.azure_credential_manager import get_credential_manager
from invoice_lifecycle_api.application.interfaces.service_interfaces import CompareOperator, JoinOperator, TableServiceInterface


logger = get_logger(__name__)

AZURE_TABLE_METADATA_FIELDS = {'PartitionKey', 'RowKey', 'Timestamp', 'etag', 'odata.etag', 'odata.metadata'}

class CompoundKeyStructure(str, Enum):
    LOWER_BOUND = ":"
    UPPER_BOUND = ";"
    

class TableStorageService(TableServiceInterface):

    def __init__(self, storage_account_url, table_name, standalone: bool = False):
        self.account_url = storage_account_url
        self.table_name = table_name
        self.standalone = standalone

        credential_manager = get_credential_manager()
        self.table_client = TableClient(
            endpoint=self.account_url,
            table_name=self.table_name,
            credential=credential_manager.get_credential()
        )

    async def upsert_entity(self, entity: dict, partition_key: str, row_key: str) -> str:
        """Save an entity to the Azure Table Storage."""
        try:
            entity["PartitionKey"] = partition_key
            entity["RowKey"] = row_key

            _ = await self.table_client.upsert_entity(entity=entity)
            logger.info(f"Entity saved successfully. Row Key: {row_key}")
            return row_key
        except Exception as e:
            logger.error(f"Error saving entity to Table Storage: {e}")
            return ""

    async def get_entity(self, partition_key: str, row_key: str) -> dict | None:
        """Retrieve entity data from Azure Table Storage by entity ID."""

        try:
            entity = await self.table_client.get_entity(partition_key=partition_key, row_key=row_key)
            logger.info(f"Entity retrieved successfully. Row Key: {row_key}")
            return self._strip_metadata(dict(entity))
        except Exception as e:
            logger.error(f"Error retrieving entity from Table Storage: {e}")
            return None

    async def query_compound_key(self, partition_key: str, row_key: str) -> list[dict]:
        """Query entity from Azure Table Storage using PartitionKey and RowKey."""
        try:
            filter_query = "PartitionKey eq @partition_key and RowKey ge @lower and RowKey lt @upper"
            parameters = {
                "partition_key": partition_key,
                "lower": row_key,
                "upper": row_key + CompoundKeyStructure.UPPER_BOUND.value  # Upper bound is exclusive
            }

            logger.info(f"Querying entity with PartitionKey: {partition_key}, RowKey: {row_key}")

            entities = self.table_client.query_entities(query_filter=filter_query,
                                                        parameters=parameters)

            results = []
            async for entity in entities:
                logger.info(f"Entity queried successfully. Row Key: {row_key}")
                results.append(self._strip_metadata(dict(entity)))

            if not results:
                logger.info(f"No entity found with PartitionKey: {partition_key}, RowKey: {row_key}")
                return []

            return results

        except Exception as e:
            logger.error(f"Error querying entity from Table Storage: {e}")
            traceback.print_exc()
            return []

    async def query_entities(self, filters_query: list[tuple[str, str]], 
                             join_operator: JoinOperator = JoinOperator.AND, 
                             compare_operator: CompareOperator = CompareOperator.EQUAL) -> list[dict]:
        """Query entities from Azure Table Storage using a filter string."""
        results = []
        try:
            parameters = {}

            index = 1
            for field, value in filters_query:
                if parameters.get(f"{field.lower()}") is None:
                    parameters[f"{field.lower()}"] = value
                else:
                    parameters[f"{field.lower()}{index}"] = value
                    index += 1
            
            name_filter = f"{join_operator.value}".join([f"{filter_name} {compare_operator.value} @{param_name}" for (filter_name, filter_value), param_name in zip(filters_query, parameters) ])
            
            logger.info(f"Querying entities with filter:[{name_filter}]. Parameters: {parameters}")

            entities = self.table_client.query_entities(query_filter=name_filter,
                                                        parameters=parameters)

            async for entity in entities:
                results.append(self._strip_metadata(dict(entity)))
            logger.info(f"Queried {len(results)} entities successfully. filter:[{name_filter}]. Parameters: {parameters}")
        except Exception as e:
            logger.error(f"Error querying entities from Table Storage: {e}")
            traceback.print_exc()
        return results

    async def delete_entity(self, partition_key: str, row_key: str) -> None:
        """Delete entity data from Azure Table Storage by entity ID."""
        try:
            await self.table_client.delete_entity(partition_key=partition_key, row_key=row_key)
            logger.info(f"Entity deleted successfully. Row Key: {row_key}")
        except Exception as e:
            logger.error(f"Error deleting entity from Table Storage: {e}")

    async def close(self) -> None:
        """Close the Table Storage client."""
        if self.table_client:
            await self.table_client.close()
            logger.info("Table Storage client closed.")
        
        if self.standalone:
            credential_manager = get_credential_manager()
            await credential_manager.close()
            logger.info("Credential manager closed.")

    def _strip_metadata(self, entity: dict) -> dict:
        """Remove Azure Table Storage metadata fields."""
        return {k: v for k, v in entity.items() if k not in AZURE_TABLE_METADATA_FIELDS}

    async def __aenter__(self) -> "TableStorageService":
       """Enter the runtime context related to this object."""
       return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
       """Exit the runtime context related to this object."""
       await self.close()