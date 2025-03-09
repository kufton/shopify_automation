import os
import anthropic
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, g, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func
from models import db, Product, Tag, Collection, EnvVar, product_tags, Store
from forms import ProductForm, EnvVarForm, CollectionForm, TagForm, AutoTagForm, CreateCollectionsForm, StoreForm, StoreSelectForm
from claude_integration import ClaudeTaggingService
from shopify_integration import ShopifyIntegration
from store_management import get_current_store, set_current_store, filter_query_by_store, get_all_stores
from config import Config
from auto_migrate import run_migrations
import json

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    csrf = CSRFProtect(app)
    
    # Ensure the instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)
    
    # Initialize services
    claude_service = ClaudeTaggingService()
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
        
        # Run database migrations to ensure multi-store support
        try:
            # Run migrations using SQLAlchemy
            print("Running database migrations...")
            # Check if store_id column exists in products table
            try:
                db.engine.execute('SELECT store_id FROM products LIMIT 1')
                print("store_id column exists in products table")
            except Exception:
                print("Adding store_id column to products table")
                db.engine.execute('ALTER TABLE products ADD COLUMN store_id INTEGER')
            
            # Check if store_id column exists in collections table
            try:
                db.engine.execute('SELECT store_id FROM collections LIMIT 1')
                print("store_id column exists in collections table")
            except Exception:
                print("Adding store_id column to collections table")
                db.engine.execute('ALTER TABLE collections ADD COLUMN store_id INTEGER')
            
            # Check if store_id column exists in tags table
            try:
                db.engine.execute('SELECT store_id FROM tags LIMIT 1')
                print("store_id column exists in tags table")
            except Exception:
                print("Adding store_id column to tags table")
                db.engine.execute('ALTER TABLE tags ADD COLUMN store_id INTEGER')
            
            # Associate all products, collections, and tags with the default store if they don't have a store_id
            default_store = Store.query.first()
            if default_store:
                db.engine.execute(f'UPDATE products SET store_id = {default_store.id} WHERE store_id IS NULL')
                db.engine.execute(f'UPDATE collections SET store_id = {default_store.id} WHERE store_id IS NULL')
                db.engine.execute(f'UPDATE tags SET store_id = {default_store.id} WHERE store_id IS NULL')
                print(f"Associated orphaned items with default store (ID: {default_store.id})")
        except Exception as e:
            print(f"Error during migrations: {str(e)}")
        
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
        
        # Load environment variables from database
        env_vars = EnvVar.query.all()
        for env_var in env_vars:
            # Update the runtime environment
            os.environ[env_var.key] = env_var.value
            
            # Update Config object
            if env_var.key == 'ANTHROPIC_API_KEY':
                Config.ANTHROPIC_API_KEY = env_var.value
                # Update Claude service
                claude_service.api_key = env_var.value
                if env_var.value:  # Only create client if API key is not empty
                    claude_service.client = anthropic.Anthropic(api_key=env_var.value)
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
            elif env_var.key == 'SECRET_KEY':
                Config.SECRET_KEY = env_var.value
            elif env_var.key == 'DATABASE_URI':
                Config.SQLALCHEMY_DATABASE_URI = env_var.value
    
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
        # Filter products by store
        products_query = Product.query
        
        if g.current_store:
            products_query = products_query.filter_by(store_id=g.current_store.id)
        
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
            
            # Auto-tag the product if Claude API key is available
            if Config.ANTHROPIC_API_KEY:
                tags = claude_service.generate_tags(product)
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
                flash('Product added. Claude API key not set, skipping auto-tagging.', 'warning')
            
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
    
    @app.route('/products/auto-tag', methods=['POST'])
    async def auto_tag_products():
        """Auto-tag selected products using Claude asynchronously."""
        product_ids = request.form.getlist('product_ids')
        
        if not product_ids:
            flash('No products selected for auto-tagging', 'warning')
            return redirect(url_for('products'))
        
        if not Config.ANTHROPIC_API_KEY:
            flash('Claude API key not set. Please set it in environment variables.', 'danger')
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
        results = await claude_service.batch_generate_tags(products, batch_size=50)
        
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
            
            # Check if a collection with this slug already exists
            # If so, append a unique identifier
            slug_query = Collection.query
            if g.current_store:
                slug_query = slug_query.filter_by(store_id=g.current_store.id)
            
            counter = 1
            while slug_query.filter_by(slug=slug).first():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
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
                # If so, append a unique identifier
                slug_query = Collection.query
                if g.current_store:
                    slug_query = slug_query.filter_by(store_id=g.current_store.id)
                
                counter = 1
                while slug_query.filter(Collection.slug == slug, Collection.id != collection.id).first():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                
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
                
            # Check if a collection already exists for this tag
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
                
                # Check if a collection with this slug already exists
                # If so, append a unique identifier
                slug_query = Collection.query
                if g.current_store:
                    slug_query = slug_query.filter_by(store_id=g.current_store.id)
                
                counter = 1
                while slug_query.filter_by(slug=slug).first():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                
                # Get product titles for meta description
                product_titles = [p.title for p in tag.products[:5]]
                product_titles_text = ", ".join(product_titles)
                if len(product_titles) < len(tag.products):
                    product_titles_text += f", and {len(tag.products) - len(product_titles)} more"
                
                # Get product examples for description generation
                product_examples = [
                    {"title": p.title, "description": p.description} 
                    for p in tag.products[:5]
                ]
                
                # Use Claude to generate meta description and description
                meta_description = f"Explore our {tag.name} collection featuring {product_titles_text}. Find the perfect {tag.name} for your needs."
                
                description = f"""
                <p>Welcome to our curated collection of {tag.name} products. We've carefully selected {product_count} items that represent the best in quality and value.</p>
                <p>Whether you're looking for {tag.name} for personal use or as a gift, our collection offers a variety of options to suit your needs.</p>
                <h2>Why Choose Our {tag.name.title()} Products?</h2>
                <ul>
                    <li>Premium quality materials and craftsmanship</li>
                    <li>Carefully selected for durability and performance</li>
                    <li>Perfect for both everyday use and special occasions</li>
                    <li>Backed by our satisfaction guarantee</li>
                </ul>
                <p>Browse our complete {tag.name} collection below and find the perfect item for you today!</p>
                """
                
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
        untagged_query = Product.query.filter(~Product.tags.any())
        if g.current_store:
            untagged_query = untagged_query.filter_by(store_id=g.current_store.id)
        
        untagged_products = untagged_query.all()
        if untagged_products:
            flash(f'Analyzing {len(untagged_products)} untagged products for collections. This may take a while...', 'info')
            
            # Process products in batches asynchronously
            results = await claude_service.batch_analyze_products_for_collections(untagged_products, batch_size=50)
            
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
                    # Check if a collection already exists for this category
                    collection_query = Collection.query.filter_by(name=f"{category.capitalize()} Collection")
                    if g.current_store:
                        collection_query = collection_query.filter_by(store_id=g.current_store.id)
                    
                    existing_collection = collection_query.first()
                    if not existing_collection:
                        # Generate SEO-friendly slug
                        base_slug = category.lower().replace(' ', '-')
                        slug = base_slug
                        
                        # Check if a collection with this slug already exists
                        # If so, append a unique identifier
                        slug_query = Collection.query
                        if g.current_store:
                            slug_query = slug_query.filter_by(store_id=g.current_store.id)
                        
                        counter = 1
                        while slug_query.filter_by(slug=slug).first():
                            slug = f"{base_slug}-{counter}"
                            counter += 1
                        
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
            flash('No new collections created. Collections already exist for
