"""R49 assistant constants. Bump AI_PROMPT_VERSION on any prompt or tool change."""

AI_PROMPT_VERSION = "assistant-1.2"

#: Model -> tools -> model rounds before the model is asked for a final answer without tools.
MAX_TOOL_ROUNDS = 6
MAX_OUTPUT_TOKENS = 1500
#: Web searches a model may run for one answer, summed over its rounds (R50 B6).
MAX_WEB_SEARCHES = 3
#: The key check ("Test & save") needs one answer token, no more.
KEY_TEST_MAX_TOKENS = 16

#: Earlier messages of a conversation sent back to the model.
MAX_HISTORY_MESSAGES = 20
#: Rows any list-returning tool may hand to the model.
MAX_TOOL_ROWS = 25

STATUS_ANSWERED = "answered"
STATUS_UNVERIFIED = "unverified"
STATUS_ERROR = "error"
STATUS_CAP_REACHED = "cap_reached"
