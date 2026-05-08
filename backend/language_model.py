import torch
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

class RAGSystem:
    """
    Retrieval-Augmented Generation (RAG) pipeline
    
    """

    def __init__(
        self,
        model,
        tokenizer,
        max_new_tokens: int = 500,
    ):
        """
        Initialise the RAG system.

        Args:
            model          : fine-tuned causal language model used for generation.
            tokenizer      : tokenizer corresponding to *model*
            max_new_tokens : maximum number of new tokens the model may generate
                             per call to :meth:`generate`.
        """
        self.model = model
        self.tokenizer = tokenizer
        self.max_new_tokens = max_new_tokens
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)

    def build_prompt(
        self,
        query: str,
        retrieved_docs: list[str],
        instruction: str = None,
    ) -> str:
        """
        Assemble the instruction-tuning prompt used for RAG generation.

        Follows the same three-block template as Assignment 2's ``format_prompt``:
        ``### Instruction``, ``### Input``, ``### Response``.  
        
        Retrieved documents are concatenated (title + body) and inserted as the
        ``Document`` field of the input block, allowing the model to draw on
        multiple passages in a single forward pass.

        **Tip**: If you are unsure what the prompt should look like, inspect a
        few samples from your Assignment 2 test set — the structure used there
        is exactly what this method should replicate (minus the retrieved
        context, which replaces the original document field).

        Args:
            query         : the user question or instruction to be answered.
            retrieved_docs: list of document dicts, each containing ``"title"``
                            and ``"text"`` keys (as stored in ``BM25.docs_store``).
            instruction   : optional override for the ``### Instruction`` block.
                            Defaults to a generic technical-QA instruction when
                            *None*. Look at Test data samples for sample instructions

        Returns:
            Formatted prompt string ready for tokenisation, ending with
            ``"### Response:\\n"`` so the model continues from that position.
        """
        if instruction is None:
            instruction = "Answer the following question using only the information in the document."
        
        # Formatting of the "Input" block: "Question:\n{query}\n\nDocument:\n{title}\n{text}"
        
        # Concatenate retrieved documents
        document_field = "\n".join(retrieved_docs)
            
        # Build the content of the Input block from the query (Question field) and documents (Document field)
        input = f"Question:\n{query}\n\nDocument:{document_field}"
        
        # Concatenate all three blocks using the same template as in Assignment 2
        prompt_string = f"### Instruction:\n{instruction}\n\n### Input:\n{input}\n\n### Response:\n"
        return prompt_string

    def generate(
        self,
        query: str,
        retrieved_docs: list[str],
        instruction: str = None,
    ) -> str:
        """
        Run the full RAG pipeline for a single query.

        ...
        """
        
        # Build prompt
        prompt = self.build_prompt(query, retrieved_docs, instruction)
        
        # Tokenize prompt
        model_inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        
        # Get output tokens
        generated_ids = self.model.generate(
            **model_inputs,
            max_new_tokens=self.max_new_tokens
        )
        
        # Strip prompt tokens
        prefix_len = model_inputs["input_ids"].shape[1]
        output_ids = generated_ids[0][prefix_len:]
    
        # Decode the output tokens
        answer = self.tokenizer.decode(output_ids)
        
        return answer

def sentence_transformers_embedding(model, tokenizer, text: str) -> list[float]:
    return model.encode(text)[0].tolist()