from app.db import get_db_connection


class DocumentCategoriesRepo:
  _DEFAULTS = [
    "Công văn",
    "Quyết định",
    "Thông báo",
    "Kế hoạch",
    "Báo cáo",
    "Tờ trình",
    "Hướng dẫn",
    "Công điện",
  ]

  def ensure_schema(self) -> None:
    try:
      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute("ALTER TABLE document_categories ADD COLUMN description TEXT NULL")
    except Exception:
      pass

  def ensure_default_categories(self, *, user_id: int) -> None:
    self.ensure_schema()
    try:
      with get_db_connection() as conn:
        with conn.cursor() as cur:
          cur.execute("SELECT COUNT(*) AS c FROM document_categories WHERE user_id=%s", (user_id,))
          c = int((cur.fetchone() or {}).get("c") or 0)
          if c > 0:
            return
          sort = 1
          for name in self._DEFAULTS:
            cur.execute(
              "INSERT INTO document_categories (user_id, school_id, name, description, parent_id, sort_order) VALUES (%s,%s,%s,%s,%s,%s)",
              (int(user_id), None, str(name), None, None, int(sort)),
            )
            sort += 1
    except Exception:
      return

  def list_categories(self, *, user_id: int) -> list[dict]:
    self.ensure_default_categories(user_id=user_id)
    sql = "SELECT id, name, description, parent_id, sort_order, created_at, updated_at FROM document_categories WHERE user_id=%s ORDER BY sort_order ASC, id ASC"
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, (user_id,))
        return list(cur.fetchall())

  def create_category(self, *, user_id: int, school_id: int | None, name: str, description: str | None, parent_id: int | None, sort_order: int) -> int:
    self.ensure_schema()
    sql = "INSERT INTO document_categories (user_id, school_id, name, description, parent_id, sort_order) VALUES (%s,%s,%s,%s,%s,%s)"
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, (user_id, school_id, name, description, parent_id, sort_order))
        return int(cur.lastrowid)

  def update_category(self, *, user_id: int, category_id: int, name: str, description: str | None, parent_id: int | None, sort_order: int) -> None:
    self.ensure_schema()
    sql = "UPDATE document_categories SET name=%s, description=%s, parent_id=%s, sort_order=%s WHERE id=%s AND user_id=%s"
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, (name, description, parent_id, sort_order, category_id, user_id))

  def delete_category(self, *, user_id: int, category_id: int) -> None:
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute("UPDATE document_categories SET parent_id=NULL WHERE parent_id=%s AND user_id=%s", (category_id, user_id))
        cur.execute("DELETE FROM document_categories WHERE id=%s AND user_id=%s", (category_id, user_id))

  def list_document_categories(self, *, user_id: int, ioffice_document_id: int) -> list[dict]:
    sql = """
      SELECT c.id, c.name, c.parent_id
      FROM document_category_items i
      JOIN document_categories c ON c.id=i.category_id
      WHERE c.user_id=%s AND i.ioffice_document_id=%s
      ORDER BY c.sort_order ASC, c.id ASC
    """
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, (user_id, ioffice_document_id))
        return list(cur.fetchall())

  def add_document_to_category(self, *, category_id: int, ioffice_document_id: int) -> None:
    sql = "INSERT IGNORE INTO document_category_items (category_id, ioffice_document_id) VALUES (%s, %s)"
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, (category_id, ioffice_document_id))

  def remove_document_from_category(self, *, category_id: int, ioffice_document_id: int) -> None:
    sql = "DELETE FROM document_category_items WHERE category_id=%s AND ioffice_document_id=%s"
    with get_db_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, (category_id, ioffice_document_id))
