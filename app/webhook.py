import httpx
import os
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

WEBHOOK_URL = os.getenv("WEBHOOK_URL", None)

async def emit_webhook_event(event_type: str, payload: Dict[str, Any]):
    """Emit a webhook event to the configured URL"""
    if not WEBHOOK_URL:
        # No webhook configured, skip
        return
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                WEBHOOK_URL,
                json={
                    "event_type": event_type,
                    "payload": payload,
                    "timestamp": str(__import__("datetime").datetime.now())
                },
                timeout=5.0
            )
            response.raise_for_status()
            logger.info(f"Webhook event emitted: {event_type}")
    except Exception as e:
        logger.error(f"Failed to emit webhook event: {str(e)}")


