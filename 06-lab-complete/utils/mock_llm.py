"""Mock LLM used for offline deployment labs."""
import random
import time


MOCK_RESPONSES = {
    "default": [
        "This is a mock AI response. In production this can be replaced by OpenAI or another LLM.",
        "The production agent received your question and is running normally.",
        "Your cloud-deployed agent is healthy, secured, and ready to serve requests.",
    ],
    "docker": [
        "Docker packages the application and its dependencies so it runs consistently everywhere."
    ],
    "deploy": [
        "Deployment moves code from a local machine to a cloud service with a public URL."
    ],
    "redis": [
        "Redis is used here for shared state: conversation history, rate limits, and budget tracking."
    ],
}


def ask(question: str, delay: float = 0.05) -> str:
    time.sleep(delay + random.uniform(0, 0.03))
    question_lower = question.lower()
    for keyword, responses in MOCK_RESPONSES.items():
        if keyword in question_lower:
            return random.choice(responses)
    return random.choice(MOCK_RESPONSES["default"])
