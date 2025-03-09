from flask import Flask
from models import db, Product, Tag, Collection, EnvVar
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    # Create tables
    db.create_all()
    
    # Check if tables exist
    print("Checking database tables...")
    
    # Check Products table
    products = Product.query.all()
    print(f"Products table exists, found {len(products)} products")
    
    # Check Tags table
    tags = Tag.query.all()
    print(f"Tags table exists, found {len(tags)} tags")
    
    # Check Collections table
    collections = Collection.query.all()
    print(f"Collections table exists, found {len(collections)} collections")
    
    # Check EnvVars table
    env_vars = EnvVar.query.all()
    print(f"EnvVars table exists, found {len(env_vars)} environment variables")
    
    print("Database check completed successfully!")
