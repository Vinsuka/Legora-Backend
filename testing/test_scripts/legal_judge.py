# Use a pipeline as a high-level helper
from transformers import pipeline
from transformers import AutoTokenizer, AutoModelForCausalLM

messages = [
    {"role": "user", "content": "Who are you?"},
]
pipe = pipeline("text-generation", model="Faybulous/DeepSeek-R1-LegalReasoning")
pipe(messages)

tokenizer = AutoTokenizer.from_pretrained("Faybulous/DeepSeek-R1-LegalReasoning")
model = AutoModelForCausalLM.from_pretrained("Faybulous/DeepSeek-R1-LegalReasoning")