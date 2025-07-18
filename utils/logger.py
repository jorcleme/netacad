import logging


class EmojiLoggerAdapter(logging.LoggerAdapter):
    # Emoji mapping for standard log levels
    EMOJI_MAP = {
        logging.DEBUG: "🔍",
        logging.INFO: "🟢",
        logging.WARNING: "⚠️",
        logging.ERROR: "❌",
        logging.CRITICAL: "🚨",
    }

    def process(self, msg, kwargs):
        # Get the log level of the current record
        level = kwargs.get("levelno", self.logger.level)
        emoji = self.EMOJI_MAP.get(level, "")
        return f"{emoji} {msg}", kwargs

    # Optional: convenience methods to handle log level emoji correctly
    def debug(self, msg, *args, **kwargs):
        super().debug(f"🔍 {msg}", *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        super().info(f"🟢 {msg}", *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        super().warning(f"⚠️ {msg}", *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        super().error(f"❌ {msg}", *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        super().critical(f"🚨 {msg}", *args, **kwargs)
