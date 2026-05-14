from __future__ import annotations

from src.bridge.bridge_controller import BridgeController, BridgeConfig
from src.input.input_client import InputClient
from src.input.simulated_input_client import SimulatedInputClient
# from src.input.keyence_input_client import KeyenceInputClient
from src.display.terminal_app import BridgeTuiApp


def build_input_client(use_simulator: bool, keyence_port: str) -> InputClient:
    if use_simulator:
        return SimulatedInputClient()

    # Uncomment when real hardware is ready:
    # return KeyenceInputClient(port=keyence_port)
    raise RuntimeError("Real Keyence client is not enabled yet.")


if __name__ == "__main__":
    config = BridgeConfig(
        use_simulator=True,
        keyence_port="COM3",
        spc_port="COM9",
        average_samples=5,
    )

    input_client = build_input_client(
        use_simulator=config.use_simulator,
        keyence_port=config.keyence_port,
    )

    controller = BridgeController(
        config=config,
        input_client=input_client,
    )

    BridgeTuiApp(controller=controller).run()

if __name__ == "__main__":
    from src.input.simulated_input_client import SimulatedInputClient

    config = BridgeConfig(use_simulator=True, keyence_port="COM3", spc_port="COM9")
    client: InputClient = SimulatedInputClient()
    controller = BridgeController(config=config, input_client=client)
    BridgeTuiApp(controller=controller).run()
