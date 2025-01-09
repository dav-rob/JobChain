import asyncio
import os

import pytest
import yaml

import jobchain.jc_logging as logging
from jobchain.jc_graph import validate_graph
from jobchain.job import Task
from jobchain.job_chain import JobChain  # Import JobChain
from jobchain.job_loader import ConfigLoader, JobFactory
from jobchain.jobs.llm_jobs import OpenAIJob

# Test configuration
TEST_CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_jc_config"))

@pytest.fixture
def job_factory():
    factory = JobFactory()
    # Load both the test jobs and the real jobs
    #  the real jobs are always loaded by the factory
    factory.load_jobs_into_registry([TEST_CONFIG_DIR])
    return factory

def test_job_type_registration(job_factory):
    """Test that all expected job types are registered"""
    # Get all registered job types
    job_types = job_factory._job_types
    
    # Expected job types from test directory
    assert "MockJob" in job_types, "MockJob should be registered"
    assert "MockFileReadJob" in job_types, "MockFileReadJob should be registered"
    assert "MockDatabaseWriteJob" in job_types, "MockDatabaseWriteJob should be registered"
    assert "DummyJob" in job_types, "DummyJob should be registered"
    
    # Expected job type from real jobs directory
    assert "OpenAIJob" in job_types, "OpenAIJob should be registered"

@pytest.mark.asyncio
async def test_job_instantiation_and_execution(job_factory):
    """Test that jobs can be instantiated and run"""
    # Create a mock job instance
    mock_job = job_factory.create_job(
        name="test_mock_job",
        job_type="MockJob",
        job_def={"properties": {"test_param": "test_value"}}
    )
    
    # Verify job creation
    assert mock_job is not None
    assert mock_job.name == "test_mock_job"
    
    # Run the job with required inputs
    result = await mock_job.run(inputs={"test_input": "test_value"})
    assert result is not None
    assert mock_job.name in result

@pytest.mark.asyncio
async def test_openai_job_instantiation_and_execution(job_factory):
    """Test that OpenAIJob can be instantiated and run"""
    # Get the OpenAIJob class from the registry
    assert "OpenAIJob" in job_factory._job_types, "OpenAIJob should be registered"
    OpenAIJobClass = job_factory._job_types["OpenAIJob"]
    
    openai_job = job_factory.create_job(
        name="test_openai_job",
        job_type="OpenAIJob",
        job_def={
            "properties": {
                "api": {
                    "model": "gpt-4",
                    "temperature": 0.7
                },
                "rate_limit": {
                    "max_rate": 1,
                    "time_period": 4
                }
            }
        }
    )
    
    assert openai_job is not None
    assert openai_job.name == "test_openai_job"
    assert isinstance(openai_job, OpenAIJobClass), "Job should be an instance of OpenAIJob"
    
    # Run the job
    result = await openai_job.run({})
    assert result is not None
    assert "response" in result
    assert isinstance(result["response"], str)
    assert len(result["response"]) > 0

def test_config_loader_separate():
    """Test loading configurations from separate files"""
    # Get absolute paths
    test_config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_jc_config"))
    logging.info(f"\nTest config dir: {test_config_dir}")
    logging.info(f"Directory exists: {os.path.exists(test_config_dir)}")
    logging.info(f"Directory contents: {os.listdir(test_config_dir)}")
    
    # Reset ConfigLoader state and set directories
    ConfigLoader._cached_configs = None  # Reset cached configs
    ConfigLoader._set_directories([str(test_config_dir)])  # Convert to string for anyconfig
    logging.info(f"ConfigLoader directories: {ConfigLoader.directories}")
    
    # Test graphs config
    graphs_config = ConfigLoader.get_graphs_config()
    logging.info(f"Graphs config: {graphs_config}")
    assert graphs_config is not None
    with open(os.path.join(test_config_dir, "graphs.yaml"), 'r') as f:
        expected_graphs = yaml.safe_load(f)
    logging.info(f"Expected graphs: {expected_graphs}")
    assert graphs_config == expected_graphs
    
    # Test jobs config
    jobs_config = ConfigLoader.get_jobs_config()
    assert jobs_config is not None
    with open(os.path.join(test_config_dir, "jobs.yaml"), 'r') as f:
        expected_jobs = yaml.safe_load(f)
    assert jobs_config == expected_jobs
    
    # Test parameters config
    params_config = ConfigLoader.get_parameters_config()
    assert params_config is not None
    with open(os.path.join(test_config_dir, "parameters.yaml"), 'r') as f:
        expected_params = yaml.safe_load(f)
    assert params_config == expected_params
    
    # Validate each graph separately
    for graph_name, graph in graphs_config.items():
        validate_graph(graph, graph_name)

