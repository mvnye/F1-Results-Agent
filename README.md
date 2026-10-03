# F1 Results Agent

A web chat agent for Formula 1 fans who want quick, accurate answers about the
current season: the latest results, the standings, and who can still win the title.


## Tools

| Tool | What it does |
| --- | --- |
| `get_last_race_results` | Results of the most recent Grand Prix or sprint, optionally filtered by driver or team |
| `get_standings` | Current drivers' or constructors' championship standings |
| `can_win_championship` | Whether a driver or team can still win (or has already clinched the title), what they need at the next round, and the earliest race they could clinch |
| `get_next_race` | The next race: circuit, location, date, days until it, and whether it's a sprint weekend |

All data comes from the Ergast/Jolpica F1 API via [FastF1](https://docs.fastf1.dev/).

## Sample questions

- "When is the earliest Mercedes can clinch the constructors' title?"
- "How did Ferrari do in the last race?"
- "When's the next race, and is it a sprint weekend?"

## Setup

1. A GCP project with billing and the Vertex AI API enabled.
2. `gcloud auth application-default login`
3. `uv run app.py`, then open http://localhost:8000


