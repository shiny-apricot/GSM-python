"""Performance Profiler for execution time and memory usage."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Union, Dict, Any
from dataclasses import dataclass
import logging
import time
import cProfile
import pstats
import io
import psutil
import functools


@dataclass
class ProfilingParameters:
    """
    Settings to control how we measure performance.
    Like switches to turn different measurements on/off.
    """
    detailed: bool = False     
    memory_tracking: bool = True    
    log_level: int = logging.INFO   
    output_file: Optional[Union[str, Path]] = None  # File path to save results
    output_format: str = "text"  # "text" or "json"

def _save_profiling_results(
    output_file: Union[str, Path],
    format: str,
    results: Dict[str, Any],
    logger: logging.Logger
) -> None:
    """Helper function to save profiling results to file"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        if format == "json":
            with open(output_path, 'a') as f:
                json.dump(results, f)
                f.write('\n')
        else:  # text format
            with open(output_path, 'a') as f:
                f.write(f"\n--- Profiling Results {datetime.now().isoformat()} ---\n")
                for key, value in results.items():
                    f.write(f"{key}: {value}\n")
    except Exception as e:
        logger.error(f"❌ Failed to save profiling results: {str(e)}")

def profile_method(params: ProfilingParameters = ProfilingParameters()):
    """...existing docstring..."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # ...existing logger setup code..
            
            logger = logging.getLogger(__name__)
            logger.setLevel(params.log_level) 
            results = {
                "function_name": func.__name__,
                "timestamp": datetime.now().isoformat(),
                "execution_time": None,
                "memory_change": None,
                "detailed_profile": None
            }
            
            process = psutil.Process()
            start_memory = process.memory_info().rss / 1024 / 1024

            start_time = time.time()
            
            if params.detailed:
                profiler = cProfile.Profile()
                result = profiler.runcall(func, *args, **kwargs)
                
                s = io.StringIO()
                stats = pstats.Stats(profiler, stream=s).sort_stats('cumtime')
                stats.print_stats(20)
                detailed_output = s.getvalue()
                results["detailed_profile"] = detailed_output
                logger.log(params.log_level, f"\n🔍 Detailed profile for {func.__name__}:\n{detailed_output}")
            else:
                result = func(*args, **kwargs)
            
            execution_time = time.time() - start_time
            results["execution_time"] = f"{execution_time:.2f} seconds"
            logger.log(params.log_level, f"⏱️ {func.__name__} execution time: {execution_time:.2f} seconds")
            
            if params.memory_tracking:
                end_memory = process.memory_info().rss / 1024 / 1024
                memory_diff = end_memory - start_memory
                results["memory_change"] = f"{memory_diff:.2f} MB"
                results["current_memory"] = f"{end_memory:.2f} MB"
                logger.log(params.log_level, 
                         f"💾 Memory change: {memory_diff:.2f} MB (Current: {end_memory:.2f} MB)")
            
            # Save results if output file specified
            if params.output_file:
                _save_profiling_results(
                    params.output_file,
                    params.output_format,
                    results,
                    logger
                )
            
            return result
        return wrapper
    return decorator