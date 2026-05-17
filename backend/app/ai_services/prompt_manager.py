class PromptManager:
  def build_prompt(self, domain: str, user_input: str, context: dict | None = None) -> str:
    ctx = context or {}
    return f"[{domain}] {user_input}\n\ncontext={ctx}"

