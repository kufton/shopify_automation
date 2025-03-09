from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

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
    products = db.relationship('Product', backref='store', lazy=True)
    collections = db.relationship('Collection', backref='store', lazy=True)
    tags = db.relationship('Tag', backref='store', lazy=True)
    
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

class Product(db.Model):
    """Product model."""
    __tablename__ = 'products'
    __table_args__ = (
        db.Index('idx_product_shopify_id', 'shopify_id'),
        db.Index('idx_product_title', 'title'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
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
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'price': self.price,
            'image_url': self.image_url,
            'shopify_id': self.shopify_id,
            'tags': [tag.name for tag in self.tags],
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

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

class Collection(db.Model):
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
    meta_description = db.Column(db.Text)
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
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'meta_description': self.meta_description,
            'tag': self.tag.name if self.tag else None,
            'product_count': len(self.products),
            'store_id': self.store_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

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
