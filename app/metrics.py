from typing import Dict
from collections import defaultdict
import time

class MetricsCollector:
    def __init__(self):
        self.counters = defaultdict(int)
        self.start_time = time.time()
    
    def increment(self, metric_name: str, value: int = 1):
        """Increment a counter metric"""
        self.counters[metric_name] += value
    
    def get_metrics(self) -> Dict:
        """Get all metrics"""
        uptime_seconds = time.time() - self.start_time
        return {
            "counters": dict(self.counters),
            "uptime_seconds": uptime_seconds
        }

# Global metrics instance
metrics = MetricsCollector()

