import sqlglot
from sqlglot import exp
from typing import Dict, Any

class Parser:
    """
    Parses a SQL string and extracts all Common Table Expressions (CTEs).
    """
    def __init__(self, dialect: str = "postgres"):
        self.dialect = dialect

    def extract_ctes(self, sql: str) -> tuple[str, Dict[str, exp.Expression]]:
        """
        Parses the SQL and returns a tuple containing:
        1. Setup SQL (string of all statements before the CTE query)
        2. A dictionary mapping CTE names to their AST nodes.
        """
        statements = sqlglot.parse(sql, read=self.dialect)
        ctes = {}
        setup_statements = []
        
        for statement in statements:
            if not statement: continue
            
            if hasattr(statement, 'ctes') and statement.ctes:
                for cte in statement.ctes:
                    cte_name = cte.alias
                    cte_query = cte.this
                    ctes[cte_name] = cte_query
                break # We only care about the first query with CTEs
            else:
                setup_statements.append(statement.sql(dialect=self.dialect))
                
        setup_sql = ";\n".join(setup_statements)
        if setup_sql:
            setup_sql += ";"
            
        return setup_sql, ctes
