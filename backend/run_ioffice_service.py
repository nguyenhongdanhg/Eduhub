import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()


def main():
  host = (os.environ.get("EDUAI_HOST") or "0.0.0.0").strip()
  port = int((os.environ.get("EDUAI_PORT") or "3000").strip())
  uvicorn.run("app.ioffice_main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
  main()

