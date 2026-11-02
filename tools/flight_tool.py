
import os
import re
import certifi
import airportsdata
import pycountry
import requests
from dotenv import load_dotenv

# --------------------------------------------------
# 1. ENVIRONMENT CONFIGURATION
# --------------------------------------------------

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

API_KEY = os.getenv("AVIATIONSTACK_API_KEY")

# Default origin: Dhaka, Bangladesh
DEFAULT_ORIGIN_IATA = os.getenv("DEFAULT_ORIGIN_DATA", "DAC")

BASE_URL = "https://api.aviationstack.com/v1/flights"

AIRPORTS = airportsdata.load("IATA")


# --------------------------------------------------
# 2. COUNTRY ALIASES
# --------------------------------------------------

COUNTRY_ALIASES = {
    "usa": "US",
    "u.s.a": "US",
    "u.s.": "US",
    "america": "US",
    "united states": "US",
    "uk": "GB",
    "u.k.": "GB",
    "britain": "GB",
    "england": "GB",
    "uae": "AE",
    "dubai": "AE",
    "south korea": "KR",
    "korea": "KR",
    "russia": "RU",
    "vietnam": "VN",
    "bangladesh": "BD",
    "india": "IN",
    "japan": "JP",
    "china": "CN",
    "singapore": "SG",
    "malaysia": "MY",
    "thailand": "TH",
    "indonesia": "ID",
    "nepal": "NP",
    "qatar": "QA",
    "saudi arabia": "SA",
    "turkey": "TR",
    "canada": "CA",
    "australia": "AU",
    "germany": "DE",
    "france": "FR",
    "italy": "IT",
    "spain": "ES",
}


# --------------------------------------------------
# 3. COUNTRY MAIN AIRPORT MAPPING
# --------------------------------------------------

COUNTRY_MAIN_AIRPORT = {
    "BD": "DAC",
    "IN": "DEL",
    "JP": "NRT",
    "US": "JFK",
    "GB": "LHR",
    "AE": "DXB",
    "SG": "SIN",
    "MY": "KUL",
    "TH": "BKK",
    "ID": "CGK",
    "CN": "PEK",
    "KR": "ICN",
    "NP": "KTM",
    "QA": "DOH",
    "SA": "JED",
    "TR": "IST",
    "CA": "YYZ",
    "AU": "SYD",
    "DE": "FRA",
    "FR": "CDG",
    "IT": "FCO",
    "ES": "MAD",
}


# --------------------------------------------------
# 4. CITY MAIN AIRPORT MAPPING
# --------------------------------------------------

CITY_MAIN_AIRPORT = {
    "dhaka": "DAC",
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "kolkata": "CCU",
    "chennai": "MAA",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "tokyo": "NRT",
    "osaka": "KIX",
    "kyoto": "KIX",
    "new york": "JFK",
    "london": "LHR",
    "dubai": "DXB",
    "singapore": "SIN",
    "kuala lumpur": "KUL",
    "bangkok": "BKK",
    "doha": "DOH",
    "istanbul": "IST",
    "toronto": "YYZ",
    "sydney": "SYD",
    "paris": "CDG",
    "rome": "FCO",
    "madrid": "MAD",
    "frankfurt": "FRA",
}


# --------------------------------------------------
# 5. CLEAN TEXT
# --------------------------------------------------

def clean_text(text: str) -> str:

    text = text.lower().strip()

    text = re.sub(r"[^a-z0-9\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    stop_words = [
        "flight", "flights", "ticket", "tickets",
        "trip", "travel", "plan", "complete",
        "days", "day", "including", "hotel",
        "hotels", "sightseeing", "under",
        "budget", "info", "information"
    ]

    words = [
        word for word in text.split()
        if word not in stop_words
    ]

    return " ".join(words).strip()


# --------------------------------------------------
# 6. COUNTRY NAME TO COUNTRY CODE
# --------------------------------------------------

def country_name_to_code(text: str):

    try:
        country = pycountry.countries.lookup(text)
        return country.alpha_2

    except LookupError:
        pass

    # Detect country name inside longer text
    for country in pycountry.countries:

        country_name = country.name.lower()

        if country_name in text:
            return country.alpha_2

    for alias, code in COUNTRY_ALIASES.items():

        if alias in text:
            return code

    return None


# --------------------------------------------------
# 7. CHECK AIRPORT COUNTRY
# --------------------------------------------------

