# Real-time Borsuk-Ulam visualizer

This repo provides the source code for a web app that visualizes the global temperature and barometric pressures, and finds points that lie exactly opposite each other on the globe and have identical temperatures and pressures. At least one pair of points are guaranteed to exist due to the [Borsuk-Ulam](https://en.wikipedia.org/wiki/Borsuk–Ulam_theorem) theorem.

You can learn more about the "why" behind this app [here](https://christian-johnson.github.io/blog/2025/pyodide/).

The code does the following things:
- Fetches global weather model data directly from the official [GFS server](https://nomads.ncep.noaa.gov/).
- Paints a map of temperature and pressure onto a Javascript globe (using [globe.gl](globe.gl)).
- Searches the data to find Borsuk-Ulam compatible points, and plots those on top of the globe.
- Uses Pyodide, so all the requests and computation happen in your browser, rather than on a server.

## Running locally

Follow the following steps:
1. Clone this repo: `git clone git@github.com:christian-johnson/borsuk-ulam.git`
2. Change into the directory: `cd borsuk-ulam`
3. Install dependencies: `npm install`
4. Build the application: `npm run build`
5. Serve the page with the web server of your choice, e.g. `cd dist/ && python -m http.server`
6. Visit the appropriate address in your browser (in this case, it would be `localhost:8000`).
7. Wait for the Python kernel to load, click the button, and enjoy!

## Contributing

Bug fixes & PRs are more than welcome! 
