from typing import Any, Dict

from jobchain.job import JobABC


class MockFileReadJob(JobABC):
    async def run(self, inputs: Dict[str, Any]) -> Any:
        print(f"\nFileReadJob '{self.name}' reading file: {self.properties.get('filepath')}, inputs:{inputs}")
        file_content = f"Contents of {self.properties.get('filepath')}"
        return {"file_content":file_content}

class MockDatabaseWriteJob(JobABC):
    async def run(self, inputs: Dict[str, Any]) -> Any:
        print(f"\nDatabaseWriteJob '{self.name}' writing to: {self.properties.get('database_url')}, table: {self.properties.get('table_name')}, inputs:{inputs}")
        data_result = f"Data written to table {self.properties.get('table_name')} on db {self.properties.get('database_url')} from {inputs}"
        return {"data_result":data_result}
        
class DummyJob(JobABC):
    async def run(self, inputs: Dict[str, Any]) -> Any:
        print(f"\ndummy_job '{self.name}' with properties: {self.properties}, inputs: {inputs}")
        return {"dummy_job_result":f"Ran function '{self.name}' with {inputs}"}
    