# Data Transformation Tool - Application Structure

## Project Structure
```
data_transformation_tool/
├── src/
│   ├── __init__.py
│   ├── data_layer/
│   │   ├── __init__.py
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py
│   │   │   ├── models.py
│   │   │   └── repository.py
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── file_storage.py
│   │   │   └── cache_storage.py
│   │   └── entities/
│   │       ├── __init__.py
│   │       ├── source_data.py
│   │       ├── filter_config.py
│   │       ├── transformation_result.py
│   │       └── execution_context.py
│   ├── service_layer/
│   │   ├── __init__.py
│   │   ├── data_loader/
│   │   │   ├── __init__.py
│   │   │   ├── excel_loader.py
│   │   │   ├── csv_loader.py
│   │   │   └── database_loader.py
│   │   ├── transformation/
│   │   │   ├── __init__.py
│   │   │   ├── transformation_engine.py
│   │   │   ├── parallel_engine.py
│   │   │   ├── filter_processor.py
│   │   │   └── functions/
│   │   │       ├── __init__.py
│   │   │       ├── base_transformation.py
│   │   │       ├── data_cleaning.py
│   │   │       ├── aggregation.py
│   │   │       └── custom_functions.py
│   │   └── orchestration/
│   │       ├── __init__.py
│   │       ├── workflow_manager.py
│   │       ├── parallel_orchestrator.py
│   │       └── task_scheduler.py
│   ├── presentation_layer/
│   │   ├── __init__.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py
│   │   │   └── middleware.py
│   │   ├── cli/
│   │   │   ├── __init__.py
│   │   │   └── commands.py
│   │   └── config/
│   │       ├── __init__.py
│   │       ├── settings.py
│   │       └── filter_config_parser.py
│   └── utils/
│       ├── __init__.py
│       ├── logger.py
│       ├── exceptions.py
│       └── validators.py
├── tests/
│   ├── __init__.py
│   ├── test_data_layer/
│   ├── test_service_layer/
│   └── test_presentation_layer/
├── config/
│   ├── database.yaml
│   ├── transformations.yaml
│   └── logging.yaml
├── requirements.txt
├── setup.py
└── README.md
```

## Core Implementation Files

### 1. Data Layer

#### src/data_layer/entities/source_data.py
```python
from dataclasses import dataclass
from typing import Dict, Any, Optional
import pandas as pd
from datetime import datetime

@dataclass
class SourceData:
    """Entity representing source data"""
    database_name: str
    table_name: str
    data: pd.DataFrame
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime] = #### src/presentation_layer/api/routes.py
```python
from flask import Flask, request, jsonify
from typing import Dict, Any
import threading
from ...service_layer.data_loader.excel_loader import ExcelLoader
from ...service_layer.transformation.parallel_engine import ParallelTransformationEngine, ParallelExecutionConfig
from ...service_layer.orchestration.parallel_orchestrator import ParallelOrchestrator
from ...service_layer.transformation.functions.aggregation import AggregationTransformation
from ...data_layer.database.repository import InMemoryRepository
from ...utils.exceptions import DataLoadError, TransformationError

app = Flask(__name__)

# Initialize services
repository = InMemoryRepository()
excel_loader = ExcelLoader()

# Parallel execution configuration
parallel_config = ParallelExecutionConfig(
    max_workers=4,
    execution_mode="thread",  # Can be "thread", "process", or "async"
    batch_size=10
)

parallel_engine = ParallelTransformationEngine(repository, parallel_config)
orchestrator = ParallelOrchestrator(repository, parallel_config)

# Register transformations
parallel_engine.register_transformation("aggregation", AggregationTransformation())
orchestrator.
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'database_name': self.database_name,
            'table_name': self.table_name,
            'row_count': len(self.data),
            'columns': list(self.data.columns),
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
```

#### src/data_layer/entities/filter_config.py
```python
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

@dataclass
class FilterConfig:
    """Entity representing filter configuration from Excel"""
    transformation_function: str
    filter_columns: Dict[str, Any]  # column_name -> filter_value
    parameters: Dict[str, Any]
    priority: int = 0
    description: Optional[str] = None
    
    @classmethod
    def from_excel_row(cls, row: Dict[str, Any]) -> 'FilterConfig':
        """Create FilterConfig from Excel row"""
        transformation_function = row.get('transformation_function', '')
        
        # Extract filter columns (columns starting with 'filter_')
        filter_columns = {}
        parameters = {}
        
        for key, value in row.items():
            if key.startswith('filter_col'):
                col_name = key.replace('filter_col', '').strip('_')
                if pd.notna(value):
                    filter_columns[col_name] = value
            elif key.startswith('param_'):
                param_name = key.replace('param_', '')
                if pd.notna(value):
                    parameters[param_name] = value
        
        return cls(
            transformation_function=transformation_function,
            filter_columns=filter_columns,
            parameters=parameters,
            priority=row.get('priority', 0),
            description=row.get('description')
        )
```

#### src/data_layer/entities/execution_context.py
```python
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

