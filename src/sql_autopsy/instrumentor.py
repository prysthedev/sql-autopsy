from sqlglot import exp
from typing import Dict, List, Tuple

class Instrumentor:
    """
    Takes extracted CTEs and their execution order, and generates statements
    to materialize them as temporary tables, and probe them.
    """
    def __init__(self, prefix: str = "autopsy_"):
        self.prefix = prefix

    def _get_temp_table_name(self, cte_name: str) -> str:
        return f"{self.prefix}{cte_name}"

    def get_materialization_statements(self, ctes: Dict[str, exp.Expression], order: List[str]) -> List[Tuple[str, str]]:
        """
        Returns a list of (cte_name, sql_statement) to create temp tables.
        For each CTE, it modifies the query to reference previously materialized temp tables instead of the original CTEs.
        """
        statements = []
        for cte_name in order:
            ast_node = ctes[cte_name].copy() # Work on a copy
            
            # Replace references to earlier CTEs with their temp table names
            for table in ast_node.find_all(exp.Table):
                ref_name = table.name
                if ref_name in ctes and ref_name != cte_name:
                    # It's a reference to another CTE, replace its name
                    table.set("this", exp.to_identifier(self._get_temp_table_name(ref_name)))

            temp_name = self._get_temp_table_name(cte_name)
            # Create a CREATE TEMP TABLE statement
            # Using sql() directly might lose some formatting, but it is valid SQL.
            sql = f"CREATE TEMP TABLE {temp_name} AS {ast_node.sql(dialect='postgres')}"
            statements.append((cte_name, sql))
            
        return statements

    def get_probe_statements(self, order: List[str]) -> List[Tuple[str, str]]:
        """
        Returns a list of (cte_name, sql_statement) to probe the row count of each temp table.
        """
        probes = []
        for cte_name in order:
            temp_name = self._get_temp_table_name(cte_name)
            sql = f"SELECT COUNT(*) as row_count FROM {temp_name}"
            probes.append((cte_name, sql))
        return probes
