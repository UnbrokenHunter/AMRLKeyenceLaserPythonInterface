"""Hover-help registration for the bridge UI."""

from __future__ import annotations

from textual.widget import Widget

from src.display.hover_help import set_hover_help


HELP_ITEMS = {
    "#spc-coms-panel": "SPC serial traffic. RX is received from SPC software; TX is sent back to SPC.",
    "#keyence-coms-panel": "Keyence serial traffic. Use this panel for raw/manual Keyence communication and diagnostics.",
    "#spc-show-raw": "Toggle raw SPC log output. Raw mode shows the literal message plus a comment.",
    "#spc-show-time": "Toggle timestamps for SPC log lines.",
    "#spc-wrap": "Toggle text wrapping for SPC log lines.",
    "#spc-show-rx": "Toggle display of SPC RX entries already in the log and future entries.",
    "#spc-show-tx": "Toggle display of SPC TX entries already in the log and future entries.",
    "#spc-coms-log": "SPC log history. Use RAW/TIME/WRAP/RX/TX to change how this history is shown.",
    "#spc-command-prompt": "Manual SPC debug prompt. Type a message and press Enter to send it through the SPC serial peer.",
    "#keyence-show-raw": "Toggle raw Keyence log output. Raw mode shows the literal message plus a comment.",
    "#keyence-show-time": "Toggle timestamps for Keyence log lines.",
    "#keyence-wrap": "Toggle text wrapping for Keyence log lines.",
    "#keyence-show-rx": "Toggle display of Keyence RX entries already in the log and future entries.",
    "#keyence-show-tx": "Toggle display of Keyence TX entries already in the log and future entries.",
    "#keyence-coms-log": "Keyence log history. Shows commands sent to and responses received from the Keyence controller.",
    "#keyence-command-prompt": "Manual Keyence debug prompt. Type a command and press Enter to send it to Keyence.",
    "#continuous-panel": "Height display panel. Select LIVE height or a tracking registry and inspect current value, min, max, and average.",
    "#height-source-panel": "Height source selector. Choose LIVE data or one of the SPC tracking registries.",
    "#height-source-select": "Choose which height stream or tracker registry is plotted.",
    "#height-source-list": "Available height sources. Active trackers are marked and show sample counts.",
    "#height-graph-panel": "Height graph and summary statistics for the selected source.",
    "#height-current-value": "Most recent height value for the selected source.",
    "#height-graph-stats": "Minimum, maximum, and average of valid values in the selected source.",
    "#height-graph": "ASCII height plot. LIVE shows recent samples; trackers show the full registry history compressed to fit.",
    "#status-column": "Connection and bridge state. Configure serial ports and inspect current runtime status.",
    "#keyence-status": "Keyence connection status, latest height, serial port, and selected output channel.",
    "#keyence-title": "Keyence status panel.",
    "#keyence-connected": "Whether the bridge currently has the Keyence serial port open.",
    "#keyence-height": "Latest valid Keyence height value known by the bridge.",
    "#keyence-state": "Current Keyence-side state reported by the bridge.",
    "#keyence-port-label": "Keyence serial port setting.",
    "#keyence-port": "Serial port for the Keyence controller or USB-RS232 adapter. Press Enter to apply.",
    "#keyence-keyence_out_no-label": "Keyence output channel setting.",
    "#keyence-keyence_out_no": "Keyence OUT channel used by read commands. Press Enter to apply.",
    "#spc-status": "SPC virtual serial peer status and settings. Python opens this side of the virtual COM pair.",
    "#spc-title": "SPC virtual serial peer status panel.",
    "#spc-connected": "Whether the bridge currently has the SPC virtual serial port open.",
    "#spc-state": "Current SPC-side state reported by the bridge.",
    "#spc-port-label": "SPC virtual serial port setting.",
    "#spc-port": "Python-side SPC virtual COM port. SPC software should open the paired port. Press Enter to apply.",
    "#spc-spc_baudrate-label": "SPC baud-rate setting.",
    "#spc-spc_baudrate": "SPC serial baud rate. Match this to SpiiPlusSmartProcessCommander. Press Enter to apply.",
    "#spc-spc_line_ending-label": "SPC reply line-ending setting.",
    "#spc-spc_line_ending": "Line ending appended to SPC replies, such as CRLF. Press Enter to apply.",
    "#misc-state-panel": "Bridge runtime summary: simulator mode, stream state, serial counts, and current configuration.",
    "#misc-state": "Live bridge counters and settings.",
    "#misc-error": "Most recent bridge error. This turns red when an error is present.",
    "#controls": "Main controls for connection, simulator mode, reads, streaming, and panel visibility.",
    "#close-button": "Close serial connections and exit the bridge UI.",
    "#connect-button": "Apply the current serial settings and connect to Keyence and SPC ports.",
    "#simulator-toggle": "Toggle simulator mode. Simulator mode generates fake Keyence readings without hardware.",
    "#read-once-button": "Request one immediate Keyence height read.",
    "#stream-toggle": "Start or stop Keyence automatic transmission.",
    "#continuous-toggle": "Show or hide the height source and graph panel.",
    "#status-toggle": "Show or hide all status panels.",
    "#spc-coms-toggle": "Show or hide the SPC communications panel.",
    "#keyence-coms-toggle": "Show or hide the Keyence communications panel.",
    "#spc-docs-toggle": "Show or hide the SPC command documentation panel.",
    "#help-footer": "Context help bar. Hover over controls and panels to see what they do.",
    "#spc-docs-panel": "SPC command reference. This is generated from the same registry that handles SPC requests.",
    "#spc-command-docs-scroll": "Accepted SPC commands, aliases, descriptions, and reply formats.",
    "#spc-command-docs": "Accepted SPC commands, aliases, descriptions, and reply formats.",
}


def install_hover_help(root: Widget) -> None:
    for selector, help_text in HELP_ITEMS.items():
        for widget in root.query(selector):
            if isinstance(widget, Widget):
                set_hover_help(widget, help_text)
