#!/usr/bin/env python3
"""
FastAPI D2 Diagram Generator
Generates technical and stakeholder diagrams for FastAPI backend modules
"""

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class EndpointInfo:
    method: str
    path: str
    function_name: str
    dependencies: List[str]
    response_model: Optional[str] = None
    request_model: Optional[str] = None


@dataclass
class ServiceInfo:
    functions: List[str]
    dependencies: List[str]
    database_calls: List[str]
    external_services: List[str]


@dataclass
class ModuleAnalysis:
    module_name: str
    endpoints: List[EndpointInfo]
    services: ServiceInfo
    schemas: List[str]
    utils: List[str]


class FastAPIAnalyzer:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.modules = {}
        
    def analyze_router_file(self, router_path: Path) -> List[EndpointInfo]:
        """Analyze router.py file to extract endpoint information"""
        endpoints = []
        
        try:
            with open(router_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
                
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Look for FastAPI route decorators
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Call) and hasattr(decorator.func, 'attr'):
                            method = decorator.func.attr.lower()
                            if method in ['get', 'post', 'put', 'delete', 'patch']:
                                path = self._extract_path_from_decorator(decorator)
                                deps = self._extract_dependencies(node)
                                
                                endpoint = EndpointInfo(
                                    method=method.upper(),
                                    path=path,
                                    function_name=node.name,
                                    dependencies=deps
                                )
                                endpoints.append(endpoint)
                                
        except Exception as e:
            print(f"Error analyzing router {router_path}: {e}")
            
        return endpoints
    
    def analyze_service_file(self, service_path: Path) -> ServiceInfo:
        """Analyze service.py file to extract service information"""
        functions = []
        dependencies = []
        database_calls = []
        external_services = []
        
        try:
            with open(service_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
                
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)
                    
                    # Look for database operations
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call) and hasattr(child.func, 'attr'):
                            func_name = child.func.attr
                            if func_name in ['query', 'execute', 'commit', 'add', 'merge']:
                                database_calls.append(f"{node.name} -> {func_name}")
                        
                        # Look for external service calls (redis, celery, etc.)
                        if isinstance(child, ast.Name):
                            if child.id in ['redis', 'celery', 'requests']:
                                external_services.append(child.id)
                                
        except Exception as e:
            print(f"Error analyzing service {service_path}: {e}")
            
        return ServiceInfo(
            functions=functions,
            dependencies=dependencies,
            database_calls=database_calls,
            external_services=list(set(external_services))
        )
    
    def analyze_schema_file(self, schema_path: Path) -> List[str]:
        """Analyze schema.py file to extract Pydantic models"""
        schemas = []
        
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
                
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if it inherits from BaseModel or similar
                    for base in node.bases:
                        if hasattr(base, 'id') and 'Model' in base.id:
                            schemas.append(node.name)
                            break
                        elif hasattr(base, 'attr') and 'Model' in base.attr:
                            schemas.append(node.name)
                            break
                            
        except Exception as e:
            print(f"Error analyzing schema {schema_path}: {e}")
            
        return schemas
    
    def analyze_module(self, module_path: Path) -> ModuleAnalysis:
        """Analyze a complete module directory"""
        module_name = module_path.name
        
        # Analyze each file type
        router_file = module_path / "router.py"
        service_file = module_path / "service.py"
        schema_file = module_path / "schema.py"
        utils_file = module_path / "utils.py"
        
        endpoints = []
        if router_file.exists():
            endpoints = self.analyze_router_file(router_file)
            
        services = ServiceInfo([], [], [], [])
        if service_file.exists():
            services = self.analyze_service_file(service_file)
            
        schemas = []
        if schema_file.exists():
            schemas = self.analyze_schema_file(schema_file)
            
        utils = []
        if utils_file.exists():
            utils = self._extract_functions(utils_file)
            
        return ModuleAnalysis(
            module_name=module_name,
            endpoints=endpoints,
            services=services,
            schemas=schemas,
            utils=utils
        )
    
    def _extract_path_from_decorator(self, decorator: ast.Call) -> str:
        """Extract path from FastAPI route decorator"""
        if decorator.args and isinstance(decorator.args[0], ast.Str):
            return decorator.args[0].s
        elif decorator.args and isinstance(decorator.args[0], ast.Constant):
            return decorator.args[0].value
        return "/"
    
    def _extract_dependencies(self, func_node: ast.FunctionDef) -> List[str]:
        """Extract dependencies from function parameters"""
        deps = []
        for arg in func_node.args.args:
            if arg.annotation and hasattr(arg.annotation, 'id'):
                if 'Depends' in str(arg.annotation.id):
                    deps.append(arg.arg)
        return deps
    
    def _extract_functions(self, file_path: Path) -> List[str]:
        """Extract function names from a Python file"""
        functions = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
                
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)
                    
        except Exception as e:
            print(f"Error extracting functions from {file_path}: {e}")
            
        return functions