def test_config_loader_all():
    """Test loading configurations from a single combined file"""
    # Get absolute paths
    test_config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_jc_config_all"))
    logging.info(f"\nTest config dir: {test_config_dir}")
    logging.info(f"Directory exists: {os.path.exists(test_config_dir)}")
    logging.info(f"Directory contents: {os.listdir(test_config_dir)}")
    
    # Reset ConfigLoader state and set directories
    ConfigLoader._cached_configs = None  # Reset cached configs
    ConfigLoader._set_directories([str(test_config_dir)])  # Convert to string for anyconfig
    logging.info(f"ConfigLoader directories: {ConfigLoader.directories}")
    
    # Load the combined config file for comparison
    with open(os.path.join(test_config_dir, "jobchain_all.yaml"), 'r') as f:
        all_config = yaml.safe_load(f)
    logging.info(f"All config: {all_config}")
    
    # Test graphs config
    graphs_config = ConfigLoader.get_graphs_config()
    logging.info(f"Graphs config: {graphs_config}")
    assert graphs_config is not None
    assert graphs_config == all_config.get('graphs', {})
    
    # Test jobs config
    jobs_config = ConfigLoader.get_jobs_config()
    logging.info(f"Jobs config: {jobs_config}")
    assert jobs_config is not None
    assert jobs_config == all_config.get('jobs', {})
    
    # Test parameters config
    params_config = ConfigLoader.get_parameters_config()
    logging.info(f"Parameters config: {params_config}")
    assert params_config is not None
    assert params_config == all_config.get('parameters', {})
    
    # Validate each graph separately
    for graph_name, graph in graphs_config.items():
        validate_graph(graph, graph_name)

def test_create_head_jobs_from_config(job_factory):
    """Test that create_head_jobs_from_config creates the correct number of graphs with correct structure"""
    # Set up test config directory
    test_config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_jc_config"))
    logging.info(f"\nTest config dir: {test_config_dir}")
    logging.info(f"Directory exists: {os.path.exists(test_config_dir)}")
    logging.info(f"Directory contents: {os.listdir(test_config_dir)}")
    
    # Reset ConfigLoader state and set directories
    ConfigLoader._cached_configs = None  # Reset cached configs
    ConfigLoader._set_directories([str(test_config_dir)])  # Convert to string for anyconfig

    # Create head jobs
    head_jobs = JobFactory.get_head_jobs_from_config()
    
    # Should create 4 graphs:
    # - 2 from four_stage_parameterized (params1 and params2)
    # - 1 from three_stage (params1)
    # - 1 from three_stage_reasoning (no params)
    assert len(head_jobs) == 4, f"Expected 4 head jobs, got {len(head_jobs)}"
    
    # Get graph definitions for validation
    graphs_config = ConfigLoader.get_graphs_config()
    
    # Validate each head job's structure matches its graph definition
    for i, head_job in enumerate(head_jobs):
        print(f"\nJob Graph {i + 1}:")
        
        # Print all jobs in this graph using DFS
        visited = set()
        def print_job_graph(job):
            if job in visited:
                return
            visited.add(job)
            print(str(job))
            for child in job.next_jobs:
                print_job_graph(child)
        
        print_job_graph(head_job)
        print("----------------------")
        
        # Extract graph name and param group from job name
        job_parts = head_job.name.split("_")
        if len(job_parts) >= 3 and job_parts[0] in graphs_config:
            graph_name = job_parts[0]
            param_group = job_parts[1] if job_parts[1].startswith("params") else None
            
            # Get graph definition
            graph_def = graphs_config[graph_name]
            
            # Validate job structure matches graph definition
            def validate_job_structure(job, graph_def):
                # Get job's base name (without graph and param prefixes)
                base_job_name = "_".join(job.name.split("_")[2:]) if param_group else "_".join(job.name.split("_")[1:])
                
                # Check that next_jobs match graph definition
                expected_next = set(graph_def[base_job_name].get("next", []))
                actual_next = {next_job.name.split("_")[-1] for next_job in job.next_jobs}
                assert expected_next == actual_next, \
                    f"Mismatch in next_jobs for {job.name}. Expected: {expected_next}, Got: {actual_next}"
                
                # Recursively validate next jobs
                for next_job in job.next_jobs:
                    validate_job_structure(next_job, graph_def)
            
            validate_job_structure(head_job, graph_def)

