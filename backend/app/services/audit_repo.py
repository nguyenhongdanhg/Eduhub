import json

from app.db import get_db_connection


class AuditRepo:
  def log(
    self,
    *,
    action: str,
    user_id: int | None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    payload: dict | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
  ) -> None:
    sql = """
      INSERT INTO audit_logs (user_id, action, entity_type, entity_id, payload, ip, user_agent)
      VALUES (%s,%s,%s,%s,%s,%s,%s)
    """
    payload_json = json.dumps(payload or {}, ensure_ascii=False)
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, (user_id, action, entity_type, entity_id, payload_json, ip, user_agent))

