import duckdb
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import os
import logging
load_dotenv()

logger = logging.getLogger(__name__)

class PerpPostgresClient:
    """
    DuckDB client with PostgreSQL attachment.
    Each instance manages its own connection.
    For thread-safety, create a fresh instance per operation/thread instead of sharing.
    """

    def __init__(
        self,
        host: str = os.getenv("DUCKDB_OHLCV_HOST"),
        port: int = os.getenv("DUCKDB_OHLCV_PORT"),
        database: str = os.getenv("DUCKDB_OHLCV_DATABASE"),
        username: str = os.getenv("DUCKDB_OHLCV_USERNAME"),
        password: str = os.getenv("DUCKDB_OHLCV_PASSWORD"),
        db_alias: str = "postgres_quant_db",
        time_range_days: Optional[int] = None
    ):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.db_alias = db_alias
        self.time_range_days = time_range_days
        self.connection = None
        self._filtered_views: Dict[str, str] = {}
        self._created_views: set = set()

    def connect(self) -> bool:
        if self.connection is not None:
            return True

        try:
            self.connection = duckdb.connect(database=':memory:', read_only=False)
            self.connection.execute("SET TimeZone='UTC';")
            self.connection.execute("INSTALL postgres;")
            self.connection.execute("LOAD postgres;")
            self.connection.execute("SET TimeZone='UTC';")

            attach_statement = f"""
            ATTACH 'dbname={self.database} user={self.username} host={self.host} port={self.port} password={self.password}'
            AS {self.db_alias} (TYPE postgres);
            """
            self.connection.execute(attach_statement)

            self.connection.execute(f"USE {self.db_alias}.public")
            logger.info(f"Set default schema to '{self.db_alias}.public'")

            if self.time_range_days:
                logger.info(f"DuckDB attached to PostgreSQL with time filter: last {self.time_range_days} days")
            else:
                logger.info(f"DuckDB attached to PostgreSQL database '{self.database}' at {self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to attach PostgreSQL database: {e}")
            return False

    def create_filtered_view(self, table_name: str, force: bool = False) -> str:
        if not self.time_range_days:
            return f'{self.db_alias}."{table_name}"'

        if not self.connection:
            self.ensure_connected()

        clean_table_name = table_name.replace('"', '').replace(f'{self.db_alias}.', '')
        view_name = f"filtered_{clean_table_name.replace('-', '_')}"

        if view_name in self._created_views and not force:
            return view_name

        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=self.time_range_days)
            cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:%M:%S")

            create_view_sql = f"""
            CREATE OR REPLACE TEMP VIEW {view_name} AS
            SELECT * FROM {self.db_alias}."{clean_table_name}"
            WHERE open_time >= TIMESTAMP '{cutoff_str}'
            """
            self.connection.execute(create_view_sql)

            self._created_views.add(view_name)
            logger.info(f"Created filtered view '{view_name}' for table {clean_table_name} (last {self.time_range_days} days)")
            return view_name

        except Exception as e:
            logger.error(f"Failed to create filtered view for {table_name}: {e}")
            return f'{self.db_alias}."{clean_table_name}"'

    def get_table_reference(self, table_name: str, apply_time_filter: bool = False) -> str:
        clean_name = table_name.replace('"', '').replace(f'{self.db_alias}.', '')

        if apply_time_filter and self.time_range_days:
            return self.create_filtered_view(clean_name)

        return f'{self.db_alias}."{clean_name}"'

    def ensure_connected(self) -> bool:
        if self.connection is None:
            return self.connect()

        try:
            self.connection.execute(f"SELECT 1 FROM {self.db_alias}.information_schema.tables LIMIT 1")
            return True
        except Exception as e:
            logger.warning(f"DuckDB PostgreSQL attachment is stale ({e}), reconnecting...")
            try:
                self.connection.close()
            except:
                pass
            self.connection = None
            self._filtered_views = {}
            self._created_views = set()
            return self.connect()

    def disconnect(self):
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
                self._filtered_views = {}
                self._created_views = set()
                logger.info("DuckDB connection closed")
            except Exception as e:
                logger.error(f"Error closing DuckDB connection: {e}")

    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        if not self.connection:
            raise Exception("Not connected to database")

        try:
            processed_query = query.replace('%s', '?') if '%s' in query else query

            if params:
                result = self.connection.execute(processed_query, params)
            else:
                result = self.connection.execute(processed_query)

            if result.description:
                columns = [desc[0] for desc in result.description]
                rows = result.fetchall()
                result_data = [dict(zip(columns, row)) for row in rows]
                logger.info(f"Query executed successfully, returned {len(result_data)} rows")
                return result_data
            else:
                logger.info("Query executed successfully (no rows returned)")
                return []

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        if not self.connection:
            raise Exception("Not connected to database")

        try:
            processed_query = query.replace('%s', '?') if '%s' in query else query

            if params:
                result = self.connection.execute(processed_query, params)
            else:
                result = self.connection.execute(processed_query)

            columns = [desc[0] for desc in result.description]
            row = result.fetchone()

            if row:
                return dict(zip(columns, row))
            return None

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        return self.execute_query(query, params)

    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        query = f"""
        SELECT column_name, data_type, is_nullable, column_default
        FROM {self.db_alias}.information_schema.columns
        WHERE table_name = ?
        ORDER BY ordinal_position
        """
        return self.fetch_all(query, (table_name,))

    def list_tables(self) -> List[str]:
        query = f"""
        SELECT table_name
        FROM {self.db_alias}.information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
        """
        result = self.fetch_all(query)
        return [row['table_name'] for row in result]


    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
