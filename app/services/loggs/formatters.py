import json
from datetime import datetime
from logging import Formatter, LogRecord


class CustomJSONFormatter(Formatter):
    """Форматтер для логов, который выводит записи в формате JSON.

    Этот класс наследует от `Formatter` и переопределяет метод `format`,
    чтобы создать JSON-объект, содержащий информацию о записи лога.

    Атрибуты, такие как уровень, сообщение, модуль, функция и номер строки,
    добавляются в JSON-объект, а также любые дополнительные атрибуты,
    которые не являются стандартными и не начинаются с символа подчеркивания.

    Пример использования:
        logger = get_logger("my_logger", INFO, CustomJSONFormatter)
    """

    def format(self, record: LogRecord) -> str:
        """Форматирует запись лога в JSON-строку.

        :param record: Запись лога, содержащая информацию о событии.
        :return: Строка в формате JSON, представляющая запись лога.
        """
        log_record = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        for attr, value in record.__dict__.items():
            if attr not in [
                "args",
                "message",
                "msg",
                "levelname",
                "module",
                "funcName",
                "lineno",
            ] and not attr.startswith("_"):
                log_record[attr] = str(value)

        return json.dumps(log_record, ensure_ascii=False)
