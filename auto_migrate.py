"""
Auto-migration module for Shopify Automation app.
This module provides functions to automatically migrate the database schema
to support multi-store functionality and new features.
"""

from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from models import db, Product, Tag, Collection, Store, SEODefaults # Ensure SEODefaults is imported

# Helper function to add a column if it doesn't exist
def add_column_if_not_exists(conn, table_name, column_name, column_type):
    """Checks if a column exists and adds it if not."""
    try:
        # Simple check - query the column
        # Use LIMIT 0 for efficiency, we only care about column existence
        conn.execute(text(f"SELECT {column_name} FROM {table_name} LIMIT 0"))
        # print(f"Column '{column_name}' exists in table '{table_name}'.") # Optional: reduce verbosity
    except OperationalError:
        print(f"Adding column '{column_name}' ({column_type}) to table '{table_name}'...")
        try:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
            conn.commit() # Commit after adding column
            print(f"Column '{column_name}' added.")
        except Exception as add_err:
             print(f"Error ADDING column '{column_name}' to table '{table_name}': {add_err}")
             conn.rollback() # Rollback on error
    except Exception as e:
        print(f"Error CHECKING column '{column_name}' in table '{table_name}': {e}")


def run_migrations(app):
    """
    Run database migrations to ensure schema matches models.
    """
    with app.app_context():
        try:
            print("Running database migrations...")

            # --- Ensure Core Tables Exist (using create_all for simplicity) ---
            # Check for a known table like 'stores' or 'products' first
            try:
                 with db.engine.connect() as conn:
                     conn.execute(text("SELECT id FROM stores LIMIT 0"))
                 print("Core tables seem to exist.")
            except OperationalError:
                 print("Core tables not found. Running db.create_all() to initialize schema...")
                 db.create_all()
                 print("db.create_all() completed.")
                 # After initial creation, the rest of the checks might still be needed
                 # if create_all doesn't handle ALTER on existing dbs (depends on Flask-Migrate/Alembic setup)

            # --- Add Specific Columns if Missing (using helper) ---
            # Use a single connection for all ALTER statements in this block
            with db.engine.connect() as conn:
                print("Checking/Adding standard columns...")
                # Existing column checks (simplified using helper)
                add_column_if_not_exists(conn, 'products', 'store_id', 'INTEGER')
                add_column_if_not_exists(conn, 'collections', 'store_id', 'INTEGER')
                add_column_if_not_exists(conn, 'tags', 'store_id', 'INTEGER')
                add_column_if_not_exists(conn, 'collections', 'slug', 'TEXT')
                # The original meta_description in collections is replaced by the one in SEOFields
                # We might need to handle data migration if needed, but for schema, just ensure the new one exists.
                # add_column_if_not_exists(conn, 'collections', 'meta_description', 'TEXT') # Commented out as it's replaced
                add_column_if_not_exists(conn, 'collections', 'shopify_id', 'TEXT')
                add_column_if_not_exists(conn, 'products', 'shopify_id', 'TEXT')
                add_column_if_not_exists(conn, 'products', 'cleaned_title', 'TEXT')

                print("Checking/Adding SEO columns...")
                # --- Add SEO Columns ---
                # Define columns based on SEOFields mixin
                # Note: SQLite type affinity - VARCHAR(n) becomes TEXT, JSON becomes TEXT
                seo_columns = [
                    ('meta_title', 'VARCHAR(60)'),
                    ('meta_description', 'VARCHAR(160)'),
                    ('og_title', 'VARCHAR(95)'),
                    ('og_description', 'VARCHAR(200)'),
                    ('og_image', 'VARCHAR(500)'),
                    ('og_type', 'VARCHAR(50)'),
                    ('twitter_card', 'VARCHAR(15)'), # Consider adding DEFAULT 'summary_large_image' in SQL if needed
                    ('twitter_title', 'VARCHAR(70)'),
                    ('twitter_description', 'VARCHAR(200)'),
                    ('twitter_image', 'VARCHAR(500)'),
                    ('canonical_url', 'VARCHAR(500)'),
                    ('structured_data', 'TEXT') # Use TEXT for SQLite compatibility with JSON
                ]

                for col_name, col_type in seo_columns:
                    add_column_if_not_exists(conn, 'products', col_name, col_type)
                    add_column_if_not_exists(conn, 'collections', col_name, col_type)
                # --- End SEO Columns ---

                # --- Check/Create seo_defaults table ---
                # This table should be created by db.create_all() if it was run,
                # but we add an explicit check here for robustness.
                try:
                    conn.execute(text("SELECT id FROM seo_defaults LIMIT 0"))
                    print("seo_defaults table exists.")
                except OperationalError:
                    print("seo_defaults table not found. Running db.create_all() again...")
                    # This might indicate an issue if create_all didn't work initially
                    db.create_all()
                    print("db.create_all() completed (attempt 2).")
                except Exception as table_check_err:
                    print(f"Error checking seo_defaults table: {table_check_err}")


            # --- Associate orphaned items ---
            # This should run after columns are potentially added
            print("Associating orphaned items...")
            default_store = Store.query.first()
            if default_store:
                 with db.engine.connect() as conn:
                     try:
                         conn.execute(text(f"UPDATE products SET store_id = {default_store.id} WHERE store_id IS NULL"))
                         conn.commit()
                     except Exception as e: print(f"Note: Could not update products store_id: {e}")
                     try:
                         conn.execute(text(f"UPDATE collections SET store_id = {default_store.id} WHERE store_id IS NULL"))
                         conn.commit()
                     except Exception as e: print(f"Note: Could not update collections store_id: {e}")
                     try:
                         conn.execute(text(f"UPDATE tags SET store_id = {default_store.id} WHERE store_id IS NULL"))
                         conn.commit()
                     except Exception as e: print(f"Note: Could not update tags store_id: {e}")
                 print(f"Finished associating orphaned items with default store (ID: {default_store.id}).")
            else:
                print("No default store found to associate items with.")

            print("Database migrations checks completed successfully.")
            return True
        except Exception as e:
            print(f"FATAL Error during migrations: {str(e)}")
            # Optionally re-raise the exception if startup should halt on migration failure
            # raise e
            return False

# Keep migrate_store function as is
def migrate_store(app, store_id):
    """
    Migrate a specific store's data.
    This function associates any orphaned items with the specified store.
    """
    with app.app_context():
        try:
            # Associate any orphaned products, collections, and tags with the specified store
            with db.engine.connect() as conn:
                conn.execute(text(f"UPDATE products SET store_id = {store_id} WHERE store_id IS NULL"))
                conn.execute(text(f"UPDATE collections SET store_id = {store_id} WHERE store_id IS NULL"))
                conn.execute(text(f"UPDATE tags SET store_id = {store_id} WHERE store_id IS NULL"))
                conn.commit() # Commit changes
            print(f"Associated orphaned items with store (ID: {store_id})")
            return True
        except Exception as e:
            print(f"Error during store migration: {str(e)}")
            conn.rollback() # Rollback on error
            return False
