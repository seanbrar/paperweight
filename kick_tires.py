import os
import subprocess


def run_command(command):
    print(f"Running command: {command}")
    try:
        # Use subprocess.run to execute command
        # split command string into args list
        args = command.split()
        result = subprocess.run(args, capture_output=True, text=True)
        print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return result
    except Exception as e:
        print(f"Error running command '{command}': {e}")
        return None

def check_import():
    print("\n--- Checking Import ---")
    try:
        import paperweight
        print(f"Successfully imported paperweight. File: {paperweight.__file__}")
        print("Dir(paperweight):", dir(paperweight))
    except ImportError as e:
        print(f"Failed to import paperweight: {e}")
    except Exception as e:
        print(f"Error during import check: {e}")

def main():
    print("--- Kicking the Tires of paperweight ---")

    # 1. Check if installed
    check_import()

    # 2. Run CLI help
    print("\n--- CLI Help ---")
    run_command("paperweight --help")

    # 3. Init
    print("\n--- Init ---")
    if os.path.exists("config.yaml"):
        print("config.yaml already exists. Backing it up to config.yaml.bak")
        os.rename("config.yaml", "config.yaml.bak")

    run_command("paperweight init")

    if os.path.exists("config.yaml"):
        print("config.yaml created successfully.")
    else:
        print("config.yaml was NOT created.")

    # 4. Doctor
    print("\n--- Doctor ---")
    run_command("paperweight doctor")

    # 5. Run (Dry run or real run?)
    print("\n--- Run ---")
    # README says: paperweight run --force-refresh
    run_command("paperweight run --force-refresh")

if __name__ == "__main__":
    main()
