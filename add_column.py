import sqlite3
import os

def add_column():
    """Add the shopify_id column to the collections table."""
    print("Adding shopify_id column to collections table...")
    
    # Connect to the database
    db_path = os.path.join(os.getcwd(), 'instance', 'products.db')
    print(f"Using database at: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Add the shopify_id column if it doesn't exist
        cursor.execute("PRAGMA table_info(collections)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        if 'shopify_id' not in column_names:
            print("Adding shopify_id column to collections table...")
            cursor.execute("ALTER TABLE collections ADD COLUMN shopify_id TEXT")
            print("Column added successfully!")
        else:
            print("shopify_id column already exists.")
        
        # Commit the changes
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding column: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    add_column()
