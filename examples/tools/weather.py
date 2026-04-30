async def get_temperature(latitude: float, longitude: float) -> str:
    """Get the current temperature at the given coordinates."""
    return f"Temperature at ({latitude}, {longitude}): 72°F"


async def get_forecast(city: str, days: int = 3) -> str:
    """Get a weather forecast for a city."""
    return f"Forecast for {city} over {days} days: sunny with a chance of clouds."
