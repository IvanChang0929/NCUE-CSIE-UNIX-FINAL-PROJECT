import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


LOGGER_NAME = "ai_sandbox"
DEFAULT_LOG_LEVEL = logging.INFO
MAX_LOG_SIZE = 1024 * 1024       # 1 MB
BACKUP_COUNT = 5                 # sandbox.log.1 ~ sandbox.log.5


def _find_project_root() -> Path:
    """
    嘗試找出專案根目錄。

    支援 logger.py 放在：
    - backend/logger.py
    - utils/logger.py
    - 專案根目錄/logger.py

    判斷依據：
    往上找是否存在 backend、frontend、sandbox 其中任一資料夾。
    """
    current = Path(__file__).resolve()

    for parent in [current.parent, *current.parents]:
        if (
            (parent / "backend").exists()
            or (parent / "frontend").exists()
            or (parent / "sandbox").exists()
        ):
            return parent

    # 找不到時退回目前工作目錄
    return Path.cwd().resolve()


PROJECT_ROOT = _find_project_root()
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "sandbox.log"


def setup_logger(
    name: str = LOGGER_NAME,
    level: int = DEFAULT_LOG_LEVEL,
    log_file: Optional[Path] = None,
    enable_console: bool = True,
) -> logging.Logger:
    """
    建立並回傳共用 logger。

    避免重複 addHandler：
    同一個 logger 在不同檔案 import 時，不會重複輸出多次。
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    target_file = Path(log_file) if log_file else LOG_FILE

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(source)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        target_file,
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


_logger = setup_logger()


def _log(level: int, source: str, message: str, *args, **kwargs) -> None:
    """
    統一處理 source 欄位。

    使用方式：
        log_info("API", "Job created: job_id=%s", job_id)
    """
    extra = kwargs.pop("extra", {})
    extra["source"] = source
    _logger.log(level, message, *args, extra=extra, **kwargs)


def log_debug(source: str, message: str, *args, **kwargs) -> None:
    _log(logging.DEBUG, source, message, *args, **kwargs)


def log_info(source: str, message: str, *args, **kwargs) -> None:
    _log(logging.INFO, source, message, *args, **kwargs)


def log_warning(source: str, message: str, *args, **kwargs) -> None:
    _log(logging.WARNING, source, message, *args, **kwargs)


def log_error(source: str, message: str, *args, **kwargs) -> None:
    _log(logging.ERROR, source, message, *args, **kwargs)


def log_exception(source: str, message: str, *args, **kwargs) -> None:
    """
    在 except 區塊使用，會自動記錄 traceback。
    """
    kwargs["exc_info"] = True
    _log(logging.ERROR, source, message, *args, **kwargs)


def get_logger() -> logging.Logger:
    """
    如果想直接使用 Python logging 原生 API，可以呼叫這個。
    """
    return _logger


def get_log_file_path() -> str:
    """
    給前端顯示 log 檔案位置用。
    """
    return str(LOG_FILE)


# 啟動時先寫一筆，方便確認 logger 有成功初始化。
log_info("LOGGER", "Logger initialized: file=%s", LOG_FILE)
