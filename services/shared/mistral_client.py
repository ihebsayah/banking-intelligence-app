import requests
import json
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class MistralClient:
    """
    Client for Mistral LLM via Ollama.
    Uses Ollama REST API (no Python client needed).
    """
    def __init__(self, base_url: str, model: str, timeout: int = 120, max_tokens: int = 1000):
        self.base_url = base_url  # http://localhost:11434
        self.model = model  # mistral
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.health_checked = False

    async def check_health(self) -> bool:
        """Verify Ollama is running and mistral model is available."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                model_names = [m.get("name", "") for m in models]
                
                if any(self.model in name for name in model_names):
                    logger.info(f"✅ Mistral model available: {self.model}")
                    self.health_checked = True
                    return True
                else:
                    logger.error(f"❌ Mistral model '{self.model}' not found in Ollama")
                    logger.error(f"   Available models: {model_names}")
                    return False
        except Exception as e:
            logger.error(f"❌ Cannot connect to Ollama at {self.base_url}: {str(e)}")
            return False

    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate response from Mistral using Ollama API.
        
        Args:
            prompt: User message
            system_prompt: Optional system instruction
        
        Returns:
            Generated text from Mistral
        """
        
        if not self.health_checked:
            healthy = await self.check_health()
            if not healthy:
                raise RuntimeError("Mistral/Ollama not available")
        
        try:
            # Build the full prompt
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            # Call Ollama API
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "temperature": 0.7,
                    "num_predict": self.max_tokens,
                    "timeout": self.timeout
                },
                timeout=self.timeout + 10
            )
            
            if response.status_code == 200:
                data = response.json()
                generated_text = data.get("response", "").strip()
                
                if not generated_text:
                    logger.error("Mistral returned empty response")
                    raise ValueError("Empty response from Mistral")
                
                return generated_text
            
            else:
                logger.error(f"Mistral API error: {response.status_code}")
                logger.error(f"Response: {response.text}")
                raise RuntimeError(f"Mistral error: {response.status_code}")
        
        except requests.Timeout:
            logger.error(f"Mistral request timeout after {self.timeout}s")
            raise RuntimeError("Mistral request timeout")
        
        except Exception as e:
            logger.error(f"Mistral generation failed: {str(e)}")
            raise RuntimeError(f"Mistral error: {str(e)}")
