#!/usr/bin/env python3
"""
Startup script for the Prompt Management System
Starts both the FastAPI backend and Streamlit UI
"""

import subprocess
import sys
import time
import os
import signal
from pathlib import Path
from typing import Optional

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.absolute()

def start_fastapi() -> Optional[subprocess.Popen]:
    """Start the FastAPI backend server"""
    print("🚀 Starting FastAPI backend server...")
    
    try:
        # Start FastAPI server
        fastapi_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "prompt_manager.app.main:app", "--reload"],
            cwd=PROJECT_ROOT,
            env={
                **os.environ,
                "PYTHONPATH": str(PROJECT_ROOT),
                "LOG_LEVEL": "INFO"
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait a moment for the server to start
        time.sleep(3)
        return fastapi_process
        
    except Exception as e:
        print(f"❌ Failed to start FastAPI server: {e}")
        return None
    
    return fastapi_process

def start_streamlit() -> Optional[subprocess.Popen]:
    """Start the Streamlit UI"""
    print("🎨 Starting Streamlit UI...")
    
    try:
        # Start Streamlit UI
        streamlit_process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "streamlit_ui.py"],
            cwd=PROJECT_ROOT,
            env={
                **os.environ,
                "PYTHONPATH": str(PROJECT_ROOT),
                "LOG_LEVEL": "INFO"
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait a moment for the UI to start
        time.sleep(3)
        return streamlit_process
        
    except Exception as e:
        print(f"❌ Failed to start Streamlit UI: {e}")
        return None

def cleanup(processes: list[subprocess.Popen]):
    """Cleanup function to terminate all processes"""
    for process in processes:
        if process and process.poll() is None:  # If process is still running
            print(f"🛑 Terminating process {process.pid}")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

def main():
    """Main function to start both services"""
    processes = []
    
    try:
        # Start FastAPI backend
        fastapi_process = start_fastapi()
        if fastapi_process:
            processes.append(fastapi_process)
            print(f"✅ FastAPI server started (PID: {fastapi_process.pid})")
        else:
            print("❌ Failed to start FastAPI server")
            cleanup(processes)
            return
        
        # Start Streamlit UI
        streamlit_process = start_streamlit()
        if streamlit_process:
            processes.append(streamlit_process)
            print(f"✅ Streamlit UI started (PID: {streamlit_process.pid})")
            print("\n🌐 Access the application at: http://localhost:8501")
        else:
            print("❌ Failed to start Streamlit UI")
            cleanup(processes)
            return
        
        # Keep the script running
        while any(p.poll() is None for p in processes if p):
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Shutting down services...")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
    finally:
        cleanup(processes)
        print("✅ All services have been stopped")

if __name__ == "__main__":
    main()

def main():
    """Main startup function"""
    print("=" * 60)
    print("🚀 Prompt Management System Startup")
    print("=" * 60)
    
    try:
        # Start FastAPI backend
        fastapi_proc = start_fastapi()
        
        # Start Streamlit UI
        streamlit_proc = start_streamlit()
        
        print("\n✅ Both services started successfully!")
        print("\n📋 Access Points:")
        print("   • FastAPI Backend: http://localhost:8000")
        print("   • API Documentation: http://localhost:8000/docs")
        print("   • Streamlit UI: http://localhost:8501")
        print("\n⚠️  Press Ctrl+C to stop both services")
        
        # Wait for user interrupt
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down services...")
            
            # Terminate processes
            fastapi_proc.terminate()
            streamlit_proc.terminate()
            
            # Wait for clean shutdown
            fastapi_proc.wait(timeout=5)
            streamlit_proc.wait(timeout=5)
            
            print("✅ Services stopped successfully!")
            
    except Exception as e:
        print(f"❌ Error starting services: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
