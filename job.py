import asyncio
from abc import ABC, ABCMeta, abstractmethod
from typing import Any, Dict, Set, Type, Union, Optional
import uuid

import jc_logging as logging
from utils.otel_wrapper import trace_function


def _is_traced(method):
    """Helper function to check if a method is traced."""
    return hasattr(method, '_is_traced') and method._is_traced


def _has_own_traced_execute(cls):
    """Helper function to check if a class has its own traced _execute (not inherited)."""
    return '_execute' in cls.__dict__ and _is_traced(cls.__dict__['_execute'])


def _mark_traced(method):
    """Helper function to mark a method as traced."""
    method._is_traced = True
    return method


def traced_job(cls: Type) -> Type:
    """
    Class decorator that ensures the execute method is traced.
    This is only applied to the JobABC class itself.
    """
    if hasattr(cls, '_execute'):
        original_execute = cls._execute
        traced_execute = trace_function(original_execute, detailed_trace=True)
        traced_execute = _mark_traced(traced_execute)
        # Store original as executeNoTrace
        cls.executeNoTrace = original_execute
        # Replace execute with traced version
        cls._execute = traced_execute
    return cls


class JobMeta(ABCMeta):
    """Metaclass that automatically applies the traced_job decorator to JobABC only."""
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if name == 'JobABC':  # Only decorate the JobABC class itself
            return traced_job(cls)
        # For subclasses, ensure they inherit JobABC's traced _execute
        if '_execute' in namespace:
            # If subclass defines its own _execute, ensure it's not traced again
            # but still inherits the tracing from JobABC
            del namespace['_execute']
            cls = super().__new__(mcs, name, bases, namespace)
        return cls


class Task(dict):
    """A task dictionary with a unique identifier."""
    def __init__(self, data: Union[Dict[str, Any], str], job_name: Optional[str] = None):
        # Convert string input to dict
        if isinstance(data, str):
            data = {'task': data}
        elif isinstance(data, dict):
            data = data.copy()  # Create a copy to avoid modifying the original
        else:
            data = {'task': str(data)}
        
        super().__init__(data)
        self.jobchain_unique_id = str(uuid.uuid4())
        if job_name is not None:
            self['job_name'] = job_name

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Task):
            return NotImplemented
        return self.jobchain_unique_id == other.jobchain_unique_id

    def __hash__(self) -> int:
        return hash(self.jobchain_unique_id)


class JobABC(ABC, metaclass=JobMeta):
    """
    Abstract base class for jobs. Only this class will have tracing enabled through the JobMeta metaclass.
    Subclasses will inherit the traced version of _execute but won't add additional tracing.
    """

    # class variable to keep track of instance counts for each class
    _instance_counts = {}

    # type hints
    name: str  # this should be a unique name in the JobChain server / cluster
    description: str
    finished: bool
    input_needed_jobs: Set['JobABC']
    jobs_dependent_on: Set['JobABC']
    job_output: Dict[str, Any]
    input_to_process: Dict[str, Any]

    def __init__(self, name: str):
        """
        Initialize an JobABC instance.

        Args:
            name (str): A unique identifier for this job within the context of a JobChain.
                       The name must be unique among all jobs in the same JobChain to ensure
                       proper job identification and dependency resolution.

        Note:
            The uniqueness of the name is crucial for proper JobChain operation. Using
            duplicate names within the same JobChain can lead to unexpected behavior
            in job execution and dependency management.
        """
        self.name = name
        self.description = ""  # blank by default
        self.finished = True  # True by default
        self.job_output = {}  # initialized empty
        self.input_to_process = {}  # initialized empty
        self.logger = logging.getLogger(self.__class__.__name__)

    @classmethod
    def getUniqueName(cls):
        # Increment the counter for the current class
        cls._instance_counts[cls] = cls._instance_counts.get(cls, 0) + 1
        # Return a unique name based on the current class
        return f"{cls.__name__}_{cls._instance_counts[cls]}"

    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name}>"

    def add_input_needed_jobs(self, jobs: Union['JobABC', Set['JobABC']]) -> None:
        """Add job(s) as input dependencies."""
        if not hasattr(self, 'input_needed_jobs'):
            self.input_needed_jobs = set()
        if isinstance(jobs, JobABC):
            self.input_needed_jobs.add(jobs)
        else:
            self.input_needed_jobs.update(jobs)

    def add_dependent_jobs(self, jobs: Union['JobABC', Set['JobABC']]) -> None:
        """Add job(s) that depend on this job."""
        if not hasattr(self, 'jobs_dependent_on'):
            self.jobs_dependent_on = set()
        if isinstance(jobs, JobABC):
            self.jobs_dependent_on.add(jobs)
        else:
            self.jobs_dependent_on.update(jobs)

    async def _execute(self, task: Task) -> Dict[str, Any]:
        """
        This method is called by JobChain to start-off the Jobs, and is 
        responsible for the control flow of starting Jobs when dependencies are
        met and for Jobs handing-off to other Jobs.
        This method will be traced only in the JobABC class through the JobMeta metaclass.
        """
        if not self.has_all_dependencies():
            self.logger.info(f"Dependencies not met for {self.name}, skipping execution")
            return {}

        result = await self.run(task)

        if self.has_finished():
            self.do_finishing_actions()
        else:
            self.do_intermediate_actions()

        return result

    @abstractmethod
    async def run(self, task: Task) -> Dict[str, Any]:
        """Execute the job on the given task. Must be implemented by subclasses."""
        pass

    def has_all_dependencies(self) -> bool:
        """
        Check if all dependencies are satisfied.
        Returns False by default as specified.
        """
        return True

    def has_finished(self) -> bool:
        """
        Check if the job has finished execution.
        Returns True by default as specified.
        """
        return True

    def do_finishing_actions(self) -> None:
        """
        Perform actions when job has finished successfully.
        Stub implementation.
        """
        self.logger.info(f"Performing finishing actions for {self.name}")

    def do_intermediate_actions(self) -> None:
        """
        Perform actions when job has not finished.
        Stub implementation.
        """
        self.logger.info(f"Performing intermediate actions for {self.name}")


class SimpleJob(JobABC):
    """A Job implementation that provides a simple default behavior."""
    
    async def run(self, task: Task) -> Dict[str, Any]:
        """Run a simple job that logs and returns the task."""
        self.logger.info(f"Async JOB for {task}")
        await asyncio.sleep(1)  # Simulate network delay
        return {"task": task._data, "status": "complete"}


class JobFactory:
    """Factory class for creating Job instances with proper tracing."""
    
    @staticmethod
    def _load_from_file(params: Dict[str, Any]) -> JobABC:
        """Create a traced job instance from file configuration."""
        logger = logging.getLogger('JobFactory')
        logger.info(f"Loading job with params: {params}")
        return SimpleJob("File Job")

    @staticmethod
    def _load_from_datastore(params: Dict[str, Any]) -> JobABC:
        """Create a traced job instance from datastore."""
        logger = logging.getLogger('JobFactory')
        logger.info(f"Loading job from datastore with params: {params}")
        return SimpleJob("Datastore Job")

    @staticmethod
    def load_job(job_context: Dict[str, Any]) -> JobABC:
        """Load a job instance with proper tracing based on context."""
        load_type = job_context.get("type", "").lower()
        params = job_context.get("params", {})

        if load_type == "file":
            return JobFactory._load_from_file(params)
        elif load_type == "datastore":
            return JobFactory._load_from_datastore(params)
        else:
            raise ValueError(f"Unsupported job type: {load_type}")