def test_validate_all_jobs_in_graph():
    """Test that validation catches jobs referenced in graphs but not defined in jobs"""
    # Test with invalid configuration
    invalid_config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_jc_config_invalid"))
    ConfigLoader._set_directories([invalid_config_dir])
    
    with pytest.raises(ValueError) as exc_info:
        ConfigLoader.load_all_configs()
    assert "Job 'nonexistent_job' referenced in 'next' field of job 'read_file' in graph 'four_stage_parameterized'" in str(exc_info.value)
    
    # Test with valid configuration
    valid_config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_jc_config"))
    ConfigLoader._set_directories([valid_config_dir])
    
    try:
        ConfigLoader.load_all_configs()
    except ValueError as e:
        pytest.fail(f"Validation failed for valid configuration: {str(e)}")

def test_validate_all_parameters_filled():
    """Test that validation catches missing or invalid parameter configurations"""
    # Test with invalid parameter configuration
    invalid_config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_jc_config_invalid_parameters"))
    ConfigLoader._set_directories([invalid_config_dir])
    
    with pytest.raises(ValueError) as exc_info:
        ConfigLoader.load_all_configs()
    
    error_msg = str(exc_info.value)
    # Should catch missing parameters for read_file in params1
    assert "Job 'read_file' in graph 'four_stage_parameterized' requires parameters {'filepath'} but has no entry in parameter group 'params1'" in error_msg
    
    # Test with valid configuration
    valid_config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_jc_config"))
    ConfigLoader._set_directories([valid_config_dir])
    
    try:
        ConfigLoader.load_all_configs()
    except ValueError as e:
        pytest.fail(f"Validation failed for valid configuration: {str(e)}")



@pytest.mark.asyncio
async def test_job_execution_chain(caplog):
    """Test that all jobs in a graph are executed when _execute is called on the head job."""
    caplog.set_level('DEBUG')  # Set the logging level
    # Load custom job types
    JobFactory.load_jobs_into_registry([TEST_CONFIG_DIR])

    # Set config directory for test
    ConfigLoader._set_directories([os.path.join(os.path.dirname(__file__), "test_jc_config")])
    ConfigLoader.reload_configs()

    # Get head jobs from config
    head_jobs = JobFactory.get_head_jobs_from_config()

    # Get the first head job from four_stage_parameterized_params1
    head_job = [job for job in head_jobs if 'four_stage_parameterized_params1_read_file' in job.name][0]

    # Execute the head job
    await asyncio.create_task(head_job._execute(Task({"task": "Test task"})))

    # Expected job names in the graph
    expected_jobs = {
        'four_stage_parameterized_params1_read_file',
        'four_stage_parameterized_params1_ask_llm',
        'four_stage_parameterized_params1_save_to_db',
        'four_stage_parameterized_params1_summarize'
    }

    # Check that all jobs were executed by verifying their presence in the log output
    for job_name in expected_jobs:
        assert f"{job_name} finished running" in caplog.text, f"Job {job_name} was not executed"

   

@pytest.mark.asyncio
async def test_head_jobs_in_jobchain_serial():
    """Test that head jobs from config can be executed in JobChain with serial processing"""
    # Set config directory for test
    ConfigLoader._set_directories([os.path.join(os.path.dirname(__file__), "test_jc_config")])

   
    results = []
    
    
    def result_processor(result):
        results.append(result)
        logging.info(f"Processed result: {result}")
    
    # Create JobChain with serial processing to ensure deterministic results
    job_chain = JobChain(job=None, result_processing_function=result_processor, serial_processing=True)
    
    # Get head jobs from config to know their names
    head_jobs = job_chain.get_job_names()
    
    # Submit tasks for each job
    for job in head_jobs:
        job_chain.submit_task({"task": "Test task"}, job_name=job)
    
    # Mark input as completed and wait for all tasks to finish
    job_chain.mark_input_completed()
    
    # Convert shared list to regular list for sorting
    results_list = list(results)
    
    # Verify results
    # We expect one result per head job
    assert len(results_list) == len(head_jobs), f"Expected {len(head_jobs)} results, got {len(results_list)}"
    
    # Sort results by job name to ensure deterministic ordering
    results_list.sort(key=lambda x: next(iter(x.keys())))
    
    # Each result should be a dictionary with job results
    for result in results_list:
        assert isinstance(result, dict), f"Expected dict result, got {type(result)}"
        
        # Verify parameter substitution for each graph type
        if 'four_stage_parameterized_params1_summarize' in result:
            result_str = str(result['four_stage_parameterized_params1_summarize'])
            # Verify save_to_db parameters
            assert 'postgres://user1:pass1@db1/mydb' in result_str, "Database URL not correctly substituted"
            assert 'table_a' in result_str, "Table name not correctly substituted"
            # Verify read_file parameters
            assert './file1.txt' in result_str, "Filepath not correctly substituted"
            
        elif 'three_stage_params1_summarize' in result:
            result_str = str(result['three_stage_params1_summarize'])
            # Verify save_to_db2 parameters are from the job definition
            assert 'sqlite://user2:pass2@db2/mydb' in result_str, "Database URL not correctly set"
            assert 'table_b' in result_str, "Table name not correctly set"


