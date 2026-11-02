print("Test file started")

from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights

print("Tavily function imported")

res = search_flights("Plan a 7 days Nepal trip from Bangladesh")
print(res)
# res = tavily_search("Best hotels in India")

# print("Search completed")
# print(res)