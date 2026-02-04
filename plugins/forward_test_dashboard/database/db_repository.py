"""
Database repository for Forward Test Dashboard.
Provides query methods for forward_test_trade_history and forward_test_performance tables.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from .perp_postgres_client import PerpPostgresClient

logger = logging.getLogger(__name__)


class ForwardTestRepository:
    """
    Repository for querying forward test data from PostgreSQL.
    Uses PerpPostgresClient for database connectivity.
    """

    def __init__(self, client: Optional[PerpPostgresClient] = None):
        """
        Initialize repository with an optional client.
        If no client provided, creates a new one.
        """
        self.client = client or PerpPostgresClient()
        self._connected = False

    def _ensure_connected(self) -> bool:
        """Ensure database connection is established."""
        if not self._connected:
            self._connected = self.client.ensure_connected()
        return self._connected

    def get_trade_history(
        self,
        model_names: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Query forward_test_trade_history table for signal data.
        
        Args:
            model_names: Optional list of model names to filter by
            start_time: Optional start time filter
            end_time: Optional end time filter
            limit: Maximum number of records to return
            
        Returns:
            List of trade history records with columns:
            - model_name, base_asset, pred_time, original_mu, new_mu,
            - score, gated_flag, sigma_norm, breakout/breakdown flags
        """
        if not self._ensure_connected():
            logger.error("Failed to connect to database")
            return []

        try:
            # Build query with optional filters
            conditions = []
            params = []

            if model_names:
                placeholders = ", ".join(["?" for _ in model_names])
                conditions.append(f"model_name IN ({placeholders})")
                params.extend(model_names)

            if start_time:
                conditions.append("pred_time >= ?")
                params.append(start_time.strftime("%Y-%m-%d %H:%M:%S"))

            if end_time:
                conditions.append("pred_time <= ?")
                params.append(end_time.strftime("%Y-%m-%d %H:%M:%S"))

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            query = f"""
            SELECT 
                model_name,
                base_asset,
                pred_time,
                original_mu,
                new_mu,
                score,
                gated_flag,
                sigma_norm,
                breakout_up_p1,
                breakdown_dn_p1,
                breakout_up_p2,
                breakdown_dn_p2,
                confirm_up_p2,
                confirm_dn_p2
            FROM forward_test_trade_history
            WHERE {where_clause}
            ORDER BY pred_time DESC
            LIMIT {limit}
            """

            result = self.client.fetch_all(query, tuple(params) if params else None)
            logger.info(f"Retrieved {len(result)} trade history records")
            return result

        except Exception as e:
            logger.error(f"Error querying trade history: {e}")
            return []

    def get_performance_snapshots(
        self,
        identities: Optional[List[str]] = None,
        pred_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query forward_test_performance table for performance snapshots.
        
        If pred_time is provided, returns the snapshot closest to that time.
        Otherwise returns latest records.
        
        Args:
            identities: Optional list of identities to filter by
            pred_time: Optional specific time to get snapshot for
            
        Returns:
            List of performance records
        """
        if not self._ensure_connected():
            logger.error("Failed to connect to database")
            return []

        try:
            conditions = []
            params = []

            if identities:
                placeholders = ", ".join(["?" for _ in identities])
                conditions.append(f"identity IN ({placeholders})")
                params.extend(identities)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            if pred_time:
                # Get snapshot closest to pred_time
                pred_time_str = pred_time.strftime("%Y-%m-%d %H:%M:%S")
                query = f"""
                SELECT DISTINCT ON (identity)
                    model_id,
                    identity,
                    model_name,
                    total_running_time,
                    status,
                    total_positions,
                    total_pnl,
                    pnl_delta_1h,
                    pnl_delta_4h,
                    pnl_delta_1d,
                    winrate,
                    max_drawdown,
                    last_position,
                    started_at,
                    updated_at
                FROM forward_test_performance
                WHERE {where_clause}
                  AND updated_at <= ?
                ORDER BY identity, updated_at DESC
                """
                params.append(pred_time_str)
            else:
                # Get latest records
                query = f"""
                SELECT DISTINCT ON (identity)
                    model_id,
                    identity,
                    model_name,
                    total_running_time,
                    status,
                    total_positions,
                    total_pnl,
                    pnl_delta_1h,
                    pnl_delta_4h,
                    pnl_delta_1d,
                    winrate,
                    max_drawdown,
                    last_position,
                    started_at,
                    updated_at
                FROM forward_test_performance
                WHERE {where_clause}
                ORDER BY identity, updated_at DESC
                """

            result = self.client.fetch_all(query, tuple(params) if params else None)
            logger.info(f"Retrieved {len(result)} performance snapshots")
            return result

        except Exception as e:
            logger.error(f"Error querying performance snapshots: {e}")
            return []

    def get_latest_performance(
        self,
        identities: Optional[List[str]] = None,
        status_filter: Optional[str] = "running",
    ) -> List[Dict[str, Any]]:
        """
        Get latest performance records for each identity.
        
        Args:
            identities: Optional list of identities to filter
            status_filter: Optional status filter (e.g., 'running')
            
        Returns:
            List of latest performance records
        """
        if not self._ensure_connected():
            logger.error("Failed to connect to database")
            return []

        try:
            conditions = []
            params = []

            if identities:
                placeholders = ", ".join(["?" for _ in identities])
                conditions.append(f"identity IN ({placeholders})")
                params.extend(identities)

            if status_filter:
                conditions.append("status = ?")
                params.append(status_filter)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            query = f"""
            SELECT DISTINCT ON (identity)
                model_id,
                identity,
                model_name,
                total_running_time,
                status,
                total_positions,
                total_pnl,
                pnl_delta_1h,
                pnl_delta_4h,
                pnl_delta_1d,
                winrate,
                max_drawdown,
                last_position,
                started_at,
                updated_at
            FROM forward_test_performance
            WHERE {where_clause}
            ORDER BY identity, updated_at DESC
            """

            result = self.client.fetch_all(query, tuple(params) if params else None)
            logger.info(f"Retrieved {len(result)} latest performance records")
            return sorted(result, key=lambda x: x.get("started_at") or "")

        except Exception as e:
            logger.error(f"Error querying latest performance: {e}")
            return []

    def get_performance_at_time(
        self,
        pred_time: datetime,
        model_names: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get performance snapshot at a specific prediction time.
        This allows viewing historical performance state at each timeframe.
        
        Args:
            pred_time: The prediction time to get performance snapshot for
            model_names: Optional list of model names to filter
            
        Returns:
            List of performance records at that time
        """
        if not self._ensure_connected():
            logger.error("Failed to connect to database")
            return []

        try:
            conditions = []
            params = []
            
            pred_time_str = pred_time.strftime("%Y-%m-%d %H:%M:%S")

            if model_names:
                placeholders = ", ".join(["?" for _ in model_names])
                conditions.append(f"model_name IN ({placeholders})")
                params.extend(model_names)

            # Find records with updated_at closest to but <= pred_time
            where_clause = " AND ".join(conditions) if conditions else "1=1"

            query = f"""
            SELECT DISTINCT ON (identity)
                model_id,
                identity,
                model_name,
                total_running_time,
                status,
                total_positions,
                total_pnl,
                pnl_delta_1h,
                pnl_delta_4h,
                pnl_delta_1d,
                winrate,
                max_drawdown,
                last_position,
                started_at,
                updated_at
            FROM forward_test_performance
            WHERE {where_clause}
              AND updated_at <= ?
            ORDER BY identity, updated_at DESC
            """
            params.append(pred_time_str)

            result = self.client.fetch_all(query, tuple(params) if params else None)
            logger.info(f"Retrieved {len(result)} performance records at {pred_time_str}")
            return result

        except Exception as e:
            logger.error(f"Error querying performance at time: {e}")
            return []

    def get_price_deltas(
        self,
        start_time: datetime,
        end_time: datetime,
        assets: List[str]
    ) -> Dict[tuple, float]:
        """
        Get price deltas from ohlcv_binance-futures_1h table.
        Returns a dictionary mapping (open_time, base_asset) -> percentage change.
        Change is calculated as (close - open) / open.
        
        Args:
            start_time: Start time for query
            end_time: End time for query
            assets: List of base assets to fetch
            
        Returns:
            Dict[(open_time, base_asset), delta_float]
        """
        if not self._ensure_connected() or not assets:
            return {}

        try:
            placeholders = ", ".join(["?" for _ in assets])
            start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
            end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Note: We use open_time as the reference time to match pred_time
            query = f"""
            SELECT 
                open_time,
                base_asset,
                (close-open)/open as delta
            FROM "ohlcv_binance-futures_1h"
            WHERE base_asset IN ({placeholders})
              AND open_time >= ?
              AND open_time <= ?
            """
            
            params = list(assets) + [start_str, end_str]
            result = self.client.fetch_all(query, tuple(params))
            
            # Build map: (open_time, base_asset) -> delta
            price_map = {}
            for row in result:
                # Ensure time is naive or UTC consistent
                t = row["open_time"]
                if hasattr(t, "tzinfo") and t.tzinfo:
                     t = t.replace(tzinfo=None) # Make naive for comparison
                
                price_map[(t, row["base_asset"])] = row["delta"]
                
            return price_map
            
        except Exception as e:
            logger.error(f"Error fetching price deltas: {e}")
            return {}

    def get_performance_history(
        self,
        identity: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all performance records for a specific identity within a time range.
        Used for building equity curves from historical snapshots.
        
        Args:
            identity: The identity to query
            start_time: Optional start time
            end_time: Optional end time
            
        Returns:
            List of performance records ordered by time
        """
        if not self._ensure_connected():
            logger.error("Failed to connect to database")
            return []

        try:
            conditions = ["identity = ?"]
            params = [identity]

            if start_time:
                conditions.append("updated_at >= ?")
                params.append(start_time.strftime("%Y-%m-%d %H:%M:%S"))

            if end_time:
                conditions.append("updated_at <= ?")
                params.append(end_time.strftime("%Y-%m-%d %H:%M:%S"))

            where_clause = " AND ".join(conditions)

            query = f"""
            SELECT
                model_id,
                identity,
                model_name,
                total_running_time,
                status,
                total_positions,
                total_pnl,
                pnl_delta_1h,
                pnl_delta_4h,
                pnl_delta_1d,
                winrate,
                max_drawdown,
                last_position,
                started_at,
                updated_at
            FROM forward_test_performance
            WHERE {where_clause}
            ORDER BY updated_at ASC
            """

            result = self.client.fetch_all(query, tuple(params))
            logger.info(f"Retrieved {len(result)} historical records for {identity}")
            return result

        except Exception as e:
            logger.error(f"Error querying performance history: {e}")
            return []

    def close(self):
        """Close the database connection."""
        if self.client:
            self.client.disconnect()
            self._connected = False

    def __enter__(self):
        self._ensure_connected()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
