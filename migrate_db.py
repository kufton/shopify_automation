import sqlite3
import os
from config import Config

def migrate_database():
    """Migrate the database to add new columns to the collections table."""
    print("Starting database migration...")
    
    # Get the database path from the config
    db_uri = Config.SQLALCHEMY_DATABASE_URI
    print(f"Database URI from config: {db_uri}")
    
    # List files in current directory
    print(f"Current working directory: {os.getcwd()}")
    print("Files in current directory:")
    for file in os.listdir(os.getcwd()):
        print(f"  - {file}")
    
    # Handle different URI formats
    if db_uri.startswith('sqlite:///'):
        # Relative path
        db_path = os.path.join(os.getcwd(), db_uri.replace('sqlite:///', ''))
    elif db_uri.startswith('sqlite:////'):
        # Absolute path
        db_path = db_uri.replace('sqlite:////', '')
    else:
        print(f"Unsupported database URI: {db_uri}")
        return False
    
    print(f"Using database at: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}")
        # Try to find the database file in the instance folder
        instance_path = os.path.join(os.getcwd(), 'instance')
        if os.path.exists(instance_path):
            print(f"Checking instance folder: {instance_path}")
            for file in os.listdir(instance_path):
                print(f"  - {file}")
                if file.endswith('.db'):
                    db_path = os.path.join(instance_path, file)
                    print(f"Found database file: {db_path}")
                    break
        
        if not os.path.exists(db_path):
            print(f"Database file not found at {db_path}")
            return False
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if the slug column exists
        cursor.execute("PRAGMA table_info(collections)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        # Add the slug column if it doesn't exist
        if 'slug' not in column_names:
            print("Adding slug column to collections table...")
            cursor.execute("ALTER TABLE collections ADD COLUMN slug TEXT")
        
        # Add the meta_description column if it doesn't exist
        if 'meta_description' not in column_names:
            print("Adding meta_description column to collections table...")
            cursor.execute("ALTER TABLE collections ADD COLUMN meta_description TEXT")
        
        # Add the shopify_id column if it doesn't exist
        if 'shopify_id' not in column_names:
            print("Adding shopify_id column to collections table...")
            cursor.execute("ALTER TABLE collections ADD COLUMN shopify_id TEXT")
        
        # Commit the changes
        conn.commit()
        print("Database migration completed successfully!")
        return True
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()
