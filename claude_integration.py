import anthropic
import asyncio
import aiohttp
import json
from config import Config

class ClaudeTaggingService:
    """Service for tagging products using Claude 3.7."""
    
    def __init__(self, api_key=None):
        """Initialize the Claude client."""
        self.api_key = api_key or Config.ANTHROPIC_API_KEY
        # We'll use AsyncAnthropic client per request instead of storing an instance
        self.model = "claude-3-7-sonnet-20250219"
        
        # List of generic tags to avoid
        self.generic_tags = [
            "product", "item", "good", "merchandise", "quality", "value", 
            "best", "new", "popular", "trending", "featured", "recommended",
            "sale", "discount", "deal", "offer", "promotion", "bargain",
            "general", "misc", "miscellaneous", "other", "various", "assorted",
            "collection", "set", "bundle", "pack", "kit", "package", "group"
        ]
        
        # Maximum number of concurrent API calls
        self.max_concurrent_calls = 10
    
    async def generate_tags_async(self, product):
        """Generate tags for a product using Claude 3.7 asynchronously."""
        print(f"Generating tags for product: {product.title}")
        
        if not self.api_key:
            print("API key is missing, returning api_key_missing tag")
            return product, ["api_key_missing"]
        
        # Prepare the prompt
        prompt = f"""
        You are a product tagging expert. Your task is to analyze the following product information and generate comprehensive, specific tags.

        Every tag will become a collection, so ensure to give each product at least all of the tags that will allow it to sit in the correct collection on my ecommerce.
        
        Product Title: {product.title}
        Product Description: {product.description}
        
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
        - Avoid generic terms like "product", "item", "quality", "value", "new", "trending", etc.
        - Combine related concepts into meaningful phrases (e.g., "stainless steel coffee maker" instead of just "coffee maker")
        
        Return only the tags as a comma-separated list with no additional text, categories, or explanation.
        """
        
        try:
            # Call Claude API using the messages API
            print("Attempting to connect to Claude through asyncio")
            # Use Anthropic's async client directly
            async with anthropic.AsyncAnthropic(api_key=self.api_key) as client:
                response = await client.messages.create(
                    model=self.model,
                    max_tokens=500,
                    temperature=0.2,
                    system="You are a product tagging expert that generates specific, meaningful tags that avoid generic terms and focus on distinctive product attributes.",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
            print(response)
            # Process the response
            tags_text = response.content[0].text.strip()
            print(f"Raw tags from Claude for {product.title}: {tags_text}")
            
            # Split by comma and clean up
            tags = [tag.strip().lower() for tag in tags_text.split(',')]
            
            # Remove any empty tags
            tags = [tag for tag in tags if tag]
            
            # Filter out generic tags
            tags = self.filter_generic_tags(tags)
            
            # Filter out single-word tags
            tags = [tag for tag in tags if ' ' in tag]
            
            # Ensure we have at least one tag
            if not tags:
                tags = ["multi word tag"]
                print(f"No tags after filtering for {product.title}, using 'multi word tag'")
            
            print(f"Final tags for {product.title}: {tags}")
            return product, tags
            
        except Exception as e:
            print(e)
            print(f"Error generating tags for {product.title}: {str(e)}")
            return product, ["error generating tags"]
    
    async def batch_generate_tags(self, products, batch_size=50):
        """Generate tags for multiple products in parallel."""
        results = []
        
        # Process products in batches to avoid overwhelming the API
        for i in range(0, len(products), batch_size):
            batch = products[i:i+batch_size]
            print(f"Processing batch {i//batch_size + 1} of {(len(products) + batch_size - 1) // batch_size}")
            
            # Create a semaphore to limit concurrent API calls
            semaphore = asyncio.Semaphore(self.max_concurrent_calls)
            
            async def process_with_semaphore(product):
                async with semaphore:
                    return await self.generate_tags_async(product)
            
            # Create tasks for all products in the batch
            tasks = [process_with_semaphore(product) for product in batch]
            
            # Wait for all tasks to complete
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            
            print(f"Completed batch {i//batch_size + 1}")
        
        return results
    
    def filter_generic_tags(self, tags):
        """Filter out generic tags that would create spammy collections."""
        return [tag for tag in tags if tag not in self.generic_tags]
    
    async def analyze_product_for_collection_async(self, product):
        """Analyze a product to determine what collection it should belong to."""
        if not self.api_key:
            return product, None
        
        # Prepare the prompt
        prompt = f"""
        You are a product categorization expert. Your task is to analyze the following product information and determine the most appropriate primary category for it.
        
        Product Title: {product.title}
        Product Description: {product.description}
        Current Tags: {', '.join([tag.name for tag in product.tags]) if product.tags else 'None'}
        
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
        
        try:
            # Call Claude API using the messages API
            response = await asyncio.to_thread(
                lambda: self.client.messages.create(
                    model=self.model,
                    max_tokens=50,
                    temperature=0.1,
                    system="You are a product categorization expert that determines specific, meaningful categories for products, avoiding generic terms.",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
            )
            
            # Process the response
            category = response.content[0].text.strip().lower()
            
            # Check if category is too generic
            if category in self.generic_tags:
                return product, "uncategorized product"
            
            # Ensure category is multi-word
            if ' ' not in category:
                category = f"{category} category"
            
            return product, category
            
        except Exception as e:
            print(f"Error analyzing product for collection: {str(e)}")
            return product, None
    
    async def batch_analyze_products_for_collections(self, products, batch_size=50):
        """Analyze multiple products for collections in parallel."""
        results = []
        
        # Process products in batches to avoid overwhelming the API
        for i in range(0, len(products), batch_size):
            batch = products[i:i+batch_size]
            print(f"Processing batch {i//batch_size + 1} of {(len(products) + batch_size - 1) // batch_size}")
            
            # Create a semaphore to limit concurrent API calls
            semaphore = asyncio.Semaphore(self.max_concurrent_calls)
            
            async def process_with_semaphore(product):
                async with semaphore:
                    return await self.analyze_product_for_collection_async(product)
            
            # Create tasks for all products in the batch
            tasks = [process_with_semaphore(product) for product in batch]
            
            # Wait for all tasks to complete
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            
            print(f"Completed batch {i//batch_size + 1}")
        
        return results
    
    async def generate_collection_description_async(self, tag_name, product_count, product_examples):
        """Generate a unique, creative description for a collection."""
        if not self.api_key:
            return f"A collection of {product_count} products related to {tag_name}."
        
        # Prepare the prompt
        prompt = f"""
        Create a unique, engaging description for a collection of {product_count} products tagged as '{tag_name}'.
        
        Some example products in this collection:
        {json.dumps(product_examples, indent=2)}
        
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
        
        try:
            # Call Claude API using the messages API
            response = await asyncio.to_thread(
                lambda: self.client.messages.create(
                    model=self.model,
                    max_tokens=1000,
                    temperature=0.7,
                    system="You are a creative copywriter specializing in e-commerce collection descriptions that are engaging, informative, and optimized for conversion.",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
            )
            
            # Process the response
            description = response.content[0].text.strip()
            print(f"Generated collection description for '{tag_name}' collection")
            
            return description
            
        except Exception as e:
            print(f"Error generating collection description: {str(e)}")
            return f"<p>A curated selection of {product_count} products related to {tag_name}.</p>"
    
    async def generate_collection_meta_description_async(self, tag_name, product_titles_text):
        """Generate a meta description for a collection."""
        if not self.api_key:
            return f"Explore our {tag_name} collection featuring {product_titles_text}. Find the perfect {tag_name} for your needs."
        
        # Prepare the prompt
        prompt = f"""
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
        
        try:
            # Call Claude API using the messages API
            response = await asyncio.to_thread(
                lambda: self.client.messages.create(
                    model=self.model,
                    max_tokens=200,
                    temperature=0.4,
                    system="You are an SEO expert who creates compelling meta descriptions that drive clicks while staying within character limits.",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
            )
            
            # Process the response
            meta_description = response.content[0].text.strip()
            print(f"Generated meta description for '{tag_name}' collection")
            
            return meta_description
            
        except Exception as e:
            print(f"Error generating collection meta description: {str(e)}")
            return f"Explore our {tag_name} collection featuring {product_titles_text}. Find the perfect {tag_name} for your needs."
    
    # Synchronous wrapper methods for backward compatibility
    
    def generate_tags(self, product):
        """Synchronous wrapper for generate_tags_async."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            product, tags = loop.run_until_complete(self.generate_tags_async(product))
            return tags
        finally:
            loop.close()
    
    def analyze_product_for_collection(self, product):
        """Synchronous wrapper for analyze_product_for_collection_async."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            product, category = loop.run_until_complete(self.analyze_product_for_collection_async(product))
            return category
        finally:
            loop.close()
    
    def generate_collection_description(self, tag_name, product_count, product_examples):
        """Synchronous wrapper for generate_collection_description_async."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            description = loop.run_until_complete(self.generate_collection_description_async(tag_name, product_count, product_examples))
            return description
        finally:
            loop.close()
    
    def generate_collection_meta_description(self, tag_name, product_titles_text):
        """Synchronous wrapper for generate_collection_meta_description_async."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            meta_description = loop.run_until_complete(self.generate_collection_meta_description_async(tag_name, product_titles_text))
            return meta_description
        finally:
            loop.close()
