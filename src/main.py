from __future__ import annotations

from src.bridge.bridge_controller import BridgeController, BridgeConfig
from src.display.terminal_app import BridgeTuiApp


if __name__ == "__main__":
    config = BridgeConfig(
        keyence_port="COM5",
        spc_port="COM21",
        average_samples=5,
        keyence_out_no=1,
    )

    controller = BridgeController(config=config)

    BridgeTuiApp(controller=controller).run()
