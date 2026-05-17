import os

import pymysql


def get_db_connection():
  host = os.getenv("EDUAI_DB_HOST", "127.0.0.1")
  port = int(os.getenv("EDUAI_DB_PORT", "3306"))
  user = os.getenv("EDUAI_DB_USER", "root")
  password = os.getenv("EDUAI_DB_PASSWORD", "root")
  database = os.getenv("EDUAI_DB_NAME", "eduai_hub")
  connect_timeout = float(os.getenv("EDUAI_DB_CONNECT_TIMEOUT", "2.5"))
  read_timeout = float(os.getenv("EDUAI_DB_READ_TIMEOUT", "2.5"))
  write_timeout = float(os.getenv("EDUAI_DB_WRITE_TIMEOUT", "2.5"))

  return pymysql.connect(
    host=host,
    port=port,
    user=user,
    password=password,
    database=database,
    charset="utf8mb4",
    autocommit=True,
    connect_timeout=connect_timeout,
    read_timeout=read_timeout,
    write_timeout=write_timeout,
    init_command="SET time_zone = '+07:00'",
    cursorclass=pymysql.cursors.DictCursor,
  )
