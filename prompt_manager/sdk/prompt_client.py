import os
import requests
from typing import Optional, Dict, Any
from datetime import datetime

class PromptClient:
    def __init__(self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None):
        """Initialize the Prompt Management Client"""
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key or os.getenv("PROMPT_MANAGER_API_KEY")
        self.session = requests.Session()
        
        # Configure session headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        self.session.headers.update(headers)
    
    def get_prompt(self, name: str, version: str = "latest") -> Dict[str, Any]:
        """Get a prompt by name and optional version"""
        try:
            response = self.session.get(
                f"{self.base_url}/prompts/{name}",
                params={"version": version}
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching prompt: {e}")
            raise
    
    def create_prompt(self, name: str, content: str, version: str, 
                     created_by: str, description: str = "", 
                     tags: Optional[list] = None) -> Dict[str, Any]:
        """Create a new prompt version"""
        try:
            data = {
                "name": name,
                "content": content,
                "version": version,
                "created_by": created_by,
                "description": description,
                "tags": tags or []
            }
            
            response = self.session.post(
                f"{self.base_url}/prompts/",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error creating prompt: {e}")
            raise
    
    def list_versions(self, name: str) -> list:
        """List all versions of a prompt"""
        try:
            response = self.session.get(
                f"{self.base_url}/prompts/{name}/versions"
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error listing versions: {e}")
            raise

# Example usage
if __name__ == "__main__":
    # Initialize the client
    client = PromptClient()
    
    # Example: Get the latest version of a prompt
    try:
        prompt = client.get_prompt("customer_support_assistant")
        print(f"Latest prompt: {prompt}")
        
        # Example: Create a new prompt version
        new_prompt = client.create_prompt(
            name="customer_support_assistant",
            content="You are a helpful customer support assistant...",
            version="1.0.1",
            created_by="john.doe@example.com",
            description="Updated customer support prompt with new guidelines",
            tags=["customer_support", "v1.0.1"]
        )
        print(f"Created new prompt version: {new_prompt}")
        
        # List all versions
        versions = client.list_versions("customer_support_assistant")
        print(f"Available versions: {versions}")
        
    except Exception as e:
        print(f"An error occurred: {e}")
