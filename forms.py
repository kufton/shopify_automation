from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FloatField, SubmitField, HiddenField, BooleanField, SelectField, IntegerField
from wtforms.validators import DataRequired, URL, Optional, Length, NumberRange

# --- SEO Form Mixin ---
class SEOFormMixin:
    meta_title = StringField('Meta Title (Max 60 chars)', validators=[Optional(), Length(max=60)])
    meta_description = TextAreaField('Meta Description (Max 160 chars)', validators=[Optional(), Length(max=160)])
    
    og_title = StringField('Open Graph Title (Max 95 chars)', validators=[Optional(), Length(max=95)])
    og_description = TextAreaField('Open Graph Description (Max 200 chars)', validators=[Optional(), Length(max=200)])
    og_image = StringField('Open Graph Image URL', validators=[Optional(), URL()])
    
    twitter_card = SelectField('Twitter Card Type', 
        choices=[('summary', 'Summary'), ('summary_large_image', 'Summary with Large Image')], 
        default='summary_large_image', validators=[Optional()])
    twitter_title = StringField('Twitter Title (Max 70 chars)', validators=[Optional(), Length(max=70)])
    twitter_description = TextAreaField('Twitter Description (Max 200 chars)', validators=[Optional(), Length(max=200)])
    twitter_image = StringField('Twitter Image URL', validators=[Optional(), URL()])
    
    canonical_url = StringField('Canonical URL', validators=[Optional(), URL()])

class ProductForm(FlaskForm, SEOFormMixin): # Added SEOFormMixin
    """Form for adding or editing a product."""
    # Basic Info
    title = StringField('Title', validators=[DataRequired(), Length(max=255)])
    description = TextAreaField('Description', validators=[Optional()])
    price = FloatField('Price', validators=[Optional()])
    image_url = StringField('Image URL', validators=[Optional(), URL()])
    
    # SEO Fields are inherited from SEOFormMixin
    
    submit = SubmitField('Save Product')

class EnvVarForm(FlaskForm):
    """Form for adding or editing environment variables."""
    key = StringField('Key', validators=[DataRequired(), Length(max=255)])
    value = StringField('Value', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Save')

class CollectionForm(FlaskForm, SEOFormMixin): # Added SEOFormMixin
    """Form for creating or editing a collection."""
    # Basic Info
    name = StringField('Name', validators=[DataRequired(), Length(max=255)])
    slug = StringField('Slug', validators=[Optional(), Length(max=255)])
    description = TextAreaField('Description', validators=[Optional()])
    # meta_description = TextAreaField('Meta Description (for SEO)', validators=[Optional(), Length(max=160)]) # Removed, now in mixin
    tag_id = HiddenField('Tag ID') # For smart collections
    
    # SEO Fields are inherited from SEOFormMixin
    
    submit = SubmitField('Save Collection')

class TagForm(FlaskForm):
    """Form for adding a tag manually."""
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Add Tag')

class AutoTagForm(FlaskForm):
    """Form for auto-tagging products."""
    submit = SubmitField('Auto-Tag Selected Products')

class CreateCollectionsForm(FlaskForm):
    """Form for creating collections from tags."""
    exclude_imported_tags = BooleanField('Only use tags generated by Claude (exclude imported tags)')
    submit = SubmitField('Create Collections from Tags')

class StoreForm(FlaskForm):
    """Form for adding or editing a store."""
    name = StringField('Store Name', validators=[DataRequired(), Length(max=255)])
    url = StringField('Store URL', validators=[DataRequired(), Length(max=255)])
    access_token = StringField('Access Token', validators=[Optional(), Length(max=255)])
    concept = TextAreaField('Store Concept', validators=[Optional()]) # Added concept field
    keyword_map = TextAreaField('Keyword Map (JSON)', validators=[Optional()]) # Added keyword_map field
    submit = SubmitField('Save')

class StoreSelectForm(FlaskForm):
    """Form for selecting the current store."""
    store_id = SelectField('Select Store', coerce=int)
    submit = SubmitField('Switch Store')

class CleanupRuleForm(FlaskForm):
    """Form for adding or editing cleanup rules."""
    pattern = StringField('Pattern to Find', validators=[DataRequired(), Length(max=255)])
    replacement = StringField('Replace With', validators=[DataRequired(message="Replacement cannot be empty, use '' for removing."), Length(max=255)])
    is_regex = BooleanField('Use Regular Expression')
    priority = IntegerField('Priority (Lower number runs first)', default=0, validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField('Save Rule')

# --- Add SEODefaults Form ---
class SEODefaultsForm(FlaskForm):
    """Form for editing SEO default templates."""
    # Product Templates
    product_title_template = StringField('Product Title Template', validators=[Optional(), Length(max=255)])
    product_description_template = TextAreaField('Product Meta Description Template', validators=[Optional(), Length(max=500)])
    product_og_title_template = StringField('Product OG Title Template', validators=[Optional(), Length(max=255)])
    product_og_description_template = TextAreaField('Product OG Description Template', validators=[Optional(), Length(max=500)])
    product_twitter_title_template = StringField('Product Twitter Title Template', validators=[Optional(), Length(max=255)])
    product_twitter_description_template = TextAreaField('Product Twitter Description Template', validators=[Optional(), Length(max=500)])
    
    # Collection Templates
    collection_title_template = StringField('Collection Title Template', validators=[Optional(), Length(max=255)])
    collection_description_template = TextAreaField('Collection Meta Description Template', validators=[Optional(), Length(max=500)])
    collection_og_title_template = StringField('Collection OG Title Template', validators=[Optional(), Length(max=255)])
    collection_og_description_template = TextAreaField('Collection OG Description Template', validators=[Optional(), Length(max=500)])
    collection_twitter_title_template = StringField('Collection Twitter Title Template', validators=[Optional(), Length(max=255)])
    collection_twitter_description_template = TextAreaField('Collection Twitter Description Template', validators=[Optional(), Length(max=500)])
    
    submit = SubmitField('Save SEO Defaults')

# --- Add BlogPost Form ---
class BlogPostForm(FlaskForm, SEOFormMixin):
   """Form for editing a blog post."""
   title = StringField('Title', validators=[DataRequired(), Length(max=255)])
   content = TextAreaField('Content', validators=[DataRequired()])
   status = SelectField('Status',
                        choices=[('draft', 'Draft'), ('published', 'Published'), ('failed', 'Failed'), ('outline_generated', 'Outline Generated')],
                        validators=[DataRequired()])
   # SEO fields (seo_title, meta_description, etc.) are inherited from SEOFormMixin
   submit = SubmitField('Save Blog Post')
