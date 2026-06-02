# AMRL Keyence / SpiiPlusSPC Bridge Interface

This project is a Python/Textual terminal application that lets SpiiPlusSPC request Keyence height data over a com0com virtual serial link. SPC remains responsible for motion, toolpaths, and process timing. Python opens the other side of the com0com pair, talks to the Keyence controller, tracks height data when requested, and sends replies back to SPC.

## Jump To Sections

- [Quick Start](#quick-start)
- [System Overview For Operators](#system-overview-for-operators)
- [Installation](#installation)
  - [Option A: Install With Script](#option-a-install-with-script)
  - [Option B: Manual Install](#option-b-manual-install)
- [Running The App](#running-the-app)
  - [Option A: Run With Script](#option-a-run-with-script)
  - [Option B: Manual Run](#option-b-manual-run)
  - [App Layout](#app-layout)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Recommended SPC Serial Settings](#recommended-spc-serial-settings)
- [App Panels And Features](#app-panels-and-features)
  - [SPC Coms Panel](#spc-coms-panel)
  - [Keyence Coms Panel](#keyence-coms-panel)
  - [Height Panel](#height-panel)
  - [Simulator Mode](#simulator-mode)
- [Export Analysis](#export-analysis)
- [SPC Command Reference](#spc-command-reference)
  - [Tracking Registries](#tracking-registries)
- [Error Behavior](#error-behavior)
  - [SPC Protocol Errors](#spc-protocol-errors)
  - [App/System Errors](#appsystem-errors)
  - [Keyence Target And Read Errors](#keyence-target-and-read-errors)
- [Troubleshooting](#troubleshooting)
  - [SPC Times Out Waiting For A Reply](#spc-times-out-waiting-for-a-reply)
  - [Wrong COM Side Selected](#wrong-com-side-selected)
  - [Mismatched Line Ending](#mismatched-line-ending)
  - [Keyence Not Connected](#keyence-not-connected)
  - [Keyence Read Fails Or Returns Invalid Data](#keyence-read-fails-or-returns-invalid-data)
  - [`NO_HEIGHT`](#no_height)
  - [`ERROR KEYENCE_NOT_CONNECTED`](#error-keyence_not_connected)
  - [com0com Virtual COM Pair Not Linked](#com0com-virtual-com-pair-not-linked)
  - [`run_bridge.bat` Says The Virtual Environment Is Missing](#run_bridgebat-says-the-virtual-environment-is-missing)
- [Developer And LLM Guidance](#developer-and-llm-guidance)

## Quick Start

For normal use:

1. Open this project folder on the bridge computer.
2. If this is the first run on this computer, run `install_bridge.bat`.
3. Start the app with `run_bridge.bat`.
4. In the app, confirm the serial settings.
5. Press `Connect`.
6. Run the SPC recipe or serial command that talks to the com0com paired port.

Default port assumptions:

- Keyence controller: `COM5`
- Python SPC peer: `COM21`
- SPC software com0com paired port: usually `COM20`

With a com0com pair such as `COM20 <-> COM21`, SPC opens `COM20` and this Python bridge opens `COM21`.

## System Overview For Operators

The bridge is intentionally narrow. Python does not replace SPC motion control, toolpath execution, galvo control, stage control, or laser timing. SPC owns those parts of the manufacturing process.

Python owns:

- Keyence serial communication
- latest height state
- height tracking registries
- replies to SPC serial requests
- communication logs and operator display

Typical topology using com0com:

```text
SPC software
    |
    | COM20
    |
com0com virtual COM pair
    |
    | COM21
    |
Python bridge
    |
    | real RS232 / USB-RS232
    |
Keyence controller
```

From Python's perspective:

- `RX` means Python received a message from SPC or Keyence.
- `TX` means Python sent a message to SPC or Keyence.
- `SYS` means local application/system status.

## Installation

There are two install paths. Use the script path unless you need to debug setup manually.

This project was built with Python 3.14. Use Python 3.14 for the fewest dependency and runtime issues.

### Option A: Install With Script

From the project root, run:

```bat
install_bridge.bat
```

The script:

- creates `myenv` if it does not already exist
- activates `myenv`
- upgrades `pip`
- installs `requirements.txt`
- pauses on failure so the error can be read

This installer needs access to the required Python packages. On an offline machine, prepare `myenv` on another machine or copy a known-good `myenv` folder into the project root.

### Option B: Manual Install

Open the project root and create the virtual environment:

```bat
py -3.14 -m venv myenv
```

If the Python launcher is not available, use the Python 3.14 executable directly.

Activate the virtual environment:

```bat
myenv\Scripts\activate
```

Install dependencies:

```bat
pip install -r requirements.txt
```

## Running The App

There are also two run paths.

### Option A: Run With Script

From the project root, run:

```bat
run_bridge.bat
```

The script activates `myenv` and runs:

```bat
python -m src.main
```

If `myenv` is missing or the app exits with an error, the script leaves the terminal open so the message can be read.

`run_bridge.bat` does not install packages. It only uses the existing `myenv\Scripts\python.exe`.

### Option B: Manual Run

Activate the virtual environment:

```bat
myenv\Scripts\activate
```

Run the app:

```bat
python -m src.main
```

### App Layout

The app is a terminal UI. It is organized around these panels:

- `SPC Docs`: in-app documentation for the SPC commands accepted by the bridge.
- `SPC Coms`: serial traffic between SPC software and Python over com0com.
- `Keyence Coms`: serial traffic between Python and the Keyence controller.
- `Status`: current Keyence, SPC, and bridge state.
- `Control bar`: connect/read/stream/simulator/view toggles.
- `Height`: live height graph and tracking-registry graph.
- `Footer help bar`: hover over controls and panels to see contextual help.

Main controls:

- `Close`: closes serial connections and exits the app.
- `Connect`: applies the current settings and opens the Keyence/SPC serial connections.
- `Simulator`: toggles simulated Keyence readings.
- `Read`: performs one averaged Keyence read.
- `Keyence Stream`: starts or stops Keyence automatic transmission.
- `Height`: shows or hides the height graph panel.
- `Status`: shows or hides all status panels.
- `SPC`: shows or hides the SPC communications panel.
- `Keyence`: shows or hides the Keyence communications panel.
- `Docs`: shows or hides the SPC command documentation panel.

The port/settings fields in the status panels apply when you press `Enter` or when the field loses focus.

The `Logs` field in Bridge State controls how many session log files are kept in the project `logs` folder. Use `0` for unlimited logs. The app records raw SPC/Keyence TX/RX, system messages, and errors before UI filters such as RAW, TIME, RX, TX, or WRAP are applied.

The `Exports` field controls how many CSV export files are kept in the project `exports` folder. Use `0` for unlimited exports.

`analyze_latest_export.bat` runs the separate offline analysis tools against the newest CSV export and writes graphs to `analysis_outputs`.

## Keyboard Shortcuts

| Key | Action |
| --- | --- |
| `q` | Quit |
| `c` | Connect |
| `h` | Toggle Height panel |
| `d` | Toggle SPC Docs |
| `s` | Toggle simulator |
| `r` | Read once |

## Recommended SPC Serial Settings

In SpiiPlusSmartProcessCommander or equivalent SPC serial tooling, configure the SPC side of the com0com pair. For the common `COM20 <-> COM21` pair, SPC uses `COM20` and Python uses `COM21`.

| Setting | Value |
| --- | --- |
| Port | `COM20` |
| Baud | `9600` |
| Data bits | `8` |
| Parity | `None` |
| Stop bits | `1` |
| Flow | `None` |
| Line End | `CR+LF` |
| Wait reply | `Yes` |
| Timeout | `5000 ms` |

The Python app should open the other side of the com0com virtual pair, usually `COM21`.

If SPC times out waiting for a reply, first check:

- SPC is opening the SPC-side com0com port, usually `COM20`.
- Python is opening the paired Python-side com0com port, usually `COM21`.
- Both sides use the same baud rate.
- SPC is waiting for a reply.
- Line ending is `CR+LF` / `CRLF`.

## App Panels And Features

This section describes the main interactive panels. These panels are for operator visibility and debugging; the actual SPC request/reply behavior still happens through the serial bridge.

### SPC Coms Panel

The SPC Coms panel shows traffic between SPC software and Python over the com0com virtual serial pair.

Typical use:

- confirm SPC messages are reaching Python
- confirm Python replies are being sent back to SPC
- inspect protocol-level errors such as `ERROR UNKNOWN_COMMAND ...`
- manually send debug messages through the SPC serial peer

Log directions:

- `RX`: Python received a message from SPC.
- `TX`: Python sent a reply/message to SPC.
- `SYS`: local bridge/system status related to SPC.

SPC Coms includes filter controls:

- `RAW`: show literal messages with command comments when available.
- `TIME`: show or hide timestamps.
- `WRAP`: wrap long log lines.
- `RX`: show or hide received SPC messages.
- `TX`: show or hide sent SPC messages.

The prompt at the bottom of the panel is for manual debugging. Type a message and press `Enter` to send it through the SPC serial peer. Use the Up/Down arrow keys to recall previous entries.

Normal process flow should still be SPC recipe to Python request to Python reply. The manual prompt is not the normal production path.

### Keyence Coms Panel

The Keyence Coms panel shows traffic between Python and the Keyence controller.

Typical use:

- verify Keyence commands are being sent
- inspect raw Keyence responses
- confirm read/stream commands are succeeding
- diagnose Keyence connection, read, or stream errors
- manually send Keyence debug commands when connected and not streaming

Log directions:

- `TX`: Python sent a command to Keyence.
- `RX`: Python received a response or stream line from Keyence.
- `SYS`: local bridge/system status related to Keyence.

Keyence Coms has the same filter controls as SPC Coms:

- `RAW`
- `TIME`
- `WRAP`
- `RX`
- `TX`

Manual Keyence commands are sent from the prompt at the bottom of the panel. Manual commands are blocked while streaming is active because automatic transmission can interleave with normal command responses.

If Keyence reads fail, first make sure there is an appropriate target under the sensor at a reasonable height.

### Height Panel

The Height panel can show live height data or data from a tracking registry.

Sources:

- `LIVE`: recent live height samples.
- tracking registries: named registries created by SPC tracking commands.

You can also choose `CREATE NEW...` from the Height Source dropdown, type a register name, and press `Enter` to create and select an empty inactive register.

Graph behavior:

- `LIVE` shows recent samples.
- tracking registries show the full registry history compressed to fit the panel width.
- tracking registries can be viewed as all layers or as one selected scan layer.

Displayed statistics:

- latest value
- minimum
- maximum
- average

The `INV` toggle controls whether invalid readings are included in the graph and CSV export. The `EXPORT CSV` button exports the currently selected source to the project `exports` folder. Old CSV exports are pruned according to the Bridge State `Exports` setting; `0` means unlimited.

The `NEXT LAYER` button advances the selected tracking registry to a new scan layer. It does not assign any physical axis or offset.

The Height panel is for operator visibility. SPC command replies are still handled through the SPC serial request/reply path.

### Simulator Mode

Simulator mode is not recommended for normal operation. It is mainly a programming/debugging aid for development work.

Important simulator limitations:

- It is not guaranteed to be updated with every newer bridge feature.
- It should not be treated as a full SPC/com0com/hardware simulation.
- It is mainly useful for testing Keyence-style communications and UI behavior without the Keyence controller attached.
- It is not intended to validate SPC Coms behavior. Use a real com0com pair for SPC-side testing.

## Export Analysis

The analysis tools are separate from the bridge app. They do not open serial ports, connect to Keyence, or talk to SPC. They only read exported CSV files from `exports` and write analysis output to `analysis_outputs`.

To analyze the newest export, run:

```bat
analyze_latest_export.bat
```

The batch file opens a terminal prompt where you can type analysis flags. Press `Enter` with no flags to use the defaults.

The batch file runs:

```bat
python -m src.analysis.run_latest_export
```

The runner finds the newest `.csv` file in `exports`, loads its height samples and metadata, then runs the selected analysis modules in `src.analysis.analyses`.

By default, graphs open as interactive Matplotlib windows and are not saved to disk. Add `--save` to write files to `analysis_outputs`.

Current generated outputs include:

- `height_trace.png`: height versus timestamp or sample index.
- `height_by_layer.png`: one trace per scan layer, when multiple layers exist.
- `height_histogram.png`: distribution of valid height readings.
- `heightmap_top_down.png`: top-down physical X/Y heightmap where color represents Z height, with optional contours.
- `heightmap_3d.png`: 3D surface heightmap with Z exaggeration. Produced by the `surface3d` graph.
- `summary.txt`: sample counts, metadata, and valid-height summary statistics.

Analysis plots use the exported scan metadata when available. Metadata such as `X`, `Y`, `LENGTH`, `WIDTH`, `DELTAY`, and `SCANSPEED` is shown in titles and summaries. Sample timestamps use `collected_at_ns` when present.

By default, all available outputs are produced interactively. To choose specific graphs, pass `--graphs`:

```bat
analyze_latest_export.bat --graphs trace heightmap summary
```

To save selected outputs:

```bat
analyze_latest_export.bat --graphs trace heightmap summary --save
```

Available graph/report names:

- 1D graphs: `trace`, `layers`, `histogram`
- 2D graph: `heightmap`
- 3D graph: `surface3d`
- Report: `summary`
- Everything: `all`

`heightmap` produces one top-down 2D X/Y plot where color and contour lines show Z height. Use `surface3d` separately when you want the 3D surface view.

For 1D graphs and the summary report, you can filter to one layer:

```bat
analyze_latest_export.bat --graphs trace histogram --layer 2
```

You can set a custom title with:

```bat
analyze_latest_export.bat --graphs heightmap --title "Scan 12"
```

Heightmap options:

```bat
analyze_latest_export.bat --graphs heightmap --heightmap-contours 20
```

```bat
analyze_latest_export.bat --graphs heightmap --heightmap-tilt-correction --heightmap-gaussian-sigma 1.5
```

```bat
analyze_latest_export.bat --graphs heightmap --heightmap-force-metadata-size --heightmap-z-exaggeration 2
```

```bat
analyze_latest_export.bat --graphs heightmap surface3d --heightmap-z-exaggeration 20
```

```bat
analyze_latest_export.bat --graphs heightmap --heightmap-grid-x-count 350 --heightmap-grid-y-count 350 --heightmap-cmap turbo
```

Heightmap flags:

- `--heightmap-tilt-correction`: subtracts a best-fit plane before plotting.
- `--heightmap-gaussian-sigma <number>`: smooths the heightmap; `0` disables smoothing.
- `--heightmap-force-metadata-size`: resamples layer rows so the map fills the metadata extents even when layers have different sample counts. If metadata size is missing, this forces a square visible plotting area from the available sample/layer span.
- `--heightmap-z-exaggeration <number>`: multiplies displayed Z values for `surface3d`.
- `--heightmap-contours <count>`: controls contour line count; `0` disables contours.
- `--heightmap-grid-x-count <count>`: interpolation grid resolution along X.
- `--heightmap-grid-y-count <count>`: interpolation grid resolution along Y.
- `--heightmap-cmap <name>`: Matplotlib colormap, such as `turbo`, `viridis`, `plasma`, `inferno`, or `cividis`.
- `--surface3d-max-grid <count>`: maximum grid width/height used for interactive 3D rendering. Lower values are faster.

The heightmap normalizes X separately for each scan layer, spreads layers across Y, interpolates the uneven points onto a rectangular grid, and then plots both a top-down map and a 3D surface. This matches the intended scan shape better when different layers have different sample counts.

The analysis tools require Matplotlib. Heightmap interpolation and Gaussian smoothing require SciPy. If the analysis script reports that Matplotlib or SciPy is missing, install/update the environment on a machine with dependency access:

```bat
pip install -r requirements.txt
```

## SPC Command Reference

The app's SPC command documentation is generated from the command registry in `src.bridge.spc_commands`. The in-app `SPC Docs` panel reads from that same registry.

| Command | Aliases | Purpose | Reply |
| --- | --- | --- | --- |
| `PING` | | Check whether the Python bridge is responding. | `1` |
| `STATUS` | | Return current bridge, SPC peer, stream, and height state. | `KEYENCE_CONNECTED=...;SPC_CONNECTED=...;STREAMING=...;HEIGHT=...` |
| `GET_LAST_HEIGHT` | `GET_HEIGHT`, `HEIGHT?` | Return the latest known Keyence height without forcing a read. | numeric height or `NO_HEIGHT` |
| `READ_HEIGHT` | `READ_ONCE` | Perform a fresh averaged Keyence read and return the height. | numeric height or `ERROR ...` |
| `GET_PROGRAM` | `PROGRAM?`, `GET_KEYENCE_PROGRAM` | Return the active Keyence program number using `PR`. | numeric program number or `ERROR ...` |
| `SET_PROGRAM <program>` | `CHANGE_PROGRAM`, `SET_KEYENCE_PROGRAM` | Change the active Keyence program using `PW,<program>`. | `1` on success, `0` on failure |
| `START_STREAM` | | Start Keyence automatic transmission. | `1` on success, `0` on failure |
| `STOP_STREAM` | | Stop Keyence automatic transmission. | `1` on success, `0` on failure |
| `START_TRACKING <registry>` | | Start appending valid heights to a named tracking registry. | `1` on success, `0` on failure |
| `STOP_TRACKING <registry>` | | Stop appending heights to a named tracking registry. | `1` on success, `0` on failure |
| `PAUSE_TRACKING <registry>` | | Temporarily stop appending heights without ending the tracking session. | `1` on success, `0` on failure |
| `RESUME_TRACKING <registry>` | | Resume appending heights to a paused tracking registry. | `1` on success, `0` on failure |
| `CLEAR_TRACKING <registry>` | | Stop tracking a named registry, then clear its samples. | `1` on success, `0` on failure |
| `SET_SCAN_METADATA <registry> X=... Y=... WIDTH=... LENGTH=... DELTAY=... SCANSPEED=...` | `SET_SCAN_INFO`, `SCAN_METADATA` | Store optional scan metadata for CSV export. | `1` on success, `0` on failure |
| `NEXT_LAYER <registry>` | `NEXT_SCAN_LAYER` | Advance a tracking registry to a new scan layer. | `1` on success, `0` on failure |
| `PREPARE <registry>` | `PREPARE_TRACKING`, `PREPARE_SCAN` | Stop tracking/scanning, clear a registry, start tracking it, and start Keyence scanning/streaming. | `1` on success, `0` on failure |
| `SAVE <registry>` | `SAVE_TRACKING`, `SAVE_SCAN` | Stop tracking a registry, stop Keyence scanning/streaming, and export the registry to CSV. | `1` on success, `0` on failure |
| `SAVE_CSV <registry>` | `EXPORT_CSV`, `SAVE_TRACKING_CSV`, `EXPORT_TRACKING_CSV` | Save a named tracking registry to a CSV file in `exports`. | `1` on success, `0` on failure |
| `RETURN_TRACKING <registry>` | | Return all samples from a named tracking registry. | `TRACKING <registry> COUNT=<n> VALUES=<comma-separated-mm-values>` |
| `AVERAGE_TRACKING <registry>` | `AVG_TRACKING` | Return the average of a named tracking registry. | `TRACKING_AVG <registry> <value>` or `NO_TRACKING_DATA <registry>` |
| `MAX_TRACKING <registry>` | | Return the maximum sample in a named tracking registry. | `TRACKING_MAX <registry> <value>` or `NO_TRACKING_DATA <registry>` |
| `MIN_TRACKING <registry>` | | Return the minimum sample in a named tracking registry. | `TRACKING_MIN <registry> <value>` or `NO_TRACKING_DATA <registry>` |

Reply rules:

- Data commands return data.
- Boolean/status-style commands use numeric replies so SPC does not need string comparison.
- For those commands, `1` means success and `0` means failure.
- Unknown commands return `ERROR UNKNOWN_COMMAND <message>`.
- Commands may be sent with underscores or spaces between command words. For example, `MAX_TRACKING 1` and `MAX TRACKING 1` are both accepted.

### Tracking Registries

Tracking registries are named buckets of valid Keyence height samples. SPC can start tracking one registry, later start another, and query them independently.

Example:

```text
START_TRACKING 1
```

This starts collecting new valid Keyence heights into registry `1`.

```text
STOP_TRACKING 1
```

This stops adding new samples to registry `1`.

```text
RETURN_TRACKING 1
```

This returns all samples collected in registry `1`.

Multiple registries can exist independently:

```text
START_TRACKING 1
START_TRACKING 2
STOP_TRACKING 1
RETURN_TRACKING 2
```

Active trackers collect valid Keyence height samples whenever the bridge records a valid height. This can happen from reads or stream updates.

Optional scan metadata can be attached to a registry before or during a scan:

```text
SET_SCAN_METADATA 1 X=0 Y=0 WIDTH=10 LENGTH=20 DELTAY=0.1 SCANSPEED=5
```

Supported fields are `X`, `Y`, `WIDTH`, `LENGTH`, `HEIGHT`, `DELTAY`, and `SCANSPEED`. These are optional and are written once per exported row in the CSV. Each collected height sample also receives its own timestamp in the CSV.

Use pause/resume tracking to ignore transition motion while Keyence streaming continues:

```text
PAUSE_TRACKING 1
NEXT_LAYER 1
RESUME_TRACKING 1
```

`PAUSE_TRACKING` stops adding new samples to the registry without stopping Keyence streaming or resetting the current layer. `RESUME_TRACKING` starts appending samples again into the current layer.

Registries can also be divided into scan layers. A layer is only an ordering marker; it does not imply X, Y, or any physical offset. Use:

```text
NEXT_LAYER 1
```

after SPC has moved to the next scan layer. CSV exports include `layer_index` and `layer_sample_index` columns.

Useful tracker query commands:

```text
RETURN_TRACKING 1
AVERAGE_TRACKING 1
MAX_TRACKING 1
MIN_TRACKING 1
PAUSE_TRACKING 1
RESUME_TRACKING 1
NEXT_LAYER 1
SAVE_CSV 1
```

CSV exports are written to the project `exports` folder. The UI Height panel can export the currently selected source, including `LIVE`; SPC CSV commands export named tracking registries.

For recipe-style SPC use, the combined helper commands are usually simpler:

```text
PREPARE 1
SAVE 1
```

`PREPARE 1` stops any current tracking/scanning state for registry `1`, clears registry `1`, starts tracking registry `1`, and starts Keyence streaming. `SAVE 1` stops tracking registry `1`, stops Keyence streaming, and saves registry `1` to CSV.

## Error Behavior

There are two main classes of errors.

### SPC protocol errors

These are command-level errors caused by messages from SPC, such as unknown commands or missing arguments.

Examples:

```text
ERROR UNKNOWN_COMMAND FOO
0
ERROR KEYENCE_NOT_CONNECTED
```

Boolean/status-style command failures are sent back as `0` and logged in SPC Coms as `TX`. Data-command and unknown-command errors may still return `ERROR ...` text for diagnosis.

### App/system errors

These are local bridge errors such as serial failures, Keyence read failures, or poll failures.

They appear as system lines:

```text
SYS | ERROR: ...
```

Routing behavior:

- Keyence read/stream errors route to Keyence Coms.
- SPC serial/poll errors route to SPC Coms.
- The Bridge State error field highlights red when `last_error` is set.

### Keyence target and read errors

The Keyence sensor can return invalid readings or errors if there is nothing under it, the target is outside the valid range, or the surface is not readable. If read commands are failing, place an appropriate object or surface under the sensor at a reasonable height and try again.

This is especially relevant for:

```text
READ_HEIGHT
GET_LAST_HEIGHT
START_STREAM
```

`GET_LAST_HEIGHT` does not force a new read, but it can only return a useful value after the bridge has already received a valid height.

## Troubleshooting

### SPC times out waiting for a reply

Check:

- SPC is opening the SPC-side com0com port, usually `COM20`.
- Python is opening the paired com0com port, usually `COM21`.
- The com0com virtual COM pair is actually linked.
- SPC has `Wait reply` enabled.
- SPC line ending is `CR+LF`.
- Python line ending is `CRLF`.
- Baud rates match, usually `9600`.

### Wrong COM side selected

If Python and SPC both open the same side of the com0com pair, messages will not flow correctly.

Use this pattern:

```text
SPC software: COM20
Python app:   COM21
```

or the reverse, as long as the two ports are paired by com0com and not the same port.

### Mismatched line ending

Use:

```text
CR+LF
```

in SPC, and:

```text
CRLF
```

in the Python app.

### Keyence not connected

Symptoms:

```text
ERROR KEYENCE_NOT_CONNECTED
Cannot read: Keyence is not connected
Cannot start stream: Keyence is not connected
```

Fixes:

- Check the Keyence port, usually `COM5`.
- Check the USB-RS232 adapter or RS232 connection.
- Check that no other program has the Keyence port open.
- Press `Connect` after changing the port.
- Do not rely on simulator mode for normal operation.

### Keyence read fails or returns invalid data

The Keyence may fail to return a valid measurement if no target is under the sensor or the target is out of range.

Fixes:

- Put an appropriate object or surface under the sensor.
- Move it to a reasonable measurement height.
- Try changing the Keyence OUT setting in the app. This project defaults to OUT `1`; an invalid response such as `MS,-99.9998,2,--` can happen when the selected OUT channel is not producing a valid measurement.
- Press `Read` again.
- If using SPC, retry `READ_HEIGHT`.

### `NO_HEIGHT`

`NO_HEIGHT` means the bridge does not currently have a valid latest height.

Fixes:

- Connect to Keyence.
- Put a target under the sensor.
- Press `Read`.
- Send `READ_HEIGHT` from SPC.
- Start stream if streaming is appropriate for the test.

### `ERROR KEYENCE_NOT_CONNECTED`

This means SPC requested a Keyence-dependent operation before the Keyence side was connected.

Fixes:

- Connect the bridge.
- Confirm Keyence status says connected.
- Retry the SPC command.

### com0com virtual COM pair not linked

Symptoms:

- Python shows connected but no SPC RX.
- SPC waits until timeout.
- A terminal on the paired port receives nothing.

Fixes:

- Confirm com0com is installed and running.
- Confirm the pair is `COM20 <-> COM21` or update the ports accordingly.
- Make sure each side opens a different port in the com0com pair.

### `run_bridge.bat` says the virtual environment is missing

`run_bridge.bat` expects:

```text
myenv\Scripts\activate.bat
```

Fix:

```bat
install_bridge.bat
```

Or install manually:

```bat
python -m venv myenv
myenv\Scripts\activate
pip install -r requirements.txt
```

Then run:

```bat
run_bridge.bat
```

## Developer And LLM Guidance

For development notes, safety boundaries, and guidance for future maintainers or LLM agents, see `LLM_Guidance.md`.

Implementation details are documented in the relevant Python module docstrings, especially:

- `src.bridge.bridge_controller`
- `src.bridge.spc_commands`
- `src.output.spc_software_client`
- `src.input.keyence_input_client`
- `src.input.simulated_input_client`
- `src.display.terminal_app`
