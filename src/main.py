from __future__ import annotations

from src.bridge.bridge_controller import BridgeController, BridgeConfig
from src.display.terminal_app import BridgeTuiApp


if __name__ == "__main__":
    config = BridgeConfig(
        use_simulator=False,
        keyence_port="COM5",
        spc_port="COM9",
        average_samples=5,
        keyence_out_no=2,
        simulated_base_height_mm=15.0,
        simulated_noise_std_mm=0.005,

    )

    controller = BridgeController(config=config)

    BridgeTuiApp(controller=controller).run()