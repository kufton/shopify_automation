# Blog Generation Feature Design (Multi-Stage)

This document outlines the approved design for the blog generation feature, utilizing a multi-stage AI process.

## 1. Data Model Changes (`models.py`)

### Store Model Enhancements

Add fields to the `Store` model to support richer context for AI generation:

```python
# In models.py, within the Store class definition:
class Store(db.Model):
    # ... existing fields ...
    concept = db.Column(db.Text, nullable=True) # Existing
    keyword_map = db.Column(JSON, nullable=True) # Existing
    target_audience = db.Column(db.Text, nullable=True) # ADDED: Description of target audience
    tone_of_voice = db.Column(db.String(100), nullable=True) # ADDED: Desired tone (e.g., 'friendly', 'professional')
    sitemap_url = db.Column(db.String(500), nullable=True) # ADDED: URL to the store's sitemap

    # ... rest of the Store model ...
```

### New BlogPost Model

Add a new `BlogPost` model to store generated content and related metadata:

```python
# Proposed addition/modification to models.py
from .mixins import SEOFields # Assuming SEOFields is moved to a mixins file or defined above
from datetime import datetime
from sqlalchemy import JSON

class BlogPost(db.Model, SEOFields):
    """Blog Post model."""
    __tablename__ = 'blog_posts'
    __table_args__ = (
        db.Index('idx_blogpost_status', 'status'),
        db.Index('idx_blogpost_store_tag', 'store_id', 'source_tag_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False) # Can be generated initially or after outline
    content = db.Column(db.Text, nullable=False) # Stores the FINAL combined content
    status = db.Column(db.String(50), nullable=False, default='draft', index=True) # e.g., 'draft', 'published', 'archived'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    generated_by_model = db.Column(db.String(100), nullable=True) # Tracks AI model used
    prompt_text = db.Column(db.Text, nullable=False) # Stores the INITIAL prompt used for the outline
    outline = db.Column(JSON, nullable=True) # Stores the generated outline (e.g., list of strings or structured JSON)

    # Store relationship
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    store = db.relationship('Store', backref=db.backref('blog_posts', lazy=True, cascade="all, delete-orphan"))

    # Link to the source Tag that inspired the post
    source_tag_id = db.Column(db.Integer, db.ForeignKey('tags.id'), nullable=True) # Nullable if a post can be created manually
    source_tag = db.relationship('Tag', backref=db.backref('generated_blog_posts', lazy=True))

    def __repr__(self):
        return f'<BlogPost {self.id}: {self.title[:50]}... ({self.status})>'

    def to_dict(self):
        # Include SEO fields
        seo_dict = {key: getattr(self, key) for key in SEOFields.__dict__ if not key.startswith('_') and not callable(getattr(SEOFields, key))}
        base_dict = {
            'id': self.id,
            'title': self.title,
            # 'content': self.content, # Omit full content for list views
            'status': self.status,
            'store_id': self.store_id,
            'source_tag_id': self.source_tag_id,
            'source_tag_name': self.source_tag.name if self.source_tag else None,
            'generated_by_model': self.generated_by_model,
            'outline': self.outline, # Include outline
            # 'prompt_text': self.prompt_text, # Omit prompt text for list views
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        base_dict.update(seo_dict)
        return base_dict
```

## 2. AI Service Interface Changes (`ai_services/base.py`)

Add new abstract methods to the `BaseAIService` class to support the multi-stage generation:

```python
# In ai_services/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple # Ensure necessary imports

class BaseAIService(ABC):
    # ... existing __init__, get_prompt, etc. ...

    @abstractmethod
    async def generate_tags_async(self, product: Any) -> Tuple[Any, List[str]]:
        pass # Existing

    @abstractmethod
    async def analyze_product_for_collection_async(self, product: Any) -> Tuple[Any, Optional[str]]:
        pass # Existing

    @abstractmethod
    async def generate_collection_description_async(self, tag_name: str, product_count: int, product_examples: List[Dict[str, str]]) -> str:
        pass # Existing

    @abstractmethod
    async def generate_collection_meta_description_async(self, tag_name: str, product_titles_text: str) -> str:
        pass # Existing

    @abstractmethod
    async def generate_keyword_map_async(self, concept: str) -> Dict[str, Any]:
        pass # Existing

    # --- NEW METHODS FOR BLOG GENERATION ---

    @abstractmethod
    async def generate_outline_async(self, context: Dict[str, Any]) -> List[str]: # Or Dict, depending on desired outline structure
        """
        Generate a blog post outline based on the provided context.
        Context should include keys like: 'tag_name', 'store_concept', 'target_audience',
        'tone_of_voice', 'sitemap_url', 'product_examples', 'existing_blogs'.
        """
        pass

    @abstractmethod
    async def generate_content_block_async(self, context: Dict[str, Any]) -> str:
        """
        Generate a block of content for a specific part of the blog post.
        Context should include keys like: 'outline_point', 'full_outline', 'tag_name',
        'store_concept', 'target_audience', 'tone_of_voice'.
        """
        pass

    # ... batch methods and synchronous wrappers ...
```