def airport_country_matches(airport: dict, country_code: str) -> bool:

    airport_country = str(
        airport.get("country", "")
    ).upper().strip()

    if airport_country == country_code:
        return True

    try:
        country = pycountry.countries.get(
            alpha_2=country_code
        )

        if country and airport_country.lower() == country.name.lower():
            return True

    except Exception:
        pass

    return False


# --------------------------------------------------
# 8. GET BEST AIRPORT FOR COUNTRY
# --------------------------------------------------

def get_best_airport_for_country(country_code: str):

    preferred = COUNTRY_MAIN_AIRPORT.get(country_code)

    if preferred and preferred in AIRPORTS:
        return preferred

    candidates = []

    for iata, airport in AIRPORTS.items():

        if not iata:
            continue

        if airport_country_matches(airport, country_code):

            name = str(
                airport.get("name", "")
            ).lower()

            city = str(
                airport.get("city", "")
            ).lower()

            score = 0

            if "international" in name:
                score += 50

            if "intl" in name:
                score += 40

            if "capital" in name:
                score += 20

            if city:
                score += 5

            candidates.append((score, iata))

    if not candidates:
        return None

    candidates.sort(reverse=True)

    return candidates[0][1]


# --------------------------------------------------
# 9. RESOLVE LOCATION TO IATA
# --------------------------------------------------

def resolve_location_to_iata(location: str):

    """
    Converts country/city/airport/IATA into IATA code.

    Examples:
    Bangladesh -> DAC
    Japan -> NRT
    Dhaka -> DAC
    Tokyo -> NRT
    DAC -> DAC
    """

    if not location:
        return None

    raw_location = location.strip()

    # Direct IATA code
    if re.fullmatch(r"[A-Za-z]{3}", raw_location):

        code = raw_location.upper()

        if code in AIRPORTS:
            return code

    location_clean = clean_text(raw_location)

    if not location_clean:
        return None

    # Check city mapping first
    if location_clean in CITY_MAIN_AIRPORT:

        airport = CITY_MAIN_AIRPORT[location_clean]

        if airport in AIRPORTS:
            return airport

    # Country preferred airport
    country_code = country_name_to_code(location_clean)

    if country_code:

        airport = get_best_airport_for_country(country_code)

        if airport:
            return airport

    # Exact city match from airport database
    city_matches = []

    for iata, airport in AIRPORTS.items():

        city = str(
            airport.get("city", "")
        ).lower().strip()

        name = str(
            airport.get("name", "")
        ).lower().strip()

        score = 0

        if city == location_clean:
            score += 100

        elif location_clean in city:
            score += 70

        if location_clean in name:
            score += 50

        if "international" in name:
            score += 10

        if score > 0:
            city_matches.append((score, iata))

    if city_matches:

        city_matches.sort(reverse=True)

        return city_matches[0][1]

    return None


# --------------------------------------------------
# 10. PARSE DEPARTURE AND ARRIVAL LOCATIONS
# --------------------------------------------------

def parse_route(query: str):

    """
    Extracts departure and arrival locations.

    Examples:
    Flights from Bangladesh to Nepal
    -> DAC, KTM

    Plan a 7 days Nepal trip from Bangladesh
    -> DAC, KTM

    Japan trip
    -> DAC, NRT
    """

    if not query:
        return None, None

    query = query.strip()

    # Pattern 1: From Bangladesh to Nepal
    match = re.search(
        r"\bfrom\s+(.+?)\s+to\s+(.+?)(?:[?.!,]|$)",
        query,
        re.IGNORECASE
    )

    if match:

        departure = match.group(1).strip()
        arrival = match.group(2).strip()

        dep_iata = resolve_location_to_iata(departure)
        arr_iata = resolve_location_to_iata(arrival)

        return dep_iata, arr_iata

    # Pattern 2: Nepal trip from Bangladesh
    match = re.search(
        r"\b(.+?)\s+trip\s+from\s+(.+?)(?:[?.!,]|$)",
        query,
        re.IGNORECASE
    )

    if match:

        arrival = match.group(1).strip()
        departure = match.group(2).strip()

        dep_iata = resolve_location_to_iata(departure)
        arr_iata = resolve_location_to_iata(arrival)

        return dep_iata, arr_iata

    # Pattern 3: Destination only, e.g. Japan trip
    cleaned_query = clean_text(query)

    arr_iata = resolve_location_to_iata(cleaned_query)

    if arr_iata:

        return DEFAULT_ORIGIN_IATA, arr_iata

    return None, None