@dataclass
class ExecutionContext:
    """Context for tracking parallel execution of transformations"""
    execution_id: str
    total_tasks: int
    completed_tasks: int = 0
    failed_tasks: int = 0
    started_at: datetime = None
    completed_at: Optional[datetime] = None
    results: List[str] = None  # List of result IDs
    errors: List[str] = None
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
    
    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.now()
        if self.results is None:
            self.results = []
        if self.errors is None:
            self.errors = []
        if self.execution_id is None:
            self.execution_id = str(uuid.uuid4())
    
    def mark_task_completed(self, result_id: str):
        """Mark a task as completed"""
        self.completed_tasks += 1
        self.results.append(result_id)
        self._update_status()
    
    def mark_task_failed(self, error: str):
        """Mark a task as failed"""
        self.failed_tasks += 1
        self.errors.append(error)
        self._update_status()
    
    def _update_status(self):
        """Update execution status based on task completion"""
        if self.completed_tasks + self.failed_tasks == self.total_tasks:
            self.completed_at = datetime.now()
            if self.failed_tasks == 0:
                self.status = "COMPLETED"
            elif self.completed_tasks == 0:
                self.status = "FAILED"
            else:
                self.status = "PARTIALLY_COMPLETED"
        else:
            self.status = "RUNNING"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'execution_id': self.execution_id,
            'total_tasks': self.total_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'results': self.results,
            'errors': self.errors,
            'status': self.status,
            'execution_time': (self.completed_at - self.started_at).total_seconds() if self.completed_at else None
        }
```

#### src/data_layer/entities/transformation_result.py
```python
from dataclasses import dataclass
from typing import Dict, Any, Optional
import pandas as pd
from datetime import datetime

@dataclass
class TransformationResult:
    """Entity representing transformation result"""
    result_id: str
    source_table: str
    transformation_function: str
    result_data: pd.DataFrame
    filter_applied: Dict[str, Any]
    execution_time: float
    created_at: datetime
    execution_id: Optional[str] = None
    worker_id: Optional[str] = None
    errors: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.result_id is None:
            import uuid
            self.result_id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'result_id': self.result_id,
            'source_table': self.source_table,
            'transformation_function': self.transformation_function,
            'result_rows': len(self.result_data),
            'result_columns': list(self.result_data.columns),
            'filter_applied': self.filter_applied,
            'execution_time': self.execution_time,
            'created_at': self.created_at.isoformat(),
            'execution_id': self.execution_id,
            'worker_id': self.worker_id,
            'errors': self.errors
        }
```

#### src/data_layer/database/repository.py
```python
from typing import List, Optional, Dict, Any
import pandas as pd
from abc import ABC, abstractmethod
from ..entities.source_data import SourceData
from ..entities.transformation_result import TransformationResult

class DataRepository(ABC):
    """Abstract repository for data operations"""
    
    @abstractmethod
    def save_source_data(self, source_data: SourceData) -> bool:
        pass
    
    @abstractmethod
    def get_source_data(self, database_name: str, table_name: str) -> Optional[SourceData]:
        pass
    
    @abstractmethod
    def save_transformation_result(self, result: TransformationResult) -> bool:
        pass
    
    @abstractmethod
    def get_transformation_results(self, source_table: str) -> List[TransformationResult]:
        pass

class InMemoryRepository(DataRepository):
    """In-memory implementation of data repository"""
    
    def __init__(self):
        self._source_data: Dict[str, SourceData] = {}
        self._transformation_results: List[TransformationResult] = []
    
    def save_source_data(self, source_data: SourceData) -> bool:
        key = f"{source_data.database_name}.{source_data.table_name}"
        self._source_data[key] = source_data
        return True
    
    def get_source_data(self, database_name: str, table_name: str) -> Optional[SourceData]:
        key = f"{database_name}.{table_name}"
        return self._source_data.get(key)
    
    def save_transformation_result(self, result: TransformationResult) -> bool:
        self._transformation_results.append(result)
        return True
    
    def get_transformation_results(self, source_table: str) -> List[TransformationResult]:
        return [r for r in self._transformation_results if r.source_table == source_table]
```

### 2. Service Layer

#### src/service_layer/data_loader/excel_loader.py
```python
import pandas as pd
from typing import List, Dict, Any
from ...data_layer.entities.source_data import SourceData
from ...data_layer.entities.filter_config import FilterConfig
from ...utils.exceptions import DataLoadError
from datetime import datetime

class ExcelLoader:
    """Service for loading data from Excel files"""
    
    def load_source_data(self, file_path: str, database_name: str, 
                        sheet_name: str = None) -> SourceData:
        """Load source data from Excel file"""
        try:
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(file_path)
            
            metadata = {
                'file_path': file_path,
                'sheet_name': sheet_name,
                'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
            }
            
            return SourceData(
                database_name=database_name,
                table_name=sheet_name or 'default',
                data=df,
                metadata=metadata,
                created_at=datetime.now()
            )
        except Exception as e:
            raise DataLoadError(f"Failed to load Excel file {file_path}: {str(e)}")
    
    def load_filter_config(self, file_path: str, sheet_name: str = None) -> List[FilterConfig]:
        """Load filter configuration from Excel file"""
        try:
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(file_path)
            
            filters = []
            for _, row in df.iterrows():
                filter_config = FilterConfig.from_excel_row(row.to_dict())
                filters.append(filter_config)
            
            return filters
        except Exception as e:
            raise DataLoadError(f"Failed to load filter config from {file_path}: {str(e)}")
