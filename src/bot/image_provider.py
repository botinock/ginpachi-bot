from aiogram.types import InputMediaPhoto, URLInputFile


class ImageProvider:
    async def lookup_image(self, query: str) -> str:
        # Placeholder implementation
        return "https://i.pinimg.com/originals/af/65/bf/af65bff950bcbb49d1ab182e9fe2a193.jpg"
    
    async def create_input_media_photo(self, image_url: str, caption: str) -> InputMediaPhoto:
        media = URLInputFile(image_url)
        return InputMediaPhoto(media=media, caption=caption)
