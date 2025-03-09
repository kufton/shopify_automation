import os
from flask import session, g
from models import Store, db
from config import Config

def normalize_url(url):
    """Normalize a URL by removing protocol and trailing slashes."""
    normalized_url = url.lower()
    if '://' in normalized_url:
        normalized_url = normalized_url.split('://', 1)[1]
    return normalized_url.rstrip('/')

def get_current_store():
    """Get the current store from session or create a default one."""
    # Check if we already have the store in g
    if hasattr(g, 'current_store'):
        return g.current_store
    
    # Check if we have a store_id in session
    store_id = session.get('current_store_id')
    
    if store_id:
        # Get store by ID
        store = Store.query.get(store_id)
        if store:
            g.current_store = store
            
            # Update environment variables to match the current store
            os.environ['SHOPIFY_STORE_URL'] = store.url
            if store.access_token:
                os.environ['SHOPIFY_ACCESS_TOKEN'] = store.access_token
                
            # Update Config object
            Config.SHOPIFY_STORE_URL = store.url
            Config.SHOPIFY_ACCESS_TOKEN = store.access_token
            
            return store
    
    # No store in session, try to get from environment variable
    store_url = Config.SHOPIFY_STORE_URL
    if store_url:
        normalized_url = normalize_url(store_url)
        
        # Find store by URL
        store = Store.query.filter_by(url=normalized_url).first()
        
        if store:
            # Store found, save to session and g
            session['current_store_id'] = store.id
            g.current_store = store
            return store
        else:
            # Create a new store
            store = create_store_from_env()
            if store:
                session['current_store_id'] = store.id
                g.current_store = store
                return store
    
    # Try to get the first store if no store is selected
    store = Store.query.first()
    if store:
        session['current_store_id'] = store.id
        g.current_store = store
        
        # Update environment variables to match the current store
        os.environ['SHOPIFY_STORE_URL'] = store.url
        if store.access_token:
            os.environ['SHOPIFY_ACCESS_TOKEN'] = store.access_token
            
        # Update Config object
        Config.SHOPIFY_STORE_URL = store.url
        Config.SHOPIFY_ACCESS_TOKEN = store.access_token
        
        return store
    
    # No store found or created
    return None

def set_current_store(store_id):
    """Set the current store in the session."""
    store = Store.query.get(store_id)
    if store:
        session['current_store_id'] = store.id
        
        # Update environment variables
        os.environ['SHOPIFY_STORE_URL'] = store.url
        if store.access_token:
            os.environ['SHOPIFY_ACCESS_TOKEN'] = store.access_token
        
        # Clear g.current_store if it exists
        if hasattr(g, 'current_store'):
            delattr(g, 'current_store')
        
        return store
    return None

def create_store_from_env():
    """Create a store from environment variables."""
    store_url = Config.SHOPIFY_STORE_URL
    if not store_url:
        return None
    
    normalized_url = normalize_url(store_url)
    store_name = normalized_url.split('.')[0]
    access_token = Config.SHOPIFY_ACCESS_TOKEN
    
    store = Store(
        name=store_name,
        url=normalized_url,
        access_token=access_token
    )
    
    db.session.add(store)
    db.session.commit()
    
    return store

def filter_query_by_store(query, model):
    """Filter a query by the current store."""
    store = get_current_store()
    if store:
        return query.filter(model.store_id == store.id)
    return query

def get_all_stores():
    """Get all stores."""
    return Store.query.all()