```

#### src/service_layer/transformation/parallel_engine.py
```python
from typing import List, Dict, Any, Optional, Callable
import pandas as pd
from datetime import datetime
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import multiprocessing
import asyncio
from dataclasses import dataclass
from ...data_layer.entities.source_data import SourceData
from ...data_layer.entities.filter_config import FilterConfig
from ...data_layer.entities.transformation_result import TransformationResult
from ...data_layer.entities.execution_context import ExecutionContext
from ...data_layer.database.repository import DataRepository
from ...utils.exceptions import TransformationError
from ...utils.logger import setup_logger
from .transformation_engine import TransformationEngine

@dataclass
class ParallelExecutionConfig:
    """Configuration for parallel execution"""
    max_workers: Optional[int] = None
    execution_mode: str = "thread"  # "thread", "process", "async"
    batch_size: int = 10
    timeout: Optional[int] = None
    memory_limit_mb: Optional[int] = None
    
    def __post_init__(self):
        if self.max_workers is None:
            self.max_workers = min(multiprocessing.cpu_count(), 8)

class ParallelTransformationEngine:
    """Engine for parallel execution of transformations"""
    
    def __init__(self, repository: DataRepository, config: ParallelExecutionConfig = None):
        self.repository = repository
        self.config = config or ParallelExecutionConfig()
        self.logger = setup_logger(f"{__name__}.ParallelTransformationEngine")
        self.transformation_engine = TransformationEngine()
        
    def register_transformation(self, name: str, transformation):
        """Register a transformation function"""
        self.transformation_engine.register_transformation(name, transformation)
    
    def execute_parallel_transformations(self, 
                                       source_data_list: List[SourceData],
                                       filter_configs: List[FilterConfig],
                                       progress_callback: Optional[Callable] = None) -> ExecutionContext:
        """Execute multiple transformations in parallel"""
        
        # Create execution context
        execution_context = ExecutionContext(
            execution_id=str(uuid.uuid4()),
            total_tasks=len(filter_configs)
        )
        
        self.logger.info(f"Starting parallel execution {execution_context.execution_id} with {len(filter_configs)} tasks")
        
        # Choose execution mode
        if self.config.execution_mode == "thread":
            return self._execute_with_threads(source_data_list, filter_configs, execution_context, progress_callback)
        elif self.config.execution_mode == "process":
            return self._execute_with_processes(source_data_list, filter_configs, execution_context, progress_callback)
        elif self.config.execution_mode == "async":
            return asyncio.run(self._execute_with_async(source_data_list, filter_configs, execution_context, progress_callback))
        else:
            raise ValueError(f"Unknown execution mode: {self.config.execution_mode}")
    
    def _execute_with_threads(self, source_data_list: List[SourceData], 
                            filter_configs: List[FilterConfig],
                            execution_context: ExecutionContext,
                            progress_callback: Optional[Callable] = None) -> ExecutionContext:
        """Execute transformations using ThreadPoolExecutor"""
        
        execution_context.status = "RUNNING"
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all tasks
            future_to_config = {}
            
            for filter_config in filter_configs:
                # Find matching source data
                source_data = self._find_matching_source_data(source_data_list, filter_config)
                if source_data:
                    future = executor.submit(
                        self._execute_single_transformation,
                        source_data,
                        filter_config,
                        execution_context.execution_id,
                        f"thread-{threading.current_thread().ident}"
                    )
                    future_to_config[future] = filter_config
                else:
                    execution_context.mark_task_failed(f"No source data found for filter: {filter_config.transformation_function}")
            
            # Process completed tasks
            for future in as_completed(future_to_config, timeout=self.config.timeout):
                filter_config = future_to_config[future]
                
                try:
                    result = future.result()
                    if result.errors:
                        execution_context.mark_task_failed(f"Task failed: {result.errors}")
                    else:
                        self.repository.save_transformation_result(result)
                        execution_context.mark_task_completed(result.result_id)
                    
                    if progress_callback:
                        progress_callback(execution_context)
                        
                except Exception as e:
                    self.logger.error(f"Task {filter_config.transformation_function} failed: {str(e)}")
                    execution_context.mark_task_failed(str(e))
                    
                    if progress_callback:
                        progress_callback(execution_context)
        
        return execution_context
    
    def _execute_with_processes(self, source_data_list: List[SourceData], 
                              filter_configs: List[FilterConfig],
                              execution_context: ExecutionContext,
                              progress_callback: Optional[Callable] = None) -> ExecutionContext:
        """Execute transformations using ProcessPoolExecutor"""
        
        execution_context.status = "RUNNING"
        
        with ProcessPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all tasks
            future_to_config = {}
            
            for filter_config in filter_configs:
                # Find matching source data
                source_data = self._find_matching_source_data(source_data_list, filter_config)
                if source_data:
                    future = executor.submit(
                        _execute_transformation_worker,
                        source_data,
                        filter