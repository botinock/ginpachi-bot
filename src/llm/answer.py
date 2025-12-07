import json
from llm.config import GENERATION_CONFIG
from llm.models import WordResponse
from llm.prompts.explain import EXPLAIN_PROMPT

from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from google.genai.errors import ServerError # Specific exceptions
from google.genai.client import AsyncClient


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type(ServerError))
async def write_answer(client: AsyncClient, text: str) -> tuple[str, bool]:
    response = await client.models.generate_content(
        model="gemini-2.5-flash",
        contents=EXPLAIN_PROMPT.format(word=text),
        config=GENERATION_CONFIG.model_copy(update={
            "response_mime_type": "application/json",
            "response_schema": WordResponse}
        )
    )

    try:
        # The response is a JSON string representing your Pydantic object
        data = json.loads(response.text)
        result = WordResponse(**data)
        
        return result.answer, result.should_search_image
    except Exception as e:
        # Fallback if something fails (return text without image search)
        print(f"Error parsing JSON: {e}")
        return response.text, False
