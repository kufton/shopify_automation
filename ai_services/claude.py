import anthropic
import asyncio
import json
from typing import List, Tuple, Dict, Any, Optional

from .base import BaseAIService
from config import Config # Assuming Config holds the default API key if needed

# Default prompts specific to Claude
DEFAULT_CLAUDE_TAG_PROMPT = """
You are a product tagging expert. Your task is to analyze the following product information and generate comprehensive, specific tags.

Product Title: {product_title}
Product Description: {product_description}

Please generate tags in the following categories:

1. BASE TAGS (required):
   - Extract ALL nouns from the title and description
   - Extract ALL adjectives that describe the product
   - Include materials, colors, sizes, styles, and product types
   - Include brand names if mentioned

2. FEATURE TAGS (required):
   - Specific features and functionalities
   - Technical specifications
   - Special attributes or capabilities

3. USE CASE TAGS (required):
   - Where or how the product is used
   - Problems it solves
   - Activities it's designed for

4. AUDIENCE TAGS (if applicable):
   - Target demographic (age, gender, profession)
   - Skill level (beginner, professional, etc.)
   - Specific user groups

Guidelines:
- Each tag MUST be a multi-word phrase (2-4 words)
- DO NOT create single-word tags
- All tags should be lowercase with no special characters
- Be comprehensive - it's better to have more specific tags than fewer generic ones
- Avoid generic terms like "product", "item", "quality", "value", "new", "trending", etc. (Refer to base class filter list)
- Combine related concepts into meaningful phrases (e.g., "stainless steel coffee maker" instead of just "coffee maker")

Return only the tags as a comma-separated list with no additional text, categories, or explanation.
"""

DEFAULT_CLAUDE_COLLECTION_ANALYSIS_PROMPT = """
You are a product categorization expert. Your task is to analyze the following product information and determine the most appropriate primary category for it.

Product Title: {product_title}
Product Description: {product_description}
Current Tags: {product_tags}

Please determine the single most appropriate category for this product. The category should be:
- A specific, meaningful category that accurately represents this product type
- Descriptive enough to be useful for grouping similar products
- Not too generic (avoid terms like "product", "item", "goods", etc.)
- A multi-word phrase (2-3 words)
- Lowercase with no special characters

Focus on categories that would be useful in an e-commerce context, such as:
- Product type (e.g., "bluetooth speaker", "cotton t-shirt", "ceramic mug")
- Primary material (e.g., "leather goods", "wooden furniture")
- Primary function (e.g., "kitchen tools", "office supplies")

Return only the category name with no additional text or explanation.
"""

DEFAULT_CLAUDE_COLLECTION_DESC_PROMPT = """
Create a unique, engaging description for a collection of {product_count} products tagged as '{tag_name}'.

Some example products in this collection:
{product_examples_json}

The description should:
- Be creative and unique to this specific collection
- Highlight the key features or benefits of products in this category
- Be written in an engaging, conversational tone
- Include appropriate HTML formatting (paragraphs, maybe a list of features)
- Be 3-5 paragraphs in length
- Focus on quality, value, and product benefits
- Use h2 or h3 tags for any headings (never h1)

Return only the HTML content with no additional text, categories, or explanation.
"""

DEFAULT_CLAUDE_META_DESC_PROMPT = """
Create a concise, SEO-friendly meta description for a collection of products tagged as '{tag_name}'.

Some products in this collection include: {product_titles_text}

The meta description should:
- Be 150-160 characters maximum
- Include the collection name ('{tag_name}')
- Be compelling and encourage clicks
- NOT make claims about shipping, pricing, or guarantees
- Focus on the value proposition of the collection

Return only the meta description text with no additional explanation.
"""

