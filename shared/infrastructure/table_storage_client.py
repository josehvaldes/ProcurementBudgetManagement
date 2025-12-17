"""
Azure Table Storage client wrapper.
"""

import logging
from typing import Optional, Dict, Any, List
from azure.data.tables import TableServiceClient, TableClient
from azure.core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)


class TableStorageClient:
    """
    Wrapper for Azure Table Storage operations.
    Handles CRUD operations for invoices, vendors, and other entities.
    """
    
    def __init__(self, connection_string: str):
        """
        Initialize Table Storage client.
        
        Args:
            connection_string: Azure Storage connection string
        """
        self.connection_string = connection_string
        self.service_client = TableServiceClient.from_connection_string(connection_string)
    
    def get_table_client(self, table_name: str) -> TableClient:
        """
        Get a table client for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            TableClient instance
        """
        return self.service_client.get_table_client(table_name)
    
    def create_table_if_not_exists(self, table_name: str) -> None:
        """
        Create a table if it doesn't exist.
        
        Args:
            table_name: Name of the table to create
        """
        try:
            self.service_client.create_table_if_not_exists(table_name)
            logger.info(f"Table '{table_name}' ready")
        except Exception as e:
            logger.error(f"Failed to create table '{table_name}': {e}")
            raise
    
    def insert_entity(self, table_name: str, entity: Dict[str, Any]) -> None:
        """
        Insert an entity into a table.
        
        Args:
            table_name: Name of the table
            entity: Entity to insert (must have PartitionKey and RowKey)
        """
        table_client = self.get_table_client(table_name)
        try:
            table_client.create_entity(entity)
            logger.debug(f"Inserted entity into '{table_name}'")
        except Exception as e:
            logger.error(f"Failed to insert entity: {e}")
            raise
    
    def get_entity(
        self,
        table_name: str,
        partition_key: str,
        row_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get an entity from a table.
        
        Args:
            table_name: Name of the table
            partition_key: Partition key
            row_key: Row key
            
        Returns:
            Entity dictionary or None if not found
        """
        table_client = self.get_table_client(table_name)
        try:
            entity = table_client.get_entity(partition_key, row_key)
            return dict(entity)
        except ResourceNotFoundError:
            logger.debug(f"Entity not found: {partition_key}/{row_key}")
            return None
        except Exception as e:
            logger.error(f"Failed to get entity: {e}")
            raise
    
    def update_entity(
        self,
        table_name: str,
        entity: Dict[str, Any],
        mode: str = "merge"
    ) -> None:
        """
        Update an entity in a table.
        
        Args:
            table_name: Name of the table
            entity: Entity to update (must have PartitionKey and RowKey)
            mode: Update mode ('merge' or 'replace')
        """
        table_client = self.get_table_client(table_name)
        try:
            if mode == "merge":
                table_client.update_entity(entity, mode="merge")
            else:
                table_client.update_entity(entity, mode="replace")
            logger.debug(f"Updated entity in '{table_name}'")
        except Exception as e:
            logger.error(f"Failed to update entity: {e}")
            raise
    
    def query_entities(
        self,
        table_name: str,
        filter_query: Optional[str] = None,
        select: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Query entities from a table.
        
        Args:
            table_name: Name of the table
            filter_query: OData filter query
            select: List of properties to select
            
        Returns:
            List of entity dictionaries
        """
        table_client = self.get_table_client(table_name)
        try:
            entities = table_client.query_entities(
                query_filter=filter_query,
                select=select
            )
            return [dict(entity) for entity in entities]
        except Exception as e:
            logger.error(f"Failed to query entities: {e}")
            raise
    
    def delete_entity(
        self,
        table_name: str,
        partition_key: str,
        row_key: str
    ) -> None:
        """
        Delete an entity from a table.
        
        Args:
            table_name: Name of the table
            partition_key: Partition key
            row_key: Row key
        """
        table_client = self.get_table_client(table_name)
        try:
            table_client.delete_entity(partition_key, row_key)
            logger.debug(f"Deleted entity from '{table_name}'")
        except Exception as e:
            logger.error(f"Failed to delete entity: {e}")
            raise
