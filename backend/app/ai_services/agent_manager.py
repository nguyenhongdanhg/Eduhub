class AgentManager:
  def run(self, domain: str, prompt: str, rag_context: list[dict]) -> dict:
    return {"domain": domain, "prompt": prompt, "rag_context": rag_context, "suggestion": None}

