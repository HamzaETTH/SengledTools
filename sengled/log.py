"""
Logging and CLI output formatting utilities.
Provides styled console output with emoji support, indentation control,
and configurable verbosity levels for user-friendly terminal interaction.
"""

import logging
import os
import platform

# Custom OK level removed; we now use success() with glyphs
def _supports_emoji():
    """Detect if terminal supports emoji display"""
    if platform.system() != "Windows":
        term = os.environ.get('TERM', '')
        return term in ('xterm-256color', 'gnome-256color', 'konsole-256color')
    
    term_program = os.environ.get('TERM_PROGRAM', '')
    if 'WindowsTerminal' in term_program or 'ConEmu' in term_program:
        return True
    
    if 'ANSICON' in os.environ or 'ConEmuANSI' in os.environ:
        return True
    
    try:
        import msvcrt
        import ctypes
        kernel32 = ctypes.windll.kernel32
        return kernel32.GetConsoleMode(kernel32.GetStdHandle(-11)) & 0x0004
    except:
        pass
    
    return False


class _LowercaseLevelFormatter(logging.Formatter):
	def format(self, record: logging.LogRecord) -> str:  # noqa: D401
		# Lowercase level names for desired CLI look
		if record.levelname:
			record.levelname = record.levelname.lower()
		return super().format(record)


_logger = logging.getLogger("sengled")
_logger.propagate = False


_GL_SUB = "- "
_GL_OK = "[✓] "
_GL_WAIT = "[…] "
_GL_RESULT = "-> "
_GL_CMD = ">> "
_GL_WARN = "[!] "
_GL_STOP = "[✗] "
_GL_DANGER = "[!!] "
_GL_HIGHLIGHT = "[*] "


def configure(verbose: bool = False, compact_steps: bool = True, show_payloads: bool = False) -> None:
	"""Configure the global CLI logger.

	verbose=True  -> show debug + [level] tags
	compact_steps -> use '— Title' instead of ===== banners
	show_payloads -> print raw send/recv payloads
	"""
	_logger.setLevel(logging.DEBUG)
	_logger.handlers[:] = []

	handler = logging.StreamHandler()

	# Levels
	if verbose:
		handler.setLevel(logging.DEBUG)
		_error_filter = None
	else:
		handler.setLevel(logging.INFO)
		# Hide ERROR in normal mode per UX requirements
		_error_filter = lambda rec: rec.levelno != logging.ERROR  # type: ignore[assignment]

	# Formatter: only show [debug] tags in verbose mode
	if verbose:
		fmt = _LowercaseLevelFormatter("%(message)s")
		# Add debug filter to only show [debug] prefix
		class DebugOnlyFormatter(_LowercaseLevelFormatter):
			def format(self, record):
				if record.levelno == logging.DEBUG:
					return f"[debug] {record.getMessage()}"
				return record.getMessage()
		fmt = DebugOnlyFormatter()
	else:
		# tagless, message-only
		fmt = _LowercaseLevelFormatter("%(message)s")

	handler.setFormatter(fmt)
	if _error_filter:
		handler.addFilter(_error_filter)  # type: ignore[arg-type]
	_logger.addHandler(handler)

	# Store style flags (used by helpers below)
	_logger.compact_steps = bool(compact_steps)           # type: ignore[attr-defined]
	_logger.show_payloads = bool(show_payloads or verbose)  # type: ignore[attr-defined]
	_logger.indent = 0  # type: ignore[attr-defined]
	_logger.verbose = bool(verbose)  # type: ignore[attr-defined]

	# Configure glyphs based on emoji support
	global _GL_SUB, _GL_OK, _GL_WAIT, _GL_RESULT
	global _GL_CMD, _GL_STOP
	global _GL_WARN, _GL_DANGER, _GL_HIGHLIGHT

	if _supports_emoji():
		_GL_SUB    = "➖ "
		_GL_OK     = "✅ "
		_GL_WAIT   = "⏳ "
		_GL_RESULT = "➡️ "
		_GL_CMD    = "⮞ "
		_GL_WARN   = "⚠️ "
		_GL_STOP   = "🚫 "
		_GL_DANGER = "💀 "
		_GL_HIGHLIGHT = "🔍 "


# Thin UX helpers
def say(msg: str, *, extra_indent: int = 0) -> None:
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	print(f"{prefix}{msg}")


