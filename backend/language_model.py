from transformers import AutoTokenizer, AutoModelForCausalLM

# Load tokenizer
def load_tokenizer(model_name):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer

# Load model
def load_model(model_name):
    model = AutoModelForCausalLM.from_pretrained(model_name)
    return model

def sentence_transformers_embedding(model, tokenizer, text: str) -> list[float]:
    return model.encode(text)[0].tolist()