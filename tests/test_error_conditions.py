"""
    Test resilience under error conditions:

        - Tests basic error handling and propagation
        - Tests timeout scenarios
        - Tests process termination handling
        - Tests invalid input handling
        - Tests resource cleanup
        - Tests result processing errors
        - Tests memory error handling
        - Tests unpicklable result scenarios
"""

import asyncio
import multiprocessing as mp
import signal
from unittest.mock import Mock, patch

import pytest

from job import AbstractJob
from job_chain import JobChain


class ErrorTestJob(AbstractJob):
    """Job implementation for testing error conditions"""
    def __init__(self):
        super().__init__(name="ErrorTestJob")
    
    async def run(self, task):
        if task.get('raise_error'):
            raise Exception(task.get('error_message', 'Simulated error'))
        if task.get('timeout'):
            await asyncio.sleep(float(task['timeout']))
            return {'task': task, 'status': 'timeout_completed'}
        if task.get('memory_error'):
            # Explicitly raise MemoryError instead of trying to create a large list
            raise MemoryError("Simulated memory error")
        if task.get('invalid_result'):
            # Return an unpicklable object
            return lambda x: x  # Functions can't be pickled
        return {'task': task, 'status': 'completed'}


def test_basic_error_handling():
    """Test handling of basic exceptions during task execution"""
    results = []
    errors = []
    
    def collect_result(result):
        if isinstance(result, Exception):
            errors.append(result)
        else:
            results.append(result)
    
    job_chain = JobChain(ErrorTestJob(), collect_result, serial_processing=True)
    
    # Submit mix of successful and failing tasks
    tasks = [
        {'task_id': 1},
        {'task_id': 2, 'raise_error': True, 'error_message': 'Task 2 error'},
        {'task_id': 3},
        {'task_id': 4, 'raise_error': True, 'error_message': 'Task 4 error'}
    ]
    
    for task in tasks:
        job_chain.submit_task(task)
    
    job_chain.mark_input_completed()
    
    # Verify successful tasks completed
    assert len(results) == 2
    assert all(r['status'] == 'completed' for r in results)
    
    # Verify errors were captured
    assert len(errors) == 0  # Errors should be logged, not passed to result processor

def test_timeout_handling():
    """Test handling of task timeouts"""
    results = []
    def collect_result(result):
        results.append(result)
    
    job_chain = JobChain(ErrorTestJob(), collect_result, serial_processing=True)
    
    # Submit tasks with varying timeouts
    tasks = [
        {'task_id': 1, 'timeout': 0.3},
        {'task_id': 2, 'timeout': 0.2},
        {'task_id': 3, 'timeout': 0.1}
    ]
    
    for task in tasks:
        job_chain.submit_task(task)
    
    job_chain.mark_input_completed()
    
    # Verify all tasks eventually completed
    assert len(results) == 3
    assert all(r['status'] == 'timeout_completed' for r in results)
    
    # Verify tasks completed in order of timeout
    task_ids = [r['task']['task_id'] for r in results]
    assert task_ids == [3, 2, 1]

def test_process_termination():
    """Test handling of process termination"""
    job_chain = JobChain(ErrorTestJob())
    
    # Submit a long-running task
    job_chain.submit_task({'task_id': 1, 'timeout': 1.0})
    
    # Force terminate the process
    job_chain.job_executor_process.terminate()
    
    # Verify cleanup handles terminated process
    job_chain._cleanup()
    assert not job_chain.job_executor_process.is_alive()

def test_invalid_input():
    """Test handling of invalid input data"""
    job_chain = JobChain(ErrorTestJob())
    
    # Test various invalid inputs
    invalid_inputs = [
        None,
        "",
        {},
        {'task_id': None},
        {'task_id': object()},  # Unpicklable object
        []
    ]
    
    for invalid_input in invalid_inputs:
        job_chain.submit_task(invalid_input)
    
    job_chain.mark_input_completed()
    # Should complete without raising exceptions

def test_resource_cleanup():
    """Test proper cleanup of resources"""
    job_chain = JobChain(ErrorTestJob())
    
    # Submit some tasks
    for i in range(5):
        job_chain.submit_task({'task_id': i})
    
    # Get queue references
    task_queue = job_chain._task_queue
    result_queue = job_chain._result_queue
    
    # Cleanup
    job_chain._cleanup()
    
    # Verify queues are closed
    assert task_queue._closed
    assert result_queue._closed
    
    # Verify processes are terminated
    assert not job_chain.job_executor_process.is_alive()
    if job_chain.result_processor_process:
        assert not job_chain.result_processor_process.is_alive()

def test_error_in_result_processing():
    """Test handling of errors in result processing function"""
    def failing_processor(result):
        raise Exception("Result processing error")
    
    job_chain = JobChain(ErrorTestJob(), failing_processor, serial_processing=True)
    
    # Submit tasks
    for i in range(3):
        job_chain.submit_task({'task_id': i})
    
    job_chain.mark_input_completed()
    # Should complete without hanging or crashing

def test_memory_error_handling():
    """Test handling of memory errors"""
    results = []
    def collect_result(result):
        results.append(result)
    
    job_chain = JobChain(ErrorTestJob(), collect_result, serial_processing=True)
    
    # Submit task that will cause memory error
    job_chain.submit_task({'task_id': 1, 'memory_error': True})
    
    job_chain.mark_input_completed()
    
    # Process should handle the memory error gracefully
    assert len(results) == 0  # No results should be processed

def test_unpicklable_result():
    """Test handling of unpicklable results"""
    results = []
    def collect_result(result):
        results.append(result)
    
    job_chain = JobChain(ErrorTestJob(), collect_result, serial_processing=True)
    
    # Submit task that returns unpicklable result
    job_chain.submit_task({'task_id': 1, 'invalid_result': True})
    
    job_chain.mark_input_completed()
    
    # Process should handle the pickling error gracefully
    assert len(results) == 0  # No results should be processed

if __name__ == '__main__':
    pytest.main(['-v', 'test_error_conditions.py'])
