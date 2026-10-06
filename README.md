# F1 Results Agent

A web chat agent for Formula 1 fans who want quick answers about the latest results, the current season's standings, and who can still win the title.

## How To Use 
Go to **https://f1-results-agent-git-636637173930.europe-west1.run.app** 
- Pick one of the sample questions, or type your question in the chat box (see sample questions and tools table for what you can ask about) 
- Each response shows which tools the agent called and the data it used
- The first question may take a few seconds while the race data loads 

## Sample questions

- "When is the earliest Mercedes can clinch the constructors' title?"
- "How did Ferrari do in the last race?"
- "When and where is the next race?"

## Tools

| Tool | What it does |
| --- | --- |
| `get_last_race_results` | Results of the most recent Grand Prix or sprint, optionally filtered by driver or team |
| `get_standings` | Current drivers' or constructors' championship standings |
| `can_win_championship` | Whether a driver or team can still win (or has already clinched the title), what they need at the next round, and the earliest race they could win at |
| `get_next_race` | The next race: circuit, location, date, days until it, and whether it's a sprint weekend |

All data comes from the Ergast/Jolpica F1 API via FastF1, model is built from the `gemini-web-tool-calling base code`. 



