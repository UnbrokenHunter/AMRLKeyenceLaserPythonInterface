import time

from src.input.input_client import InputClient
from src.input.simulated_input_client import SimulatedInputClient


print("Hello World")

if __name__ == "__main__":
    client: InputClient = SimulatedInputClient()
    # client: InputClient = KeyenceInputClient(port="COM3")

    client.open()
    try:
        client.initialize()

        for _ in range(10):
            reading = client.read_average(samples=5)
            print(reading)
            time.sleep(0.25)

    finally:
        client.close()
