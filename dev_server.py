#!/usr/bin/env python3
"""
Development server startup script.
"""
import uvicorn

from shared.config.settings import settings

print(f"Starting environment settings for: {settings.environment}")   

def main():
    """Development server entry point."""
    uvicorn.run(
        "invoice_lifecycle_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
