from functools import reduce

from . import jc_logging as logging
from .job import JobABC
from .jobs.wrapping_job import WrappingJob

logger = logging.getLogger(__name__)

class Parallel:
    def __init__(self, *components):
        self.components = components
        self.obj = None  # No direct object for this composite

    def __or__(self, other):
        """Support chaining with | operator"""
        if not isinstance(other, (JobABC, Parallel, Serial)):
            other = WrappingJob(other)
        
        return Parallel(*list(self.components) + [other])
        
    def __rshift__(self, other):
        """Support chaining with >> operator"""
        if not isinstance(other, (JobABC, Parallel, Serial)):
            other = WrappingJob(other)
            
        return Serial(self, other)

    def __repr__(self):
        return f"parallel({', '.join(repr(c) for c in self.components)})"

class Serial:
    def __init__(self, *components):
        self.components = components
        self.obj = None  # No direct object for this composite
        
    def __or__(self, other):
        """Support chaining with | operator"""
        if not isinstance(other, (JobABC, Parallel, Serial)):
            other = WrappingJob(other)
            
        return Parallel(self, other)
        
    def __rshift__(self, other):
        """Support chaining with >> operator"""
        if not isinstance(other, (JobABC, Parallel, Serial)):
            other = WrappingJob(other)
            
        return Serial(*list(self.components) + [other])
        
    def __repr__(self):
        return f"serial({', '.join(repr(c) for c in self.components)})"


def wrap(obj=None, **kwargs):
    """
    Wrap any object to enable direct graph operations with | and >> operators.
    
    This function is the key to enabling the clean syntax:
    wrap(obj1) | wrap(obj2)  # For parallel composition
    wrap(obj1) >> wrap(obj2)  # For serial composition
    
    Enhanced functionality:
    1. Single object wrapping (original behavior):
       wrap(obj) - wraps the object as before
    
    2. Single named object wrapping:
       wrap(object_name=object) or wrap({"object_name": object})
       - For JobABC instances: sets the name property and returns the instance
       - For Serial/Parallel: returns the object unchanged
       - For other objects: creates a WrappingJob with the given name
    
    3. Multiple object wrapping:
       wrap(obj_a_name=obj_a, obj_b_name=obj_b) or wrap({"obj_a_name": obj_a, "obj_b_name": obj_b})
       - Returns a collection of wrapped objects following the rules in case 2
    """
    # Case 1: Only keyword arguments provided (no positional argument)
    if obj is None and kwargs:
        # Process keyword arguments
        result = {}
        for name, value in kwargs.items():
            if isinstance(value, JobABC):
                value.name = name
                result[name] = value
            elif isinstance(value, (Parallel, Serial)):
                result[name] = value
            else:
                result[name] = WrappingJob(value, name)
        
        # If only one item, return just that item
        if len(result) == 1:
            return next(iter(result.values()))
        return result
    
    # Case 2: Dictionary passed as the first argument
    if isinstance(obj, dict):
        result = {}
        for name, value in obj.items():
            if isinstance(value, JobABC):
                value.name = name
                result[name] = value
            elif isinstance(value, (Parallel, Serial)):
                result[name] = value
            else:
                result[name] = WrappingJob(value, name)
        
        # If only one item, return just that item
        if len(result) == 1:
            return next(iter(result.values()))
        return result
    
    # Case 3: Original behavior - single object
    # Handle the case where obj is None (could happen if called with wrap())
    if obj is None:
        raise ValueError("wrap() requires at least one argument")
        
    if isinstance(obj, (JobABC, Parallel, Serial)):
        return obj  # Already has the operations we need
    return WrappingJob(obj)

# Synonym for wrap
w = wrap

def parallel(*objects):
    """
    Create a parallel composition from multiple objects.
    
    This utility function takes objects (which can be a mix of JobABC
    instances and regular objects) and creates a parallel composition of all of them.
    
    Example:
        graph = parallel(obj1, obj2, obj3)  # Equivalent to wrap(obj1) | wrap(obj2) | wrap(obj3)
        
        # Also supports list argument for backward compatibility
        objects = [obj1, obj2, obj3]
        graph = parallel(objects)  # Still works if a single list is passed
    """
    # Handle case where a single list is passed (for backward compatibility)
    if len(objects) == 1 and isinstance(objects[0], list):
        objects = objects[0]
        
    if not objects:
        raise ValueError("Cannot create a parallel composition from empty arguments")
    if len(objects) == 1:
        return wrap(objects[0])
    return reduce(lambda acc, obj: acc | wrap(obj), objects[1:], wrap(objects[0]))

# Synonym for parallel
p = parallel

def serial(*objects):
    """
    Create a serial composition from multiple objects.
    
    This utility function takes objects (which can be a mix of JobABC
    instances and regular objects) and creates a serial composition of all of them.
    
    Example:
        graph = serial(obj1, obj2, obj3)  # Equivalent to wrap(obj1) >> wrap(obj2) >> wrap(obj3)
        
        # Also supports list argument for backward compatibility
        objects = [obj1, obj2, obj3]
        graph = serial(objects)  # Still works if a single list is passed
    """
    # Handle case where a single list is passed (for backward compatibility)
    if len(objects) == 1 and isinstance(objects[0], list):
        objects = objects[0]
        
    if not objects:
        raise ValueError("Cannot create a serial composition from empty arguments")
    if len(objects) == 1:
        return wrap(objects[0])
    return reduce(lambda acc, obj: acc >> wrap(obj), objects[1:], wrap(objects[0]))

# Synonym for serial
s = serial

# Graph evaluation utilities have been moved to tests/test_utils/graph_evaluation.py