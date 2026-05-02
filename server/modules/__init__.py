from .home_automation import handle as home_automation_handle
from .alexa import handle as alexa_handle
from .calendar import handle as calendar_handle
from .web_search import handle as web_search_handle

MODULE_HANDLERS = {
    "home_automation": home_automation_handle,
    "alexa":           alexa_handle,
    "calendar":        calendar_handle,
    "web_search":      web_search_handle,
}