"""
Script to clear the database and start fresh.
This will delete all data in the database and recreate the tables.
"""

import os
from flask import Flask
from models import db
from config import Config

def clear_database():
    """Clear the database and recreate tables."""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize the database
    db.init_app(app)
    
    with app.app_context():
        # Drop all tables
        db.drop_all()
        print("All tables dropped.")
        
        # Recreate all tables
        db.create_all()
        print("All tables recreated.")
        
        print("Database cleared successfully.")

if __name__ == "__main__":
    clear_database()
