from sqlalchemy import create_engine, text
from typing import Dict, List, Tuple

class Executor:
    """
    Executes the generated SQL statements against a database.
    """
    def __init__(self, target: str = "duckdb:///:memory:"):
        self.engine = create_engine(target)

    def run_autopsy(self, materializations: List[Tuple[str, str]], probes: List[Tuple[str, str]], prefix: str = "autopsy_") -> Dict[str, int]:
        """
        Runs materialization and probing within a single connection so TEMP tables persist.
        Cleans up at the end.
        """
        results = {}
        with self.engine.connect() as conn:
            try:
                for cte_name, sql in materializations:
                    conn.execute(text(sql))
                    
                for cte_name, sql in probes:
                    result = conn.execute(text(sql)).scalar()
                    results[cte_name] = result
            finally:
                # Cleanup
                for cte_name, _ in materializations:
                    temp_name = f"{prefix}{cte_name}"
                    conn.execute(text(f"DROP TABLE IF EXISTS {temp_name}"))
                    
            conn.commit() # Important for some dialects
        return results

    def execute_setup(self, setup_sql: str):
        """Utility for setting up dummy data in testing"""
        with self.engine.connect() as conn:
            # DuckDB allows executing multiple statements separated by semicolon
            for statement in setup_sql.split(';'):
                if statement.strip():
                    conn.execute(text(statement.strip()))
            conn.commit()
