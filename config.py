import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-please-change')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///products_new.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Claude API key
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    
    # Shopify credentials
    SHOPIFY_ACCESS_TOKEN = os.environ.get('SHOPIFY_ACCESS_TOKEN', '')
    SHOPIFY_STORE_URL = os.environ.get('SHOPIFY_STORE_URL', '')
    
    # Default environment variables
    DEFAULT_ENV_VARS = {
        'ANTHROPIC_API_KEY': '',
        'DATABASE_URI': 'sqlite:///products_new.db',
        'SECRET_KEY': 'dev-key-please-change',
        'SHOPIFY_ACCESS_TOKEN': '',
        'SHOPIFY_STORE_URL': ''
    }
    
    @staticmethod
    def init_app(app):
        pass
