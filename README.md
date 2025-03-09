# Product Manager with Claude 3.7 and Shopify Integration

A Flask-based product management application with automatic tagging using Claude 3.7 and Shopify integration.

## Features

- Product management (add, edit, delete)
- Automatic product tagging with Claude 3.7
- Tag management
- Collection creation from tags
- Shopify integration (import/export products and collections)
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

### Products

- Add products with title, description, price, and image URL
- Products are automatically tagged using Claude 3.7 if an API key is provided
- Manage tags for each product
- View all products in a table

### Tags

- View all tags with product counts
- Create collections from tags
- Delete tags

### Collections

- Create collections based on tags
- View products in collections
- Edit and delete collections

### Environment Variables

- Manage environment variables through the UI
- Secure storage of sensitive information like API keys

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

### Using Shopify Integration

- **Import Products**: Click the "Import from Shopify" button on the Products page to import products from your Shopify store
- **Export Product**: When editing a product, click the "Export to Shopify" button to export the product to your Shopify store
- **Export Collection**: When viewing a collection, click the "Export to Shopify" button to export the collection to your Shopify store

Imported products will maintain their Shopify ID for syncing, and any tags will be imported as well.

## License

MIT
