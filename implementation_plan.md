# SEO Enhancement Implementation Plan

## Overview
This plan outlines the implementation of enhanced SEO features, focusing on meta fields, Open Graph tags, and Twitter Cards for products and collections.

## Database Changes

### 1. SEO Fields Mixin
```python
class SEOFields(object):
    """Mixin for SEO fields"""
    meta_title = db.Column(db.String(60))
    meta_description = db.Column(db.String(160))
    
    # Open Graph
    og_title = db.Column(db.String(95))
    og_description = db.Column(db.String(200))
    og_image = db.Column(db.String(500))
    og_type = db.Column(db.String(50))
    
    # Twitter Cards
    twitter_card = db.Column(db.String(15), default='summary_large_image')
    twitter_title = db.Column(db.String(70))
    twitter_description = db.Column(db.String(200))
    twitter_image = db.Column(db.String(500))
    
    # Common
    canonical_url = db.Column(db.String(500))
    structured_data = db.Column(db.JSON)
```

### 2. SEO Defaults Model
```python
class SEODefaults(db.Model):
    """Store-level SEO defaults"""
    __tablename__ = 'seo_defaults'
    
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    entity_type = db.Column(db.String(50))  # 'product' or 'collection'
    
    # Templates
    title_template = db.Column(db.String(255))
    description_template = db.Column(db.String(500))
    og_title_template = db.Column(db.String(255))
    og_description_template = db.Column(db.String(500))
    twitter_title_template = db.Column(db.String(255))
    twitter_description_template = db.Column(db.String(500))
```

## Form Updates

### 1. SEO Form Mixin
```python
class SEOFormMixin:
    meta_title = StringField('Meta Title', validators=[Length(max=60)])
    meta_description = TextAreaField('Meta Description', validators=[Length(max=160)])
    
    og_title = StringField('OG Title', validators=[Length(max=95)])
    og_description = TextAreaField('OG Description', validators=[Length(max=200)])
    og_image = StringField('OG Image URL', validators=[Optional(), URL()])
    
    twitter_card = SelectField('Twitter Card Type', 
        choices=[('summary', 'Summary'), ('summary_large_image', 'Large Image')])
    twitter_title = StringField('Twitter Title', validators=[Length(max=70)])
    twitter_description = TextAreaField('Twitter Description', validators=[Length(max=200)])
    twitter_image = StringField('Twitter Image URL', validators=[Optional(), URL()])
    
    canonical_url = StringField('Canonical URL', validators=[Optional(), URL()])
```

## Template Variables

### Available Variables
- Products:
  - `{title}`: Product title
  - `{price}`: Product price
  - `{store_name}`: Store name
  - `{description_excerpt}`: First 100 chars of description
  - `{primary_tag}`: First product tag

- Collections:
  - `{name}`: Collection name
  - `{product_count}`: Number of products
  - `{example_products}`: First 3 product names
  - `{store_name}`: Store name
  - `{tag_name}`: Associated tag name (for smart collections)

### Default Templates
```python
default_templates = {
    'product': {
        'title': '{title} | {store_name}',
        'description': 'Shop {title} at {store_name}. {description_excerpt}',
        'og_title': '{title} - Available at {store_name}',
        'twitter_title': 'Shop {title} at {store_name}'
    },
    'collection': {
        'title': '{name} Collection | {store_name}',
        'description': 'Explore our {name} collection. {product_count} products including {example_products}',
        'og_title': 'Shop {name} Collection at {store_name}',
        'twitter_title': '{name} Collection at {store_name}'
    }
}
```

## Original Implementation Steps (Pre-Review)

1. **Database Updates**
   - Add SEO fields to Product and Collection models
   - Create SEODefaults table
   - Create migration script
   - Update existing records with defaults

2. **Form Updates**
   - Add SEO tab to product/collection forms
   - Implement character counters
   - Add preview cards for meta/social
   - Add template variable substitution

3. **Template Updates**
   - Update base.html with meta blocks
   - Create SEO preview components
   - Add social media preview cards
   - Implement live preview functionality

4. **Testing**
   - Validate meta tag generation
   - Test template variable substitution
   - Verify character limits
   - Test social media previews

## Revised Implementation Steps (Post-Review - 2025-04-03)

Based on the clarification that SEO data is for Shopify (via metafields) and not this application's frontend.

### Current Status Summary

*   **Completed:**
    *   Database models defined (`SEOFields` mixin, `SEODefaults`).
    *   Migration script created (`142f42794f63...`).
    *   Forms updated (`SEOFormMixin` added to `ProductForm`, `CollectionForm`).
    *   Basic SEO sections added to product/collection edit templates.
    *   Character counters implemented in forms.
*   **Remaining:**
    *   Run the database migration (`flask db upgrade`).
    *   Verify/Implement backend logic for saving SEO form data to the database.
    *   Implement backend logic for Shopify API integration (sending SEO data, likely via metafields).
    *   Implement frontend preview components (Google snippet, social cards) in forms.
    *   Perform testing (local saving, Shopify integration, previews).

### Revised Plan Steps

1.  **(Manual Step for User):** Run the database migration (`flask db upgrade` or similar).
2.  **Backend Logic - Data Saving:** Ensure Flask view functions correctly save all `SEOFormMixin` fields to the `Product`/`Collection` models upon form submission.
3.  **Backend Logic - Shopify Integration:** Modify Shopify API interaction code (e.g., in `shopify_integration.py`) to read saved SEO fields and include them in product/collection create/update API calls, likely using Shopify `metafields`.
4.  **Frontend Previews:** Implement HTML/CSS/JS in form templates (`product_form.html`, `collection_form.html`) and `static/js/script.js` to display live previews of Google snippets and social cards based on form input.
5.  **Testing:** Thoroughly test data saving, Shopify API integration (check metafields in Shopify), and frontend preview functionality.

### Plan Flowchart

```mermaid
graph TD
    A[Start: Current Status] --> B(Run DB Migration - Manual);
    B --> C(Implement Backend Logic - Data Saving);
    C --> D(Implement Backend Logic - Shopify Integration);
    D --> E(Implement Frontend Previews);
    E --> F(Testing);
    F --> G(Done);

    style A fill:#f9f,stroke:#333,stroke-width:2px
    style G fill:#ccf,stroke:#333,stroke-width:2px
    style D fill:#f8d7da,stroke:#721c24,stroke-width:2px; /* Highlight critical Shopify step */