class D2DiagramGenerator:
    def __init__(self):
        self.colors = {
            'endpoint': '#4CAF50',
            'service': '#2196F3', 
            'database': '#FF9800',
            'external': '#9C27B0',
            'schema': '#607D8B',
            'utils': '#795548'
        }
    
    def generate_technical_diagram(self, analysis: ModuleAnalysis) -> str:
        """Generate detailed technical diagram for developers"""
        d2_content = f'''# Technical Architecture - {analysis.module_name.title()} Module
# Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

direction: right

# Module Components
{analysis.module_name}_module: {{
  label: "{analysis.module_name.title()} Module"
  style.fill: "#f5f5f5"
  style.stroke: "#333"
  
  router: {{
    label: "Router\\n(Endpoints)"
    style.fill: "{self.colors['endpoint']}"
  }}
  
  service: {{
    label: "Service\\n(Business Logic)"
    style.fill: "{self.colors['service']}"
  }}
  
  schema: {{
    label: "Schema\\n(Data Models)"
    style.fill: "{self.colors['schema']}"
  }}
  
  utils: {{
    label: "Utils\\n(Helpers)"
    style.fill: "{self.colors['utils']}"
  }}
}}

# External Systems
postgres: {{
  label: "PostgreSQL\\nDatabase"
  style.fill: "{self.colors['database']}"
}}

redis: {{
  label: "Redis\\nCache"
  style.fill: "{self.colors['external']}"
}}

bq: {{
  label: "BigQuery\\nWarehouse"
  style.fill: "{self.colors['database']}"
}}

celery: {{
  label: "Celery\\nWorker"
  style.fill: "{self.colors['external']}"
}}

# API Endpoints Detail
endpoints: {{
  label: "API Endpoints"
  style.fill: "#e8f5e8"
  
'''
        
        # Add endpoints
        for i, endpoint in enumerate(analysis.endpoints):
            d2_content += f'''  ep_{i}: {{
    label: "{endpoint.method} {endpoint.path}\\n{endpoint.function_name}"
    style.fill: "{self.colors['endpoint']}"
  }}
  
'''
        
        d2_content += "}\n\n"
        
        # Add service functions
        if analysis.services.functions:
            d2_content += '''# Service Functions
services: {
  label: "Service Layer"
  style.fill: "#e3f2fd"
  
'''
            for func in analysis.services.functions:
                d2_content += f'''  {func}: {{
    label: "{func}()"
    style.fill: "{self.colors['service']}"
  }}
  
'''
            d2_content += "}\n\n"
        
        # Add connections
        d2_content += "# Data Flow Connections\n"
        d2_content += f"{analysis.module_name}_module.router -> {analysis.module_name}_module.service: \"calls\"\n"
        d2_content += f"{analysis.module_name}_module.service -> {analysis.module_name}_module.schema: \"validates\"\n"
        d2_content += f"{analysis.module_name}_module.service -> postgres: \"queries\"\n"
        
        if 'redis' in analysis.services.external_services:
            d2_content += f"{analysis.module_name}_module.service -> redis: \"caches\"\n"
            
        if 'celery' in analysis.services.external_services:
            d2_content += f"{analysis.module_name}_module.service -> celery: \"queues task\"\n"
        
        # Connect endpoints to services
        for i, endpoint in enumerate(analysis.endpoints):
            d2_content += f"endpoints.ep_{i} -> {analysis.module_name}_module.service: \"processes\"\n"
        
        return d2_content
    
    def generate_stakeholder_diagram(self, analysis: ModuleAnalysis) -> str:
        """Generate simplified diagram for stakeholders"""
        d2_content = f'''# Business Flow - {analysis.module_name.title()} Module
# Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

direction: right

# User Journey
user: {{
  label: "User/Client"
  style.fill: "#4CAF50"
}}

api: {{
  label: "{analysis.module_name.title()}\\nAPI Service"
  style.fill: "#2196F3"
}}

database: {{
  label: "Data\\nStorage"
  style.fill: "#FF9800"
}}

# Business Operations
operations: {{
  label: "Available Operations"
  style.fill: "#f5f5f5"
  
'''
        
        # Group endpoints by business function
        endpoint_groups = self._group_endpoints_by_business_function(analysis.endpoints)
        
        for group_name, endpoints in endpoint_groups.items():
            d2_content += f'''  {group_name}: {{
    label: "{group_name.title()}"
    style.fill: "#e8f5e8"
  }}
  
'''
        
        d2_content += "}\n\n"
        
        # Add flow
        d2_content += "# Business Flow\n"
        d2_content += "user -> api: \"sends request\"\n"
        d2_content += "api -> database: \"stores/retrieves data\"\n"
        d2_content += "database -> api: \"returns data\"\n"
        d2_content += "api -> user: \"sends response\"\n\n"
        
        # Connect operations
        for group_name in endpoint_groups.keys():
            d2_content += f"api -> operations.{group_name}: \"handles\"\n"
        
        return d2_content
    
    def _group_endpoints_by_business_function(self, endpoints: List[EndpointInfo]) -> Dict[str, List[EndpointInfo]]:
        """Group endpoints by business function based on HTTP method and path"""
        groups = {
            'create': [],
            'read': [],
            'update': [],
            'delete': [],
            'search': [],
            'export': []
        }
        
        for endpoint in endpoints:
            if endpoint.method == 'POST':
                groups['create'].append(endpoint)
            elif endpoint.method == 'GET':
                if 'search' in endpoint.path.lower() or 'filter' in endpoint.path.lower():
                    groups['search'].append(endpoint)
                elif 'export' in endpoint.path.lower():
                    groups['export'].append(endpoint)
                else:
                    groups['read'].append(endpoint)
            elif endpoint.method in ['PUT', 'PATCH']:
                groups['update'].append(endpoint)
            elif endpoint.method == 'DELETE':
                groups['delete'].append(endpoint)
        
        # Remove empty groups
        return {k: v for k, v in groups.items() if v}
    
    def generate_full_system_diagram(self, modules: List[ModuleAnalysis]) -> str:
        """Generate system-wide architecture diagram"""
        d2_content = f'''# Full System Architecture
# Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

direction: down

# Frontend Layer
frontend: {{
  label: "React Frontend\\n(Vite)"
  style.fill: "#61DAFB"
}}

# API Gateway/Load Balancer (if applicable)
gateway: {{
  label: "API Gateway"
  style.fill: "#FF6B6B"
}}

# Backend Services
backend: {{
  label: "FastAPI Backend"
  style.fill: "#009688"
  
'''
        
        for module in modules:
            d2_content += f'''  {module.module_name}: {{
    label: "{module.module_name.title()}\\nModule"
    style.fill: "{self.colors['service']}"
  }}
  
'''
        
        d2_content += '''}

# Data Layer
data_layer: {
  label: "Data Layer"
  style.fill: "#f5f5f5"
  
  postgres: {
    label: "PostgreSQL\\nMain Database"
    style.fill: "#336791"
  }
  
  redis: {
    label: "Redis\\nCache & Sessions"
    style.fill: "#DC382D"
  }
  
  bq: {
    label: "BigQuery\\nAnalytics"
    style.fill: "#4285F4"
  }
}

# Background Processing
worker: {
  label: "Celery Workers"
  style.fill: "#37B24D"
}

# Connections
frontend -> gateway: "HTTP/HTTPS"
gateway -> backend: "routes requests"

'''
        
        # Connect modules to data layer
        for module in modules:
            d2_content += f"backend.{module.module_name} -> data_layer.postgres: \"queries\"\n"
            d2_content += f"backend.{module.module_name} -> data_layer.redis: \"caches\"\n"
            if 'celery' in module.services.external_services:
                d2_content += f"backend.{module.module_name} -> worker: \"queues tasks\"\n"
        
        d2_content += "\nworker -> data_layer.postgres: \"updates data\"\n"
        d2_content += "worker -> data_layer.bq: \"analytics data\"\n"
        
        return d2_content


