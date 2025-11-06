import sys
import io
import signal
from typing import Dict, Any, Tuple
from contextlib import contextmanager
import traceback


class TimeoutException(Exception):
    pass


@contextmanager
def timeout(seconds: int):
    """Context manager for timing out code execution"""
    def timeout_handler(signum, frame):
        raise TimeoutException(f"Code execution exceeded {seconds} seconds")
    
    # Set the signal handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class CodeExecutor:
    """Safely execute user-provided Python code with restrictions"""
    
    # Safe built-ins available to user code
    SAFE_BUILTINS = {
        'abs': abs,
        'all': all,
        'any': any,
        'bool': bool,
        'dict': dict,
        'enumerate': enumerate,
        'float': float,
        'int': int,
        'len': len,
        'list': list,
        'max': max,
        'min': min,
        'range': range,
        'round': round,
        'set': set,
        'sorted': sorted,
        'str': str,
        'sum': sum,
        'tuple': tuple,
        'zip': zip,
        'map': map,
        'filter': filter,
        'print': print,
    }
    
    @staticmethod
    def execute(
        code: str,
        constants: Dict[str, Any],
        inputs: Dict[str, Any],
        context: Dict[str, Any],
        timeout_seconds: int = 300
    ) -> Tuple[bool, Any, str]:
        """
        Execute user code in a restricted environment
        
        Args:
            code: Python code to execute
            constants: Static values defined in node
            inputs: Outputs from predecessor nodes
            context: Global execution context
            timeout_seconds: Maximum execution time
            
        Returns:
            (success, output, error_message)
        """
        # Prepare execution namespace
        exec_globals = {
            '__builtins__': CodeExecutor.SAFE_BUILTINS,
            'constants': constants,
            'inputs': inputs,
            'context': context,
        }
        
        # Capture stdout/stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            
            # Execute with timeout
            with timeout(timeout_seconds):
                exec_locals = {}
                exec(code, exec_globals, exec_locals)
                
                # Look for 'output' variable in locals
                output = exec_locals.get('output', None)
                
                # If no output variable, return stdout
                if output is None:
                    stdout_content = stdout_capture.getvalue()
                    if stdout_content:
                        output = stdout_content
                
                return True, output, ""
                
        except TimeoutException as e:
            return False, None, str(e)
        
        except SyntaxError as e:
            error_msg = f"Syntax Error: {str(e)}\nLine {e.lineno}: {e.text}"
            return False, None, error_msg
        
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            stderr_content = stderr_capture.getvalue()
            if stderr_content:
                error_msg += f"\nStderr: {stderr_content}"
            return False, None, error_msg
        
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    
    @staticmethod
    def validate_code(code: str) -> Tuple[bool, str]:
        """
        Validate code syntax without executing
        Returns: (is_valid, error_message)
        """
        try:
            compile(code, '<string>', 'exec')
            return True, ""
        except SyntaxError as e:
            return False, f"Syntax Error at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, f"Validation Error: {str(e)}"


# Enhanced version with subprocess (for better isolation)
# Uncomment if you need stronger isolation

"""
import subprocess
import json
import tempfile
import os

class SubprocessCodeExecutor:
    '''Execute code in a separate subprocess for better isolation'''
    
    @staticmethod
    def execute(
        code: str,
        constants: Dict[str, Any],
        inputs: Dict[str, Any],
        context: Dict[str, Any],
        timeout_seconds: int = 300
    ) -> Tuple[bool, Any, str]:
        '''Execute code in isolated subprocess'''
        
        # Create wrapper script
        wrapper = f'''
import json
import sys

constants = {json.dumps(constants)}
inputs = {json.dumps(inputs)}
context = {json.dumps(context)}

try:
    exec("""{code}""")
    result = locals().get('output', None)
    print(json.dumps({{"success": True, "output": result}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e)}}))
    sys.exit(1)
'''
        
        try:
            # Write to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(wrapper)
                temp_file = f.name
            
            # Execute with timeout
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            
            # Parse result
            output = json.loads(result.stdout)
            
            if output['success']:
                return True, output['output'], ""
            else:
                return False, None, output['error']
                
        except subprocess.TimeoutExpired:
            return False, None, f"Execution timeout after {timeout_seconds} seconds"
        except Exception as e:
            return False, None, f"Execution error: {str(e)}"
        finally:
            if 'temp_file' in locals():
                os.unlink(temp_file)
"""
