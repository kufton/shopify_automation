import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-please-change')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///products_new.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # --- AI Provider Configuration ---
    # Select the AI provider ('claude', 'gemini', 'grok', 'llama')
    AI_PROVIDER = os.environ.get('AI_PROVIDER', 'claude').lower()

    # API Keys (keep ANTHROPIC_API_KEY for potential direct use or backward compatibility)
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    GROK_API_KEY = os.environ.get('GROK_API_KEY', '') # Assuming Grok needs one

    # Llama Configuration (for local models via API like Ollama, LM Studio, etc.)
    LLAMA_API_BASE_URL = os.environ.get('LLAMA_API_BASE_URL', '') # e.g., 'http://localhost:11434/v1'
    LLAMA_API_KEY = os.environ.get('LLAMA_API_KEY', 'ollama') # Often not needed or a placeholder

    # Optional Model Override
    # If set, this overrides the default model for the selected provider
    AI_MODEL_NAME = os.environ.get('AI_MODEL_NAME', None)

    # Custom Prompts (as JSON string in env var)
    AI_CUSTOM_PROMPT_JSON = os.environ.get('AI_CUSTOM_PROMPT_JSON', '{}')
    try:
        AI_CUSTOM_PROMPTS = json.loads(AI_CUSTOM_PROMPT_JSON)
        if not isinstance(AI_CUSTOM_PROMPTS, dict):
            print("Warning: AI_CUSTOM_PROMPT_JSON did not parse to a dictionary. Using empty prompts.")
            AI_CUSTOM_PROMPTS = {}
    except json.JSONDecodeError:
        print("Warning: Could not parse AI_CUSTOM_PROMPT_JSON. Using empty prompts.")
        AI_CUSTOM_PROMPTS = {}
    # --- End AI Provider Configuration ---
    
    # Shopify credentials
    SHOPIFY_ACCESS_TOKEN = os.environ.get('SHOPIFY_ACCESS_TOKEN', '')
    SHOPIFY_STORE_URL = os.environ.get('SHOPIFY_STORE_URL', '')
    
    # Default environment variables (add the new ones)
    DEFAULT_ENV_VARS = {
        'SECRET_KEY': 'dev-key-please-change',
        'DATABASE_URI': 'sqlite:///products_new.db',
        'SHOPIFY_ACCESS_TOKEN': '',
        'SHOPIFY_STORE_URL': '',
        'AI_PROVIDER': 'claude',
        'ANTHROPIC_API_KEY': '',
        'GEMINI_API_KEY': '',
        'GROK_API_KEY': '',
        'LLAMA_API_BASE_URL': '',
        'LLAMA_API_KEY': '',
        'AI_MODEL_NAME': '',
        'AI_CUSTOM_PROMPT_JSON': '{}'
    }
    
    @staticmethod
    def init_app(app):
        pass

    @classmethod
    def get_ai_api_key(cls):
        """Returns the API key for the configured AI_PROVIDER."""
        if cls.AI_PROVIDER == 'claude':
            return cls.ANTHROPIC_API_KEY
        elif cls.AI_PROVIDER == 'gemini':
            return cls.GEMINI_API_KEY
        elif cls.AI_PROVIDER == 'grok':
            return cls.GROK_API_KEY
        elif cls.AI_PROVIDER == 'llama':
            # Llama might use a specific key or none depending on the local setup
            return cls.LLAMA_API_KEY
        else:
            return None # Or raise an error for unsupported provider

    @classmethod
    def get_ai_config(cls):
        """Returns a dictionary with relevant AI configuration."""
        return {
            "provider": cls.AI_PROVIDER,
            "api_key": cls.get_ai_api_key(),
            "model_name": cls.AI_MODEL_NAME, # Will be None if not set
            "custom_prompts": cls.AI_CUSTOM_PROMPTS,
            # Add provider-specific details if needed, e.g., base URL for Llama
            "llama_base_url": cls.LLAMA_API_BASE_URL if cls.AI_PROVIDER == 'llama' else None
        }