## 3. Multi-Stage Workflow Outline

The generation process follows these steps:

```mermaid
graph TD
    A[User Action: Selects Store & Initiates Blog Generation] --> B{Identify Popular Tags};
    B --> C{User Selects Target Tag(s)};
    C --> D{Gather Rich Context};
    D --> E1{Construct Initial Prompt};
    E1 --> E2{Invoke AI: Generate Outline};
    E2 --> F1{Receive & Store Outline};
    F1 --> G{Loop Through Outline Points};
    G -- For Each Point (Intro, Body, Summary) --> H{Construct Block Prompt};
    H --> I{Invoke AI: Generate Content Block};
    I --> J{Collect Content Blocks};
    G -- After Loop --> K{Combine Blocks into Final Content};
    K --> L{Store Final BlogPost Data};
    L --> M[Display Draft to User];

    subgraph "Backend Logic"
        B; C; D; E1; E2; F1; G; H; I; J; K; L;
    end

    subgraph "Database (models.py)"
        style B fill:#f9f,stroke:#333,stroke-width:2px
        style D fill:#f9f,stroke:#333,stroke-width:2px
        style F1 fill:#f9f,stroke:#333,stroke-width:2px
        style L fill:#f9f,stroke:#333,stroke-width:2px
        B -- Query product_tags & tags --> DB[(SQLAlchemy ORM)];
        D -- Read Store (concept, audience, tone, sitemap), Products, other BlogPosts --> DB;
        F1 -- Save Outline & Initial Prompt --> DB;
        L -- Save Final Content, Title, etc. --> DB;
    end

    subgraph "AI Service (ai_services/)"
        style E2 fill:#ccf,stroke:#333,stroke-width:2px
        style I fill:#ccf,stroke:#333,stroke-width:2px
        E2 -- Call generate_outline_async --> AI[(BaseAIService)];
        I -- Call generate_content_block_async --> AI;
    end

    subgraph "User Interface (Flask Templates/Routes)"
        style A fill:#cfc,stroke:#333,stroke-width:2px
        style C fill:#cfc,stroke:#333,stroke-width:2px
        style M fill:#cfc,stroke:#333,stroke-width:2px
        A; C; M;
    end
```

### Workflow Steps Detailed:

1.  **Trigger (A, B, C):** User selects a store, views popular tags (derived from `product_tags` count per tag for that store), and selects a tag to generate a blog post from.
2.  **Gather Rich Context (D):** Retrieve:
    *   Selected `tag_name`.
    *   From `Store`: `concept`, `target_audience`, `tone_of_voice`, `sitemap_url`.
    *   Relevant `Product` titles/URLs associated with the tag.
    *   Relevant existing `BlogPost` titles/URLs from the same store.
3.  **Construct Initial Prompt (E1):** Create a detailed prompt string instructing the AI to generate a blog post *outline*. This prompt should incorporate all the context gathered in step D. Store this prompt string temporarily.
4.  **Invoke AI: Generate Outline (E2):** Call the new `ai_service.generate_outline_async(context=...)` method, passing the necessary context elements.
5.  **Receive & Store Outline (F1):**
    *   Receive the generated outline (e.g., list of strings).
    *   Create a new `BlogPost` record.
    *   Populate `store_id`, `source_tag_id`, `generated_by_model`.
    *   Store the initial prompt string (from E1) in the `prompt_text` field (non-nullable).
    *   Store the received outline in the `outline` (JSON) field.
    *   Set `status` to a temporary state like 'generating' or keep as 'draft'. `title` and `content` are initially empty/placeholders.
    *   Save this preliminary record.
6.  **Loop Through Outline Points (G):** Iterate through the items in the stored `outline` field. Include implicit steps for generating an introduction and a conclusion/summary.
7.  **Construct Block Prompt (H):** For each outline point (or intro/summary), create a specific, focused prompt instructing the AI to write the content for *that section*. This prompt should reference the specific outline point, the overall topic (`tag_name`), target audience, tone, etc.
8.  **Invoke AI: Generate Content Block (I):** Call the new `ai_service.generate_content_block_async(context=...)` method with the block-specific prompt/context.
9.  **Collect Content Blocks (J):** Store the generated content string for each block in memory.
10. **Combine Blocks into Final Content (K):** After the loop finishes, concatenate the introduction block, all body blocks, and the summary block into a single final `content` string. Generate a suitable `title` (e.g., using another AI call based on the outline/content, or deriving from the main tag).
11. **Store Final BlogPost Data (L):** Update the `BlogPost` record (created in F1) with the final combined `content`, the generated `title`, and set `status` to 'draft'. Save the changes.
12. **Display Draft to User (M):** Redirect the user to the edit page for the newly completed draft blog post or show a success message.

## 4. Flexibility Considerations

The default workflow is the multi-stage process. If simpler, single-prompt generation is desired later, consider:
*   Adding a UI option to choose the generation method.
*   Adding a `use_multistage_blog_generation` flag to the `Store` model.

This design provides a robust framework for generating detailed blog posts based on popular product tags and rich store context.