def step(title: str, *, extra_indent: int = 0) -> None:
	# Alias to subsection for consistency
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	print(f"{prefix}{_GL_SUB}{title}")


def info(msg: str, *, extra_indent: int = 0) -> None:
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	_logger.info(f"{prefix}{msg}")


def warn(msg: str, *, extra_indent: int = 0) -> None:
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	_logger.warning(f"{prefix}{msg}")


def warn_(msg: str, *, extra_indent: int = 0) -> None:
	"""Warning messages with clear visual indicator"""
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	print(f"{prefix}{_GL_WARN}{msg}")


def ok(msg: str, *, extra_indent: int = 0) -> None:
	# Deprecated shim: route to success for backward compatibility
	success(msg, extra_indent=extra_indent)


def debug(msg: str, *, extra_indent: int = 0) -> None:
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	_logger.debug(f"{prefix}{msg}")


def error(msg: str, *, extra_indent: int = 0) -> None:
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	_logger.error(f"{prefix}{msg}")


def send(proto: str, payload: str, *, extra_indent: int = 0) -> None:
	if getattr(_logger, "show_payloads", False):
		base = int(getattr(_logger, "indent", 0))
		add = max(0, int(extra_indent or 0))
		prefix = " " * (base + add)
		print(f"{prefix}>> {proto} send: {payload}")


def recv(proto: str, payload: str, *, extra_indent: int = 0) -> None:
	if getattr(_logger, "show_payloads", False):
		base = int(getattr(_logger, "indent", 0))
		add = max(0, int(extra_indent or 0))
		prefix = " " * (base + add)
		print(f"{prefix}<< {proto} recv: {payload}")


def section(title: str) -> None:
	"""Major section header with clear visual separation"""
	bar = "─" * 60
	print(f"\n{bar}")
	# Center title within the bar width
	print(" " + title.center(58))
	print(f"{bar}")
	_logger.indent = 0  # type: ignore[attr-defined]


def subsection(title: str, *, extra_indent: int = 0) -> None:
	"""Subsection with subtle separation"""
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	print(f"{prefix}{_GL_SUB}{title}")
	_logger.indent = 2  # type: ignore[attr-defined]


def success(msg: str, *, extra_indent: int = 0) -> None:
	"""Success messages with clear visual indicator"""
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	print(f"{prefix}{_GL_OK}{msg}")


def highlight(msg: str, *, extra_indent: int = 0) -> None:
	"""Highlight important messages with clear visual emphasis"""
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	print(f"{prefix}{_GL_HIGHLIGHT}{msg}")


def waiting(msg: str, *, extra_indent: int = 0) -> None:
	"""Waiting/status messages"""
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	print(f"{prefix}{_GL_WAIT}{msg}")


def result(msg: str, *, extra_indent: int = 0) -> None:
	"""Result/outcome messages"""
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	print(f"{prefix}{_GL_RESULT}{msg}")


def stop(msg: str, *, extra_indent: int = 0) -> None:
	"""Stop/blocked messages with clear visual indicator"""
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	print(f"{prefix}{_GL_STOP}{msg}")


def cmd(msg: str, *, extra_indent: int = 0) -> None:
	"""Command hint lines with arrow prefix."""
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	print(f"{prefix}{_GL_CMD}{msg}")


def rule(width: int = 16, *, extra_indent: int = 0) -> None:
	"""Print a horizontal rule honoring current indent."""
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	print(f"{prefix}{'─'*max(1, width)}")


def set_indent(spaces: int) -> None:
	"""Set current indentation (non-negative)."""
	_logger.indent = max(0, int(spaces))  # type: ignore[attr-defined]


def get_indent() -> int:
	"""Return current indentation in spaces."""
	return int(getattr(_logger, "indent", 0))


def firmware_warn(msg: str, *, extra_indent: int = 0) -> None:
	"""Firmware-specific warning messages with danger indicator"""
	base = int(getattr(_logger, "indent", 0))
	add = max(0, int(extra_indent or 0))
	prefix = " " * (base + add)
	print(f"{prefix}{_GL_DANGER}{msg}")


def is_verbose() -> bool:
	"""Return True if logger is in verbose mode."""
	return bool(getattr(_logger, "verbose", False))


