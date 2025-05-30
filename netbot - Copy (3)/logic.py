import os
import yaml

# Define absolute path for the upload folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def parse_text_file(filename):
    with open(filename, "r") as file:
        lines = file.readlines()
    data = {}
    for line in lines:
        line = line.strip()
        if "TR number:" in line:
            data["tr_number"] = line.split(":")[-1].strip()
        elif "Routers:" in line:
            data["routers"] = line.split(":")[-1].strip().split(",")
        elif "BGP number:" in line:
            data["bgp_number"] = line.split(":")[-1].strip()
        elif "VRF name:" in line:
            data["vrf_name"] = line.split(":")[-1].strip()
        elif "prefix filter name:" in line:
            data["prefix_filter"] = line.split(":")[-1].strip()
        elif "prefix:" in line:
            data["prefix"] = line.split(":")[-1].strip()

    print("Parsed data:", data)
    return data

def generate_yaml(data):
    bgp_map = {
        1: data["bgp_number"],
        2: "171.17.31.46"  # You can customize this logic if more routers exist
    }

    base_yaml = [
        {
            "TR_NUMBER": data["tr_number"],
            "Section": []
        }
    ]

    # Show commands for each router
    for i, router in enumerate(data["routers"], 1):
        base_yaml[0]["Section"].append({
            "device_type": "juniper",
            "list": [router],
            "command": {
                "show_commands": [
                    f"show route receive-protocol bgp {bgp_map[i]} table {data['vrf_name']}.inet.0 hidden | match {data['prefix']}",
                    f"show route receive-protocol bgp {bgp_map[i]} table {data['vrf_name']}.inet.0 | match {data['prefix']}",
                    f"show route advertising-protocol bgp {bgp_map[i]} table {data['vrf_name']}.inet.0 82.150.240.192"
                ]
            }
        })

    # Implementation and reversion commands
    base_yaml[0]["Section"].append({
        "device_type": "juniper",
        "list": data["routers"],
        "command": {
            "implementation": [
                f"set policy-options prefix-list {data['prefix_filter']} {data['prefix']}"
            ],
            "reversion": [
                f"delete policy-options prefix-list {data['prefix_filter']} {data['prefix']}"
            ]
        }
    })

    output_path = os.path.join(UPLOAD_FOLDER, "output.yaml")
    print(f"Saving YAML to {output_path}")
    with open(output_path, "w") as file:
        yaml.dump(base_yaml, file, default_flow_style=False, sort_keys=False, indent=4)

    if not os.path.exists(output_path):
        raise FileNotFoundError(f"YAML file was not created: {output_path}")

    return output_path
