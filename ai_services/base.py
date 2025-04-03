import asyncio
import re # Import regex module
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional

# Assuming Product is defined elsewhere, e.g., in models.py
# from models import Product # Uncomment if Product type hinting is needed

class BaseAIService(ABC):
    """Abstract base class for AI services for product tagging and collection generation."""

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None, custom_prompts: Optional[Dict[str, str]] = None):
        """
        Initialize the AI service.

        Args:
            api_key: The API key for the service.
            model_name: The specific model to use (if applicable).
            custom_prompts: A dictionary of custom prompts keyed by function name
                            (e.g., 'generate_tags', 'generate_collection_description').
        """
        self.api_key = api_key
        self.model_name = model_name
        self.custom_prompts = custom_prompts or {}
        self.generic_tags = [
            "product", "item", "good", "merchandise", "quality", "value",
            "best", "new", "popular", "trending", "featured", "recommended",
            "sale", "discount", "deal", "offer", "promotion", "bargain",
            "general", "misc", "miscellaneous", "other", "various", "assorted",
            "collection", "set", "bundle", "pack", "kit", "package", "group"
        ]
        # Consider making max_concurrent_calls configurable
        self.max_concurrent_calls = 10

    def get_prompt(self, prompt_key: str, default_prompt: str) -> str:
        """Returns the custom prompt if available, otherwise the default."""
        return self.custom_prompts.get(prompt_key, default_prompt)

    def filter_generic_tags(self, tags: List[str]) -> List[str]:
        """Filter out generic tags."""
        return [tag for tag in tags if tag not in self.generic_tags]

    def clean_tags(self, tags_text: str) -> List[str]:
        """Cleans the raw tag string from the AI."""
        # First, replace all internal whitespace sequences (including newlines) with a single space
        cleaned_text = re.sub(r'\s+', ' ', tags_text).strip()

        # Now split by comma and process
        tags = [tag.strip().lower() for tag in cleaned_text.split(',')]
        tags = [tag for tag in tags if tag] # Remove empty
        tags = self.filter_generic_tags(tags)
        tags = [tag for tag in tags if ' ' in tag] # Remove single-word
        if not tags:
            tags = ["multi word tag"] # Default if all filtered
        return tags

    @abstractmethod
    async def generate_tags_async(self, product: Any) -> Tuple[Any, List[str]]:
        """Generate tags for a product asynchronously."""
        pass

    @abstractmethod
    async def analyze_product_for_collection_async(self, product: Any) -> Tuple[Any, Optional[str]]:
        """Analyze a product to determine its primary collection/category asynchronously."""
        pass

    @abstractmethod
    async def generate_collection_description_async(self, tag_name: str, product_count: int, product_examples: List[Dict[str, str]]) -> str:
        """Generate a description for a collection asynchronously."""
        pass

    @abstractmethod
    async def generate_collection_meta_description_async(self, tag_name: str, product_titles_text: str) -> str:
        """Generate a meta description for a collection asynchronously."""
        pass

    @abstractmethod
    async def generate_keyword_map_async(self, concept: str) -> Dict[str, Any]:
        """Generate a semantic keyword map based on a store concept asynchronously."""
        pass

    async def batch_generate_tags(self, products: List[Any], batch_size: int = 50) -> List[Tuple[Any, List[str]]]:
        """Generate tags for multiple products in parallel."""
        results = []
        for i in range(0, len(products), batch_size):
            batch = products[i:i+batch_size]
            print(f"Processing tag batch {i//batch_size + 1} of {(len(products) + batch_size - 1) // batch_size}")
            semaphore = asyncio.Semaphore(self.max_concurrent_calls)

            async def process_with_semaphore(prod: Any):
                async with semaphore:
                    return await self.generate_tags_async(prod)

            tasks = [process_with_semaphore(product) for product in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            print(f"Completed tag batch {i//batch_size + 1}")
        return results

    async def batch_analyze_products_for_collections(self, products: List[Any], batch_size: int = 50) -> List[Tuple[Any, Optional[str]]]:
        """Analyze multiple products for collections in parallel."""
        results = []
        for i in range(0, len(products), batch_size):
            batch = products[i:i+batch_size]
            print(f"Processing collection analysis batch {i//batch_size + 1} of {(len(products) + batch_size - 1) // batch_size}")
            semaphore = asyncio.Semaphore(self.max_concurrent_calls)

            async def process_with_semaphore(prod: Any):
                async with semaphore:
                    return await self.analyze_product_for_collection_async(prod)

            tasks = [process_with_semaphore(product) for product in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            print(f"Completed collection analysis batch {i//batch_size + 1}")
        return results

    # Synchronous wrappers (can be kept in base or moved to implementations if needed)
    # These might need adjustment depending on how event loops are managed in Flask/sync contexts

    def generate_tags(self, product: Any) -> List[str]:
        """Synchronous wrapper for generate_tags_async."""
        # Note: Managing event loops like this globally can be tricky.
        # Consider using a library like `nest_asyncio` or running async code differently in Flask.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # No running event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            close_loop = True
        else:
            close_loop = False

        try:
            product_out, tags = loop.run_until_complete(self.generate_tags_async(product))
            return tags
        finally:
            if close_loop:
                loop.close()


    def analyze_product_for_collection(self, product: Any) -> Optional[str]:
        """Synchronous wrapper for analyze_product_for_collection_async."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            close_loop = True
        else:
            close_loop = False

        try:
            product_out, category = loop.run_until_complete(self.analyze_product_for_collection_async(product))
            return category
        finally:
            if close_loop:
                loop.close()

    def generate_collection_description(self, tag_name: str, product_count: int, product_examples: List[Dict[str, str]]) -> str:
        """Synchronous wrapper for generate_collection_description_async."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            close_loop = True
        else:
            close_loop = False

        try:
            description = loop.run_until_complete(self.generate_collection_description_async(tag_name, product_count, product_examples))
            return description
        finally:
            if close_loop:
                loop.close()

    def generate_keyword_map(self, concept: str) -> Dict[str, Any]:
        """Synchronous wrapper for generate_keyword_map_async."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            close_loop = True
        else:
            close_loop = False

        try:
            keyword_map = loop.run_until_complete(self.generate_keyword_map_async(concept))
            return keyword_map
        finally:
            if close_loop:
                loop.close()

    def generate_collection_meta_description(self, tag_name: str, product_titles_text: str) -> str:
        """Synchronous wrapper for generate_collection_meta_description_async."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            close_loop = True
        else:
            close_loop = False

        try:
            meta_description = loop.run_until_complete(self.generate_collection_meta_description_async(tag_name, product_titles_text))
            return meta_description
        finally:
            if close_loop:
                loop.close()