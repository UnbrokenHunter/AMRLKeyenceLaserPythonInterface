from __future__ import annotations

from src.bridge.bridge_controller import BridgeController, BridgeConfig
from src.input.input_client import InputClient
from src.input.simulated_input_client import SimulatedInputClient
from src.input.keyence_input_client import KeyenceInputClient
from src.display.terminal_app import BridgeTuiApp


if __name__ == "__main__":
    config = BridgeConfig(
        use_simulator=True,
        keyence_port="COM3",
        spc_port="COM9",
        average_samples=5,
    )

    controller = BridgeController(config=config)

    BridgeTuiApp(controller=controller).run()