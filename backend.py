
import os
import certifi
import uuid
import operator

from typing import TypedDict, Annotated, Any
from dotenv import load_dotenv

# =========================================
# ENVIRONMENT CONFIGURATION
# =========================================

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


def get_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing. Add it to your .env file."
        )

    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url += f"{separator}sslmode=require"

    return database_url


DATABASE_URL = get_database_url()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY is missing. Add it to your .env file."
    )


# =========================================
# IMPORTS
# =========================================

import psycopg
from psycopg.rows import dict_row

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)

from langchain_groq import ChatGroq

from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights


# =========================================
# LLM CONFIGURATION
# =========================================

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=GROQ_API_KEY,
    temperature=0.3
)


# =========================================
# STATE DEFINITION
# =========================================

class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]

    user_query: str

    flight_results: Any
    hotel_results: Any

    itinerary: str

    llm_calls: int


# =========================================
# FLIGHT AGENT
# =========================================

def flight_agent(state: TravelState):

    print("\n[Flight Agent] Searching for flights...")

    query = state["user_query"]

    flight_data = search_flights(query)

    return {
        "flight_results": flight_data,

        "messages": [
            AIMessage(content="Flight results fetched successfully.")
        ],

        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================================
# HOTEL AGENT
# =========================================

def hotel_agent(state: TravelState):

    print("\n[Hotel Agent] Searching for hotels...")

    query = f"Best hotels and accommodation options for {state['user_query']}"

    hotel_data = tavily_search(query)

    return {
        "hotel_results": hotel_data,

        "messages": [
            AIMessage(content="Hotel information fetched successfully.")
        ],

        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================================
# ITINERARY AGENT
# =========================================

def itinerary_agent(state: TravelState):

    print("\n[Itinerary Agent] Creating travel itinerary...")

    prompt = f"""
Create a complete travel itinerary.

User Query:
{state['user_query']}

Flight Results:
{state['flight_results']}

Hotel Results:
{state['hotel_results']}

Requirements:
- Create a practical day-by-day itinerary.
- Consider the user's travel duration.
- Include popular tourist attractions.
- Suggest suitable activities.
- Consider travel time between destinations.
- Make recommendations budget-aware.
- Do not invent confirmed flight or hotel bookings.
"""

    response = llm.invoke([
        SystemMessage(
            content="You are an expert travel itinerary planner."
        ),
        HumanMessage(content=prompt)
    ])

    return {
        "itinerary": response.content,

        "messages": [response],

        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================================
# FINAL RESPONSE AGENT
# =========================================

def final_agent(state: TravelState):

    print("\n[Final Agent] Generating final travel response...")

    final_prompt = f"""
Generate the final travel response for the user.

User Request:
{state['user_query']}

Flights:
{state['flight_results']}

Hotels:
{state['hotel_results']}

Itinerary:
{state['itinerary']}

Format your answer using these sections:

1. Trip Summary
2. Flight Information
3. Hotel Suggestions
4. Day-by-Day Itinerary
5. Estimated Budget
6. Final Recommendations

Important:
- Be clear and practical.
- Do not invent flight prices or hotel availability.
- Mention when live pricing is unavailable.
- Distinguish suggestions from confirmed bookings.
- Provide a useful travel-planning response.
"""

    response = llm.invoke([
        SystemMessage(
            content="You are a professional AI travel planning assistant."
        ),
        HumanMessage(content=final_prompt)
    ])

    return {
        "messages": [response],

        "llm_calls": state.get("llm_calls", 0) + 1
    }


# =========================================
# BUILD LANGGRAPH
# =========================================

graph = StateGraph(TravelState)

graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)


# =========================================
# GRAPH EDGES
# =========================================

graph.add_edge(START, "flight_agent")

graph.add_edge("flight_agent", "hotel_agent")

graph.add_edge("hotel_agent", "itinerary_agent")

graph.add_edge("itinerary_agent", "final_agent")

graph.add_edge("final_agent", END)


# =========================================
# POSTGRESQL CHECKPOINTER
# =========================================

_conn = psycopg.connect(
    DATABASE_URL,
    autocommit=True,
    row_factory=dict_row
)

checkpointer = PostgresSaver(_conn)

# Initialize checkpoint tables
checkpointer.setup()


# =========================================
# COMPILE LANGGRAPH
# =========================================

travel_graph = graph.compile(
    checkpointer=checkpointer
)


# =========================================
# FUNCTION FOR FASTAPI / TESTING
# =========================================

def run_travel_agent(
    user_input: str,
    thread_id: str | None = None
):

    if not user_input or not user_input.strip():
        raise ValueError("User input cannot be empty.")

    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    print("\nStarting TripMate AI...")
    print("Thread ID:", thread_id)

    result = travel_graph.invoke(
        {
            "messages": [
                HumanMessage(content=user_input)
            ],

            "user_query": user_input,

            "flight_results": "",
            "hotel_results": "",

            "itinerary": "",

            "llm_calls": 0
        },
        config=config
    )

    final_answer = result["messages"][-1].content

    print("\nTripMate AI execution completed.")

    return {
        "thread_id": thread_id,

        "answer": final_answer,

        "flight_results": result.get(
            "flight_results", ""
        ),

        "hotel_results": result.get(
            "hotel_results", ""
        ),

        "itinerary": result.get(
            "itinerary", ""
        ),

        "llm_calls": result.get(
            "llm_calls", 0
        )
    }
