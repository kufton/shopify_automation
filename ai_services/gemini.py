import google.generativeai as genai
import asyncio
import json
from typing import List, Tuple, Dict, Any, Optional

from .base import BaseAIService
from config import Config # To get API key if not provided directly

# Default prompts specific to Gemini (might need adjustments)
# Gemini often works better with direct instructions rather than strict templates.
DEFAULT_GEMINI_TAG_PROMPT = """
Analyze the following product information and generate comprehensive, specific tags suitable for e-commerce collections.

Product Title: {product_title}
Product Description: {product_description}

Generate tags based on these categories:
- BASE TAGS: Nouns, adjectives, materials, colors, sizes, styles, product types, brand names.
- FEATURE TAGS: Specific features, functionalities, technical specs, special attributes.
- USE CASE TAGS: How/where the product is used, problems solved, activities.
- AUDIENCE TAGS (if applicable): Target demographic, skill level, user groups.

Guidelines:
- Each tag MUST be a multi-word phrase (2-4 words).
- DO NOT create single-word tags.
- All tags should be lowercase with no special characters.
- Be comprehensive and specific. Avoid generic terms like "product", "item", "quality", "new".
- Combine related concepts (e.g., "stainless steel coffee maker").

Return ONLY the tags as a single comma-separated string.
"""

# Placeholder prompts for other methods - these will need refinement for Gemini
DEFAULT_GEMINI_COLLECTION_ANALYSIS_PROMPT = """
Analyze the product and determine the single most appropriate primary category (2-3 words, lowercase). Focus on product type, material, or function. Avoid generic terms.

Product Title: {product_title}
Product Description: {product_description}
Current Tags: {product_tags}

Return ONLY the category name.
"""

DEFAULT_GEMINI_COLLECTION_DESC_PROMPT = """
Create a unique, engaging HTML description (3-5 paragraphs, use h2/h3 for headings) for a collection named '{tag_name}' with {product_count} products. Highlight key features/benefits. Be conversational.

Example Products:
{product_examples_json}

Return ONLY the HTML content.
"""

DEFAULT_GEMINI_META_DESC_PROMPT = """
Create a concise, SEO-friendly meta description (150-160 chars max) for the collection '{tag_name}'. Include the collection name and encourage clicks. Do not mention shipping/price. Focus on value.

Example Product Titles: {product_titles_text}

Return ONLY the meta description text.
"""


