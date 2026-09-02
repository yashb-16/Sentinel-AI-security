from app.tools.create_ticket import create_ticket
from app.tools.search_employee import search_employee

TOOLS = {
    "search_employee": search_employee,
    "create_ticket": create_ticket,
}

TOOL_DEFINITIONS_PROMPT = """
Available tools:
- search_employee(query: string) -- search for a coworker by email, within your own company only.
- create_ticket(subject: string, description: string, category: string) -- file a support ticket.

If you need to use a tool, your ENTIRE reply must be exactly this format and nothing else:
TOOL_CALL: tool_name(arg1="value1", arg2="value2")

Otherwise, answer the question normally using the reference material above.
""".strip()
