# This file makes the ai_services directory a Python package.

from config import Config
from .base import BaseAIService
from .claude import ClaudeService
# Import other services when they are created
from .gemini import GeminiService
# from .grok import GrokService
# from .llama import LlamaService

def get_ai_service() -> BaseAIService:
    """
    Factory function to get the configured AI service instance.
    """
    ai_config = Config.get_ai_config()
    provider = ai_config.get("provider", "").lower() # Get provider and convert to lowercase
    api_key = ai_config.get("api_key")
    model_name = ai_config.get("model_name") # Optional override
    custom_prompts = ai_config.get("custom_prompts")

    print(f"Initializing AI service for provider: {provider}")

    if provider == 'claude':
        return ClaudeService(api_key=api_key, model_name=model_name, custom_prompts=custom_prompts)
    elif provider == 'gemini':
        # Ensure GeminiService is imported (done above)
        return GeminiService(api_key=api_key, model_name=model_name, custom_prompts=custom_prompts)
    # elif provider == 'grok':
    #     # from .grok import GrokService
    #     # return GeminiService(api_key=api_key, model_name=model_name, custom_prompts=custom_prompts)
    #     print(f"Warning: AI Provider '{provider}' selected but not implemented yet. Falling back to Claude.")
    #     return ClaudeService(api_key=Config.ANTHROPIC_API_KEY, model_name=model_name, custom_prompts=custom_prompts) # Fallback for now
    # elif provider == 'grok':
    #     # from .grok import GrokService
    #     # return GrokService(api_key=api_key, model_name=model_name, custom_prompts=custom_prompts)
    #     print(f"Warning: AI Provider '{provider}' selected but not implemented yet. Falling back to Claude.")
    #     return ClaudeService(api_key=Config.ANTHROPIC_API_KEY, model_name=model_name, custom_prompts=custom_prompts) # Fallback for now
    # elif provider == 'llama':
    #     # from .llama import LlamaService
    #     # llama_base_url = ai_config.get("llama_base_url")
    #     # return LlamaService(api_base_url=llama_base_url, api_key=api_key, model_name=model_name, custom_prompts=custom_prompts)
    #     print(f"Warning: AI Provider '{provider}' selected but not implemented yet. Falling back to Claude.")
    #     return ClaudeService(api_key=Config.ANTHROPIC_API_KEY, model_name=model_name, custom_prompts=custom_prompts) # Fallback for now
    else:
        print(f"Warning: Unknown AI Provider '{provider}' configured. Falling back to Claude.")
        # Fallback to Claude or raise an error
        return ClaudeService(api_key=Config.ANTHROPIC_API_KEY, model_name=model_name, custom_prompts=custom_prompts) # Default/Fallback

# Make the factory function easily accessible
__all__ = ['BaseAIService', 'ClaudeService', 'GeminiService', 'get_ai_service']