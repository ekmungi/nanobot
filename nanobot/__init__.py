"""
nanobot - A lightweight AI agent framework
"""

__version__ = "0.1.0"

# Use ASCII-safe logo to avoid UnicodeEncodeError on Windows legacy consoles
# where Rich's LegacyWindowsTerm uses cp1252 encoding.
import os as _os
if _os.name == "nt":
    __logo__ = "[nb]"
else:
    __logo__ = "\U0001f408"  # cat emoji
