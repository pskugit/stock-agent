import os
from dotenv import load_dotenv
load_dotenv()
import openai
openai.api_key = os.getenv("OPENAI_API_KEY")

model_prices = {
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4o": (2.5, 10),
    "o1": (15, 60),
    "o1-mini": (3, 12)
}

def query_llm(prompt, model="gpt-4o-mini"):
    chat_completion = openai.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an autonomous stock-trading agent."},
            {"role": "user", "content": prompt}
        ]
    )
    cost = (chat_completion.usage.prompt_tokens * model_prices[model][0]) + (chat_completion.usage.completion_tokens * model_prices[model][1])
    cost /= 1000000
    return chat_completion.choices[0].message.content, cost
        
        
        
# Example usage
#prompt = "This is an initial testprompt. Please answer with 'OK'" #create_prompt(agent_state, environment_data)
#chat_completion = query_llm(prompt)
#print(chat_completion)