def main():
    """Main function to generate diagrams"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate D2 diagrams for FastAPI application')
    parser.add_argument('--backend-path', required=True, help='Path to backend directory')
    parser.add_argument('--module', help='Specific module to analyze (optional)')
    parser.add_argument('--output-dir', default='./diagrams', help='Output directory for diagrams')
    parser.add_argument('--type', choices=['technical', 'stakeholder', 'full'], 
                       default='technical', help='Type of diagram to generate')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    analyzer = FastAPIAnalyzer(args.backend_path)
    generator = D2DiagramGenerator()
    
    if args.module:
        # Analyze specific module
        module_path = Path(args.backend_path) / args.module
        if not module_path.exists():
            print(f"Module {args.module} not found at {module_path}")
            return
            
        analysis = analyzer.analyze_module(module_path)
        
        if args.type == 'technical':
            content = generator.generate_technical_diagram(analysis)
            filename = f"{args.module}_technical.d2"
        elif args.type == 'stakeholder':
            content = generator.generate_stakeholder_diagram(analysis)
            filename = f"{args.module}_stakeholder.d2"
            
        with open(output_dir / filename, 'w') as f:
            f.write(content)
            
        print(f"Generated {filename}")
        
    else:
        # Analyze all modules
        backend_path = Path(args.backend_path)
        modules = []
        
        for item in backend_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it's a module directory
                if (item / "router.py").exists() or (item / "service.py").exists():
                    analysis = analyzer.analyze_module(item)
                    modules.append(analysis)
        
        if args.type == 'full':
            content = generator.generate_full_system_diagram(modules)
            filename = "full_system_architecture.d2"
            
            with open(output_dir / filename, 'w') as f:
                f.write(content)
                
            print(f"Generated {filename}")
        else:
            # Generate for all modules
            for analysis in modules:
                if args.type == 'technical':
                    content = generator.generate_technical_diagram(analysis)
                    filename = f"{analysis.module_name}_technical.d2"
                else:
                    content = generator.generate_stakeholder_diagram(analysis)
                    filename = f"{analysis.module_name}_stakeholder.d2"
                    
                with open(output_dir / filename, 'w') as f:
                    f.write(content)
                    
                print(f"Generated {filename}")


if __name__ == "__main__":
    main()