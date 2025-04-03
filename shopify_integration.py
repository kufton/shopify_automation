import requests
import json
from config import Config
from models import Product, Tag, Collection

class ShopifyIntegration:
    """Integration with Shopify API."""

    def __init__(self, access_token=None, store_url=None):
        """Initialize the Shopify API client with default/global config."""
        # Store default/global config if needed as fallback
        self.default_access_token = access_token or Config.SHOPIFY_ACCESS_TOKEN
        self.default_store_url = store_url or Config.SHOPIFY_STORE_URL

        # Initialize with defaults, will be overridden by set_store_context
        self.access_token = self.default_access_token
        self.store_url = self.default_store_url
        self._update_headers() # Initial header setup

    def _update_headers(self):
        """Internal method to update headers based on current token and URL."""
        temp_url = self.store_url

        if temp_url:
            # Ensure the URL starts with https://
            if not temp_url.startswith(('http://', 'https://')):
                temp_url = f"https://{temp_url}"
            
            # Remove trailing slash from store URL if present
            if temp_url.endswith('/'):
                temp_url = temp_url[:-1]

        self.headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }
        # Update the store_url attribute after potential modification
        self.store_url = temp_url

    def set_store_context(self, store):
        """Set the Shopify credentials based on the provided store object. Returns True if successful."""
        if store and store.access_token and store.url:
            self.access_token = store.access_token
            self.store_url = store.url
            self._update_headers()
            print(f"ShopifyIntegration context set for store: {store.name} ({self.store_url})") # Debugging
            return True
        else:
            # Clear context if store is invalid or lacks credentials
            self.access_token = None
            self.store_url = None
            self.headers = {}
            store_name = store.name if store else 'None'
            print(f"ShopifyIntegration context FAILED for store: {store_name}. Missing credentials.") # Debugging
            return False

    def is_configured(self):
        """Check if Shopify integration is currently configured with valid credentials."""
        # This now checks the *currently set* context
        return bool(self.access_token and self.store_url)
    
    def get_products(self, limit=50):
        """Fetch products from Shopify."""
        if not self.is_configured():
            return {'error': 'Shopify integration not configured'}
        
        url = f"{self.store_url}/admin/api/2023-07/products.json?limit={limit}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
    
    def get_product(self, product_id):
        """Fetch a specific product from Shopify."""
        if not self.is_configured():
            return {'error': 'Shopify integration not configured'}
        
        url = f"{self.store_url}/admin/api/2023-07/products/{product_id}.json"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
    
    def create_product(self, product_data):
        """Create a product in Shopify."""
        if not self.is_configured():
            return {'error': 'Shopify integration not configured'}
        
        url = f"{self.store_url}/admin/api/2023-07/products.json"
        
        try:
            response = requests.post(url, headers=self.headers, json=product_data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
    
    def update_product(self, product_id, product_data):
        """Update a product in Shopify."""
        if not self.is_configured():
            return {'error': 'Shopify integration not configured'}
        
        url = f"{self.store_url}/admin/api/2023-07/products/{product_id}.json"
        
        try:
            print(f"Updating product {product_id} in Shopify with data: {json.dumps(product_data, indent=2)}")
            response = requests.put(url, headers=self.headers, json=product_data)
            
            # Print response details for debugging
            print(f"Shopify API Response Status: {response.status_code}")
            print(f"Shopify API Response Headers: {response.headers}")
            
            try:
                response_json = response.json()
                print(f"Shopify API Response Body: {json.dumps(response_json, indent=2)}")
            except:
                print(f"Shopify API Response Body (not JSON): {response.text}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            
            # Try to get more detailed error information
            try:
                if hasattr(e, 'response') and e.response is not None:
                    error_json = e.response.json()
                    if 'errors' in error_json:
                        error_msg = f"{error_msg} - Details: {json.dumps(error_json['errors'])}"
            except:
                pass
                
            print(f"Error updating product in Shopify: {error_msg}")
            return {'error': error_msg}
    
    def delete_product(self, product_id):
        """Delete a product from Shopify."""
        if not self.is_configured():
            return {'error': 'Shopify integration not configured'}
        
        url = f"{self.store_url}/admin/api/2023-07/products/{product_id}.json"
        
        try:
            response = requests.delete(url, headers=self.headers)
            response.raise_for_status()
            return {'success': True}
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
    
    def get_collections(self):
        """Fetch custom collections from Shopify."""
        if not self.is_configured():
            return {'error': 'Shopify integration not configured'}
        
        url = f"{self.store_url}/admin/api/2023-07/custom_collections.json"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
    
    def get_all_collections(self):
        """Fetch all collections from Shopify using pagination."""
        if not self.is_configured():
            return {'error': 'Shopify integration not configured'}
        
        all_collections = []
        page_info = None
        limit = 250  # Maximum allowed by Shopify API
        
        # First, get custom collections
        while True:
            url = f"{self.store_url}/admin/api/2023-07/custom_collections.json?limit={limit}"
            
            # Add pagination parameter if we have a page_info token
            if page_info:
                url += f"&page_info={page_info}"
            
            try:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                
                # Get collections from response
                collections_page = response.json().get('custom_collections', [])
                all_collections.extend(collections_page)
                
                # Check if there are more pages
                link_header = response.headers.get('Link')
                if not link_header or 'rel="next"' not in link_header:
                    break
                
                # Extract the page_info parameter from the Link header
                next_link = [link for link in link_header.split(',') if 'rel="next"' in link][0]
                page_info = next_link.split('page_info=')[1].split('&')[0].split('>')[0]
                
                print(f"Fetched {len(collections_page)} custom collections, total so far: {len(all_collections)}")
                
                # If we got fewer collections than the limit, we're done
                if len(collections_page) < limit:
                    break
                
            except requests.exceptions.RequestException as e:
                return {'error': str(e)}
        
        # Now, get smart collections
        page_info = None
        while True:
            url = f"{self.store_url}/admin/api/2023-07/smart_collections.json?limit={limit}"
            
            # Add pagination parameter if we have a page_info token
            if page_info:
                url += f"&page_info={page_info}"
            
            try:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                
                # Get collections from response
                collections_page = response.json().get('smart_collections', [])
                all_collections.extend(collections_page)
                
                # Check if there are more pages
                link_header = response.headers.get('Link')
                if not link_header or 'rel="next"' not in link_header:
                    break
                
                # Extract the page_info parameter from the Link header
                next_link = [link for link in link_header.split(',') if 'rel="next"' in link][0]
                page_info = next_link.split('page_info=')[1].split('&')[0].split('>')[0]
                
                print(f"Fetched {len(collections_page)} smart collections, total so far: {len(all_collections)}")
                
                # If we got fewer collections than the limit, we're done
                if len(collections_page) < limit:
                    break
                
            except requests.exceptions.RequestException as e:
                return {'error': str(e)}
        
        return {'collections': all_collections}
    
    def create_collection(self, collection_data):
        """Create a custom collection in Shopify."""
        if not self.is_configured():
            return {'error': 'Shopify integration not configured'}
        
        url = f"{self.store_url}/admin/api/2023-07/custom_collections.json"
        
        try:
            response = requests.post(url, headers=self.headers, json=collection_data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
    
    def add_product_to_collection(self, collection_id, product_id):
        """Add a product to a collection in Shopify."""
        if not self.is_configured():
            return {'error': 'Shopify integration not configured'}
        
        url = f"{self.store_url}/admin/api/2023-07/collects.json"
        
        collect_data = {
            "collect": {
                "product_id": product_id,
                "collection_id": collection_id
            }
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=collect_data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
    
    def get_all_products(self):
        """Fetch all products from Shopify using pagination."""
        if not self.is_configured():
            return {'error': 'Shopify integration not configured'}
        
        all_products = []
        page_info = None
        limit = 250  # Maximum allowed by Shopify API
        
        while True:
            url = f"{self.store_url}/admin/api/2023-07/products.json?limit={limit}"
            
            # Add pagination parameter if we have a page_info token
            if page_info:
                url += f"&page_info={page_info}"
            
            try:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                
                # Get products from response
                products_page = response.json().get('products', [])
                all_products.extend(products_page)
                
                # Check if there are more pages
                link_header = response.headers.get('Link')
                if not link_header or 'rel="next"' not in link_header:
                    break
                
                # Extract the page_info parameter from the Link header
                next_link = [link for link in link_header.split(',') if 'rel="next"' in link][0]
                page_info = next_link.split('page_info=')[1].split('&')[0].split('>')[0]
                
                print(f"Fetched {len(products_page)} products, total so far: {len(all_products)}")
                
                # If we got fewer products than the limit, we're done
                if len(products_page) < limit:
                    break
                
            except requests.exceptions.RequestException as e:
                return {'error': str(e)}
        
        return {'products': all_products}
    
    def import_products_from_shopify(self, db, current_store=None): # Keep current_store for association
        """Import products from Shopify to the local database."""
        # is_configured() now checks the context set by set_store_context
        if not self.is_configured():
            error_msg = 'Shopify integration not configured for the selected store.'
            if current_store:
                 error_msg += f' Please check credentials for store "{current_store.name}".'
            return {'error': error_msg, 'imported': 0}

        print(f"Starting import from Shopify for store: {self.store_url}...")
        shopify_products = self.get_all_products() # Uses the currently set context

        if 'error' in shopify_products:
            # Add context to the error
            error_msg = shopify_products['error']
            if current_store:
                 error_msg += f' (Store: "{current_store.name}")'
            return {'error': error_msg, 'imported': 0}

        products = shopify_products.get('products', [])
        print(f"Found {len(products)} products in Shopify store: {self.store_url}")
        
        imported_count = 0
        updated_count = 0
        
        # Get the current store from the normalized URL
        from store_management import normalize_url
        from models import Store
        
        store = None
        if current_store:
            store = current_store
        else:
            normalized_url = normalize_url(self.store_url)
            store = Store.query.filter_by(url=normalized_url).first()
        
        for shopify_product in products:
            # Check if product already exists in database
            existing_product = Product.query.filter_by(shopify_id=str(shopify_product['id'])).first()
            
            if existing_product:
                # Update existing product
                existing_product.title = shopify_product['title']
                existing_product.description = shopify_product['body_html']
                
                # Get price from first variant
                if shopify_product['variants'] and 'price' in shopify_product['variants'][0]:
                    existing_product.price = float(shopify_product['variants'][0]['price'])
                
                # Get image URL from first image
                if shopify_product['images'] and 'src' in shopify_product['images'][0]:
                    existing_product.image_url = shopify_product['images'][0]['src']
                
                # Update tags
                if 'tags' in shopify_product and shopify_product['tags']:
                    tag_names = [tag.strip() for tag in shopify_product['tags'].split(',')]
                    
                    # Clear existing tags
                    existing_product.tags = []
                    
                    # Add new tags
                    for tag_name in tag_names:
                        if tag_name:
                            tag = Tag.query.filter_by(name=tag_name.lower()).first()
                            if not tag:
                                tag = Tag(name=tag_name.lower())
                                db.session.add(tag)
                            existing_product.tags.append(tag)
            else:
                # Create new product
                new_product = Product(
                    title=shopify_product['title'],
                    description=shopify_product['body_html'],
                    shopify_id=str(shopify_product['id'])
                )
                
                # Associate with store if available
                if store:
                    new_product.store_id = store.id
                
                # Get price from first variant
                if shopify_product['variants'] and 'price' in shopify_product['variants'][0]:
                    new_product.price = float(shopify_product['variants'][0]['price'])
                
                # Get image URL from first image
                if shopify_product['images'] and 'src' in shopify_product['images'][0]:
                    new_product.image_url = shopify_product['images'][0]['src']
                
                # Add tags
                if 'tags' in shopify_product and shopify_product['tags']:
                    tag_names = [tag.strip() for tag in shopify_product['tags'].split(',')]
                    
                    for tag_name in tag_names:
                        if tag_name:
                            # Check if tag exists for this store
                            tag_query = Tag.query.filter_by(name=tag_name.lower())
                            if store:
                                tag_query = tag_query.filter_by(store_id=store.id)
                            
                            tag = tag_query.first()
                            if not tag:
                                tag = Tag(name=tag_name.lower())
                                if store:
                                    tag.store_id = store.id
                                db.session.add(tag)
                            new_product.tags.append(tag)
                
                db.session.add(new_product)
                imported_count += 1
        
        db.session.commit()
        
        return {
            'success': True,
            'imported': imported_count,
            'total': len(shopify_products.get('products', []))
        }
    
    def export_product_to_shopify(self, product, current_store=None): # Add current_store for context
        """Export a product from the local database to Shopify."""
        # is_configured() now checks the context set by set_store_context
        if not self.is_configured():
            error_msg = 'Shopify integration not configured for the selected store.'
            if current_store:
                 error_msg += f' Please check credentials for store "{current_store.name}".'
            return {'error': error_msg}

        # Get tags as a comma-separated string
        tag_string = ",".join([tag.name for tag in product.tags])
        print(f"Exporting product {product.title} (ID: {product.id}, Shopify ID: {product.shopify_id}) to store {self.store_url} with tags: {tag_string}")

        # --- Prepare SEO Metafields ---
        metafields = []
        seo_namespace = "custom_seo" # Define a namespace for our SEO fields

        seo_fields_map = {
            'meta_title': 'single_line_text_field',
            'meta_description': 'multi_line_text_field',
            'og_title': 'single_line_text_field',
            'og_description': 'multi_line_text_field',
            'og_image': 'url',
            'twitter_card': 'single_line_text_field',
            'twitter_title': 'single_line_text_field',
            'twitter_description': 'multi_line_text_field',
            'twitter_image': 'url',
            'canonical_url': 'url'
        }

        for field_name, field_type in seo_fields_map.items():
            value = getattr(product, field_name, None)
            if value: # Only add metafield if value exists
                metafields.append({
                    "namespace": seo_namespace,
                    "key": field_name,
                    "value": value,
                    "type": field_type
                })
        # --- End Prepare SEO Metafields ---

        
        # Check if product already exists in Shopify
        if product.shopify_id:
            # First, get the current product from Shopify to ensure we have all required fields
            current_product_result = self.get_product(product.shopify_id)
            
            if 'error' in current_product_result:
                print(f"Error getting product from Shopify: {current_product_result.get('error', 'Unknown error')}")
                return current_product_result
            
            # Extract the current product data
            current_product = current_product_result.get('product', {})
            
            # Update only the fields we want to change
            product_data = {
                "product": {
                    "id": product.shopify_id,
                    "tags": tag_string,
                    # Add metafields for update
                    "metafields": metafields
                }
            }
            
            # Only update these fields if they've changed
            if product.title != current_product.get('title'):
                product_data["product"]["title"] = product.title
            
            if (product.description or "") != current_product.get('body_html', ""):
                product_data["product"]["body_html"] = product.description or ""
            
            # Don't update variants or images unless necessary
            # This minimizes the risk of validation errors
            
            print(f"Updating product in Shopify with minimal data: {json.dumps(product_data, indent=2)}")
            result = self.update_product(product.shopify_id, product_data)
            
            # Check if the update was successful
            if 'error' not in result and 'product' in result:
                print(f"Successfully updated product in Shopify with tags: {tag_string}")
            else:
                print(f"Error updating product in Shopify: {result.get('error', 'Unknown error')}")
                
                # If we get an error, try an even more minimal update with just tags
                print("Trying minimal update with just tags...")
                minimal_product_data = {
                    "product": {
                        "id": product.shopify_id,
                        "tags": tag_string
                    }
                }
                
                result = self.update_product(product.shopify_id, minimal_product_data)
                if 'error' not in result and 'product' in result:
                    print(f"Successfully updated product tags in Shopify: {tag_string}")
        else:
            # Create new product
            product_data = {
                "product": {
                    "title": product.title,
                    "body_html": product.description or "",
                    "vendor": "Product Manager",
                    "product_type": "",
                    "tags": tag_string,
                    "variants": [
                        {
                            "price": str(product.price) if product.price else "0.00"
                        }
                    ]
                }
            }
            
            if product.image_url:
                product_data["product"]["images"] = [{"src": product.image_url}]
            
            result = self.create_product(product_data)
            
            # Check if the creation was successful
            if 'error' not in result and 'product' in result:
                print(f"Successfully created product in Shopify with tags: {tag_string}")
                
                # Update local product with Shopify ID
                if 'id' in result['product']:
                    product.shopify_id = str(result['product']['id'])
            else:
                print(f"Error creating product in Shopify: {result.get('error', 'Unknown error')}")
        
        return result
    
    def import_collections_from_shopify(self, db, current_store=None): # Keep current_store for association
        """Import collections from Shopify to the local database."""
        # is_configured() now checks the context set by set_store_context
        if not self.is_configured():
            error_msg = 'Shopify integration not configured for the selected store.'
            if current_store:
                 error_msg += f' Please check credentials for store "{current_store.name}".'
            return {'error': error_msg, 'imported': 0, 'updated': 0} # Add updated key

        print(f"Starting import of collections from Shopify for store: {self.store_url}...")
        shopify_collections = self.get_all_collections() # Uses the currently set context

        if 'error' in shopify_collections:
            # Add context to the error
            error_msg = shopify_collections['error']
            if current_store:
                 error_msg += f' (Store: "{current_store.name}")'
            return {'error': error_msg, 'imported': 0, 'updated': 0} # Add updated key

        collections = shopify_collections.get('collections', [])
        print(f"Found {len(collections)} collections in Shopify")
        
        imported_count = 0
        updated_count = 0
        
        # Get the current store from the normalized URL
        from store_management import normalize_url
        from models import Store
        
        store = None
        if current_store:
            store = current_store
        else:
            normalized_url = normalize_url(self.store_url)
            store = Store.query.filter_by(url=normalized_url).first()
        
        # Fetch cleanup rules for this store
        cleanup_rules = CleanupRule.query.filter_by(store_id=store.id).order_by(CleanupRule.priority).all() if store else []
        
        for shopify_collection in collections:
            # Extract collection data
            collection_id = str(shopify_collection.get('id'))
            collection_title = shopify_collection.get('title', '')
            collection_handle = shopify_collection.get('handle', '')
            collection_body_html = shopify_collection.get('body_html', '')
            
        # Apply cleanup rules to the collection description
        for rule in cleanup_rules:
            if rule.is_regex:
                collection_body_html = re.sub(re.escape(rule.pattern), rule.replacement, collection_body_html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
            else:
                collection_body_html = collection_body_html.replace(rule.pattern, rule.replacement, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
            
            # Ensure the cleanup rule is applied to all occurrences
            collection_body_html = re.sub(re.escape(rule.pattern), rule.replacement, collection_body_html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
            
            # Apply cleanup rules to the collection description again to ensure all occurrences are replaced
            collection_body_html = re.sub(re.escape(rule.pattern), rule.replacement, collection_body_html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
            # Check if collection already exists in database
            existing_collection = Collection.query.filter_by(shopify_id=collection_id).first()
            
            if existing_collection:
                # Update existing collection
                existing_collection.name = collection_title
                existing_collection.slug = collection_handle
                existing_collection.description = collection_body_html
                updated_count += 1
            else:
                # Create new collection
                new_collection = Collection(
                    name=collection_title,
                    slug=collection_handle,
                    description=collection_body_html,
                    shopify_id=collection_id
                )
                
                # Associate with store if available
                if store:
                    new_collection.store_id = store.id
                db.session.add(new_collection)
                imported_count += 1
        
        db.session.commit()
        
        # Now fetch products for each collection
        for shopify_collection in collections:
            collection_id = str(shopify_collection.get('id'))
            
            # Get the local collection
            local_collection = Collection.query.filter_by(shopify_id=collection_id).first()
            if not local_collection:
                continue
            
            # Get products in this collection from Shopify
            try:
                url = f"{self.store_url}/admin/api/2023-07/collections/{collection_id}/products.json?limit=250"
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                
                collection_products = response.json().get('products', [])
                print(f"Found {len(collection_products)} products in collection {local_collection.name}")
                
                # Clear existing products
                local_collection.products = []
                
                # Add products to collection
                for shopify_product in collection_products:
                    product_id = str(shopify_product.get('id'))
                    local_product = Product.query.filter_by(shopify_id=product_id).first()
                    
                    if local_product and local_product not in local_collection.products:
                        local_collection.products.append(local_product)
                
                db.session.commit()
                
            except requests.exceptions.RequestException as e:
                print(f"Error fetching products for collection {collection_id}: {str(e)}")
        
        return {
            'success': True,
            'imported': imported_count,
            'updated': updated_count,
            'total': len(collections)
        }
    
    def create_smart_collection(self, collection_data):
        """Create a smart collection in Shopify."""
        if not self.is_configured():
            return {'error': 'Shopify integration not configured'}
        
        url = f"{self.store_url}/admin/api/2023-07/smart_collections.json"
        
        try:
            response = requests.post(url, headers=self.headers, json=collection_data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
    
    def export_collection_to_shopify(self, collection, current_store=None): # Add current_store for context
        """Export a collection from the local database to Shopify."""
        # is_configured() now checks the context set by set_store_context
        if not self.is_configured():
            error_msg = 'Shopify integration not configured for the selected store.'
            if current_store:
                 error_msg += f' Please check credentials for store "{current_store.name}".'
            return {'error': error_msg}

        print(f"Exporting collection {collection.name} to store {self.store_url}...") # Add print statement

        # Prepare metafields based on collection attributes
        metafields = []
        if hasattr(collection, 'seo_title') and collection.seo_title:
            metafields.append({
                "key": "title_tag",
                "value": collection.seo_title,
                "type": "single_line_text_field",
                "namespace": "global"
            })
        if hasattr(collection, 'seo_description') and collection.seo_description:
             metafields.append({
                 "key": "description_tag",
                 "value": collection.seo_description,
                 "type": "single_line_text_field",
                 "namespace": "global"
             })
        # TODO: Add logic for seo_defaults if needed later

        # If this is a smart collection (based on a tag), create a smart collection in Shopify
        if collection.tag:
            # Create a smart collection with a rule based on the tag
            collection_data = {
                "smart_collection": {
                    "title": collection.name,
                    "body_html": collection.description or "",
                    "published": True,
                    "handle": collection.slug if collection.slug else None,
                    "rules": [
                        {
                            "column": "tag",
                            "relation": "equals",
                            "condition": collection.tag.name
                        }
                    ],
                    # Use the pre-built metafields array
                    "metafields": metafields
                }
            }
            # Removed old specific meta_description handling
            
            print(f"Exporting smart collection to Shopify: {json.dumps(collection_data, indent=2)}")
            
            result = self.create_smart_collection(collection_data)
            
            if 'error' in result:
                return result
            
            print(f"Created smart collection {collection.name} in Shopify based on tag: {collection.tag.name}")
            
            return result
        else:
            # For regular collections, create a custom collection
            collection_data = {
                "custom_collection": {
                    "title": collection.name,
                    "body_html": collection.description or "",
                    "published": True,
                    "handle": collection.slug if collection.slug else None,
                    # Use the pre-built metafields array
                    "metafields": metafields
                }
            }
            # Removed old specific meta_description handling
            
            print(f"Exporting custom collection to Shopify: {json.dumps(collection_data, indent=2)}")
            
            result = self.create_collection(collection_data)
            
            if 'error' in result:
                return result
            
            # Get collection ID
            collection_id = result['custom_collection']['id']
            
            # Add products to collection
            products_added = 0
            for product in collection.products:
                if product.shopify_id:
                    add_result = self.add_product_to_collection(collection_id, product.shopify_id)
                    if 'error' not in add_result:
                        products_added += 1
            
            print(f"Added {products_added} products to collection {collection.name} in Shopify")
            
            return result
