from google.genai import types

GENERATION_CONFIG = types.GenerateContentConfig(
    # Низька температура для детермінованих, фактичних відповідей
    temperature=0.3,
    # Обмеження довжини виводу, щоб запобігти 'Chain-of-Thought' та зайвому тексту
    max_output_tokens=250,
    thinking_config=types.ThinkingConfig(
            # thinking_level=types.ThinkingLevel.LOW,
            thinkingBudget=0
        )
)