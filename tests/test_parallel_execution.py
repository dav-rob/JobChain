import multiprocessing as mp
import asyncio
import time
from time import sleep
from utils.print_utils import printh
from job_chain import JobChain
from job import Job, JobFactory

class DelayedJob(Job):
    def __init__(self, name: str, prompt: str, model: str, time_delay: float):
        super().__init__(name, prompt, model)
        self.time_delay = time_delay

    async def execute(self, task) -> dict:
        print(f"Async DelayedJob for {task} with delay {self.time_delay}")
        await asyncio.sleep(self.time_delay)  # Use specified delay
        return {"task": task, "status": "complete"}

def create_delayed_job(params: dict) -> Job:
    time_delay = params.get('time_delay', 1.0)
    return DelayedJob("Test Job", "Test prompt", "test-model", time_delay)

# Store original load_from_file function
original_load_from_file = JobFactory._load_from_file

def setup_module(module):
    """Set up test environment"""
    JobFactory._load_from_file = create_delayed_job

def teardown_module(module):
    """Restore original implementation"""
    JobFactory._load_from_file = original_load_from_file

def dummy_result_processor(result):
    """Dummy function for processing results in tests"""
    print(f"Processing result: {result}")

async def run_job_chain(time_delay: float, use_direct_job: bool = False) -> float:
    """Run job chain with specified delay and return execution time"""
    start_time = time.perf_counter()
    
    if use_direct_job:
        # Create and pass Job instance directly
        job = DelayedJob("Test Job", "Test prompt", "test-model", time_delay)
        job_chain = JobChain(job, dummy_result_processor)
    else:
        # Use traditional dictionary initialization
        job_chain_context = {
            "job_context": {
                "type": "file",
                "params": {"time_delay": time_delay}
            }
        }
        job_chain = JobChain(job_chain_context, dummy_result_processor)

    # Feed 10 tasks with a delay between each to simulate data gathering
    for i in range(10):
        job_chain.submit_task(f"Task {i}")
        await asyncio.sleep(0.2)  # Simulate time taken to gather data
    # Indicate there is no more input data to process to initiate shutdown
    job_chain.mark_input_completed()

    execution_time = time.perf_counter() - start_time
    print(f"Execution time for delay {time_delay}s: {execution_time:.2f}s")
    return execution_time

def test_parallel_execution():
    # Test with 1 second delay
    time_1s = asyncio.run(run_job_chain(1.0))
    
    # Test with 2 second delay
    time_2s = asyncio.run(run_job_chain(2.0))
    
    # Calculate the ratio of execution times
    time_ratio = time_2s / time_1s
    print(f"\nTime with 1s delay: {time_1s:.2f}s")
    print(f"Time with 2s delay: {time_2s:.2f}s")
    print(f"Ratio: {time_ratio:.2f}x")
    
    assert time_1s <= 3.3, (
        f"Expected tasks to complete in ~3.3s (including data gathering + overhead), took {time_1s:.2f}s. "
        "This suggests tasks are running sequentially"
    )
    
    assert time_2s <= 4.3, (
        f"Expected tasks to complete in ~4.3s (including data gathering + overhead), took {time_2s:.2f}s. "
        "This suggests tasks are running sequentially"
    )
    
    assert time_ratio <= 1.5, (
        f"Expected time ratio <= 1.5, got {time_ratio:.2f}. "
        "This suggests tasks are running sequentially instead of in parallel"
    )

def test_direct_job_initialization():
    """Test that direct Job instance initialization works equivalently"""
    # Run with dictionary initialization
    time_dict = asyncio.run(run_job_chain(1.0, use_direct_job=False))
    
    # Run with direct Job instance
    time_direct = asyncio.run(run_job_chain(1.0, use_direct_job=True))
    
    # Calculate the ratio of execution times
    time_ratio = abs(time_direct - time_dict) / time_dict
    print(f"\nTime with dict initialization: {time_dict:.2f}s")
    print(f"Time with direct Job instance: {time_direct:.2f}s")
    print(f"Difference ratio: {time_ratio:.2f}")
    
    # The execution times should be very similar (within 10% of each other)
    assert time_ratio <= 0.1, (
        f"Expected similar execution times, but difference ratio was {time_ratio:.2f}. "
        "This suggests the two initialization methods are not equivalent"
    )

async def run_batch_job_chain() -> float:
    """Run job chain with batches of website analysis jobs"""
    start_time = time.perf_counter()
    
    job_chain_context = {
        "job_context": {
            "type": "file",
            "params": {"time_delay": 0.70}
        }
    }

    job_chain = JobChain(job_chain_context, dummy_result_processor)

    # Process 4 batches of 25 links each
    for batch in range(4):
        # Simulate scraping 25 links, 1 second per link
        for link in range(25):
            job_chain.submit_task(f"Batch{batch}_Link{link}")
            await asyncio.sleep(0.10)  # Simulate time to scrape each link
    # Indicate there is no more input data to process to initiate shutdown
    job_chain.mark_input_completed()

    execution_time = time.perf_counter() - start_time
    print(f"\nTotal execution time: {execution_time:.2f}s")
    return execution_time

def test_parallel_execution_in_batches():
    """Test parallel execution of website analysis in batches while scraping continues"""
    execution_time = asyncio.run(run_batch_job_chain())
    
    assert execution_time <= 11, (
        f"Expected execution to complete in ~10.7s, took {execution_time:.2f}s. "
        "This suggests analysis jobs are not running in parallel with scraping"
    )
    
    assert execution_time >= 9.5, (
        f"Execution completed too quickly in {execution_time:.2f}s. "
        "Expected ~10s for scraping all links"
    )

async def run_parallel_load_test(num_tasks: int) -> float:
    """Run a load test with specified number of parallel tasks"""
    start_time = time.perf_counter()
    
    job_chain_context = {
        "job_context": {
            "type": "file",
            "params": {"time_delay": 1.0}
        }
    }

    job_chain = JobChain(job_chain_context, dummy_result_processor)

    # Submit all tasks immediately
    for i in range(num_tasks):
        job_chain.submit_task(f"Task_{i}")
    # Indicate there is no more input data to process to initiate shutdown
    job_chain.mark_input_completed()

    execution_time = time.perf_counter() - start_time
    print(f"\nExecution time for {num_tasks} tasks: {execution_time:.2f}s")
    return execution_time

def test_maximum_parallel_execution():
    """Test the maximum theoretical parallel execution capacity"""
    
    # Test with increasing number of tasks
    task_counts = [100, 500, 2500, 10000]
    
    for count in task_counts:
        execution_time = asyncio.run(run_parallel_load_test(count))
        
        assert execution_time < 3.0, (
            f"Expected {count} tasks to complete in under 2 seconds with parallel execution, "
            f"took {execution_time:.2f}s"
        )
        
        tasks_per_second = count / execution_time
        print(f"Tasks per second with {count} tasks: {tasks_per_second:.2f}")

async def run_job_chain_without_result_processor() -> bool:
    """Run job chain without a result processing function"""
    try:
        job = DelayedJob("Test Job", "Test prompt", "test-model", 0.1)
        job_chain = JobChain(job)  # Pass no result_processing_function

        # Submit a few tasks
        for i in range(3):
            job_chain.submit_task(f"Task {i}")
        # Indicate there is no more input data to process to initiate shutdown
        job_chain.mark_input_completed()
        return True
    except Exception as e:
        print(f"Error occurred: {e}")
        return False

def test_no_result_processor():
    """Test that JobChain works without setting result_processing_function"""
    success = asyncio.run(run_job_chain_without_result_processor())
    assert success, "JobChain should execute successfully without result_processing_function"
