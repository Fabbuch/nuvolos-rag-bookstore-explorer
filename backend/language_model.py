from sentence_transformers import SentenceTransformer
import ollama
from ollama import ResponseError

class RAGGenerator:
    def __init__(self, base_model: str, model_name: str, system_prompt: str):
        self.base_model = base_model
        self.model_name = model_name
        self.system_prompt = system_prompt
        # Pull ollama base model if it does not exist already in the OLLAMA_MODELS directory:
        try:
            existing_models = [list_response.model for list_response in ollama.list().models]
            if base_model not in existing_models:
                print(f"Pulling base model {base_model}")
                ollama.pull(base_model)
            if model_name not in existing_models:
                print(f"Creating model {model_name} from base model {base_model}.")
                # Create a model instance with the system prompt:
                ollama.create(model_name, from_=base_model, system=system_prompt)
            print(f"Ollama model {model_name} is ready to use.")
        except ResponseError as e:
            print(f"Error occurred while loading ollama model: {e}")
    
    def generate(self, history: list[dict[str, str]], query: str, retrieved_docs: list[str]) -> str:
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
        """
        prompt = self.build_prompt(query, retrieved_docs)
        response = ollama.chat(
            self.model_name,
            messages=[{"role": "system", "content": self.system_prompt}] + history + [{"role": "user", "content": prompt}],
            )
        return response.message.content

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
    model = SentenceTransformer(model_name)
    return model