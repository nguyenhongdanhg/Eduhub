class MemoryService:
  def write(self, scope: str, key: str, value: dict) -> None:
    _ = (scope, key, value)
    return None

  def read(self, scope: str, key: str) -> dict | None:
    _ = (scope, key)
    return None

