import os
import anthropic
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, g, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate # Add Migrate import
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func
from models import db, Product, Tag, Collection, EnvVar, product_tags, Store, CleanupRule, SEODefaults # Added CleanupRule, SEODefaults
from forms import ProductForm, EnvVarForm, CollectionForm, TagForm, AutoTagForm, CreateCollectionsForm, StoreForm, StoreSelectForm, CleanupRuleForm # Added CleanupRuleForm
# from claude_integration import ClaudeTaggingService # Replaced by ai_services
from ai_services import get_ai_service # Import the factory function
import re # Added re import
from shopify_integration import ShopifyIntegration
from store_management import get_current_store, set_current_store, filter_query_by_store, get_all_stores
from config import Config
# from auto_migrate import run_migrations # Remove old migration import
import json
import re # Make sure re is imported if not already done by previous step

# Helper function to apply cleanup rules
def apply_cleanup_rules(input_text):
    """Applies cleanup rules for the current store to the input text."""
    if not g.current_store or not input_text:
        return input_text

    rules = CleanupRule.query.filter_by(store_id=g.current_store.id).order_by(CleanupRule.priority).all()
    
    cleaned_text = input_text
    for rule in rules:
        try:
            # Determine the actual replacement value, handling the '' case for empty string
            actual_replacement = "" if rule.replacement == "''" else rule.replacement
            
            if rule.is_regex:
                # Use actual_replacement for the regex substitution
                cleaned_text = re.sub(rule.pattern, actual_replacement, cleaned_text)
            else:
                # Use actual_replacement for the simple string replacement
                cleaned_text = cleaned_text.replace(rule.pattern, actual_replacement)
        except re.error as e:
            print(f"Error applying regex rule (ID: {rule.id}, Pattern: {rule.pattern}): {e}")
            # Optionally skip this rule or handle the error differently
            continue
        except Exception as e:
            print(f"Error applying rule (ID: {rule.id}): {e}")
            continue # Skip rule on error
    
    return cleaned_text.strip() # Remove leading/trailing whitespace

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    csrf = CSRFProtect(app)
    migrate = Migrate(app, db) # Initialize Flask-Migrate
    
    # Ensure the instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)
    
    # Initialize services
    # AI service will be initialized after loading DB env vars
    ai_service = None # Placeholder
    shopify_service = ShopifyIntegration()
    
    # Make Config, current_store, and get_all_stores available to all templates
    @app.context_processor
    def inject_template_vars():
        return dict(
            Config=Config, 
            current_store=get_current_store(),
            get_all_stores=get_all_stores
        )
    
    # Set up request handlers
    @app.before_request
    def before_request():
        # Initialize current store for this request
        g.current_store = get_current_store()
    
    # Create database tables and run migrations
    with app.app_context():
        db.create_all()
        
        # Flask-Migrate handles migrations now, remove old call
        # run_migrations(app)
        
        # Initialize default environment variables if they don't exist
        for key, value in Config.DEFAULT_ENV_VARS.items():
            if not EnvVar.query.filter_by(key=key).first():
                env_var = EnvVar(key=key, value=value, description=f"Default {key}")
                db.session.add(env_var)
        
        # Create a default store if none exists
        if not Store.query.first():
            # Try to get store URL from environment
            store_url = Config.SHOPIFY_STORE_URL
            if store_url:
                # Normalize the URL
                normalized_url = store_url.lower()
                if '://' in normalized_url:
                    normalized_url = normalized_url.split('://', 1)[1]
                normalized_url = normalized_url.rstrip('/')
                
                # Create a store name from the URL
                store_name = normalized_url.split('.')[0].capitalize()
                
                default_store = Store(
                    name=f"{store_name} Store",
                    url=normalized_url,
                    access_token=Config.SHOPIFY_ACCESS_TOKEN or ""
                )
            else:
                default_store = Store(
                    name="Default Store",
                    url="default-store.myshopify.com",
                    access_token=""
                )
            
            db.session.add(default_store)
            db.session.commit()
            
            # We can't set the session outside of a request context
            # This will be handled by the get_current_store function
        
        db.session.commit()
        
        # Load environment variables from database and update Config/Services
        env_vars = EnvVar.query.all()
        ai_config_changed = False
        for env_var in env_vars:
            # Update the runtime environment (important for libraries reading directly)
            os.environ[env_var.key] = env_var.value

            # Update Config object attributes directly
            if hasattr(Config, env_var.key):
                setattr(Config, env_var.key, env_var.value)
                # Track if AI-related config changed
                if env_var.key.startswith('AI_') or env_var.key in ['ANTHROPIC_API_KEY', 'GEMINI_API_KEY', 'GROK_API_KEY', 'LLAMA_API_BASE_URL', 'LLAMA_API_KEY']:
                    ai_config_changed = True
            elif env_var.key == 'SHOPIFY_ACCESS_TOKEN':
                 Config.SHOPIFY_ACCESS_TOKEN = env_var.value
                 # Update Shopify service
                 shopify_service.access_token = env_var.value
                 shopify_service.headers['X-Shopify-Access-Token'] = env_var.value
            elif env_var.key == 'SHOPIFY_STORE_URL':
                 Config.SHOPIFY_STORE_URL = env_var.value
                 # Update Shopify service
                 shopify_service.store_url = env_var.value
                 if env_var.value and env_var.value.endswith('/'):
                     shopify_service.store_url = env_var.value[:-1]
            # Handle specific config updates if needed (e.g., parsing JSON for prompts again)
            if env_var.key == 'AI_CUSTOM_PROMPT_JSON':
                try:
                    Config.AI_CUSTOM_PROMPTS = json.loads(env_var.value)
                    if not isinstance(Config.AI_CUSTOM_PROMPTS, dict):
                        print("Warning: DB AI_CUSTOM_PROMPT_JSON did not parse to a dictionary.")
                        Config.AI_CUSTOM_PROMPTS = {}
                except json.JSONDecodeError:
                    print("Warning: Could not parse DB AI_CUSTOM_PROMPT_JSON.")
                    Config.AI_CUSTOM_PROMPTS = {}
                ai_config_changed = True # Ensure re-initialization

        # Now that Config is updated with DB values, initialize the AI service
        print(f"Initializing AI Service with provider: {Config.AI_PROVIDER}")
        ai_service = get_ai_service()
        # Make ai_service accessible in request contexts if needed, e.g., via app context or g
        # For simplicity now, routes will use the 'ai_service' variable from the create_app scope.
    
    @app.route('/')
    def index():
        """Home page."""
        # Filter products and collections by store
        products_query = Product.query
        collections_query = Collection.query
        
        if g.current_store:
            products_query = products_query.filter_by(store_id=g.current_store.id)
            collections_query = collections_query.filter_by(store_id=g.current_store.id)
        
        # Limit the number of products and collections for better performance
        products = products_query.order_by(Product.created_at.desc()).limit(20).all()
        collections = collections_query.order_by(Collection.created_at.desc()).limit(10).all()
        
        # Get all stores for the store selector
        stores = Store.query.all()
        
        return render_template('index.html', products=products, collections=collections, stores=stores)
    
    @app.route('/products')
    def products():
        """List all products."""
        # Get search parameter
        search = request.args.get('search', '').strip()
        
        # Filter products by store and search term
        products_query = Product.query
        
        if g.current_store:
            products_query = products_query.filter_by(store_id=g.current_store.id)
        
        # Add search filter if search term provided
        if search:
            search_term = f"%{search}%"
            products_query = products_query.filter(Product.title.ilike(search_term))
        
        # Add pagination
        page = request.args.get('page', 1, type=int)
        per_page = 20  # Number of products per page
        pagination = products_query.paginate(page=page, per_page=per_page, error_out=False)
        products = pagination.items
        
        auto_tag_form = AutoTagForm()
        create_collections_form = CreateCollectionsForm()
        
        return render_template('products.html', products=products, pagination=pagination,
                              auto_tag_form=auto_tag_form, create_collections_form=create_collections_form)
    
    @app.route('/products/add', methods=['GET', 'POST'])
    def add_product():
        """Add a new product."""
        form = ProductForm()
        if form.validate_on_submit():
            product = Product(
                title=form.title.data,
                description=form.description.data,
                price=form.price.data,
                image_url=form.image_url.data
            )
            
            # Associate with current store
            if g.current_store:
                product.store_id = g.current_store.id
            db.session.add(product)
            db.session.commit()
            
            # Auto-tag the product if AI service is configured with an API key
            if ai_service and ai_service.api_key:
                try:
                    tags = ai_service.generate_tags(product) # Use synchronous wrapper
                except Exception as e:
                    print(f"Error during sync tag generation: {e}")
                    tags = ["error generating tags"]
                for tag_name in tags:
                    # Check if tag exists for this store, create if not
                    tag_query = Tag.query.filter_by(name=tag_name)
                    if g.current_store:
                        tag_query = tag_query.filter_by(store_id=g.current_store.id)
                    
                    tag = tag_query.first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        if g.current_store:
                            tag.store_id = g.current_store.id
                        db.session.add(tag)
                    product.tags.append(tag)
                db.session.commit()
                flash(f'Product added and auto-tagged with: {", ".join(tags)}', 'success')
            else:
                flash(f'Product added. AI Provider ({Config.AI_PROVIDER}) not configured or API key missing, skipping auto-tagging.', 'warning')
            
            return redirect(url_for('products'))
        return render_template('product_form.html', form=form, title='Add Product')
    
    @app.route('/products/<int:id>/edit', methods=['GET', 'POST'])
    def edit_product(id):
        """Edit an existing product."""
        product = Product.query.get_or_404(id)
        form = ProductForm(obj=product)
        if form.validate_on_submit():
            form.populate_obj(product)
            db.session.commit()
            flash('Product updated successfully', 'success')
            return redirect(url_for('products'))
        return render_template('product_form.html', form=form, title='Edit Product')
    
    @app.route('/products/<int:id>/delete', methods=['POST'])
    def delete_product(id):
        """Delete a product."""
        product = Product.query.get_or_404(id)
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully', 'success')
        return redirect(url_for('products'))

    @app.route('/products/bulk-delete', methods=['POST'])
    def bulk_delete_products():
        """Bulk delete selected products."""
        product_ids = request.form.getlist('product_ids')

        if not product_ids:
            flash('No products selected for deletion.', 'warning')
            return redirect(url_for('products'))

        # Ensure we only delete products belonging to the current store
        products_query = Product.query.filter(Product.id.in_(product_ids))
        if g.current_store:
            products_query = products_query.filter_by(store_id=g.current_store.id)

        products_to_delete = products_query.all()
        deleted_count = len(products_to_delete)

        if not products_to_delete:
            flash('No valid products found for deletion in the current store.', 'warning')
            return redirect(url_for('products'))

        for product in products_to_delete:
            db.session.delete(product)

        db.session.commit()
        flash(f'{deleted_count} products deleted successfully.', 'success')
        return redirect(url_for('products'))
    
    @app.route('/products/<int:id>/tags', methods=['GET', 'POST'])
    def manage_product_tags(id):
        """Manage tags for a product."""
        product = Product.query.get_or_404(id)
        form = TagForm()
        
        if form.validate_on_submit():
            tag_name = form.name.data.lower().strip()
            # Check if tag exists for this store, create if not
            tag_query = Tag.query.filter_by(name=tag_name)
            if g.current_store:
                tag_query = tag_query.filter_by(store_id=g.current_store.id)
            
            tag = tag_query.first()
            if not tag:
                tag = Tag(name=tag_name)
                if g.current_store:
                    tag.store_id = g.current_store.id
                db.session.add(tag)
            
            # Add tag to product if not already added
            if tag not in product.tags:
                product.tags.append(tag)
                db.session.commit()
                flash(f'Tag "{tag_name}" added to product', 'success')
            else:
                flash(f'Tag "{tag_name}" already exists for this product', 'warning')
            
            return redirect(url_for('manage_product_tags', id=product.id))
        
        return render_template('manage_tags.html', product=product, form=form)
    
    @app.route('/products/<int:product_id>/tags/<int:tag_id>/remove', methods=['POST'])
    def remove_product_tag(product_id, tag_id):
        """Remove a tag from a product."""
        product = Product.query.get_or_404(product_id)
        tag = Tag.query.get_or_404(tag_id)
        
        if tag in product.tags:
            product.tags.remove(tag)
            db.session.commit()
            flash(f'Tag "{tag.name}" removed from product', 'success')
        
        return redirect(url_for('manage_product_tags', id=product_id))

    @app.route('/products/<int:product_id>/tags/remove-all', methods=['POST'])
    def remove_all_product_tags(product_id):
        """Remove all tags from a specific product."""
        product = Product.query.get_or_404(product_id)

        # Ensure the product belongs to the current store or there's no store context
        if g.current_store and product.store_id != g.current_store.id:
             flash('Product not found in the current store.', 'danger')
             return redirect(url_for('products')) # Or appropriate redirect

        if not product.tags:
            flash('Product already has no tags.', 'info')
        else:
            product.tags = [] # Clear the relationship
            db.session.commit()
            flash(f'All tags removed from product "{product.title}"', 'success')

        return redirect(url_for('manage_product_tags', id=product_id))
    
    @app.route('/products/auto-tag', methods=['POST'])
    async def auto_tag_products():
        """Auto-tag selected products using Claude asynchronously."""
        product_ids = request.form.getlist('product_ids')
        
        if not product_ids:
            flash('No products selected for auto-tagging', 'warning')
            return redirect(url_for('products'))
        
        # Check if the configured AI service has an API key
        if not (ai_service and ai_service.api_key):
            flash(f'AI Provider ({Config.AI_PROVIDER}) API key not set. Please set it in environment variables.', 'danger')
            return redirect(url_for('env_vars'))
        
        # Get all products to tag (filtered by store)
        products_query = Product.query.filter(Product.id.in_(product_ids))
        if g.current_store:
            products_query = products_query.filter_by(store_id=g.current_store.id)
        
        products = products_query.all()
        
        if not products:
            flash('No valid products found for auto-tagging', 'warning')
            return redirect(url_for('products'))
        
        flash(f'Started auto-tagging {len(products)} products. This may take a while for large batches...', 'info')
        
        # Process products in batches asynchronously
        # Use the configured AI service
        results = await ai_service.batch_generate_tags(products, batch_size=50)
        
        tagged_count = 0
        total_tags_added = 0
        
        for product, tags in results:
            if tags and tags != ["error_generating_tags"] and tags != ["api_key_missing"]:
                print(f"Adding tags to product {product.id}: {tags}")
                tags_added = 0
                
                for tag_name in tags:
                    # Check if tag exists for this store, create if not
                    tag_query = Tag.query.filter_by(name=tag_name)
                    if g.current_store:
                        tag_query = tag_query.filter_by(store_id=g.current_store.id)
                    
                    tag = tag_query.first()
                    if not tag:
                        # Double check if tag exists with this name for any store
                        existing_tag = Tag.query.filter_by(name=tag_name).first()
                        if existing_tag:
                            # Tag exists but for a different store, create a new one for this store
                            print(f"Tag {tag_name} exists for another store, creating for current store")
                            tag = Tag(name=f"{tag_name}", store_id=g.current_store.id if g.current_store else None)
                        else:
                            print(f"Creating new tag: {tag_name}")
                            tag = Tag(name=tag_name)
                            if g.current_store:
                                tag.store_id = g.current_store.id
                        
                        db.session.add(tag)
                        try:
                            db.session.flush()  # Flush to get the tag ID
                        except Exception as e:
                            print(f"Error creating tag {tag_name}: {str(e)}")
                            db.session.rollback()
                            continue
                    
                    # Add tag to product if not already added
                    if tag not in product.tags:
                        print(f"Adding tag {tag.name} to product {product.title}")
                        product.tags.append(tag)
                        tags_added += 1
                
                if tags_added > 0:
                    tagged_count += 1
                    total_tags_added += tags_added
        
        db.session.commit()
        
        # Export tagged products to Shopify
        if Config.SHOPIFY_ACCESS_TOKEN and Config.SHOPIFY_STORE_URL:
            export_count = 0
            export_errors = 0
            
            flash(f'Exporting {tagged_count} tagged products to Shopify...', 'info')
            
            for product, _ in results:
                if product.tags:  # Only export products that have tags
                    result = shopify_service.export_product_to_shopify(product)
                    if 'error' not in result:
                        export_count += 1
                    else:
                        export_errors += 1
            
            if export_errors > 0:
                flash(f'Warning: {export_errors} products failed to export to Shopify', 'warning')
            
            flash(f'Successfully auto-tagged {tagged_count} products and exported {export_count} to Shopify', 'success')
        else:
            flash(f'Successfully auto-tagged {tagged_count} products. Shopify integration not configured, skipping export.', 'success')
        
        return redirect(url_for('products'))
    
    @app.route('/collections')
    def collections():
        """List all collections with pagination."""
        page = request.args.get('page', 1, type=int)
        per_page = 12  # Number of collections per page
        
        # Get paginated collections (filtered by store)
        collections_query = Collection.query
        if g.current_store:
            collections_query = collections_query.filter_by(store_id=g.current_store.id)
        
        pagination = collections_query.paginate(page=page, per_page=per_page, error_out=False)
        collections = pagination.items
        
        return render_template('collections.html', collections=collections, pagination=pagination)
    
    @app.route('/collections/add', methods=['GET', 'POST'])
    def add_collection():
        """Add a new collection."""
        form = CollectionForm()
        # Get all tags for selection (filtered by store)
        tags_query = Tag.query
        if g.current_store:
            tags_query = tags_query.filter_by(store_id=g.current_store.id)
        
        tags = tags_query.all()
        
        if form.validate_on_submit():
            # Generate a slug from the name if not provided
            base_slug = form.name.data.lower().replace(' ', '-')
            slug = base_slug
            
            # Check if a collection with this slug already exists (across all stores)
            # We need to check globally to avoid unique constraint violations
            slug_query = Collection.query.filter_by(slug=slug)
            
            counter = 1
            while slug_query.first():
                slug = f"{base_slug}-{counter}"
                counter += 1
                # Check the new slug
                slug_query = Collection.query.filter_by(slug=slug)
            
            collection = Collection(
                name=form.name.data,
                slug=slug,
                description=form.description.data
            )
            
            # Associate with current store
            if g.current_store:
                collection.store_id = g.current_store.id
            
            # Set tag if provided
            if form.tag_id.data:
                tag = Tag.query.get(form.tag_id.data)
                if tag:
                    collection.tag = tag
                    # Add all products with this tag to the collection
                    for product in tag.products:
                        collection.products.append(product)
            
            db.session.add(collection)
            db.session.commit()
            flash('Collection created successfully', 'success')
            return redirect(url_for('collections'))
        
        return render_template('collection_form.html', form=form, tags=tags, title='Add Collection')
    
    @app.route('/collections/<int:id>/edit', methods=['GET', 'POST'])
    def edit_collection(id):
        """Edit an existing collection."""
        collection = Collection.query.get_or_404(id)
        form = CollectionForm(obj=collection)
        # Get all tags for selection (filtered by store)
        tags_query = Tag.query
        if g.current_store:
            tags_query = tags_query.filter_by(store_id=g.current_store.id)
        
        tags = tags_query.all()
        
        if form.validate_on_submit():
            # Check if name has changed
            if form.name.data != collection.name:
                # Generate a new slug from the name
                base_slug = form.name.data.lower().replace(' ', '-')
                slug = base_slug
                
                # Check if a collection with this slug already exists (excluding this collection)
                # We need to check globally to avoid unique constraint violations
                slug_query = Collection.query.filter(Collection.slug == slug, Collection.id != collection.id)
                
                counter = 1
                while slug_query.first():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                    # Check the new slug
                    slug_query = Collection.query.filter(Collection.slug == slug, Collection.id != collection.id)
                
                # Update the slug
                collection.slug = slug
            
            # Update other fields
            form.populate_obj(collection)
            
            # Update tag if changed
            if form.tag_id.data and str(collection.tag_id) != form.tag_id.data:
                tag = Tag.query.get(form.tag_id.data)
                if tag:
                    collection.tag = tag
                    # Clear existing products and add all products with this tag
                    collection.products = []
                    for product in tag.products:
                        collection.products.append(product)
            
            db.session.commit()
            flash('Collection updated successfully', 'success')
            return redirect(url_for('collections'))
        
        # Pre-select current tag
        if collection.tag:
            form.tag_id.data = collection.tag_id
        
        return render_template('collection_form.html', form=form, tags=tags, title='Edit Collection')
    
    @app.route('/collections/<int:id>/delete', methods=['POST'])
    def delete_collection(id):
        """Delete a collection."""
        collection = Collection.query.get_or_404(id)
        db.session.delete(collection)
        db.session.commit()
        flash('Collection deleted successfully', 'success')
        return redirect(url_for('collections'))

    @app.route('/collections/bulk-delete', methods=['POST'])
    def bulk_delete_collections():
        """Bulk delete selected collections."""
        collection_ids = request.form.getlist('collection_ids')

        if not collection_ids:
            flash('No collections selected for deletion.', 'warning')
            return redirect(url_for('collections'))

        # Ensure we only delete collections belonging to the current store
        collections_query = Collection.query.filter(Collection.id.in_(collection_ids))
        if g.current_store:
            collections_query = collections_query.filter_by(store_id=g.current_store.id)

        collections_to_delete = collections_query.all()
        deleted_count = len(collections_to_delete)

        if not collections_to_delete:
            flash('No valid collections found for deletion in the current store.', 'warning')
            return redirect(url_for('collections'))

        for collection in collections_to_delete:
            db.session.delete(collection)

        db.session.commit()
        flash(f'{deleted_count} collections deleted successfully.', 'success')
        return redirect(url_for('collections'))
    
    @app.route('/collections/create-from-tags', methods=['POST'])
    async def create_collections_from_tags():
        """Create collections from all tags asynchronously."""
        form = CreateCollectionsForm()
        exclude_imported_tags = form.exclude_imported_tags.data
        
        if exclude_imported_tags:
            print("Only using tags generated by Claude (excluding imported tags)")
        
        created_count = 0
        skipped_count = 0
        
        # Get tags with product counts (filtered by store)
        tag_query = db.session.query(
            Tag, func.count(product_tags.c.product_id).label('product_count')
        ).outerjoin(product_tags).group_by(Tag.id)
        
        if g.current_store:
            tag_query = tag_query.filter(Tag.store_id == g.current_store.id)
        
        tag_counts = tag_query.all()
        
        # First, create collections from existing tags
        for tag, product_count in tag_counts:
            # Skip tags with no products or only one product
            if product_count <= 1:
                print(f"Skipping tag '{tag.name}' with only {product_count} product(s)")
                skipped_count += 1
                continue
            
            # Skip tags that don't have at least 2 words
            if len(tag.name.split()) < 2:
                print(f"Skipping single-word tag: {tag.name}")
                skipped_count += 1
                continue
            
            # Skip tags that contain underscores
            if '_' in tag.name:
                print(f"Skipping tag with underscore: {tag.name}")
                skipped_count += 1
                continue
            
            # If exclude_imported_tags is True, skip tags that were imported from Shopify
            if exclude_imported_tags and ('imported' in tag.name.lower() or 'shopify' in tag.name.lower()):
                print(f"Skipping imported tag: {tag.name}")
                skipped_count += 1
                continue
                
            # Check if a collection already exists for this tag (filtered by store)
            collection_query = Collection.query.filter_by(tag_id=tag.id)
            if g.current_store:
                collection_query = collection_query.filter_by(store_id=g.current_store.id)
            
            existing_collection = collection_query.first()
            if not existing_collection:
                # Generate SEO-friendly title
                title = f"{tag.name.title()} Collection | Premium {tag.name.title()} Products"
                
                # Generate SEO-friendly slug
                base_slug = tag.name.lower().replace(' ', '-')
                slug = base_slug
                
                # Check if a collection with this slug already exists (across all stores)
                # We need to check globally to avoid unique constraint violations
                slug_query = Collection.query.filter_by(slug=slug)
                
                counter = 1
                while slug_query.first():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                    # Check the new slug
                    slug_query = Collection.query.filter_by(slug=slug)
                
                # Get cleaned product titles for meta description
                cleaned_product_titles = [apply_cleanup_rules(p.title) for p in tag.products[:5]]
                product_titles_text = ", ".join(cleaned_product_titles)
                if len(cleaned_product_titles) < len(tag.products):
                    product_titles_text += f", and {len(tag.products) - len(cleaned_product_titles)} more"
                
                # Get product examples for description generation
                product_examples = [
                    {"title": p.title, "description": p.description} 
                    for p in tag.products[:5]
                ]
                
                # Use Claude to generate meta description and description
                meta_description = f"Explore our {tag.name} collection featuring {product_titles_text}. Find the perfect {tag.name} for your needs."
                
                # Generate SEO-optimized title
                title = f"{tag.name.title()} Collection | Shop Premium {tag.name.title()}"
                
                # Get cleaned product examples for description
                product_examples = tag.products[:3]
                example_text = ""
                if product_examples:
                    # Apply cleanup rules to titles before joining
                    cleaned_titles = [apply_cleanup_rules(p.title) for p in product_examples]
                    example_text = "Featuring " + ", ".join(cleaned_titles)
                    if len(tag.products) > 3:
                        example_text += f" and {len(tag.products) - 3} more items"
                
                # Generate SEO-optimized description with product examples
                description = f"""
                <h1>Premium {tag.name.title()} Collection</h1>
                <p>Discover our exclusive collection of {tag.name} products, carefully curated to bring you the finest selection. {example_text}.</p>
                <h2>Why Shop Our {tag.name.title()} Collection?</h2>
                <ul>
                    <li>Handpicked selection of premium {tag.name} products</li>
                    <li>High-quality materials and expert craftsmanship</li>
                    <li>Trendy and timeless designs for every style</li>
                    <li>Fast shipping and excellent customer service</li>
                </ul>
                <h2>About Our {tag.name.title()} Products</h2>
                <p>Each item in our {tag.name} collection is selected for its quality, style, and value. Whether you're looking for everyday essentials or statement pieces, you'll find the perfect {tag.name} to suit your needs.</p>
                <p>Shop our {tag.name} collection today and experience the difference quality makes.</p>
                """
                
                # Generate SEO meta description
                meta_description = f"Shop our premium {tag.name} collection. {example_text}. Free shipping on qualifying orders. Shop now!"
                
                collection = Collection(
                    name=title,
                    slug=slug,
                    meta_description=meta_description,
                    description=description,
                    tag=tag
                )
                
                # Associate with current store
                if g.current_store:
                    collection.store_id = g.current_store.id
                
                # We don't need to manually add products to the collection
                # since it's a smart collection based on the tag
                # The tag relationship will automatically include all products with this tag
                
                db.session.add(collection)
                created_count += 1
                print(f"Created collection for tag: {tag.name} with {product_count} products")
        
        db.session.commit()
        
        # Now, analyze products without tags to create new collections (filtered by store)
        # Check if AI service is configured before attempting analysis
        if ai_service and ai_service.api_key:
            untagged_query = Product.query.filter(~Product.tags.any())
            if g.current_store:
                untagged_query = untagged_query.filter_by(store_id=g.current_store.id)

            untagged_products = untagged_query.all()
            if untagged_products:
                flash(f'Analyzing {len(untagged_products)} untagged products for collections using {Config.AI_PROVIDER}. This may take a while...', 'info')

                # Process products in batches asynchronously using the configured AI service
                try:
                    results = await ai_service.batch_analyze_products_for_collections(untagged_products, batch_size=50)
                except Exception as e:
                    print(f"Error during batch collection analysis: {e}")
                    flash(f"Error analyzing untagged products with {Config.AI_PROVIDER}: {e}", "danger")
                    results = [] # Ensure results is an empty list on error
            else:
                results = [] # No untagged products to analyze
        else:
            flash(f'AI Provider ({Config.AI_PROVIDER}) API key not set. Skipping analysis of untagged products.', 'warning')
            untagged_products = [] # Ensure this is empty if skipped
            results = [] # Ensure results is empty if skipped
            
            # Group products by category
            categories = {}
            for product, category in results:
                if category:
                    if category not in categories:
                        categories[category] = []
                    categories[category].append(product)
            
            # Create collections for each category
            for category, products in categories.items():
                if len(products) > 0:
                    # Check if a collection already exists for this category (filtered by store)
                    collection_query = Collection.query.filter_by(name=f"{category.capitalize()} Collection")
                    if g.current_store:
                        collection_query = collection_query.filter_by(store_id=g.current_store.id)
                    
                    existing_collection = collection_query.first()
                    if not existing_collection:
                        # Generate SEO-friendly slug
                        base_slug = category.lower().replace(' ', '-')
                        slug = base_slug
                        
                        # Check if a collection with this slug already exists (across all stores)
                        # We need to check globally to avoid unique constraint violations
                        slug_query = Collection.query.filter_by(slug=slug)
                        
                        counter = 1
                        while slug_query.first():
                            slug = f"{base_slug}-{counter}"
                            counter += 1
                            # Check the new slug
                            slug_query = Collection.query.filter_by(slug=slug)
                        
                        collection = Collection(
                            name=f"{category.capitalize()} Collection",
                            slug=slug,
                            description=f"Collection of {len(products)} products categorized as '{category}'",
                        )
                        
                        # Associate with current store
                        if g.current_store:
                            collection.store_id = g.current_store.id
                        
                        # Add all products with this category
                        for product in products:
                            collection.products.append(product)
                        
                        db.session.add(collection)
                        created_count += 1
            
            db.session.commit()
        
        if created_count > 0:
            flash(f'Successfully created {created_count} new collections', 'success')
        else:
            flash('No new collections created. Collections already exist for all tags with products.', 'info')
            
        return redirect(url_for('collections'))
    
    @app.route('/collections/<int:id>/view')
    def view_collection(id):
        """View a collection and its products."""
        collection = Collection.query.get_or_404(id)
        
        # If this is a smart collection (has a tag), get products with this tag
        if collection.tag:
            # Get all products with this tag (dynamically, filtered by store)
            products_query = Product.query.join(Product.tags).filter(Tag.id == collection.tag_id)
            if g.current_store:
                products_query = products_query.filter(Product.store_id == g.current_store.id)
            
            products = products_query.all()
            return render_template('view_collection.html', collection=collection, products=products)
        else:
            # For regular collections, use the pre-populated products
            return render_template('view_collection.html', collection=collection)
    
    @app.route('/collections/<int:collection_id>/set-image/<int:product_id>', methods=['POST'])
    def set_collection_image(collection_id, product_id):
        """Set the collection's featured image from a product."""
        collection = Collection.query.get_or_404(collection_id)
        product = Product.query.get_or_404(product_id)

        # Security check: Ensure both belong to the current store
        if g.current_store:
            if collection.store_id != g.current_store.id or product.store_id != g.current_store.id:
                flash('Invalid operation: Collection or product not found in the current store.', 'danger')
                return redirect(url_for('view_collection', id=collection_id))
        else:
            # Handle case where no store is selected (should ideally not happen for store-specific items)
            flash('No store selected. Please select a store first.', 'warning')
            return redirect(url_for('stores'))


        # Optional check: Ensure product is actually in the collection (might be complex for smart collections)
        # For simplicity, we'll allow setting image from any product in the same store for now.

        if not product.image_url:
            flash(f'Product "{product.title}" does not have an image URL.', 'warning')
            return redirect(url_for('view_collection', id=collection_id))

        collection.image_url = product.image_url
        db.session.commit()
        flash(f'Collection "{collection.name}" image updated successfully.', 'success')
        return redirect(url_for('view_collection', id=collection_id))
    
    @app.route('/collections/delete-all', methods=['POST'])
    def delete_all_collections():
        """Delete all collections."""
        # Filter collections by store
        collections_query = Collection.query
        if g.current_store:
            collections_query = collections_query.filter_by(store_id=g.current_store.id)
        
        collections = collections_query.all()
        count = len(collections)
        
        for collection in collections:
            db.session.delete(collection)
        
        db.session.commit()
        flash(f'Successfully deleted {count} collections', 'success')
        return redirect(url_for('collections'))
    
    @app.route('/env-vars')
    def env_vars():
        """List all environment variables."""
        env_vars = EnvVar.query.all()
        return render_template('env_vars.html', env_vars=env_vars)
    
    @app.route('/env-vars/add', methods=['GET', 'POST'])
    def add_env_var():
        """Add a new environment variable."""
        form = EnvVarForm()
        if form.validate_on_submit():
            # Check if env var already exists
            existing = EnvVar.query.filter_by(key=form.key.data).first()
            if existing:
                flash(f'Environment variable "{form.key.data}" already exists. Please edit it instead.', 'warning')
                return redirect(url_for('env_vars'))
            
            env_var = EnvVar(
                key=form.key.data,
                value=form.value.data,
                description=form.description.data
            )
            db.session.add(env_var)
            db.session.commit()
            
            # Update the runtime environment
            os.environ[form.key.data] = form.value.data
            
            # Update Config object
            if form.key.data == 'ANTHROPIC_API_KEY':
                Config.ANTHROPIC_API_KEY = form.value.data
                # Update Claude service
                claude_service.api_key = form.value.data
                claude_service.client = anthropic.Anthropic(api_key=form.value.data)
            elif form.key.data == 'SHOPIFY_ACCESS_TOKEN':
                Config.SHOPIFY_ACCESS_TOKEN = form.value.data
                # Update Shopify service
                shopify_service.access_token = form.value.data
                shopify_service.headers['X-Shopify-Access-Token'] = form.value.data
            elif form.key.data == 'SHOPIFY_STORE_URL':
                Config.SHOPIFY_STORE_URL = form.value.data
                # Update Shopify service
                shopify_service.store_url = form.value.data
                if form.value.data and form.value.data.endswith('/'):
                    shopify_service.store_url = form.value.data[:-1]
            elif form.key.data == 'SECRET_KEY':
                Config.SECRET_KEY = form.value.data
            elif form.key.data == 'DATABASE_URI':
                Config.SQLALCHEMY_DATABASE_URI = form.value.data
            
            flash('Environment variable added successfully', 'success')
            return redirect(url_for('env_vars'))
        return render_template('env_var_form.html', form=form, title='Add Environment Variable')
    
    @app.route('/env-vars/<int:id>/edit', methods=['GET', 'POST'])
    def edit_env_var(id):
        """Edit an existing environment variable."""
        env_var = EnvVar.query.get_or_404(id)
        form = EnvVarForm(obj=env_var)
        if form.validate_on_submit():
            form.populate_obj(env_var)
            db.session.commit()
            
            # Update the runtime environment
            os.environ[form.key.data] = form.value.data
            
            # Update Config object
            if form.key.data == 'ANTHROPIC_API_KEY':
                Config.ANTHROPIC_API_KEY = form.value.data
                # Update Claude service
                claude_service.api_key = form.value.data
                claude_service.client = anthropic.Anthropic(api_key=form.value.data)
            elif form.key.data == 'SHOPIFY_ACCESS_TOKEN':
                Config.SHOPIFY_ACCESS_TOKEN = form.value.data
                # Update Shopify service
                shopify_service.access_token = form.value.data
                shopify_service.headers['X-Shopify-Access-Token'] = form.value.data
            elif form.key.data == 'SHOPIFY_STORE_URL':
                Config.SHOPIFY_STORE_URL = form.value.data
                # Update Shopify service
                shopify_service.store_url = form.value.data
                if form.value.data and form.value.data.endswith('/'):
                    shopify_service.store_url = form.value.data[:-1]
            elif form.key.data == 'SECRET_KEY':
                Config.SECRET_KEY = form.value.data
            elif form.key.data == 'DATABASE_URI':
                Config.SQLALCHEMY_DATABASE_URI = form.value.data
            
            flash('Environment variable updated successfully', 'success')
            return redirect(url_for('env_vars'))
        return render_template('env_var_form.html', form=form, title='Edit Environment Variable')
    
    @app.route('/env-vars/<int:id>/delete', methods=['POST'])
    def delete_env_var(id):
        """Delete an environment variable."""
        env_var = EnvVar.query.get_or_404(id)
        
        # Don't allow deletion of default env vars
        if env_var.key in Config.DEFAULT_ENV_VARS:
            flash(f'Cannot delete default environment variable "{env_var.key}". You can edit it instead.', 'danger')
            return redirect(url_for('env_vars'))
        
        # Remove from runtime environment
        if env_var.key in os.environ:
            del os.environ[env_var.key]
        
        db.session.delete(env_var)
        db.session.commit()
        flash('Environment variable deleted successfully', 'success')
        return redirect(url_for('env_vars'))
    
    @app.route('/tags')
    def tags():
        """List all tags with product counts with pagination."""
        page = request.args.get('page', 1, type=int)
        per_page = 20  # Number of tags per page
        
        # Get total count for pagination (filtered by store)
        tags_count_query = db.session.query(Tag)
        if g.current_store:
            tags_count_query = tags_count_query.filter_by(store_id=g.current_store.id)
        
        total = tags_count_query.count()
        
        # Get paginated tags with product counts (filtered by store)
        tags_query = db.session.query(Tag, func.count(product_tags.c.product_id).label('product_count')) \
            .outerjoin(product_tags) \
            .group_by(Tag.id) \
            .order_by(Tag.name)
        
        if g.current_store:
            tags_query = tags_query.filter(Tag.store_id == g.current_store.id)
        
        # Manual pagination since we're using a complex query
        offset = (page - 1) * per_page
        tags = tags_query.limit(per_page).offset(offset).all()
        
        # Create pagination object
        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page  # Ceiling division
        }
        
        return render_template('tags.html', tags=tags, pagination=pagination)
    
    @app.route('/tags/<int:id>/delete', methods=['POST'])
    def delete_tag(id):
        """Delete a tag."""
        tag = Tag.query.get_or_404(id)
        db.session.delete(tag)
        db.session.commit()
        flash('Tag deleted successfully', 'success')
        return redirect(url_for('tags'))
    
    @app.route('/tags/remove-all-from-store', methods=['POST'])
    def remove_all_store_tags():
        """Remove all tags from all products in the current store."""
        if not g.current_store:
            flash('Please select a store first.', 'warning')
            return redirect(url_for('tags'))
    
        # Find all products associated with the current store
        products_in_store = Product.query.filter_by(store_id=g.current_store.id).all()
    
        if not products_in_store:
            flash('No products found in the current store.', 'info')
            return redirect(url_for('tags'))
    
        # Iterate and clear tags for each product
        removed_count = 0
        for product in products_in_store:
            if product.tags:
                product.tags = []
                removed_count += 1
    
        if removed_count > 0:
            db.session.commit()
            flash(f'Removed all tags from {removed_count} product(s) in store "{g.current_store.name}".', 'success')
        else:
            flash(f'No products with tags found in store "{g.current_store.name}".', 'info')
    
        return redirect(url_for('tags'))
    
    @app.route('/api/products', methods=['GET'])
    def api_products():
        """API endpoint to get all products."""
        # Filter products by store
        products_query = Product.query
        if g.current_store:
            products_query = products_query.filter_by(store_id=g.current_store.id)
        
        products = products_query.all()
        return jsonify([product.to_dict() for product in products])
    
    @app.route('/api/collections', methods=['GET'])
    def api_collections():
        """API endpoint to get all collections."""
        # Filter collections by store
        collections_query = Collection.query
        if g.current_store:
            collections_query = collections_query.filter_by(store_id=g.current_store.id)
        
        collections = collections_query.all()
        return jsonify([collection.to_dict() for collection in collections])
    
    @app.route('/debug/stores')
    def debug_stores():
        """Debug endpoint to check stores."""
        stores = get_all_stores()
        current_store = get_current_store()
        
        return jsonify({
            'stores': [{'id': store.id, 'name': store.name, 'url': store.url} for store in stores],
            'current_store': {'id': current_store.id, 'name': current_store.name, 'url': current_store.url} if current_store else None,
            'store_count': len(stores)
        })
    
    @app.route('/debug/env-vars')
    def debug_env_vars():
        """Debug endpoint to check environment variables."""
        env_vars = EnvVar.query.all()
        env_vars_dict = {env_var.key: env_var.value for env_var in env_vars}
        
        # Check if the environment variable is in the database
        anthropic_api_key_in_db = 'ANTHROPIC_API_KEY' in env_vars_dict
        
        # Check if the environment variable is in the os.environ
        anthropic_api_key_in_os = 'ANTHROPIC_API_KEY' in os.environ
        
        # Check if the environment variable is in the Config
        anthropic_api_key_in_config = bool(Config.ANTHROPIC_API_KEY)
        
        # Check the value of the environment variable in the database
        anthropic_api_key_value_in_db = env_vars_dict.get('ANTHROPIC_API_KEY', '')
        
        # Check the value of the environment variable in the os.environ
        anthropic_api_key_value_in_os = os.environ.get('ANTHROPIC_API_KEY', '')
        
        # Check the value of the environment variable in the Config
        anthropic_api_key_value_in_config = Config.ANTHROPIC_API_KEY
        
        # Check if the claude_service has the API key
        claude_service_has_api_key = bool(claude_service.api_key)
        
        # Check the value of the API key in the claude_service
        claude_service_api_key_value = claude_service.api_key
        
        return jsonify({
            'anthropic_api_key_in_db': anthropic_api_key_in_db,
            'anthropic_api_key_in_os': anthropic_api_key_in_os,
            'anthropic_api_key_in_config': anthropic_api_key_in_config,
            'anthropic_api_key_value_in_db': anthropic_api_key_value_in_db[:5] + '...' if anthropic_api_key_value_in_db else '',
            'anthropic_api_key_value_in_os': anthropic_api_key_value_in_os[:5] + '...' if anthropic_api_key_value_in_os else '',
            'anthropic_api_key_value_in_config': anthropic_api_key_value_in_config[:5] + '...' if anthropic_api_key_value_in_config else '',
            'claude_service_has_api_key': claude_service_has_api_key,
            'claude_service_api_key_value': claude_service_api_key_value[:5] + '...' if claude_service_api_key_value else '',
            'env_vars': {k: v[:5] + '...' if v else '' for k, v in env_vars_dict.items()}
        })
    
    @app.route('/migrate-database')
    def migrate_db_route():
        """Migrate the database to add new columns."""
        from auto_migrate import run_migrations
        success = run_migrations(app)
        
        if success:
            return "Database migration completed successfully. <a href='/collections'>Go to Collections</a>"
        else:
            return "Database migration encountered errors. Check the logs for details. <a href='/collections'>Go to Collections</a>"
    
    # Shopify Integration Routes
    @app.route('/shopify/import-products', methods=['POST'])
    def import_products_from_shopify():
        """Import products from Shopify."""
        # Set the Shopify context for the current store
        if not g.current_store or not shopify_service.set_store_context(g.current_store):
            store_name = g.current_store.name if g.current_store else "No store selected"
            flash(f'Shopify integration not configured for store "{store_name}". Please check store credentials.', 'danger')
            # Redirect to stores page or env vars depending on context
            redirect_target = 'stores' if g.current_store else 'env_vars'
            return redirect(url_for(redirect_target))
        
        # Now call the import function, which uses the set context
        result = shopify_service.import_products_from_shopify(db, current_store=g.current_store)
        
        if 'error' in result:
            flash(f'Error importing products from Shopify: {result["error"]}', 'danger')
        else:
            flash(f'Successfully imported {result["imported"]} products from Shopify', 'success')
        
        return redirect(url_for('products'))
    
    @app.route('/shopify/import-collections', methods=['POST'])
    def import_collections_from_shopify():
        """Import collections from Shopify."""
        # Set the Shopify context for the current store
        if not g.current_store or not shopify_service.set_store_context(g.current_store):
            store_name = g.current_store.name if g.current_store else "No store selected"
            flash(f'Shopify integration not configured for store "{store_name}". Please check store credentials.', 'danger')
            # Redirect to stores page or env vars depending on context
            redirect_target = 'stores' if g.current_store else 'env_vars'
            return redirect(url_for(redirect_target))
        
        # Now call the import function, which uses the set context
        result = shopify_service.import_collections_from_shopify(db, current_store=g.current_store)
        
        if 'error' in result:
            flash(f'Error importing collections from Shopify: {result["error"]}', 'danger')
        else:
            flash(f'Successfully imported {result["imported"]} collections and updated {result["updated"]} from Shopify', 'success')
        
        return redirect(url_for('collections'))
    
    @app.route('/shopify/export-product/<int:id>', methods=['POST'])
    def export_product_to_shopify(id):
        """Export a product to Shopify."""
        # Set the Shopify context for the current store
        if not g.current_store or not shopify_service.set_store_context(g.current_store):
            store_name = g.current_store.name if g.current_store else "No store selected"
            flash(f'Shopify integration not configured for store "{store_name}". Please check store credentials.', 'danger')
            # Redirect to stores page or env vars depending on context
            redirect_target = 'stores' if g.current_store else 'env_vars'
            return redirect(url_for(redirect_target))
        
        product = Product.query.get_or_404(id)
        # Pass current_store for context in the service method as well
        result = shopify_service.export_product_to_shopify(product, current_store=g.current_store)
        
        if 'error' in result:
            flash(f'Error exporting product to Shopify: {result["error"]}', 'danger')
        else:
            # Update product with Shopify ID if it's a new product
            if 'product' in result and 'id' in result['product'] and not product.shopify_id:
                product.shopify_id = str(result['product']['id'])
                db.session.commit()
            
            flash('Product successfully exported to Shopify', 'success')
        
        return redirect(url_for('edit_product', id=id))
    
    @app.route('/shopify/export-collection/<int:id>', methods=['POST'])
    def export_collection_to_shopify(id):
        """Export a collection to Shopify."""
        # Set the Shopify context for the current store
        if not g.current_store or not shopify_service.set_store_context(g.current_store):
            store_name = g.current_store.name if g.current_store else "No store selected"
            flash(f'Shopify integration not configured for store "{store_name}". Please check store credentials.', 'danger')
            # Redirect to stores page or env vars depending on context
            redirect_target = 'stores' if g.current_store else 'env_vars'
            return redirect(url_for(redirect_target))
        
        collection = Collection.query.get_or_404(id)
        
        # For smart collections (with a tag), we need to make sure all products with this tag
        # are included in the collection when exporting to Shopify
        if collection.tag:
            # Get all products with this tag
            products = Product.query.join(Product.tags).filter(Tag.id == collection.tag_id).all()
            
            # Temporarily store the products in the collection for export
            original_products = collection.products
            collection.products = products
            
            # Pass current_store for context
            result = shopify_service.export_collection_to_shopify(collection, current_store=g.current_store)
            
            # Restore original products
            collection.products = original_products
        else:
            # For regular collections, use the existing products
            # Pass current_store for context
            result = shopify_service.export_collection_to_shopify(collection, current_store=g.current_store)
        
        if 'error' in result:
            flash(f'Error exporting collection to Shopify: {result["error"]}', 'danger')
        else:
            # Update collection with Shopify ID if it's a new collection
            if 'custom_collection' in result and 'id' in result['custom_collection'] and not collection.shopify_id:
                collection.shopify_id = str(result['custom_collection']['id'])
                db.session.commit()
            
            flash('Collection successfully exported to Shopify', 'success')
        
        return redirect(url_for('view_collection', id=id))
    
    @app.route('/shopify/export-collections/selected', methods=['POST'])
    def export_selected_collections_to_shopify():
        """Export selected collections to Shopify with SEO optimization."""
        # Set the Shopify context for the current store
        if not g.current_store or not shopify_service.set_store_context(g.current_store):
            store_name = g.current_store.name if g.current_store else "No store selected"
            flash(f'Shopify integration not configured for store "{store_name}". Please check store credentials.', 'danger')
            # Redirect to stores page or env vars depending on context
            redirect_target = 'stores' if g.current_store else 'env_vars'
            return redirect(url_for(redirect_target))
        
        # Get selected collection IDs
        collection_ids = request.form.getlist('collection_ids')
        
        if not collection_ids:
            flash('No collections selected for export', 'warning')
            return redirect(url_for('collections'))
        
        # Get selected collections (filtered by store)
        collections_query = Collection.query.filter(Collection.id.in_(collection_ids))
        if g.current_store:
            collections_query = collections_query.filter_by(store_id=g.current_store.id)
        collections = collections_query.all()
        
        if not collections:
            flash('No collections available to export. All collections may already be exported to Shopify.', 'warning')
            return redirect(url_for('collections'))
        
        success_count = 0
        error_count = 0
        
        for collection in collections:
            # For smart collections (with a tag), we need to make sure all products with this tag
            # are included in the collection when exporting to Shopify
            if collection.tag:
                # Get all products with this tag
                products = Product.query.join(Product.tags).filter(Tag.id == collection.tag_id).all()
                
                # Temporarily store the products in the collection for export
                original_products = collection.products
                collection.products = products
                
                # Generate SEO-optimized content
                product_examples = products[:3]
                example_text = ""
                if product_examples:
                    # Apply cleanup rules to titles before joining
                    cleaned_titles = [apply_cleanup_rules(p.title) for p in product_examples]
                    example_text = "Featuring " + ", ".join(cleaned_titles)
                    if len(products) > 3:
                        example_text += f" and {len(products) - 3} more items"

                # Update collection with SEO content
                collection.name = f"{collection.tag.name.title()} Collection | Shop Premium {collection.tag.name.title()}"
                collection.description = f"""
                <h1>Premium {collection.tag.name.title()} Collection</h1>
                <p>Discover our exclusive collection of {collection.tag.name} products, carefully curated to bring you the finest selection. {example_text}.</p>
                <h2>Why Shop Our {collection.tag.name.title()} Collection?</h2>
                <ul>
                    <li>Handpicked selection of premium {collection.tag.name} products</li>
                    <li>High-quality materials and expert craftsmanship</li>
                    <li>Trendy and timeless designs for every style</li>
                    <li>Fast shipping and excellent customer service</li>
                </ul>
                <h2>About Our {collection.tag.name.title()} Products</h2>
                <p>Each item in our {collection.tag.name} collection is selected for its quality, style, and value. Whether you're looking for everyday essentials or statement pieces, you'll find the perfect {collection.tag.name} to suit your needs.</p>
                <p>Shop our {collection.tag.name} collection today and experience the difference quality makes.</p>
                """
                collection.meta_description = f"Shop our premium {collection.tag.name} collection. {example_text}. Free shipping on qualifying orders. Shop now!"

                # Pass current_store for context
                result = shopify_service.export_collection_to_shopify(collection, current_store=g.current_store)
                
                # Restore original products
                collection.products = original_products
            else:
                # For regular collections, optimize SEO content
                product_examples = collection.products[:3]
                example_text = ""
                if product_examples:
                    # Apply cleanup rules to titles before joining
                    cleaned_titles = [apply_cleanup_rules(p.title) for p in product_examples]
                    example_text = "Featuring " + ", ".join(cleaned_titles)
                    if len(collection.products) > 3:
                        example_text += f" and {len(collection.products) - 3} more items"

                # Update collection with SEO content
                base_name = collection.name.replace(" Collection", "").strip()
                collection.name = f"{base_name} Collection | Shop Premium {base_name}"
                collection.description = f"""
                <h1>Premium {base_name} Collection</h1>
                <p>Discover our exclusive collection of {base_name} products, carefully curated to bring you the finest selection. {example_text}.</p>
                <h2>Why Shop Our {base_name} Collection?</h2>
                <ul>
                    <li>Handpicked selection of premium {base_name} products</li>
                    <li>High-quality materials and expert craftsmanship</li>
                    <li>Trendy and timeless designs for every style</li>
                    <li>Fast shipping and excellent customer service</li>
                </ul>
                <h2>About Our {base_name} Products</h2>
                <p>Each item in our {base_name} collection is selected for its quality, style, and value. Whether you're looking for everyday essentials or statement pieces, you'll find the perfect {base_name} to suit your needs.</p>
                <p>Shop our {base_name} collection today and experience the difference quality makes.</p>
                """
                collection.meta_description = f"Shop our premium {base_name} collection. {example_text}. Free shipping on qualifying orders. Shop now!"

                # Pass current_store for context
                result = shopify_service.export_collection_to_shopify(collection, current_store=g.current_store)
            
            if 'error' not in result:
                # Update collection with Shopify ID
                if 'custom_collection' in result and 'id' in result['custom_collection']:
                    collection.shopify_id = str(result['custom_collection']['id'])
                    success_count += 1
            else:
                error_count += 1
        
        db.session.commit()
        
        if success_count > 0:
            flash(f'Successfully exported {success_count} collections to Shopify', 'success')
        if error_count > 0:
            flash(f'Failed to export {error_count} collections to Shopify', 'warning')
        
        return redirect(url_for('collections'))
    
    @app.route('/shopify/export-all-collections', methods=['POST'])
    def export_all_collections_to_shopify():
        """Export all collections to Shopify."""
        # Set the Shopify context for the current store
        if not g.current_store or not shopify_service.set_store_context(g.current_store):
            store_name = g.current_store.name if g.current_store else "No store selected"
            flash(f'Shopify integration not configured for store "{store_name}". Please check store credentials.', 'danger')
            # Redirect to stores page or env vars depending on context
            redirect_target = 'stores' if g.current_store else 'env_vars'
            return redirect(url_for(redirect_target))
        
        # Get all collections that haven't been exported yet (filtered by store)
        collections_query = Collection.query.filter(Collection.shopify_id.is_(None))
        if g.current_store:
            collections_query = collections_query.filter_by(store_id=g.current_store.id)
        collections = collections_query.all()
        
        if not collections:
            flash('No collections available to export. All collections may already be exported to Shopify.', 'warning')
            return redirect(url_for('collections'))
        
        success_count = 0
        error_count = 0
        
        for collection in collections:
            # For smart collections (with a tag), we need to make sure all products with this tag
            # are included in the collection when exporting to Shopify
            if collection.tag:
                # Get all products with this tag
                products = Product.query.join(Product.tags).filter(Tag.id == collection.tag_id).all()
                
                # Temporarily store the products in the collection for export
                original_products = collection.products
                collection.products = products
                
                # Pass current_store for context
                result = shopify_service.export_collection_to_shopify(collection, current_store=g.current_store)
                
                # Restore original products
                collection.products = original_products
            else:
                # For regular collections, use the existing products
                # Pass current_store for context
                result = shopify_service.export_collection_to_shopify(collection, current_store=g.current_store)
            
            if 'error' not in result:
                # Update collection with Shopify ID
                if 'custom_collection' in result and 'id' in result['custom_collection']:
                    collection.shopify_id = str(result['custom_collection']['id'])
                    success_count += 1
            else:
                error_count += 1
        
        db.session.commit()
        
        if success_count > 0:
            flash(f'Successfully exported {success_count} collections to Shopify', 'success')
        if error_count > 0:
            flash(f'Failed to export {error_count} collections to Shopify', 'warning')
        
        return redirect(url_for('collections'))
    
    # Store Management Routes
    @app.route('/stores')
    def stores():
        """List all stores."""
        stores = get_all_stores()
        return render_template('stores.html', stores=stores)
    
    @app.route('/stores/add', methods=['GET', 'POST'])
    def add_store():
        """Add a new store."""
        form = StoreForm()
        if form.validate_on_submit():
            # Check if store with this URL already exists
            existing_store = Store.query.filter_by(url=form.url.data).first()
            if existing_store:
                flash(f'A store with URL "{form.url.data}" already exists.', 'warning')
                return redirect(url_for('stores'))
            
            # Create new store
            store = Store(
                name=form.name.data,
                url=form.url.data,
                access_token=form.access_token.data
            )
            db.session.add(store)
            db.session.commit()
            
            # Run migrations for the new store
            from auto_migrate import migrate_store
            migrate_store(app, store.id)
            
            # Set as current store
            set_current_store(store.id)
            
            flash('Store added successfully and set as current store.', 'success')
            return redirect(url_for('stores'))
        
        return render_template('store_form.html', form=form, title='Add Store')
    
    @app.route('/stores/<int:id>/edit', methods=['GET', 'POST'])
    def edit_store(id):
        """Edit an existing store."""
        store = Store.query.get_or_404(id)
        form = StoreForm(obj=store)
        
        if form.validate_on_submit():
            # Check if URL changed and if new URL already exists
            if form.url.data != store.url:
                existing_store = Store.query.filter_by(url=form.url.data).first()
                if existing_store and existing_store.id != store.id:
                    flash(f'A store with URL "{form.url.data}" already exists.', 'warning')
                    return redirect(url_for('stores'))
            
            # Update store
            form.populate_obj(store)
            db.session.commit()
            
            # If this is the current store, update environment variables
            if g.current_store and g.current_store.id == store.id:
                os.environ['SHOPIFY_STORE_URL'] = store.url
                if store.access_token:
                    os.environ['SHOPIFY_ACCESS_TOKEN'] = store.access_token
            
            flash('Store updated successfully.', 'success')
            return redirect(url_for('stores'))
        
        return render_template('store_form.html', form=form, title='Edit Store')
    
    @app.route('/stores/<int:id>/delete', methods=['POST'])
    def delete_store(id):
        """Delete a store."""
        store = Store.query.get_or_404(id)
        
        # Check if this is the current store
        is_current = g.current_store and g.current_store.id == store.id
        
        # Delete the store
        db.session.delete(store)
        db.session.commit()
        
        # If this was the current store, clear the session
        if is_current:
            if 'current_store_id' in session:
                del session['current_store_id']
        
        flash('Store deleted successfully.', 'success')
        return redirect(url_for('stores'))
    
    @app.route('/stores/<int:id>/select')
    def set_current_store_route(id):
        """Set the current store."""
        store = set_current_store(id)
        if store:
            flash(f'Now viewing store: {store.name}', 'success')
        else:
            flash('Store not found.', 'danger')
        
        return redirect(url_for('index'))

    # --- Add Cleanup Rule Routes ---

    @app.route('/cleanup-rules')
    def cleanup_rules():
        """List all cleanup rules for the current store."""
        if not g.current_store:
            flash('Please select a store first.', 'warning')
            return redirect(url_for('stores'))
            
        rules = CleanupRule.query.filter_by(store_id=g.current_store.id).order_by(CleanupRule.priority).all()
        # Pass the form for the 'Add Rule' button in the template
        form = CleanupRuleForm()
        return render_template('cleanup_rules.html', rules=rules, form=form, title='Cleanup Rules')

    @app.route('/cleanup-rules/add', methods=['GET', 'POST'])
    def add_cleanup_rule():
        """Add a new cleanup rule for the current store."""
        if not g.current_store:
            flash('Please select a store first.', 'warning')
            return redirect(url_for('stores'))
            
        form = CleanupRuleForm()
        if form.validate_on_submit():
            rule = CleanupRule(
                store_id=g.current_store.id,
                pattern=form.pattern.data,
                replacement=form.replacement.data,
                is_regex=form.is_regex.data,
                priority=form.priority.data or 0 # Default priority to 0 if not provided
            )
            db.session.add(rule)
            db.session.commit()
            flash('Cleanup rule added successfully.', 'success')
            return redirect(url_for('cleanup_rules'))
        # If GET or validation fails, render the form page
        return render_template('cleanup_rule_form.html', form=form, title='Add Cleanup Rule')

    @app.route('/cleanup-rules/<int:id>/edit', methods=['GET', 'POST'])
    def edit_cleanup_rule(id):
        """Edit an existing cleanup rule."""
        rule = CleanupRule.query.get_or_404(id)
        # Ensure the rule belongs to the current store
        if not g.current_store or rule.store_id != g.current_store.id:
            flash('Rule not found or access denied.', 'danger')
            return redirect(url_for('cleanup_rules'))
            
        form = CleanupRuleForm(obj=rule)
        if form.validate_on_submit():
            form.populate_obj(rule)
            rule.priority = form.priority.data or 0 # Default priority
            db.session.commit()
            flash('Cleanup rule updated successfully.', 'success')
            return redirect(url_for('cleanup_rules'))
        return render_template('cleanup_rule_form.html', form=form, title='Edit Cleanup Rule', rule_id=id) # Pass rule_id for form action

    @app.route('/cleanup-rules/<int:id>/delete', methods=['POST'])
    def delete_cleanup_rule(id):
        """Delete a cleanup rule."""
        rule = CleanupRule.query.get_or_404(id)
        # Ensure the rule belongs to the current store
        if not g.current_store or rule.store_id != g.current_store.id:
            flash('Rule not found or access denied.', 'danger')
            return redirect(url_for('cleanup_rules'))
            
        db.session.delete(rule)
        db.session.commit()
        flash('Cleanup rule deleted successfully.', 'success')
        return redirect(url_for('cleanup_rules'))

    # --- End Cleanup Rule Routes ---

    # --- Add Bulk Apply Cleanup Route ---

    @app.route('/collections/apply-cleanup-rules', methods=['POST'])
    def apply_rules_to_collections():
        """Bulk apply cleanup rules to existing collection descriptions and meta descriptions."""
        if not g.current_store:
            flash('Please select a store first.', 'warning')
            return redirect(url_for('stores'))

        collections_query = Collection.query.filter_by(store_id=g.current_store.id)
        collections = collections_query.all()
        
        updated_count = 0
        for collection in collections:
            products_to_consider = []
            base_name = ""

            if collection.tag:
                # Smart collection: use products associated with the tag
                products_to_consider = Product.query.join(Product.tags).filter(
                    Tag.id == collection.tag_id,
                    Product.store_id == g.current_store.id # Ensure products are from the same store
                ).all()
                base_name = collection.tag.name.title()
            else:
                # Regular collection: use explicitly linked products
                # Ensure products are loaded and filtered by store if necessary (though they should be)
                products_to_consider = [p for p in collection.products if p.store_id == g.current_store.id]
                # Try to derive a base name from the collection name
                base_name = collection.name.replace(" Collection", "").replace("Shop Premium ", "").strip()

            if not products_to_consider:
                continue # Skip collections with no relevant products

            # Generate example text with cleaned titles
            product_examples = products_to_consider[:3]
            example_text = ""
            if product_examples:
                cleaned_titles = [apply_cleanup_rules(p.title) for p in product_examples]
                example_text = "Featuring " + ", ".join(cleaned_titles)
                if len(products_to_consider) > 3:
                    example_text += f" and {len(products_to_consider) - 3} more items"

            # Regenerate SEO content using cleaned example_text
            # Only update if base_name is meaningful
            if base_name:
                # Regenerate description
                collection.description = f"""
                <h1>Premium {base_name} Collection</h1>
                <p>Discover our exclusive collection of {base_name} products, carefully curated to bring you the finest selection. {example_text}.</p>
                <h2>Why Shop Our {base_name} Collection?</h2>
                <ul>
                    <li>Handpicked selection of premium {base_name} products</li>
                    <li>High-quality materials and expert craftsmanship</li>
                    <li>Trendy and timeless designs for every style</li>
                    <li>Fast shipping and excellent customer service</li>
                </ul>
                <h2>About Our {base_name} Products</h2>
                <p>Each item in our {base_name} collection is selected for its quality, style, and value. Whether you're looking for everyday essentials or statement pieces, you'll find the perfect {base_name} to suit your needs.</p>
                <p>Shop our {base_name} collection today and experience the difference quality makes.</p>
                """
                # Regenerate meta description
                collection.meta_description = f"Shop our premium {base_name} collection. {example_text}. Free shipping on qualifying orders. Shop now!"
                
                # Mark the object as modified for SQLAlchemy
                db.session.add(collection)
                updated_count += 1

        if updated_count > 0:
            try:
                db.session.commit()
                flash(f'Successfully applied cleanup rules to {updated_count} collections.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error applying rules: {str(e)}', 'danger')
        else:
            flash('No collections were updated. They might already be up-to-date or have no associated products.', 'info')

        return redirect(url_for('collections'))

    # --- End Bulk Apply Cleanup Route ---
    
    # --- CLI Commands ---
    @app.cli.command("seed-seo-defaults")
    def seed_seo_defaults():
        """Seeds the SEODefaults table with default templates for each store."""
        print("Seeding SEO defaults...")
        default_templates = {
            'product': {
                'title_template': '{title} | {store_name}',
                'description_template': 'Shop {title} at {store_name}. {description_excerpt}',
                'og_title_template': '{title} - Available at {store_name}',
                'og_description_template': 'Shop {title} at {store_name}. {description_excerpt}', # Added default
                'twitter_title_template': 'Shop {title} at {store_name}',
                'twitter_description_template': 'Shop {title} at {store_name}. {description_excerpt}' # Added default
            },
            'collection': {
                'title_template': '{name} Collection | {store_name}',
                'description_template': 'Explore our {name} collection. {product_count} products including {example_products}',
                'og_title_template': 'Shop {name} Collection at {store_name}',
                'og_description_template': 'Explore our {name} collection. {product_count} products including {example_products}', # Added default
                'twitter_title_template': '{name} Collection at {store_name}',
                'twitter_description_template': 'Explore our {name} collection. {product_count} products including {example_products}' # Added default
            }
        }

        stores = Store.query.all()
        if not stores:
            print("No stores found. Skipping seeding.")
            return

        for store in stores:
            print(f"Processing store: {store.name} (ID: {store.id})")
            for entity_type, templates in default_templates.items():
                existing_default = SEODefaults.query.filter_by(
                    store_id=store.id,
                    entity_type=entity_type
                ).first()

                if not existing_default:
                    print(f"  Creating default for entity type: {entity_type}")
                    new_default = SEODefaults(
                        store_id=store.id,
                        entity_type=entity_type,
                        title_template=templates.get('title_template'),
                        description_template=templates.get('description_template'),
                        og_title_template=templates.get('og_title_template'),
                        og_description_template=templates.get('og_description_template'),
                        twitter_title_template=templates.get('twitter_title_template'),
                        twitter_description_template=templates.get('twitter_description_template')
                    )
                    db.session.add(new_default)
                else:
                    print(f"  Default already exists for entity type: {entity_type}")

        try:
            db.session.commit()
            print("SEO defaults seeding completed successfully.")
        except Exception as e:
            db.session.rollback()
            print(f"Error seeding SEO defaults: {e}")

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
