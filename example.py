import sys
import os

# Add the src directory to the python path so imports work correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from src.sql_autopsy.parser import Parser
from src.sql_autopsy.grapher import DependencyGrapher
from src.sql_autopsy.instrumentor import Instrumentor
from src.sql_autopsy.executor import Executor

def main():
    sql = """
    WITH first_cte AS (
        SELECT id, name FROM raw_users
    ),
    second_cte AS (
        SELECT id, name, 'active' as status 
        FROM first_cte
        WHERE name IS NOT NULL
    ),
    third_cte AS (
        SELECT s.id, s.name, o.order_date
        FROM second_cte s
        JOIN orders o ON s.id = o.user_id
        WHERE o.amount > 100
    )
    SELECT * FROM third_cte;
    """
    
    # 1. Setup Data for DuckDB
    executor = Executor(target="duckdb:///:memory:")
    setup_sql = """
    CREATE TABLE raw_users (id INT, name VARCHAR);
    INSERT INTO raw_users VALUES (1, 'Alice'), (2, 'Bob'), (3, NULL);
    CREATE TABLE orders (id INT, user_id INT, amount INT, order_date DATE);
    INSERT INTO orders VALUES (101, 1, 150, '2026-01-01'), (102, 1, 50, '2026-01-02'), (103, 2, 200, '2026-01-03');
    """
    executor.execute_setup(setup_sql)
    
    # 2. Parse CTEs
    print("Parsing SQL and extracting CTEs...")
    parser = Parser(dialect="postgres")
    ctes = parser.extract_ctes(sql)
    
    # 3. Graph Dependencies
    print("Mapping dependencies...")
    grapher = DependencyGrapher()
    grapher.build_graph(ctes)
    order = grapher.get_execution_order()
    
    # 4. Instrument (Materialization & Probes)
    print("Instrumenting SQL...")
    instrumentor = Instrumentor()
    materializations = instrumentor.get_materialization_statements(ctes, order)
    probes = instrumentor.get_probe_statements(order)
    
    # 5. Execute Autopsy
    print("Running Autopsy against DuckDB...")
    results = executor.run_autopsy(materializations, probes)
    
    print("\n[Diagnosis Results]")
    for cte_name, count in results.items():
        print(f"CTE '{cte_name}' row count: {count}")

if __name__ == "__main__":
    main()
