# Windows organizer setup

This guide uses PowerShell on Windows 10 or 11. The route builder runs locally in Python. Internet access is needed while looking up addresses and road travel times; the generated volunteer HTML file is self-contained.

## Install Python and get the project

1. Install Python from [python.org](https://www.python.org/downloads/windows/). Python 3.12 is a good choice for this project. Open a new PowerShell window and check `py -3.12 --version`. If Python is already installed, this check may be enough.
2. Get the project folder from the maintainer. Once the repository has been published to GitHub, you can clone it with Git or GitHub Desktop. The generated `build` folder is not included in the repository.
3. In PowerShell, change into the project folder. Replace the example path with the folder you actually received:

```powershell
cd "$HOME\Documents\route-builder"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m route_builder.cli --help
```

The `.venv` folder keeps this project's Python packages separate from other projects. You do not need to activate it; the commands below call its Python directly. If `py -3.12` is unavailable, install Python 3.12 and open a new PowerShell window.

## Make an address CSV

Copy `sample_data\organizer_template.csv` to a new file, such as `my_addresses.csv`. Use two columns with the exact header `id,address`. Give each stop a unique ID and put double quotes around each address containing commas. Save as CSV (UTF-8), not an Excel workbook (`.xlsx`). The example addresses are test locations; replace them with your own. The tool currently expects this exact format. Keep the original CSV for your records.

```csv
id,address
01,"5073 Candlewood Dr, Grand Blanc, MI 48439"
02,"5222 Candlewood Dr, Grand Blanc, MI 48439"
```

## Create and review a route

From the project folder, run the first command with your CSV and chosen name:

```powershell
.\.venv\Scripts\python.exe -m route_builder.cli prepare .\my_addresses.csv --name "North Route" --output .\build\routes
```

The name becomes `North-Route`, so the review files appear in `build\routes\North-Route\`. Open `validation.csv` and `census_comparison.csv` in a spreadsheet and `geocode_review.html` in a browser. Check every address and destination pin. A `REVIEW`, `FAILED`, `NO MATCH`, multiple match, ZIP mismatch, or large coordinate difference needs attention. Census coordinates can be estimated along a street, so even a match deserves a pin check. Correct the input CSV and rerun the first command if needed. This step does **not** make a volunteer route.

When you have inspected the reports and are satisfied with every destination, run:

```powershell
.\.venv\Scripts\python.exe -m route_builder.cli prepare .\my_addresses.csv --name "North Route" --output .\build\routes --reviewed
```

The route builder then writes `build\routes\North-Route\North-Route.html` and `route.csv`. Open the HTML yourself to check the order and navigation links before sending it to volunteers. Share the HTML file, not the whole folder. Volunteers choose Waze, Google Maps, or Apple Maps; their progress is saved in the browser on that device. The file does not sync progress between devices. If location permission is unavailable, they can choose a starting stop from the list.

For a second route, use a different CSV and `--name`. The builder will not overwrite an existing named volunteer HTML file; choose a new name when you generate a revised route. It does not yet divide one CSV among several volunteers automatically.

## Common problems

- **“Address CSV header must be exactly: id,address”**: check the header and export as CSV, not `.xlsx`.
- **“expected 2 columns”**: an address containing commas needs double quotes.
- **No volunteer HTML after the first command**: this is intentional; inspect the review files and run again with `--reviewed`.
- **“Input CSV changed after the review files were made”**: rerun the first command to refresh the reports, then review them again.
- **A geocoding or routing request fails**: check internet access and retry. Responses are cached in the route folder, so successful earlier lookups are reused.

Python's [Windows installation guide](https://docs.python.org/3/using/windows.html) and [virtual environment guide](https://docs.python.org/3/library/venv.html) cover installation details. GitHub's [cloning guide](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository) explains how to get the repository once it is published.
