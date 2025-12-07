from pydantic import BaseModel

class WordResponse(BaseModel):
    answer: str
    should_search_image: bool
