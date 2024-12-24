import os
import sys
from pathlib import Path

import pytest
import yaml

import jc_logging as logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from jc_graph import validate_graph
from job_loader import ConfigLoader, JobFactory
from jobs.llm_jobs import OpenAIJob

# Test configuration
TEST_JOBS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_jc_config/jobs"))

@pytest.fixture
def job_factory():
    factory = JobFactory()
    # Load both the test jobs and the real jobs
    #  the real jobs are always loaded by the factory
    factory.load_custom_jobs_directory(TEST_JOBS_DIR)
    #factory.load_custom_jobs_directory(os.path.join(os.path.dirname(os.path.dirname(__file__)), "jobs"))
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
        properties={"test_param": "test_value"}
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
        properties={
            "model": "gpt-3.5-turbo",
            "api": {
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Say hello!"}
                ],
                "temperature": 0.7
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
    ConfigLoader.directories = [str(test_config_dir)]  # Convert to string for anyconfig
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
    ConfigLoader.directories = [str(test_config_dir)]  # Convert to string for anyconfig
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
    ConfigLoader.directories = [str(test_config_dir)]  # Convert to string for anyconfig

    # Create head jobs
    head_jobs = JobFactory.create_head_jobs_from_config()
    
    # Should create 4 graphs:
    # - 2 from four_stage_parameterized (params1 and params2)
    # - 1 from three_stage (params1)
    # - 1 from three_stage_reasoning (no params)
    assert len(head_jobs) == 4, f"Expected 4 head jobs, got {len(head_jobs)}"
    
    # Get graph definitions for validation
    graphs_config = ConfigLoader.get_graphs_config()
    
    # Validate each head job's structure matches its graph definition
    for head_job in head_jobs:
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
    ConfigLoader.directories = [invalid_config_dir]
    
    with pytest.raises(ValueError) as exc_info:
        ConfigLoader.load_all_configs()
    assert "Job 'nonexistent_job' referenced in 'next' field of job 'read_file' in graph 'four_stage_parameterized'" in str(exc_info.value)
    
    # Test with valid configuration
    valid_config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_jc_config"))
    ConfigLoader.directories = [valid_config_dir]
    
    try:
        ConfigLoader.load_all_configs()
    except ValueError as e:
        pytest.fail(f"Validation failed for valid configuration: {str(e)}")

def test_validate_all_parameters_filled():
    """Test that validation catches missing or invalid parameter configurations"""
    # Test with invalid parameter configuration
    invalid_config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_jc_config_invalid_parameters"))
    ConfigLoader.directories = [invalid_config_dir]
    
    with pytest.raises(ValueError) as exc_info:
        ConfigLoader.load_all_configs()
    
    error_msg = str(exc_info.value)
    # Should catch missing parameters for read_file in params1
    assert "Job 'read_file' in graph 'four_stage_parameterized' requires parameters {'filepath'} but has no entry in parameter group 'params1'" in error_msg
    
    # Test with valid configuration
    valid_config_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_jc_config"))
    ConfigLoader.directories = [valid_config_dir]
    
    try:
        ConfigLoader.load_all_configs()
    except ValueError as e:
        pytest.fail(f"Validation failed for valid configuration: {str(e)}")
