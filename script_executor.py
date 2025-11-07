"""
Dynamic Script Executor Utility
Safely loads and executes Python scripts with parameter passing and isolation.
"""

import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Optional
import importlib.util
import tempfile
import shutil


class ScriptExecutionError(Exception):
    """Custom exception for script execution errors"""
    pass


class ScriptExecutor:
    """
    Executes Python scripts in a controlled manner with parameter passing.
    
    Expected script structure:
    - Script must define a `run()` function or `main()` function
    - The function can accept **kwargs for parameter passing
    - Returns the result from the function
    """
    
    def __init__(self, script_path: str):
        """
        Initialize the executor with a script path.
        
        Args:
            script_path: Path to the Python script file
        """
        self.script_path = Path(script_path)
        if not self.script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")
        if not self.script_path.suffix == '.py':
            raise ValueError(f"File must be a Python script (.py): {script_path}")
    
    def execute(
        self, 
        params: Optional[Dict[str, Any]] = None,
        function_name: str = "run",
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute the script with given parameters.
        
        Args:
            params: Dictionary of parameters to pass to the script
            function_name: Name of the function to call (default: "run")
            timeout: Execution timeout in seconds (not implemented yet)
        
        Returns:
            Dictionary containing:
                - success: bool
                - result: Any (if successful)
                - error: str (if failed)
                - traceback: str (if failed)
        """
        params = params or {}
        
        try:
            # Load the module dynamically
            module = self._load_module()
            
            # Check if the function exists
            if not hasattr(module, function_name):
                # Fallback to 'main' if 'run' not found
                if function_name == "run" and hasattr(module, "main"):
                    function_name = "main"
                else:
                    raise ScriptExecutionError(
                        f"Function '{function_name}' not found in script. "
                        f"Available: {[x for x in dir(module) if not x.startswith('_')]}"
                    )
            
            # Get the function
            func = getattr(module, function_name)
            
            # Execute the function with parameters
            result = func(**params)
            
            return {
                "success": True,
                "result": result,
                "error": None,
                "traceback": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    def _load_module(self):
        """
        Dynamically load the Python module from file.
        
        Returns:
            The loaded module
        """
        # Create a unique module name based on the file path
        module_name = f"dynamic_script_{self.script_path.stem}_{id(self)}"
        
        # Load the module specification
        spec = importlib.util.spec_from_file_location(module_name, self.script_path)
        if spec is None or spec.loader is None:
            raise ScriptExecutionError(f"Could not load script: {self.script_path}")
        
        # Create the module
        module = importlib.util.module_from_spec(spec)
        
        # Add to sys.modules temporarily (required for some imports)
        sys.modules[module_name] = module
        
        try:
            # Execute the module
            spec.loader.exec_module(module)
        except Exception as e:
            # Clean up on failure
            sys.modules.pop(module_name, None)
            raise ScriptExecutionError(f"Error loading script: {str(e)}")
        
        return module
    
    def validate(self, function_name: str = "run") -> Dict[str, Any]:
        """
        Validate that the script can be loaded and has the required function.
        
        Args:
            function_name: Name of the function to check for
        
        Returns:
            Dictionary with validation results
        """
        try:
            module = self._load_module()
            
            has_function = hasattr(module, function_name)
            has_main = hasattr(module, "main")
            
            return {
                "valid": has_function or has_main,
                "has_function": has_function,
                "has_main": has_main,
                "available_functions": [
                    x for x in dir(module) 
                    if not x.startswith('_') and callable(getattr(module, x))
                ],
                "error": None
            }
        except Exception as e:
            return {
                "valid": False,
                "has_function": False,
                "has_main": False,
                "available_functions": [],
                "error": str(e)
            }


class IsolatedScriptExecutor(ScriptExecutor):
    """
    Extended executor that runs scripts in a more isolated environment.
    This version copies the script to a temporary location before execution.
    """
    
    def execute(
        self,
        params: Optional[Dict[str, Any]] = None,
        function_name: str = "run",
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute the script in isolation using a temporary copy.
        """
        temp_dir = None
        try:
            # Create temporary directory
            temp_dir = Path(tempfile.mkdtemp())
            temp_script = temp_dir / self.script_path.name
            
            # Copy script to temp location
            shutil.copy2(self.script_path, temp_script)
            
            # Temporarily swap the script path
            original_path = self.script_path
            self.script_path = temp_script
            
            # Execute using parent class method
            result = super().execute(params, function_name, timeout)
            
            # Restore original path
            self.script_path = original_path
            
            return result
            
        finally:
            # Cleanup temporary directory
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)


# Example usage and helper function
def execute_script(
    script_path: str,
    params: Optional[Dict[str, Any]] = None,
    isolated: bool = False,
    function_name: str = "run"
) -> Dict[str, Any]:
    """
    Convenience function to execute a script.
    
    Args:
        script_path: Path to the Python script
        params: Parameters to pass to the script
        isolated: Whether to use isolated execution
        function_name: Name of function to call
    
    Returns:
        Execution result dictionary
    """
    executor_class = IsolatedScriptExecutor if isolated else ScriptExecutor
    executor = executor_class(script_path)
    return executor.execute(params, function_name)


if __name__ == "__main__":
    # Example usage
    print("Script Executor Utility")
    print("-" * 50)
    
    # Create a sample script for testing
    sample_script = Path("sample_node_script.py")
    sample_script.write_text("""
def run(x, y, operation="add"):
    '''Sample node script that performs operations'''
    if operation == "add":
        return x + y
    elif operation == "multiply":
        return x * y
    elif operation == "subtract":
        return x - y
    else:
        return {"error": f"Unknown operation: {operation}"}
""")
    
    # Test execution
    executor = ScriptExecutor("sample_node_script.py")
    
    # Validate script
    validation = executor.validate()
    print(f"Validation: {validation}")
    
    # Execute with parameters
    result = executor.execute({"x": 10, "y": 5, "operation": "add"})
    print(f"\nExecution Result: {result}")
    
    # Test isolated execution
    result2 = execute_script(
        "sample_node_script.py",
        params={"x": 10, "y": 3, "operation": "multiply"},
        isolated=True
    )
    print(f"\nIsolated Execution Result: {result2}")
    
    # Cleanup
    sample_script.unlink()
