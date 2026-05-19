from src.input.keyence_input_client import KeyenceInputClient

client = KeyenceInputClient(port="COM5")
client.open()

try:
    print("R0 ->", client.send_command("R0"))

    for out_no in range(1, 9):
        command = f"MS,3,{out_no}"
        response = client.send_command(command)
        print(f"OUT{out_no}: {response}")

finally:
    client.close()