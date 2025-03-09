"""
Script to migrate a specific store's data.
This script is used to associate orphaned products, collections, and tags with a specific store.
"""

import sys
import os
from flask import Flask
from models import db, Store
from auto_migrate import migrate_store
from config import Config

def main():
    """
    Main function to migrate a store's data.
    
    Usage:
        python migrate_store.py <store_id>
    """
    if len(sys.argv) < 2:
        print("Usage: python migrate_store.py <store_id>")
        sys.exit(1)
    
    try:
        store_id = int(sys.argv[1])
    except ValueError:
        print("Error: store_id must be an integer")
        sys.exit(1)
    
    # Create a Flask app
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize the database
    db.init_app(app)
    
    # Check if the store exists
    with app.app_context():
        store = Store.query.get(store_id)
        if not store:
            print(f"Error: Store with ID {store_id} not found")
            sys.exit(1)
        
        print(f"Migrating store: {store.name} (ID: {store.id})")
        
        # Run the migration
        success = migrate_store(app, store_id)
        
        if success:
            print(f"Successfully migrated store: {store.name} (ID: {store.id})")
        else:
            print(f"Error migrating store: {store.name} (ID: {store.id})")

if __name__ == "__main__":
    main()