# --------------------------------------------------
# 11. FORMAT FLIGHT DETAILS
# --------------------------------------------------

def format_flight(flight: dict):

    airline = flight.get("airline") or {}
    departure = flight.get("departure") or {}
    arrival = flight.get("arrival") or {}
    flight_info = flight.get("flight") or {}

    airline_name = airline.get("name") or "Unknown airline"

    flight_number = flight_info.get("iata") or "N/A"

    status = flight.get("flight_status") or "Unknown"

    # Departure details
    dep_airport = departure.get("airport") or "Unknown departure airport"
    dep_iata = departure.get("iata") or "Unknown"
    dep_terminal = departure.get("terminal") or "N/A"
    dep_gate = departure.get("gate") or "N/A"
    dep_scheduled = departure.get("scheduled") or "Unknown"

    dep_delay = departure.get("delay")

    dep_delay_text = (
        f"{dep_delay} minutes"
        if dep_delay is not None
        else "N/A"
    )

    # Arrival details
    arr_airport = arrival.get("airport") or "Unknown arrival airport"
    arr_iata = arrival.get("iata") or "Unknown"
    arr_terminal = arrival.get("terminal") or "N/A"
    arr_gate = arrival.get("gate") or "N/A"
    arr_scheduled = arrival.get("scheduled") or "Unknown"

    arr_delay = arrival.get("delay")

    arr_delay_text = (
        f"{arr_delay} minutes"
        if arr_delay is not None
        else "N/A"
    )

    return f"""
Airline: {airline_name}
Flight: {flight_number}
Status: {status}

Departure:
- Airport: {dep_airport}
- IATA: {dep_iata}
- Terminal: {dep_terminal}
- Gate: {dep_gate}
- Scheduled: {dep_scheduled}
- Delay: {dep_delay_text}

Arrival:
- Airport: {arr_airport}
- IATA: {arr_iata}
- Terminal: {arr_terminal}
- Gate: {arr_gate}
- Scheduled: {arr_scheduled}
- Delay: {arr_delay_text}
""".strip()


# --------------------------------------------------
# 12. SEARCH FLIGHTS
# --------------------------------------------------

def search_flights(query: str, limit: int = 10):

    if not API_KEY:

        return (
            "Flight API error: AVIATIONSTACK_API_KEY is missing.\n"
            "Please add this in your .env file:\n"
            "AVIATIONSTACK_API_KEY=your_api_key_here"
        )

    # Extract departure and arrival IATA codes
    dep_iata, arr_iata = parse_route(query)

    params = {
        "access_key": API_KEY,
        "limit": min(max(limit, 1), 100),
    }

    if dep_iata:
        params["dep_iata"] = dep_iata

    if arr_iata:
        params["arr_iata"] = arr_iata

    try:

        response = requests.get(
            BASE_URL,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

    except requests.exceptions.RequestException as e:

        return f"Flight API request failed: {e}"

    except ValueError:

        return "Flight API returned invalid JSON."

    # Check API errors
    if "error" in data:

        error = data["error"]

        return (
            "Flight API error:\n"
            f"Code: {error.get('code', 'Unknown')}\n"
            f"Message: {error.get('message', 'Unknown error')}"
        )

    flight_data = data.get("data", [])

    if not flight_data:

        return (
            f"No live flight data found for {query}.\n\n"
            "Note: Aviationstack provides live/status flight data, "
            "not ticket prices. For actual fare prices, "
            "use a flight-pricing API such as Amadeus."
        )

    # Route information
    route_info = "Global live flights"

    if dep_iata and arr_iata:

        route_info = (
            f"Live flights from {dep_iata} to {arr_iata}"
        )

    elif dep_iata:

        route_info = f"Live flights from {dep_iata}"

    elif arr_iata:

        route_info = f"Live flights to {arr_iata}"

    # Format flight results
    formatted_flights = [
        format_flight(flight)
        for flight in flight_data[:limit]
    ]

    return (
        f"{route_info}\n\n"
        + "\n\n---\n\n".join(formatted_flights)
    )


# --------------------------------------------------
# 13. TESTING
# --------------------------------------------------

if __name__ == "__main__":

    print(
        search_flights(
            "Plan a 7 days Japan trip from Bangladesh"
        )
    )

    print("\n" + "=" * 80)

    print(
        search_flights(
            "all country flight info"
        )
    )
