from typing import Dict, List

from dsl_play import MockJobABC, Parallel, Serial, WrappingJob


def dsl_to_precedence_graph(dsl_obj) -> Dict[str, List[str]]:
    """
    Convert a DSL object into a precedence graph (adjacency list).
    
    Args:
        dsl_obj: A DSL object created with operators >> and |, or functions p() and s()
    
    Returns:
        Dict[str, List[str]]: A graph definition in the format:
        {
            'Task A': ['Task B', 'Task C'],
            'Task B': [],
            ...
        }
        Where keys are node string representations and values are lists of successor node representations.
    """
    # Print the DSL object structure details to help with debugging and understanding
    debug_dsl_structure(dsl_obj)
    
    # Extract all unique job objects from the DSL structure
    jobs = extract_jobs(dsl_obj)
    print(f"DEBUG: Extracted {len(jobs)} jobs from DSL")
    
    # Initialize the graph with empty adjacency lists using string representation of jobs
    graph = {str(job): [] for job in jobs}
    
    # Build connections based on DSL structure
    build_connections(dsl_obj, graph)
    
    return graph



def extract_jobs(dsl_obj):
    """
    Extract all individual job objects from a DSL structure.
    
    Args:
        dsl_obj: The DSL object to extract jobs from
        
    Returns:
        list: List of unique job objects
    """
    jobs = []
    
    def _extract(obj):
        if isinstance(obj, (Serial, Parallel)):
            # For compositional structures, extract jobs from each component
            for comp in obj.components:
                _extract(comp)
        elif isinstance(obj, MockJobABC):
            # Recursively extract jobs from wrapped compositional structures
            if isinstance(obj, WrappingJob) and isinstance(obj.wrapped_object, (Serial, Parallel)):
                _extract(obj.wrapped_object)
            # Terminal job object
            elif obj not in jobs:
                jobs.append(obj)
        else:
            # This is a primitive value that will be auto-wrapped
            wrapped = WrappingJob(obj)
            if wrapped not in jobs:
                jobs.append(wrapped)
    
    _extract(dsl_obj)
    return jobs



def build_connections(dsl_obj, graph):
    """
    Build the connections in the graph based on the DSL structure.
    
    Args:
        dsl_obj: The DSL object to analyze
        graph: The graph to build connections in where keys and values are string representations of jobs
    """
    def _process_serial(serial_obj, prev_terminals=None):
        if not serial_obj.components:
            return []
        
        # Start with the first component
        curr_terminals = []
        for i, comp in enumerate(serial_obj.components):
            # Process the current component
            if i == 0:
                # First component
                curr_terminals = _process_component(comp, prev_terminals)
            else:
                # Connect previous terminals to the current component
                curr_terminals = _process_component(comp, curr_terminals)
        
        return curr_terminals
    
    def _process_parallel(parallel_obj, prev_terminals=None):
        if not parallel_obj.components:
            return []
        
        all_terminals = []
        for comp in parallel_obj.components:
            # Process each component in parallel
            comp_terminals = _process_component(comp, prev_terminals)
            all_terminals.extend(comp_terminals)
        
        return all_terminals
    
    def _process_component(comp, prev_terminals=None):
        # Handle different types of components
        if isinstance(comp, Serial):
            return _process_serial(comp, prev_terminals)
        elif isinstance(comp, Parallel):
            return _process_parallel(comp, prev_terminals)
        elif isinstance(comp, WrappingJob):
            # Check if the wrapped object is a compositional structure
            wrapped = comp.wrapped_object
            if isinstance(wrapped, (Serial, Parallel)):
                return _process_component(wrapped, prev_terminals)
            else:
                # This is a terminal job object
                comp_str = str(comp)
                
                # Connect previous terminals to this component
                if prev_terminals:
                    for term in prev_terminals:
                        term_str = str(term)
                        if comp_str not in graph[term_str]:
                            graph[term_str].append(comp_str)
                
                return [comp]
        else:
            # This is a primitive value that will be auto-wrapped
            wrapped = WrappingJob(comp)
            comp_str = str(wrapped)
            
            # Connect previous terminals to this component
            if prev_terminals:
                for term in prev_terminals:
                    term_str = str(term)
                    if comp_str not in graph[term_str]:
                        graph[term_str].append(comp_str)
            
            return [wrapped]
    
    # Start processing from the top-level DSL object
    _process_component(dsl_obj)

def debug_dsl_structure(dsl_obj, indent=0):
    """
    Print the structure of a DSL object for debugging purposes.
    
    Args:
        dsl_obj: The DSL object to analyze
        indent: Current indentation level for nested printing
    """
    indent_str = "  " * indent
    
    if isinstance(dsl_obj, Serial):
        print(f"{indent_str}Serial with {len(dsl_obj.components)} components")
        for i, comp in enumerate(dsl_obj.components):
            print(f"{indent_str}Component {i}:")
            debug_dsl_structure(comp, indent + 1)
    
    elif isinstance(dsl_obj, Parallel):
        print(f"{indent_str}Parallel with {len(dsl_obj.components)} components")
        for i, comp in enumerate(dsl_obj.components):
            print(f"{indent_str}Component {i}:")
            debug_dsl_structure(comp, indent + 1)
    
    elif isinstance(dsl_obj, WrappingJob):
        print(f"{indent_str}WrappingJob wrapping: {dsl_obj.wrapped_object}")
    
    else:
        print(f"{indent_str}Other Type: {type(dsl_obj).__name__} - Value: {dsl_obj}")



def visualize_graph(graph: Dict[str, List[str]]):
    """
    Visualize the graph structure for debugging purposes.
    Displays parent nodes before their children for better readability.
    Ensures a node is only displayed after all of its parents have been processed.
    
    Args:
        graph: A graph definition in adjacency list format with string representations as keys
    """
    print("Graph Structure:")
    
    # Build a reverse graph (child -> parents) to track parent relationships
    reverse_graph = {}
    for node in graph:
        reverse_graph[node] = []
    
    # Find all parent-child relationships
    for parent, children in graph.items():
        for child in children:
            if child not in reverse_graph:
                reverse_graph[child] = []
            reverse_graph[child].append(parent)
    
    # Use Kahn's algorithm for topological sorting
    # Identify nodes with no parents (root nodes)
    root_nodes = []
    for node, parents in reverse_graph.items():
        if not parents and node in graph:  # Only include nodes that are in the original graph
            root_nodes.append(node)
    
    # Process nodes in order, ensuring a node is only processed after all its parents
    node_order = []
    while root_nodes:
        node = root_nodes.pop(0)  # Get a node with no unprocessed parents
        node_order.append(node)
        
        # Process this node's children
        for child in graph.get(node, []):
            # Remove this parent from the child's parent list
            reverse_graph[child].remove(node)
            # If the child has no more unprocessed parents, add it to the root nodes
            if not reverse_graph[child]:
                root_nodes.append(child)
    
    # Check for cycles or disconnected components
    remaining_nodes = [node for node in graph if node not in node_order]
    if remaining_nodes:
        # For disconnected components, process them separately
        for node in sorted(remaining_nodes):
            if node not in node_order:  # Skip if already added through processing
                node_order.append(node)
    
    # Print the graph in the calculated order
    for node in node_order:
        next_nodes = graph.get(node, [])
        if next_nodes:
            print(f"{node}: {next_nodes}")
        else:
            print(f"{node}: []")



if __name__ == "__main__":
   pass