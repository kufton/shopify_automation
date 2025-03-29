"""Add store credentials and cleanup rules tables."""
from flask import Flask
from models import db, Store, Product
from sqlalchemy import text

def run_migrations(app):
    """Run database migrations."""
    with app.app_context():
        # Create all tables first
        db.create_all()

        # Check if cleaned_title column exists using PRAGMA table_info
        result = db.session.execute(text("PRAGMA table_info(products)"))
        columns = [row[1] for row in result]
        has_cleaned_title = 'cleaned_title' in columns

        if not has_cleaned_title:
            print("Adding cleaned_title column to products table...")
            try:
                db.session.execute(text("""
                    ALTER TABLE products ADD COLUMN cleaned_title VARCHAR(255)
                """))
                db.session.commit()  # Commit after altering table
                print("Column cleaned_title added successfully.")
            except Exception as e:
                print(f"Error adding cleaned_title column: {e}")
                db.session.rollback()
                # Optionally, raise the error or handle it
                # return False # Indicate migration failure
        else:
            print("Column cleaned_title already exists.")

        # Create store_credentials table if it doesn't exist
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS store_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id INTEGER NOT NULL,
                key VARCHAR(255) NOT NULL,
                value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (store_id) REFERENCES stores (id) ON DELETE CASCADE,
                UNIQUE (store_id, key)
            )
        """))

        # Create cleanup_rules table if it doesn't exist
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS cleanup_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id INTEGER NOT NULL,
                pattern VARCHAR(255) NOT NULL,
                replacement VARCHAR(255) DEFAULT '',
                is_regex BOOLEAN DEFAULT FALSE,
                priority INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (store_id) REFERENCES stores (id) ON DELETE CASCADE
            )
        """))

        # Create index on cleanup_rules
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_cleanup_rule_store ON cleanup_rules (store_id, priority)
        """))

        # Add some common cleanup rules for each store
        stores = Store.query.all()
        for store in stores:
            common_rules = [
                ("Final Sale!", "", 100),
                ("Cannot Be Returned!", "", 90),
                ("SALE: ", "", 80),
                (" - Final Sale", "", 70),
                (" - Sale", "", 60),
                (" [Sale]", "", 50),
            ]
            
            for pattern, replacement, priority in common_rules:
                db.session.execute(text("""
                    INSERT INTO cleanup_rules (store_id, pattern, replacement, priority)
                    VALUES (:store_id, :pattern, :replacement, :priority)
                    ON CONFLICT DO NOTHING
                """), {
                    'store_id': store.id,
                    'pattern': pattern,
                    'replacement': replacement,
                    'priority': priority
                })

        # Migrate existing store credentials
        db.session.execute(text("""
            INSERT INTO store_credentials (store_id, key, value)
            SELECT s.id, 'shopify_access_token', s.access_token
            FROM stores s
            WHERE s.access_token IS NOT NULL AND s.access_token != ''
        """))

        db.session.commit()

        # Initialize cleaned_title for existing products
        products = Product.query.all()
        for product in products:
            product.clean_title()
        db.session.commit()

        return True

if __name__ == '__main__':
    app = Flask(__name__)
    # Ensure the migration script targets the correct database
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///products_new.db'
    db.init_app(app)
    
    print(f"Running migrations on database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    success = run_migrations(app)
    if success:
        print("Migrations completed successfully")
    else:
        print("Error running migrations")