class GeminiService(BaseAIService):
    """Gemini implementation for AI product tagging and collection generation."""

    # Common models: 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.0-pro'
    DEFAULT_MODEL = "gemini-1.5-flash" # Or choose another default

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None, custom_prompts: Optional[Dict[str, str]] = None):
        """Initialize the Gemini client."""
        resolved_api_key = api_key or Config.GEMINI_API_KEY # Fallback to config
        resolved_model_name = model_name or self.DEFAULT_MODEL
        super().__init__(api_key=resolved_api_key, model_name=resolved_model_name, custom_prompts=custom_prompts)

        if not self.api_key:
            print("Warning: Gemini API key is missing.")
            self.client = None
        else:
            try:
                genai.configure(api_key=self.api_key)
                # Safety settings can be adjusted as needed
                self.safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                ]
                self.generation_config = genai.types.GenerationConfig(
                    # candidate_count=1, # Default is 1
                    # stop_sequences=['\n'], # Adjust if needed
                    # max_output_tokens=500, # Set per call
                    temperature=0.2 # Default temperature for tags
                )
                self.client = genai.GenerativeModel(
                    model_name=self.model_name,
                    safety_settings=self.safety_settings,
                    generation_config=self.generation_config
                )
                print(f"Gemini client configured for model: {self.model_name}")
            except Exception as e:
                print(f"Error configuring Gemini client: {e}")
                self.client = None

    async def _call_gemini_api(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Helper method to call the Gemini API asynchronously."""
        if not self.client:
            raise ValueError("Gemini client is not configured (likely missing API key).")

        try:
            # Create a specific generation config for this call if temperature/max_tokens differ
            current_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature
            )
            # Use generate_content_async for async calls
            response = await self.client.generate_content_async(
                prompt,
                generation_config=current_config
                # stream=False # Default is False
            )

            # Handle potential safety blocks or empty responses
            if not response.candidates:
                 # Check prompt feedback for block reason
                 block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else "Unknown"
                 print(f"Warning: Gemini response blocked or empty. Reason: {block_reason}")
                 # You might want to return a specific error string or raise an exception
                 return f"error: response blocked ({block_reason})"

            # Accessing text content (assuming single candidate)
            # Need to handle potential errors if text is not available
            if response.candidates[0].content.parts:
                 return response.candidates[0].content.parts[0].text.strip()
            else:
                 print("Warning: Gemini response candidate has no content parts.")
                 return "error: empty content parts"

        except Exception as e:
            # Catch specific Google API errors if possible, e.g., google.api_core.exceptions.PermissionDenied
            print(f"An error occurred during Gemini API call: {e}")
            # Consider logging the prompt that caused the error
            # print(f"Failed prompt: {prompt}")
            raise # Re-raise for handling upstream


    async def generate_tags_async(self, product: Any) -> Tuple[Any, List[str]]:
        """Generate tags for a product using Gemini asynchronously."""
        print(f"Generating Gemini tags for product: {product.title}")

        if not self.client:
            print("Gemini client not configured, returning api_key_missing tag")
            return product, ["api_key_missing"]

        # Prepare the prompt using the base class method
        prompt_template = self.get_prompt('generate_tags', DEFAULT_GEMINI_TAG_PROMPT)
        prompt = prompt_template.format(
            product_title=product.title,
            product_description=product.description
        )

        try:
            tags_text = await self._call_gemini_api(
                prompt=prompt,
                max_tokens=500, # Adjust as needed
                temperature=0.2 # Low temp for consistent tagging
            )

            if tags_text.startswith("error:"):
                 print(f"Gemini API error for {product.title}: {tags_text}")
                 return product, ["error generating tags"]

            print(f"Raw tags from Gemini for {product.title}: {tags_text}")

            tags = self.clean_tags(tags_text) # Use base class cleaning

            print(f"Final Gemini tags for {product.title}: {tags}")
            return product, tags

        except Exception as e:
            print(f"Error generating Gemini tags for {product.title}: {e}")
            return product, ["error generating tags"]

    # --- Placeholder implementations for other methods ---
    # These need to be fully implemented similar to generate_tags_async

    async def analyze_product_for_collection_async(self, product: Any) -> Tuple[Any, Optional[str]]:
        """Analyze a product to determine its primary collection/category using Gemini."""
        print(f"Analyzing product for collection using Gemini: {product.title}")
        if not self.client:
            print("Gemini client not configured.")
            return product, None

        prompt_template = self.get_prompt('analyze_product_for_collection', DEFAULT_GEMINI_COLLECTION_ANALYSIS_PROMPT)
        prompt = prompt_template.format(
            product_title=product.title,
            product_description=product.description,
            product_tags=', '.join([tag.name for tag in product.tags]) if product.tags else 'None'
        )

        try:
            category = await self._call_gemini_api(
                prompt=prompt,
                max_tokens=50,
                temperature=0.1
            )
            category = category.lower()

            if category.startswith("error:"):
                 print(f"Gemini API error analyzing collection for {product.title}: {category}")
                 return product, None

            # Basic validation
            if category in self.generic_tags:
                print(f"Gemini suggested generic category '{category}', using default.")
                return product, "uncategorized product"
            if ' ' not in category:
                print(f"Gemini suggested single-word category '{category}', appending ' category'.")
                category = f"{category} category"

            print(f"Gemini determined category for {product.title}: {category}")
            return product, category

        except Exception as e:
            print(f"Error analyzing product for collection with Gemini: {e}")
            return product, None

    async def generate_collection_description_async(self, tag_name: str, product_count: int, product_examples: List[Dict[str, str]]) -> str:
        """Generate a description for a collection using Gemini."""
        print(f"Generating Gemini collection description for: {tag_name}")
        default_desc = f"<p>A curated selection of {product_count} products related to {tag_name}.</p>"
        if not self.client:
             print("Gemini client not configured.")
             return default_desc

        prompt_template = self.get_prompt('generate_collection_description', DEFAULT_GEMINI_COLLECTION_DESC_PROMPT)
        prompt = prompt_template.format(
            tag_name=tag_name,
            product_count=product_count,
            product_examples_json=json.dumps(product_examples, indent=2)
        )

        try:
            description = await self._call_gemini_api(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.7 # Higher temp for creativity
            )

            if description.startswith("error:"):
                 print(f"Gemini API error generating description for '{tag_name}': {description}")
                 return default_desc

            print(f"Generated Gemini collection description for '{tag_name}'")
            # Add basic validation if needed
            if not description or not ('<p>' in description or '<h2>' in description or '<h3>' in description):
                 print(f"Warning: Gemini description for '{tag_name}' seems invalid, returning default.")
                 return default_desc
            return description

        except Exception as e:
            print(f"Error generating Gemini collection description for {tag_name}: {e}")
            return default_desc

    async def generate_collection_meta_description_async(self, tag_name: str, product_titles_text: str) -> str:
        """Generate a meta description for a collection using Gemini."""
        print(f"Generating Gemini meta description for: {tag_name}")
        default_meta = f"Explore our {tag_name} collection featuring {product_titles_text}. Find the perfect {tag_name} for your needs."[:160]
        if not self.client:
            print("Gemini client not configured.")
            return default_meta

        prompt_template = self.get_prompt('generate_collection_meta_description', DEFAULT_GEMINI_META_DESC_PROMPT)
        prompt = prompt_template.format(
            tag_name=tag_name,
            product_titles_text=product_titles_text
        )

        try:
            meta_description = await self._call_gemini_api(
                prompt=prompt,
                max_tokens=60,
                temperature=0.4
            )

            if meta_description.startswith("error:"):
                 print(f"Gemini API error generating meta description for '{tag_name}': {meta_description}")
                 return default_meta

            print(f"Generated Gemini meta description for '{tag_name}'")
            # Basic validation
            if len(meta_description) > 170:
                print(f"Warning: Gemini meta description for '{tag_name}' is too long ({len(meta_description)} chars), truncating.")
                meta_description = meta_description[:160].rsplit(' ', 1)[0] + '...'

            if not meta_description:
                 print(f"Warning: Gemini returned empty meta description for '{tag_name}', using default.")
                 return default_meta

            return meta_description

        except Exception as e:
            print(f"Error generating Gemini meta description for {tag_name}: {e}")
            return default_meta