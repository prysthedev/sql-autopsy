import networkx as nx
from sqlglot import exp
from typing import Dict, List

class DependencyGrapher:
    """
    Builds a dependency graph from extracted CTEs and determines execution order.
    """
    def __init__(self):
        self.graph = nx.DiGraph()

    def build_graph(self, ctes: Dict[str, exp.Expression]) -> nx.DiGraph:
        """
        Builds a Directed Acyclic Graph (DAG) mapping CTE lineages.
        """
        # Add all CTEs as nodes
        for cte_name in ctes.keys():
            self.graph.add_node(cte_name)
            
        # Find dependencies
        for cte_name, ast_node in ctes.items():
            # Find all table references in the CTE query
            for table in ast_node.find_all(exp.Table):
                ref_name = table.name
                if ref_name in ctes:
                    # cte_name depends on ref_name
                    self.graph.add_edge(ref_name, cte_name)
                    
        return self.graph

    def get_execution_order(self) -> List[str]:
        """
        Returns a topological sort of the graph (execution order).
        """
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXUnfeasible:
            raise ValueError("Circular dependency detected in CTEs")
