from aiogram.types import InputMediaPhoto, URLInputFile, BufferedInputFile
import requests
import asyncio
import json
import os
import aiohttp



IMAGE_API_KEY = os.getenv('IMAGE_API_KEY')
IMAGE_CX = os.getenv('IMAGE_CX')


class ImageProvider:
    async def lookup_image(self, word: str) -> str:
        # Placeholder implementation
        params = {
            'q': word,
            'cx': IMAGE_CX,
            'key': IMAGE_API_KEY,
            'searchType': 'image',
            'num': 1, # Request only 1 result (the most relevant one)
            'lr': 'lang_ja',      # Restricts results to Japanese language documents
            'hl': 'ja',            # Sets interface language to Japanese
            'gl': 'jp',            # Geolocation: Japan (improves relevance)
            # 'imgSize': 'xxlarge', 
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://customsearch.googleapis.com/customsearch/v1', params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
                    if items := data.get('items'):
                        image_url = items[0].get('link')
                        return image_url
                    return None
        except aiohttp.ClientError as e:
            print(f"Network error fetching image for '{word}': {e}")
            return None
        except asyncio.TimeoutError:
            print(f"Timeout fetching image for '{word}'")
            return None
        except Exception as e:
            print(f"Unexpected error fetching image for '{word}': {e}")
            return None
    
    async def create_input_media_photo(self, image_url: str, caption: str) -> InputMediaPhoto:
        media = URLInputFile(
            image_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
        )
        return InputMediaPhoto(media=media, caption=caption)
