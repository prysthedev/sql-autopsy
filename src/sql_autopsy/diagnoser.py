from sqlglot import exp
from typing import Dict, List, Any
from sql_autopsy.executor import Executor
from sqlalchemy import text
import networkx as nx

class Diagnoser:
    """
    Analyzes the execution results to identify logical flaws like Fan-Outs, Black Holes, and Null-Outs.
    """
    def __init__(self, ctes: Dict[str, exp.Expression], order: List[str], graph: nx.DiGraph, results: Dict[str, int], executor: Executor, prefix: str = "autopsy_"):
        self.ctes = ctes
        self.order = order
        self.graph = graph
        self.results = results
        self.executor = executor
        self.prefix = prefix
        self.issues = []

    def diagnose(self) -> List[Dict[str, Any]]:
        for cte_name in self.order:
            ast_node = self.ctes[cte_name]
            self._check_drop(cte_name)
            self._check_fanout(cte_name, ast_node)
            self._check_nullout(cte_name, ast_node)
        return self.issues

    def _check_drop(self, cte_name: str):
        # Drop Detection
        preds = list(self.graph.predecessors(cte_name))
        ast = self.ctes[cte_name]
        
        if ast.args.get("where"):
            current_count = self.results.get(cte_name, 0)
            if current_count == 0:
                for pred in preds:
                    pred_count = self.results.get(pred, 0)
                    if pred_count > 0:
                        self.issues.append({
                            "type": "Fatal Drop",
                            "cte": cte_name,
                            "reason": f"WHERE clause removed 100% of incoming rows from '{pred}' ({pred_count} -> 0).",
                            "sql": ast.sql(dialect="postgres")
                        })
                        break

    def _check_fanout(self, cte_name: str, ast_node: exp.Expression):
        # Fan-Out Detection
        joins = ast_node.args.get("joins")
        if joins:
            from_table = ast_node.args.get("from")
            if not from_table:
                return
            
            left_table_node = from_table.this
            left_table_name = left_table_node.name if isinstance(left_table_node, exp.Table) else None
            
            output_count = self.results.get(cte_name, 0)
            
            for join in joins:
                right_table_node = join.this
                right_table_name = right_table_node.name if isinstance(right_table_node, exp.Table) else None
                
                left_count = self._get_table_count(left_table_name)
                right_count = self._get_table_count(right_table_name)
                
                if left_count is not None and right_count is not None:
                    if output_count > (left_count + right_count):
                        multiplier = round(output_count / max(1, left_count), 2)
                        self.issues.append({
                            "type": "Cartesian Explosion",
                            "cte": cte_name,
                            "reason": f"Output ({output_count}) > Left '{left_table_name}' ({left_count}) + Right '{right_table_name}' ({right_count}). Multiplier ~{multiplier}x.",
                            "sql": ast_node.sql(dialect="postgres")
                        })

    def _check_nullout(self, cte_name: str, ast_node: exp.Expression):
        # Null-Out Detection
        joins = ast_node.args.get("joins")
        if not joins:
            return
            
        for join in joins:
            if str(join.side).upper() == "LEFT":
                on_clause = join.args.get("on")
                if on_clause:
                    cols = list(on_clause.find_all(exp.Column))
                    temp_table = f"{self.prefix}{cte_name}"
                    
                    for col in cols:
                        col_name = col.name
                        sql = f"SELECT COUNT(*) FROM {temp_table} WHERE {col_name} IS NULL"
                        try:
                            with self.executor.engine.connect() as conn:
                                null_count = conn.execute(text(sql)).scalar()
                            
                            output_count = self.results.get(cte_name, 0)
                            if output_count > 0 and null_count == output_count:
                                self.issues.append({
                                    "type": "Join Key Mismatch",
                                    "cte": cte_name,
                                    "reason": f"LEFT JOIN resulted in 100% NULLs for column '{col_name}'.",
                                    "sql": ast_node.sql(dialect="postgres")
                                })
                                break # One column is enough to flag
                        except Exception:
                            pass # Column not in select list or other error

    def _get_table_count(self, table_name: str):
        if not table_name:
            return None
        if table_name in self.results:
            return self.results[table_name]
        try:
            with self.executor.engine.connect() as conn:
                return conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
        except Exception:
            return None
