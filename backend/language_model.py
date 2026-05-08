from transformers import AutoTokenizer, AutoModelForCausalLM
from vllm import LLM, SamplingParams

class RAGGenerator:
    def __init__(self, model_name: str, download_dir: str, system_prompt: str):
        self.model = LLM(
            model=model_name,
            # download_dir specifies the location where vllm will look for model weights and where it will download them
            download_dir=download_dir,
        )
        self.system_prompt = system_prompt
    
    def generate(self, history: list[dict[str, str]], query: str, retrieved_docs: list[str], sampling_params: SamplingParams) -> str:
        """Generate text conditioned on:
            1) a system prompt
            2) conversation history between the user and the assistant
            3) a new user query
            4) a list of retrieved documents relevant to the current query.
        
        Args:
            history: A list of dicts representing the conversation history. Each dict has the format
            {
                "role": "user" or "assistant",
                "content": "..."
            }
            query: The user's query.
            retrieved_docs: A list of retrieved documents relevant to the current query.
            sampling_params: Parameters for sampling from the model.
        """
        prompt = self.build_prompt(query, retrieved_docs)
        response = self.model.chat(
            [{"role": "system", "content": self.system_prompt}] \
            + history \
            # history: [{"role": "user", "content": ...}, {"role": "assistant", "content": ...}, ...]
            + [{"role": "user", "content": prompt}],
            sampling_params=sampling_params
        )
        return response[0].outputs[0].text

    def build_prompt(self, query: str, retrieved_docs: list[str]) -> str:
        """Construct a prompt following a template like this:
        Question: {query}
        Documents:
        {doc1}
        
        {doc2}
        
        {doc3}
        ...
        """
        prompt = f"Question: {query}\nDocuments:\n" + "\n\n".join(retrieved_docs)
        return prompt

# Load model
def load_model(model_name):
    model = AutoModelForCausalLM.from_pretrained(model_name)
    return model

# Load tokenizer
def load_tokenizer(model_name):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    return tokenizer

def sentence_transformers_embedding(model, tokenizer, text: str) -> list[float]:
    return model.encode(text)[0].tolist()