"""Machine and path configuration for the ingestion pipeline."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

MACHINES = {
    "d11t-dozer": {
        "id": "d11t-dozer",
        "name": "D11T Dozer",
        "manufacturer": "caterpillar",
        "source_dir": PROJECT_ROOT / "D11T-Dozer",
        "manual_type_map": {
            "System Operations": "system-operation",
            "Testing & Adjusting": "testing-and-adjusting",
            "Troubleshooting": "troubleshooting",
        },
    },
    "785d-dump-truck": {
        "id": "785d-dump-truck",
        "name": "785D Dump Truck",
        "manufacturer": "caterpillar",
        "source_dir": PROJECT_ROOT / "785D-Dump-Truck",
        "manual_type_map": {
            "Systems Operation": "system-operation",
            "Testing and Adjusting": "testing-and-adjusting",
            "Troubleshooting": "troubleshooting",
        },
    },
    "ex3600-7-excavator": {
        "id": "ex3600-7-excavator",
        "name": "EX3600-7 Hitachi Excavator",
        "manufacturer": "hitachi",
        "source_dir": PROJECT_ROOT / "EX3600-7-Hitachi-Excavator",
        "manual_type_map": {
            "Systems Operations.pdf": "system-operation",
            "Troubleshooting.pdf": "troubleshooting",
            "Fault codes.pdf": "fault-codes",
        },
    },
}
