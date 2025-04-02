Kaleb's updates to apply it for his agency EKOH Marketing, and other in house uses.


## Todo's
~~1. add other llm's~~
2. fix tagging display issue and trackign what tags we've added
3. symantic keyword maps from the concept of the site
4. blog generation and drafting from most popular tags
5. long tail seo optimization
6. Backlink research???



Credit to  Hamish and the team from who this was forked.
## Product Manager with Claude 3.7 and Shopify Integration

A Flask-based product management application with automatic tagging using Claude 3.7 and Shopify integration. Supports multiple stores with isolated data.

## 🚀 SEO Solutions for Your Business

- **Hire us to do your SEO** ✅ [Click here](https://bit.ly/3X4Bjps)  
- **Try our AI SEO tool** 🔥 [Check it out](https://bit.ly/3CHQ7DK)  
- **Got an agency? We'll automate it** 💣 [Learn more](https://bit.ly/3X4Bjps)  


## Features

- Product management (add, edit, delete)
- Automatic product tagging with Claude 3.7
- Tag management
- Collection creation from tags
- Shopify integration (import/export products and collections)
- Multi-store support with isolated data
- Environment variable management
- Responsive UI with Bootstrap 5

## Requirements

- Python 3.8+
- Flask
- SQLAlchemy
- Anthropic API key (for Claude 3.7 integration)

## Installation

1. Clone the repository or download the source code.

2. Install the required dependencies:

```bash
cd product_manager
pip install -r requirements.txt
```

3. Run the application:

```bash
python app.py
```

4. Open your browser and navigate to `http://localhost:5000`

## Configuration

The application uses environment variables for configuration. These can be managed through the UI:

- `ANTHROPIC_API_KEY`: Your Anthropic API key for Claude 3.7 integration
- `SECRET_KEY`: Secret key for Flask session security
- `DATABASE_URI`: Database connection string (default: SQLite)

## Usage

### Stores

- Create and manage multiple stores
- Each store has its own products, tags, and collections
- Switch between stores using the store selector
- Data is isolated between stores

### Products

- Add products with title, description, price, and image URL
- Products are automatically tagged using Claude 3.7 if an API key is provided
- Manage tags for each product
- View all products in a table
- Products are associated with the current store

### Tags

- View all tags with product counts
- Create collections from tags
- Delete tags
- Tags are store-specific

### Collections

- Create collections based on tags
- View products in collections
- Edit and delete collections
- Collections are store-specific

### Environment Variables

- Manage environment variables through the UI
- Secure storage of sensitive information like API keys
- Environment variables are shared across all stores

## Claude 3.7 Integration

The application uses Claude 3.7 for:

1. Automatic product tagging based on title and description
2. Analyzing products to determine appropriate collections

To enable these features, you need to:

1. Get an API key from [Anthropic Console](https://console.anthropic.com/)
2. Add it as an environment variable with the key `ANTHROPIC_API_KEY`

## Shopify Integration

The application integrates with Shopify to:

1. Import products from your Shopify store
2. Export products to your Shopify store
3. Export collections to your Shopify store as custom collections

To enable these features, you need to:

1. Set up a Shopify store and get an access token
2. Add the following environment variables:
   - `SHOPIFY_ACCESS_TOKEN`: Your Shopify access token
   - `SHOPIFY_STORE_URL`: Your Shopify store URL (e.g., `https://your-store.myshopify.com`)
3. Or configure these settings per store in the store management interface

### Using Shopify Integration

- **Import Products**: Click the "Import from Shopify" button on the Products page to import products from your Shopify store
- **Export Product**: When editing a product, click the "Export to Shopify" button to export the product to your Shopify store
- **Export Collection**: When viewing a collection, click the "Export to Shopify" button to export the collection to your Shopify store

Imported products will maintain their Shopify ID for syncing, and any tags will be imported as well.

## Multi-Store Support

The application supports managing multiple Shopify stores:

1. Each store has its own isolated set of products, tags, and collections
2. You can switch between stores using the store selector in the navigation bar
3. When adding a new store, you can specify:
   - Store name
   - Shopify store URL
   - Shopify access token

### Database Migrations

The application includes tools for database migrations:

- `auto_migrate.py`: Contains functions to automatically migrate the database schema
- `migrate_store.py`: Command-line tool to migrate a specific store's data

To migrate a specific store:

```bash
python migrate_store.py <store_id>
```

You can also trigger migrations through the web interface by visiting `/migrate-database`.

## License

MIT
