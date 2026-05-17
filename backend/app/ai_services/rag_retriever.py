class RagRetriever:
  def retrieve(self, domain: str, query: str, role_allowed: list[str] | None = None) -> list[dict]:
    _ = role_allowed
    return [{"domain": domain, "query": query, "chunks": []}]