def process_result(result):
    """Process a result by appending it to the global results list and logging to file"""
    print(f"Got result: {result}")
    with open("count_parallel_results", "a") as f:
        f.write(f"{str(result)}\n")


@pytest.mark.asyncio
async def test_head_jobs_in_jobchain_parallel():
    """Test that head jobs from config can be executed in JobChain with parallel processing"""
    # Clean up any existing results file
    if os.path.exists("count_parallel_results"):
        os.remove("count_parallel_results")
        
    # Set config directory for test
    ConfigLoader._set_directories([os.path.join(os.path.dirname(__file__), "test_jc_config")])
    
    # Create JobChain with parallel processing (default)
    job_chain = JobChain(job=None, result_processing_function=process_result)
    
    # Get head jobs from config to know their names
    head_jobs = job_chain.get_job_names()
    
    # Submit tasks for each job
    for job in head_jobs:
        job_chain.submit_task({"task": "Test task"}, job_name=job)
    
    # Mark input as completed and wait for all processing to finish
    job_chain.mark_input_completed()
    
    # Read results file and verify contents
    with open("count_parallel_results", "r") as f:
        results_list = [eval(line.strip()) for line in f.readlines()]
        assert len(results_list) == 4, f"Expected 4 results but got {len(results_list)}"
        
        # Each result should be a dictionary with job results
        for result in results_list:
            assert isinstance(result, dict), f"Expected dict result, got {type(result)}"
            
            # Verify parameter substitution for each graph type
            if 'four_stage_parameterized_params1_summarize' in result:
                result_str = str(result['four_stage_parameterized_params1_summarize'])
                # Verify save_to_db parameters
                assert 'postgres://user1:pass1@db1/mydb' in result_str, "Database URL not correctly substituted"
                assert 'table_a' in result_str, "Table name not correctly substituted"
                # Verify read_file parameters
                assert './file1.txt' in result_str, "Filepath not correctly substituted"
                
            elif 'four_stage_parameterized_params2_summarize' in result:
                result_str = str(result['four_stage_parameterized_params2_summarize'])
                # Verify save_to_db parameters
                assert 'sqlite://user2:pass2@db2/mydb' in result_str, "Database URL not correctly substituted"
                assert 'table_b' in result_str, "Table name not correctly substituted"
                # Verify read_file parameters
                assert './file2.txt' in result_str, "Filepath not correctly substituted"
                
            elif 'three_stage_params1_summarize' in result:
                result_str = str(result['three_stage_params1_summarize'])
                # Verify save_to_db2 parameters are from the job definition
                assert 'sqlite://user2:pass2@db2/mydb' in result_str, "Database URL not correctly set"
                assert 'table_b' in result_str, "Table name not correctly set"
                
            elif 'three_stage_reasoning__summarize' in result:
                result_str = str(result['three_stage_reasoning__summarize'])
                # Verify save_to_db2 parameters are from the job definition
                assert 'sqlite://user2:pass2@db2/mydb' in result_str, "Database URL not correctly set"
                assert 'table_b' in result_str, "Table name not correctly set"
    
    # Clean up results file
    os.remove("count_parallel_results")

def process_prompts(result):
    """Process a result by appending it to the global results list and logging to file"""
    print(f"Got result: {result}")

@pytest.mark.asyncio
async def test_single_job_multiple_prompts():
    # Set config directory for test
    ConfigLoader._set_directories([os.path.join(os.path.dirname(__file__), "test_single_job")])
    
    # Create JobChain with parallel processing (default)
    job_chain = JobChain(result_processing_function=process_prompts)

    prompts = ["what is the capital of france",
    "what is the capital of germany",
    "what is the capital of the UK",
    "what is the capital of the USA"
    ]

    for prompt in prompts:
        job_chain.submit_task({"prompt": prompt})
    
    # Mark input as completed and wait for all processing to finish
    job_chain.mark_input_completed()