DEFAULT_CLAUDE_KEYWORD_MAP_PROMPT = """
You are an SEO and e-commerce expert. Your task is to analyze the following store concept and generate a structured semantic keyword map in JSON format.

Store Concept: {concept}

Generate a JSON object with the following structure:
{
  "core_concepts": ["list of 3-5 primary keywords directly representing the concept"],
  "related_topics": ["list of 5-10 keywords for related themes or product categories"],
  "long_tail_keywords": ["list of 10-15 longer, more specific phrases potential customers might search for"],
  "audience_descriptors": ["list of 3-5 keywords describing the target audience (if inferrable)"]
}

Guidelines:
- All keywords should be lowercase.
- Keywords should be relevant for SEO and e-commerce.
- Focus on terms customers would actually use for searching.
- Ensure the output is ONLY the valid JSON object, with no surrounding text or explanations.
"""

class ClaudeService(BaseAIService):
    """Claude implementation for AI product tagging and collection generation."""

    DEFAULT_MODEL = "claude-3-7-sonnet-20250219" # Or perhaps claude-3-opus-20240229 / claude-3-haiku-20240307

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None, custom_prompts: Optional[Dict[str, str]] = None):
        """Initialize the Claude client."""
        resolved_api_key = api_key or Config.ANTHROPIC_API_KEY # Fallback to config
        resolved_model_name = model_name or self.DEFAULT_MODEL
        super().__init__(api_key=resolved_api_key, model_name=resolved_model_name, custom_prompts=custom_prompts)
        # Async client is created per request to manage resources better
        # self.client = anthropic.AsyncAnthropic(api_key=self.api_key) # Can be initialized here if preferred

    async def _call_claude_api(self, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
        """Helper method to call the Claude API."""
        if not self.api_key:
            raise ValueError("Anthropic API key is missing.")

        try:
            # Use Anthropic's async client within an async context manager
            async with anthropic.AsyncAnthropic(api_key=self.api_key) as client:
                response = await client.messages.create(
                    model=self.model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )
            # Assuming the response structure is consistent
            if response.content and len(response.content) > 0:
                 return response.content[0].text.strip()
            else:
                print(f"Warning: Received empty or unexpected response content from Claude: {response}")
                return "" # Return empty string or raise error?

        except anthropic.APIConnectionError as e:
            print(f"Claude API connection error: {e}")
            raise # Re-raise for handling upstream
        except anthropic.RateLimitError as e:
            print(f"Claude API rate limit exceeded: {e}")
            # Consider implementing backoff/retry logic here or in batch methods
            raise
        except anthropic.APIStatusError as e:
            print(f"Claude API status error: {e.status_code} - {e.response}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred during Claude API call: {e}")
            raise


    async def generate_tags_async(self, product: Any) -> Tuple[Any, List[str]]:
        """Generate tags for a product using Claude asynchronously."""
        print(f"Generating Claude tags for product: {product.title}")

        if not self.api_key:
            print("API key is missing, returning api_key_missing tag")
            return product, ["api_key_missing"]

        # Prepare the prompt using the base class method
        prompt_template = self.get_prompt('generate_tags', DEFAULT_CLAUDE_TAG_PROMPT)
        prompt = prompt_template.format(
            product_title=product.title,
            product_description=product.description
        )
        system_prompt = "You are a product tagging expert that generates specific, meaningful tags that avoid generic terms and focus on distinctive product attributes."

        try:
            tags_text = await self._call_claude_api(
                system_prompt=system_prompt,
                user_prompt=prompt,
                max_tokens=500,
                temperature=0.2
            )
            print(f"Raw tags from Claude for {product.title}: {tags_text}")

            tags = self.clean_tags(tags_text) # Use base class cleaning

            print(f"Final Claude tags for {product.title}: {tags}")
            return product, tags

        except Exception as e:
            print(f"Error generating Claude tags for {product.title}: {e}")
            # Consider more specific error tags based on exception type
            return product, ["error generating tags"]


    async def analyze_product_for_collection_async(self, product: Any) -> Tuple[Any, Optional[str]]:
        """Analyze a product to determine its primary collection/category using Claude."""
        print(f"Analyzing product for collection using Claude: {product.title}")
        if not self.api_key:
            print("API key is missing, cannot analyze product for collection.")
            return product, None

        prompt_template = self.get_prompt('analyze_product_for_collection', DEFAULT_CLAUDE_COLLECTION_ANALYSIS_PROMPT)
        prompt = prompt_template.format(
            product_title=product.title,
            product_description=product.description,
            product_tags=', '.join([tag.name for tag in product.tags]) if product.tags else 'None'
        )
        system_prompt = "You are a product categorization expert that determines specific, meaningful categories for products, avoiding generic terms."

        try:
            category = await self._call_claude_api(
                system_prompt=system_prompt,
                user_prompt=prompt,
                max_tokens=50,
                temperature=0.1
            )
            category = category.lower() # Ensure lowercase

            # Basic validation (can be enhanced)
            if category in self.generic_tags:
                print(f"Claude suggested generic category '{category}', using default.")
                return product, "uncategorized product"
            if ' ' not in category:
                print(f"Claude suggested single-word category '{category}', appending ' category'.")
                category = f"{category} category"

            print(f"Claude determined category for {product.title}: {category}")
            return product, category

        except Exception as e:
            print(f"Error analyzing product for collection with Claude: {e}")
            return product, None # Indicate failure


    async def generate_collection_description_async(self, tag_name: str, product_count: int, product_examples: List[Dict[str, str]]) -> str:
        """Generate a description for a collection using Claude."""
        print(f"Generating Claude collection description for: {tag_name}")
        default_desc = f"<p>A curated selection of {product_count} products related to {tag_name}.</p>"
        if not self.api_key:
            print("API key is missing, returning default collection description.")
            return default_desc

        prompt_template = self.get_prompt('generate_collection_description', DEFAULT_CLAUDE_COLLECTION_DESC_PROMPT)
        prompt = prompt_template.format(
            tag_name=tag_name,
            product_count=product_count,
            product_examples_json=json.dumps(product_examples, indent=2)
        )
        system_prompt = "You are a creative copywriter specializing in e-commerce collection descriptions that are engaging, informative, and optimized for conversion."

        try:
            description = await self._call_claude_api(
                system_prompt=system_prompt,
                user_prompt=prompt,
                max_tokens=1000, # Allow longer descriptions
                temperature=0.7  # Higher temperature for creativity
            )
            print(f"Generated Claude collection description for '{tag_name}'")
            # Basic validation: check if it returned something reasonable (e.g., contains HTML tags)
            if not description or not ('<p>' in description or '<h2>' in description or '<h3>' in description):
                 print(f"Warning: Claude description for '{tag_name}' seems invalid, returning default.")
                 return default_desc
            return description

        except Exception as e:
            print(f"Error generating Claude collection description for {tag_name}: {e}")
            return default_desc


    async def generate_collection_meta_description_async(self, tag_name: str, product_titles_text: str) -> str:
        """Generate a meta description for a collection using Claude."""
        print(f"Generating Claude meta description for: {tag_name}")
        default_meta = f"Explore our {tag_name} collection featuring {product_titles_text}. Find the perfect {tag_name} for your needs."[:160] # Ensure default fits approx length
        if not self.api_key:
            print("API key is missing, returning default meta description.")
            return default_meta

        prompt_template = self.get_prompt('generate_collection_meta_description', DEFAULT_CLAUDE_META_DESC_PROMPT)
        prompt = prompt_template.format(
            tag_name=tag_name,
            product_titles_text=product_titles_text
        )
        system_prompt = "You are an SEO expert who creates compelling meta descriptions that drive clicks while staying within character limits."

        try:
            meta_description = await self._call_claude_api(
                system_prompt=system_prompt,
                user_prompt=prompt,
                max_tokens=60, # Meta descriptions are short, ~160 chars = ~40-50 tokens
                temperature=0.4
            )
            print(f"Generated Claude meta description for '{tag_name}'")
            # Basic validation: check length
            if len(meta_description) > 170: # Allow a little buffer
                print(f"Warning: Claude meta description for '{tag_name}' is too long ({len(meta_description)} chars), truncating.")
                meta_description = meta_description[:160].rsplit(' ', 1)[0] + '...' # Truncate nicely

            if not meta_description:
                 print(f"Warning: Claude returned empty meta description for '{tag_name}', using default.")
                 return default_meta

            return meta_description

        except Exception as e:
            print(f"Error generating Claude meta description for {tag_name}: {e}")
            return default_meta


    async def generate_keyword_map_async(self, concept: str) -> Dict[str, Any]:
        """Generate a semantic keyword map based on a store concept using Claude."""
        print(f"Generating Claude keyword map for concept: {concept[:50]}...")
        default_map = {}
        if not self.api_key:
            print("API key is missing, cannot generate keyword map.")
            return default_map # Return empty dict on failure
        if not concept:
            print("Concept is empty, cannot generate keyword map.")
            return default_map

        prompt_template = self.get_prompt('generate_keyword_map', DEFAULT_CLAUDE_KEYWORD_MAP_PROMPT)
        prompt = prompt_template.format(concept=concept)
        system_prompt = "You are an SEO expert generating structured keyword data in JSON format based on a provided concept."

        try:
            response_text = await self._call_claude_api(
                system_prompt=system_prompt,
                user_prompt=prompt,
                max_tokens=1000, # Allow ample tokens for JSON structure
                temperature=0.3  # Lower temperature for structured output
            )
            print(f"Raw keyword map response from Claude: {response_text}")

            # Attempt to parse the JSON response
            try:
                # Find the JSON block in case Claude adds extra text (though the prompt discourages it)
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_string = response_text[json_start:json_end]
                    keyword_map = json.loads(json_string)
                    # Basic validation of structure
                    if isinstance(keyword_map, dict) and all(k in keyword_map for k in ["core_concepts", "related_topics", "long_tail_keywords", "audience_descriptors"]):
                         print(f"Successfully parsed keyword map for concept: {concept[:50]}...")
                         return keyword_map
                    else:
                        print("Error: Parsed JSON does not match expected structure.")
                        return default_map
                else:
                    print("Error: Could not find JSON object in Claude response.")
                    return default_map
            except json.JSONDecodeError as json_e:
                print(f"Error decoding JSON from Claude response: {json_e}")
                print(f"Response text was: {response_text}")
                return default_map

        except Exception as e:
            print(f"Error generating Claude keyword map for concept '{concept[:50]}...': {e}")
            return default_map

    # --- Blog Generation Methods (Placeholders) ---

    async def generate_outline_async(self, context: Dict[str, Any]) -> List[str]:
        """Generate a blog post outline using Claude (Placeholder)."""
        print(f"ClaudeService: Generating outline with context: {context.get('tag_name', 'N/A')}")
        if not self.api_key:
            print("API key is missing, cannot generate outline.")
            return ["Outline generation requires API key."]

        # TODO: Implement actual prompt construction and API call
        # Example context keys: 'tag_name', 'store_concept', 'target_audience',
        # 'tone_of_voice', 'sitemap_url', 'product_examples', 'existing_blogs'.

        # Placeholder implementation
        await asyncio.sleep(0.1) # Simulate async call
        return [
            f"Introduction to {context.get('tag_name', 'Topic')}",
            f"Key Feature 1 of {context.get('tag_name', 'Topic')}",
            f"Benefit of using {context.get('tag_name', 'Topic')}",
            f"Conclusion about {context.get('tag_name', 'Topic')}"
        ]

    async def generate_content_block_async(self, context: Dict[str, Any]) -> str:
        """Generate a block of content for a blog post using Claude (Placeholder)."""
        outline_point = context.get('outline_point', 'this section')
        print(f"ClaudeService: Generating content block for: {outline_point}")
        if not self.api_key:
            print("API key is missing, cannot generate content block.")
            return f"<p>Content generation requires an API key. This section is about: {outline_point}</p>"

        # TODO: Implement actual prompt construction and API call
        # Example context keys: 'outline_point', 'full_outline', 'tag_name',
        # 'store_concept', 'target_audience', 'tone_of_voice'.

        # Placeholder implementation
        await asyncio.sleep(0.1) # Simulate async call
        return f"<p>This is the generated content for the section about '{outline_point}'. It discusses the importance and details related to the main topic of {context.get('tag_name', 'the blog post')}, keeping in mind the target audience ({context.get('target_audience', 'general readers')}) and maintaining a {context.get('tone_of_voice', 'neutral')} tone.</p>"