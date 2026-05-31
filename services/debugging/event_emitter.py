import asyncio
from typing import Callable, List, Dict, Any
import json

class EventEmitter:
    """Emits real-time events to connected WebSocket clients"""
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {
            "agent_executed": [],
            "request_completed": [],
            "error_occurred": [],
            "cache_hit": []
        }
    
    async def emit(self, event_type: str, data: Dict[str, Any]):
        """Emit event to all subscribers"""
        if event_type in self.subscribers:
            # Create a copy of subscribers list to avoid issues if someone unsubscribes during loop
            callbacks = list(self.subscribers[event_type])
            for callback in callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    print(f"Error in event handler: {e}")
    
    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to event"""
        if event_type in self.subscribers:
            self.subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: Callable):
        """Unsubscribe from event"""
        if event_type in self.subscribers:
            try:
                self.subscribers[event_type].remove(callback)
            except ValueError:
                pass

# Global emitter
event_emitter = EventEmitter()
