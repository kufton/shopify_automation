"""
Auto-migration module for Shopify Automation app.
This module provides functions to automatically migrate the database schema
to support multi-store functionality.
"""

from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from models import db, Product, Tag, Collection, Store

def run_migrations(app):
    """
    Run database migrations to ensure multi-store support.
    
    This function checks if the necessary columns exist in the database tables
    and adds them if they don't. It also associates any orphaned items with
    the default store.
    
    Args:
        app: The Flask application instance
    """
    with app.app_context():
        try:
            print("Running database migrations...")
            
            # Check if store_id column exists in products table
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("SELECT store_id FROM products LIMIT 1"))
                print("store_id column exists in products table")
            except OperationalError:
                print("Adding store_id column to products table")
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE products ADD COLUMN store_id INTEGER"))
            
            # Check if store_id column exists in collections table
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("SELECT store_id FROM collections LIMIT 1"))
                print("store_id column exists in collections table")
            except OperationalError:
                print("Adding store_id column to collections table")
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE collections ADD COLUMN store_id INTEGER"))
            
            # Check if store_id column exists in tags table
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("SELECT store_id FROM tags LIMIT 1"))
                print("store_id column exists in tags table")
            except OperationalError:
                print("Adding store_id column to tags table")
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE tags ADD COLUMN store_id INTEGER"))
            
            # Associate all products, collections, and tags with the default store if they don't have a store_id
            default_store = Store.query.first()
            if default_store:
                with db.engine.connect() as conn:
                    conn.execute(text(f"UPDATE products SET store_id = {default_store.id} WHERE store_id IS NULL"))
                    conn.execute(text(f"UPDATE collections SET store_id = {default_store.id} WHERE store_id IS NULL"))
                    conn.execute(text(f"UPDATE tags SET store_id = {default_store.id} WHERE store_id IS NULL"))
                print(f"Associated orphaned items with default store (ID: {default_store.id})")
            
            # Check if slug column exists in collections table
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("SELECT slug FROM collections LIMIT 1"))
                print("slug column exists in collections table")
            except OperationalError:
                print("Adding slug column to collections table")
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE collections ADD COLUMN slug TEXT"))
            
            # Check if meta_description column exists in collections table
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("SELECT meta_description FROM collections LIMIT 1"))
                print("meta_description column exists in collections table")
            except OperationalError:
                print("Adding meta_description column to collections table")
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE collections ADD COLUMN meta_description TEXT"))
            
            # Check if shopify_id column exists in collections table
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("SELECT shopify_id FROM collections LIMIT 1"))
                print("shopify_id column exists in collections table")
            except OperationalError:
                print("Adding shopify_id column to collections table")
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE collections ADD COLUMN shopify_id TEXT"))
            
            # Check if shopify_id column exists in products table
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("SELECT shopify_id FROM products LIMIT 1"))
                print("shopify_id column exists in products table")
            except OperationalError:
                print("Adding shopify_id column to products table")
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE products ADD COLUMN shopify_id TEXT"))
            
            print("Database migrations completed successfully")
            return True
        except Exception as e:
            print(f"Error during migrations: {str(e)}")
            return False

def migrate_store(app, store_id):
    """
    Migrate a specific store's data.
    
    This function associates any orphaned items with the specified store.
    
    Args:
        app: The Flask application instance
        store_id: The ID of the store to migrate
    """
    with app.app_context():
        try:
            # Associate any orphaned products, collections, and tags with the specified store
            with db.engine.connect() as conn:
                conn.execute(text(f"UPDATE products SET store_id = {store_id} WHERE store_id IS NULL"))
                conn.execute(text(f"UPDATE collections SET store_id = {store_id} WHERE store_id IS NULL"))
                conn.execute(text(f"UPDATE tags SET store_id = {store_id} WHERE store_id IS NULL"))
            print(f"Associated orphaned items with store (ID: {store_id})")
            return True
        except Exception as e:
            print(f"Error during store migration: {str(e)}")
            return False
