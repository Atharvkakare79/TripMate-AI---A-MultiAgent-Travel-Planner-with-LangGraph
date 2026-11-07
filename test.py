print("Test file started")

from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights
from backend import run_travel_agent

#print("Tavily function imported")

#res = search_flights("Plan a 7 days Nepal trip from Bangladesh")
#print(res)
# res = tavily_search("Best hotels in India")

# print("Search completed")
# print(res)

user_input = input("Enter travel request: ")

response = run_travel_agent(
    user_input=user_input,
    thread_id="test_user"
)

print("\nFINAL RESPONSE:\n")
print(response["answer"])


