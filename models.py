from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import JSON # Import JSON type

db = SQLAlchemy()

# Add indexes to frequently queried columns to improve performance

# Association table for Product-Tag many-to-many relationship
product_tags = db.Table('product_tags',
    db.Column('product_id', db.Integer, db.ForeignKey('products.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

# Association table for Collection-Product many-to-many relationship
collection_products = db.Table('collection_products',
    db.Column('collection_id', db.Integer, db.ForeignKey('collections.id'), primary_key=True),
    db.Column('product_id', db.Integer, db.ForeignKey('products.id'), primary_key=True)
)

# --- SEO Mixin ---
class SEOFields(object):
    """Mixin for common SEO fields"""
    meta_title = db.Column(db.String(60))
    meta_description = db.Column(db.String(160))
    
    # Open Graph
    og_title = db.Column(db.String(95))
    og_description = db.Column(db.String(200))
    og_image = db.Column(db.String(500))
    og_type = db.Column(db.String(50)) # e.g., 'product', 'website', 'article'
    
    # Twitter Cards
    twitter_card = db.Column(db.String(15), default='summary_large_image') # 'summary', 'summary_large_image', 'app', 'player'
    twitter_title = db.Column(db.String(70))
    twitter_description = db.Column(db.String(200))
    twitter_image = db.Column(db.String(500))
    
    # Common
    canonical_url = db.Column(db.String(500))
    structured_data = db.Column(JSON) # Store JSON-LD or other structured data

class Store(db.Model):
    """Store model."""
    __tablename__ = 'stores'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(255), nullable=False, unique=True)
    access_token = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    products = db.relationship('Product', backref='store', lazy=True, cascade="all, delete-orphan")
    collections = db.relationship('Collection', backref='store', lazy=True, cascade="all, delete-orphan")
    tags = db.relationship('Tag', backref='store', lazy=True, cascade="all, delete-orphan")
    credentials = db.relationship('StoreCredentials', backref='store', lazy=True, cascade="all, delete-orphan")
    cleanup_rules = db.relationship('CleanupRule', backref='store', lazy=True, cascade="all, delete-orphan")
    seo_defaults = db.relationship('SEODefaults', backref='store', lazy=True, cascade="all, delete-orphan") # Added SEO Defaults relationship
    
    def __repr__(self):
        return f'<Store {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class Product(db.Model, SEOFields): # Added SEOFields mixin
    """Product model."""
    __tablename__ = 'products'
    __table_args__ = (
        db.Index('idx_product_shopify_id', 'shopify_id'),
        db.Index('idx_product_title', 'title'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    cleaned_title = db.Column(db.String(255))
    description = db.Column(db.Text)
    price = db.Column(db.Float)
    image_url = db.Column(db.String(500))
    shopify_id = db.Column(db.String(100))  # Shopify product ID for syncing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Store relationship
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'))
    
    # Relationships
    tags = db.relationship('Tag', secondary=product_tags, lazy='subquery',
                          backref=db.backref('products', lazy=True))
    
    def __repr__(self):
        return f'<Product {self.title}>'
    
    def to_dict(self):
        # Include SEO fields in the dictionary representation
        seo_dict = {key: getattr(self, key) for key in SEOFields.__dict__ if not key.startswith('_') and not callable(getattr(SEOFields, key))}
        base_dict = {
            'id': self.id,
            'title': self.title,
            'cleaned_title': self.cleaned_title,
            'description': self.description,
            'price': self.price,
            'image_url': self.image_url,
            'shopify_id': self.shopify_id,
            'tags': [tag.name for tag in self.tags],
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        base_dict.update(seo_dict)
        return base_dict

class Tag(db.Model):
    """Tag model."""
    __tablename__ = 'tags'
    __table_args__ = (
        db.Index('idx_tag_name', 'name'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Removed unique constraint as tags can be duplicated across stores
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Store relationship
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'))
    
    def __repr__(self):
        return f'<Tag {self.name}>'

class Collection(db.Model, SEOFields): # Added SEOFields mixin
    """Collection model."""
    __tablename__ = 'collections'
    __table_args__ = (
        db.Index('idx_collection_slug', 'slug'),
        db.Index('idx_collection_shopify_id', 'shopify_id'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255))  # Removed unique constraint as slugs can be duplicated across stores
    description = db.Column(db.Text)
    # meta_description is now part of SEOFields
    # meta_description = db.Column(db.Text) 
    shopify_id = db.Column(db.String(100))  # Shopify collection ID for syncing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Store relationship
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'))
    
    # Relationships
    products = db.relationship('Product', secondary=collection_products, lazy='subquery',
                              backref=db.backref('collections', lazy=True))
    
    # Tag that this collection is based on
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id'))
    tag = db.relationship('Tag', backref='collections')
    
    def __repr__(self):
        return f'<Collection {self.name}>'
    
    def to_dict(self):
        # Include SEO fields in the dictionary representation
        seo_dict = {key: getattr(self, key) for key in SEOFields.__dict__ if not key.startswith('_') and not callable(getattr(SEOFields, key))}
        base_dict = {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            # 'meta_description': self.meta_description, # Removed, now part of seo_dict
            'tag': self.tag.name if self.tag else None,
            'product_count': len(self.products),
            'store_id': self.store_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        base_dict.update(seo_dict)
        return base_dict

class EnvVar(db.Model):
    """Environment variable model."""
    __tablename__ = 'env_vars'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), nullable=False, unique=True)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<EnvVar {self.key}>'

class StoreCredentials(db.Model):
    """Store credentials model."""
    __tablename__ = 'store_credentials'
    
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    key = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<StoreCredentials {self.key}>'

class CleanupRule(db.Model):
    """Cleanup rule model."""
    __tablename__ = 'cleanup_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    pattern = db.Column(db.String(255), nullable=False)
    replacement = db.Column(db.String(255), nullable=False)
    is_regex = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<CleanupRule {self.pattern}>'

# --- SEO Defaults Model ---
class SEODefaults(db.Model):
    """Store-level SEO defaults"""
    __tablename__ = 'seo_defaults'
    
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)  # 'product' or 'collection'
    
    # Templates
    title_template = db.Column(db.String(255))
    description_template = db.Column(db.String(500))
    og_title_template = db.Column(db.String(255))
    og_description_template = db.Column(db.String(500))
    twitter_title_template = db.Column(db.String(255))
    twitter_description_template = db.Column(db.String(500))

    __table_args__ = (db.UniqueConstraint('store_id', 'entity_type', name='_store_entity_uc'),)

    def __repr__(self):
        return f'<SEODefaults store={self.store_id} type={self.entity_type}>'
