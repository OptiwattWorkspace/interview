"""iMessage integration: reading chat.db and sending via Messages.app."""

from .reader import Message, MessageReader, NoAllowedChats
from .sender import AppleScriptSender, ConsoleSender, SendError, Sender

__all__ = [
    "Message",
    "MessageReader",
    "NoAllowedChats",
    "AppleScriptSender",
    "ConsoleSender",
    "SendError",
    "Sender",
]
