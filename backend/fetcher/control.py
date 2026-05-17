import threading
import os
from utils import log_to_queue
from database import get_account

BASE_IOFFICE = (os.environ.get("EDUAI_IOFFICE_BASE_URL") or "https://vpdttq.vnptioffice.vn").rstrip("/")
MAX_VIEWBTN_TRIES = 2
MAX_POPUP_TRIES = 2
MAX_DOWNLOAD_TRIES = 2

_stop_flag = threading.Event()


def request_stop():
  _stop_flag.set()


def reset_stop():
  _stop_flag.clear()


def read_config():
  return get_account()


def make_logger(q=None):
  def logger(msg):
    log_to_queue(str(msg), q)

  return logger
