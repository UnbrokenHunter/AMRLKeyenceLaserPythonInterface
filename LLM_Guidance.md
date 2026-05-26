# LLM Guidance And Development Notes

This file is for future maintainers, developers, and LLM agents working on the AMRL Keyence / SpiiPlusSPC Bridge Interface.

The operator-facing documentation belongs in `README.md`. Implementation details should generally live in module docstrings near the relevant code.

## Safety Boundaries

This bridge should stay narrow.

Python should not:

- replace SPC motion control
- directly control laser firing
- directly control galvos
- directly control translation stages
- own toolpath execution or process timing

SPC owns:

- motion
- toolpaths
- laser/galvo process timing
- recipes

Python owns:

- Keyence serial reads
- latest height state
- height tracking registries
- SPC request/reply handling
- logging and operator display

When adding features, prefer changes that preserve this boundary. If a requested feature would move motion, laser, galvo, or stage authority into Python, stop and clarify the system intent before implementing it.

## Development Notes

Compile-check the source:

```bat
myenv\Scripts\python.exe -m compileall -q src
```

Run the app manually:

```bat
myenv\Scripts\activate
python -m src.main
```

Run with the launcher:

```bat
run_bridge.bat
```

Install dependencies with the setup script:

```bat
install_bridge.bat
```

Recommended smoke test:

1. Use a real com0com virtual pair, commonly `COM20 <-> COM21`.
2. Set SPC software to the SPC-side com0com port, commonly `COM20`.
3. Set the Python SPC port to the paired Python-side com0com port, commonly `COM21`.
4. Press `Connect`.
5. Send `PING` from SPC and confirm `PONG`.
6. Send `GET_LAST_HEIGHT`.
7. Toggle the Docs panel with `d`.
8. Toggle the Height panel with `h`.

Use simulator mode only for programming/debugging. It is not a full system simulator and should not be used to validate SPC/com0com behavior.

## Command And Documentation Source Of Truth

SPC commands are defined in `create_default_spc_command_registry` in `src.bridge.spc_commands`.

When adding or changing a command:

1. Add or update the `SpcCommand` entry.
2. Keep `description` and `reply_description` accurate.
3. Add aliases only when they are intentional and documented.
4. Implement the handler in the same module unless there is a strong reason to delegate.
5. Preserve the reply convention:
   - data commands return data
   - successful state-changing commands return `OK`
   - failures return `ERROR ...`

The in-app SPC Docs panel reads from the command registry. Do not maintain a separate hand-written command list in the UI.

Duplicate command names and aliases intentionally raise an error when the registry is built.

## Serial And com0com Defaults

Startup defaults live in `BridgeConfig` in `src.main`.

Current default assumptions:

- Keyence port: `COM5`
- Keyence baud: `115200`
- Python SPC peer port: `COM21`
- SPC-side com0com peer port: usually `COM20`
- SPC baud: `9600`
- SPC reply terminator: `CRLF`
- Keyence OUT: `2`
- average read samples: `5`

Shared serial settings live in `src.serial_settings`.

The UI can override some settings at runtime:

- Keyence port
- Keyence OUT
- SPC port
- SPC baud
- SPC line ending

Changing serial settings while connected closes and recreates the affected clients.

## Where Implementation Details Live

Keep conceptual implementation notes near code:

- `src.bridge.bridge_controller`: controller responsibilities and data flow.
- `src.bridge.spc_commands`: SPC command registry and documentation source.
- `src.output.spc_software_client`: Python side of the com0com SPC serial peer.
- `src.input.keyence_input_client`: real Keyence serial behavior.
- `src.input.simulated_input_client`: simulator limitations and scope.
- `src.display.terminal_app`: UI orchestration and event routing.

If a README section starts explaining internal code flow in detail, consider moving that explanation into one of these module docstrings instead.
