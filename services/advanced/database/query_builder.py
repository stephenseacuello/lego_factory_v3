"""
Query Builder - Type-safe SQL Query Construction.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 6: Research Platform Infrastructure

Provides fluent API for building SQL queries safely.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Type of SQL query."""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    UPSERT = "UPSERT"


class JoinType(Enum):
    """Type of SQL join."""
    INNER = "INNER JOIN"
    LEFT = "LEFT JOIN"
    RIGHT = "RIGHT JOIN"
    FULL = "FULL OUTER JOIN"
    CROSS = "CROSS JOIN"


class OrderDirection(Enum):
    """Sort order direction."""
    ASC = "ASC"
    DESC = "DESC"


@dataclass
class Query:
    """A built SQL query."""
    sql: str
    params: Dict[str, Any]
    query_type: QueryType

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sql": self.sql,
            "params": self.params,
            "query_type": self.query_type.value,
        }


class QueryBuilder:
    """
    Fluent SQL query builder with parameterized queries.

    Features:
    - Type-safe query construction
    - Parameterized queries (SQL injection protection)
    - Fluent API
    - Support for complex joins
    - Subquery support
    """

    def __init__(self, table: str):
        self.table = table
        self._query_type: Optional[QueryType] = None
        self._columns: List[str] = []
        self._values: Dict[str, Any] = {}
        self._where: List[Tuple[str, str, Any]] = []
        self._joins: List[Tuple[JoinType, str, str]] = []
        self._order_by: List[Tuple[str, OrderDirection]] = []
        self._group_by: List[str] = []
        self._having: List[Tuple[str, str, Any]] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._distinct: bool = False
        self._param_counter = 0

    def _next_param(self) -> str:
        """Generate next parameter name."""
        self._param_counter += 1
        return f"p{self._param_counter}"

    def select(self, *columns: str) -> 'QueryBuilder':
        """Start a SELECT query."""
        self._query_type = QueryType.SELECT
        self._columns = list(columns) if columns else ["*"]
        return self

    def insert(self, **values: Any) -> 'QueryBuilder':
        """Start an INSERT query."""
        self._query_type = QueryType.INSERT
        self._values = values
        return self

    def update(self, **values: Any) -> 'QueryBuilder':
        """Start an UPDATE query."""
        self._query_type = QueryType.UPDATE
        self._values = values
        return self

    def delete(self) -> 'QueryBuilder':
        """Start a DELETE query."""
        self._query_type = QueryType.DELETE
        return self

    def upsert(self, conflict_columns: List[str], **values: Any) -> 'QueryBuilder':
        """Start an UPSERT (INSERT ON CONFLICT) query."""
        self._query_type = QueryType.UPSERT
        self._values = values
        self._conflict_columns = conflict_columns
        return self

    def distinct(self) -> 'QueryBuilder':
        """Add DISTINCT to SELECT."""
        self._distinct = True
        return self

    def where(self, column: str, operator: str, value: Any) -> 'QueryBuilder':
        """Add a WHERE condition."""
        self._where.append((column, operator, value))
        return self

    def where_eq(self, column: str, value: Any) -> 'QueryBuilder':
        """Add a WHERE column = value condition."""
        return self.where(column, "=", value)

    def where_in(self, column: str, values: List[Any]) -> 'QueryBuilder':
        """Add a WHERE column IN (...) condition."""
        return self.where(column, "IN", values)

    def where_between(self, column: str, low: Any, high: Any) -> 'QueryBuilder':
        """Add a WHERE column BETWEEN condition."""
        return self.where(column, "BETWEEN", (low, high))

    def where_null(self, column: str) -> 'QueryBuilder':
        """Add a WHERE column IS NULL condition."""
        return self.where(column, "IS", None)

    def where_not_null(self, column: str) -> 'QueryBuilder':
        """Add a WHERE column IS NOT NULL condition."""
        return self.where(column, "IS NOT", None)

    def where_like(self, column: str, pattern: str) -> 'QueryBuilder':
        """Add a WHERE column LIKE pattern condition."""
        return self.where(column, "LIKE", pattern)

    def join(
        self,
        table: str,
        condition: str,
        join_type: JoinType = JoinType.INNER,
    ) -> 'QueryBuilder':
        """Add a JOIN clause."""
        self._joins.append((join_type, table, condition))
        return self

    def left_join(self, table: str, condition: str) -> 'QueryBuilder':
        """Add a LEFT JOIN."""
        return self.join(table, condition, JoinType.LEFT)

    def right_join(self, table: str, condition: str) -> 'QueryBuilder':
        """Add a RIGHT JOIN."""
        return self.join(table, condition, JoinType.RIGHT)

    def order_by(
        self,
        column: str,
        direction: OrderDirection = OrderDirection.ASC,
    ) -> 'QueryBuilder':
        """Add ORDER BY clause."""
        self._order_by.append((column, direction))
        return self

    def group_by(self, *columns: str) -> 'QueryBuilder':
        """Add GROUP BY clause."""
        self._group_by.extend(columns)
        return self

    def having(self, column: str, operator: str, value: Any) -> 'QueryBuilder':
        """Add HAVING clause."""
        self._having.append((column, operator, value))
        return self

    def limit(self, count: int) -> 'QueryBuilder':
        """Add LIMIT clause."""
        self._limit = count
        return self

    def offset(self, count: int) -> 'QueryBuilder':
        """Add OFFSET clause."""
        self._offset = count
        return self

    def build(self) -> Query:
        """Build the final query."""
        if self._query_type == QueryType.SELECT:
            return self._build_select()
        elif self._query_type == QueryType.INSERT:
            return self._build_insert()
        elif self._query_type == QueryType.UPDATE:
            return self._build_update()
        elif self._query_type == QueryType.DELETE:
            return self._build_delete()
        elif self._query_type == QueryType.UPSERT:
            return self._build_upsert()
        else:
            raise ValueError("Query type not set")

    def _build_select(self) -> Query:
        """Build SELECT query."""
        params = {}
        parts = []

        # SELECT
        distinct = "DISTINCT " if self._distinct else ""
        columns = ", ".join(self._columns)
        parts.append(f"SELECT {distinct}{columns}")

        # FROM
        parts.append(f"FROM {self.table}")

        # JOINs
        for join_type, table, condition in self._joins:
            parts.append(f"{join_type.value} {table} ON {condition}")

        # WHERE
        if self._where:
            where_parts = []
            for column, operator, value in self._where:
                param = self._next_param()
                if operator == "IN" and isinstance(value, list):
                    placeholders = ", ".join([f":{param}_{i}" for i in range(len(value))])
                    where_parts.append(f"{column} IN ({placeholders})")
                    for i, v in enumerate(value):
                        params[f"{param}_{i}"] = v
                elif operator == "BETWEEN" and isinstance(value, tuple):
                    where_parts.append(f"{column} BETWEEN :{param}_low AND :{param}_high")
                    params[f"{param}_low"] = value[0]
                    params[f"{param}_high"] = value[1]
                elif value is None:
                    where_parts.append(f"{column} {operator} NULL")
                else:
                    where_parts.append(f"{column} {operator} :{param}")
                    params[param] = value
            parts.append("WHERE " + " AND ".join(where_parts))

        # GROUP BY
        if self._group_by:
            parts.append("GROUP BY " + ", ".join(self._group_by))

        # HAVING
        if self._having:
            having_parts = []
            for column, operator, value in self._having:
                param = self._next_param()
                having_parts.append(f"{column} {operator} :{param}")
                params[param] = value
            parts.append("HAVING " + " AND ".join(having_parts))

        # ORDER BY
        if self._order_by:
            order_parts = [f"{col} {dir.value}" for col, dir in self._order_by]
            parts.append("ORDER BY " + ", ".join(order_parts))

        # LIMIT
        if self._limit is not None:
            parts.append(f"LIMIT {self._limit}")

        # OFFSET
        if self._offset is not None:
            parts.append(f"OFFSET {self._offset}")

        sql = " ".join(parts)
        return Query(sql=sql, params=params, query_type=QueryType.SELECT)

    def _build_insert(self) -> Query:
        """Build INSERT query."""
        params = {}
        columns = list(self._values.keys())
        param_names = []

        for col in columns:
            param = self._next_param()
            param_names.append(f":{param}")
            params[param] = self._values[col]

        sql = (
            f"INSERT INTO {self.table} ({', '.join(columns)}) "
            f"VALUES ({', '.join(param_names)})"
        )

        return Query(sql=sql, params=params, query_type=QueryType.INSERT)

    def _build_update(self) -> Query:
        """Build UPDATE query."""
        params = {}
        set_parts = []

        for col, value in self._values.items():
            param = self._next_param()
            set_parts.append(f"{col} = :{param}")
            params[param] = value

        parts = [f"UPDATE {self.table} SET {', '.join(set_parts)}"]

        # WHERE
        if self._where:
            where_parts = []
            for column, operator, value in self._where:
                param = self._next_param()
                where_parts.append(f"{column} {operator} :{param}")
                params[param] = value
            parts.append("WHERE " + " AND ".join(where_parts))

        sql = " ".join(parts)
        return Query(sql=sql, params=params, query_type=QueryType.UPDATE)

    def _build_delete(self) -> Query:
        """Build DELETE query."""
        params = {}
        parts = [f"DELETE FROM {self.table}"]

        # WHERE
        if self._where:
            where_parts = []
            for column, operator, value in self._where:
                param = self._next_param()
                where_parts.append(f"{column} {operator} :{param}")
                params[param] = value
            parts.append("WHERE " + " AND ".join(where_parts))

        sql = " ".join(parts)
        return Query(sql=sql, params=params, query_type=QueryType.DELETE)

    def _build_upsert(self) -> Query:
        """Build UPSERT (INSERT ON CONFLICT) query."""
        params = {}
        columns = list(self._values.keys())
        param_names = []

        for col in columns:
            param = self._next_param()
            param_names.append(f":{param}")
            params[param] = self._values[col]

        # Build UPDATE SET for conflict
        update_cols = [c for c in columns if c not in self._conflict_columns]
        update_parts = []
        for col in update_cols:
            update_parts.append(f"{col} = EXCLUDED.{col}")

        conflict_cols = ", ".join(self._conflict_columns)

        sql = (
            f"INSERT INTO {self.table} ({', '.join(columns)}) "
            f"VALUES ({', '.join(param_names)}) "
            f"ON CONFLICT ({conflict_cols}) "
            f"DO UPDATE SET {', '.join(update_parts)}"
        )

        return Query(sql=sql, params=params, query_type=QueryType.UPSERT)


# Convenience function
def query(table: str) -> QueryBuilder:
    """Create a new query builder for a table."""
    return QueryBuilder(table)
