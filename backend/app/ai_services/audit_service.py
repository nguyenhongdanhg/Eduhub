class AuditService:
  def log(self, action: str, user_id: int | None, payload: dict | None = None) -> None:
    _ = (action, user_id, payload)
    return None

