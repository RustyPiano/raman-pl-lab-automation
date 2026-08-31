#!/usr/bin/env python3
"""Simple demo script for the FastAPI backend."""
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "http://127.0.0.1:8008"


def request_json(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    try:
        response = urlopen(request, timeout=10)
    except HTTPError as exc:
        response = exc
    with response:
        return response.getcode(), json.loads(response.read())


def main():
    print("=" * 70)
    print("Raman/PL Lab Automation - FastAPI Backend Demo")
    print("=" * 70)

    # 1. Health check
    print("\n1. Health Check")
    print("-" * 70)
    _, body = request_json("/health")
    print(f"✓ Server is healthy: {body}")

    # 2. List available configs
    print("\n2. List Available Configurations")
    print("-" * 70)
    _, body = request_json("/api/configs")
    configs = body['configs']
    print(f"Found {len(configs)} configuration files:")
    for config in configs[:5]:
        print(f"  • {config}")

    # 3. Submit a single-point measurement (simulated mode)
    print("\n3. Submit Single-Point Measurement (Simulated Mode)")
    print("-" * 70)
    payload = {
        "config_path": "single_point.example.yaml",
        "mode": "simulated"
    }
    print(f"Request: {json.dumps(payload, indent=2)}")

    _, job = request_json("/api/workflow/single-point", payload)
    job_id = job['id']
    print(f"✓ Job created: {job_id}")
    print(f"  Status: {job['status']}")

    # 4. Poll job status
    print("\n4. Poll Job Status")
    print("-" * 70)
    for i in range(10):
        _, job = request_json(f"/api/workflow/jobs/{job_id}")
        status = job['status']
        progress = job.get('progress', {})
        percentage = progress.get('percentage', 0)

        print(f"  [{i+1}] Status: {status:12s} Progress: {percentage or 0:5.1f}%", end="")

        if job.get('result'):
            print(f" → Output: {job['result'].get('output_directory')}")
        else:
            print()

        if status in ('completed', 'failed', 'stopped'):
            break

        time.sleep(0.5)

    # 5. Final result
    print("\n5. Final Result")
    print("-" * 70)
    _, job = request_json(f"/api/workflow/jobs/{job_id}")

    if job['status'] == 'completed':
        print("✓ Measurement completed successfully!")
        print(f"  Output directory: {job['result']['output_directory']}")
        print(f"  Execution mode: {job['result']['mode']}")
        print(f"  Started at: {job['started_at']}")
        print(f"  Completed at: {job['completed_at']}")
    else:
        print(f"✗ Job ended with status: {job['status']}")
        if job.get('error'):
            print(f"  Error: {job['error']}")

    print("\n" + "=" * 70)
    print("Demo completed!")
    print("=" * 70)
    print("\nNext steps:")
    print("  • View API docs: http://127.0.0.1:8008/docs")
    print("  • Connect via WebSocket for real-time updates")
    print("  • Try real hardware mode with actual devices")
    print()


if __name__ == "__main__":
    try:
        main()
    except URLError:
        print("\n❌ Error: Cannot connect to server")
        print("Start the server first:")
        print("  ./scripts/start_api.sh")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
