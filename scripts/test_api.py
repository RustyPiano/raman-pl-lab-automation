#!/usr/bin/env python3
"""Test script for FastAPI backend."""
import json
import time
import requests

BASE_URL = "http://127.0.0.1:8008"


def test_health():
    """Test health check endpoint."""
    print("=" * 60)
    print("Testing Health Check")
    print("=" * 60)

    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("✓ Health check passed\n")


def test_api_health():
    """Test API health check endpoint."""
    print("=" * 60)
    print("Testing API Health Check")
    print("=" * 60)

    response = requests.get(f"{BASE_URL}/api/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    print("✓ API health check passed\n")


def test_list_configs():
    """Test listing configuration files."""
    print("=" * 60)
    print("Testing List Configs")
    print("=" * 60)

    response = requests.get(f"{BASE_URL}/api/configs?config_dir=configs")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Found {len(data.get('configs', []))} config files:")
        for config in data.get('configs', [])[:5]:
            print(f"  - {config}")
        print("✓ List configs passed\n")
    else:
        print(f"Response: {response.text}")
        print("⚠ List configs failed (may be expected if configs/ doesn't exist)\n")


def test_single_point_simulated():
    """Test single-point measurement in simulated mode."""
    print("=" * 60)
    print("Testing Single-Point Measurement (Simulated)")
    print("=" * 60)

    # Start job
    payload = {
        "config_path": "configs/single_point_532nm.yaml",
        "mode": "simulated"
    }

    print(f"Submitting job: {json.dumps(payload, indent=2)}")
    response = requests.post(f"{BASE_URL}/api/workflow/single-point", json=payload)
    print(f"Status: {response.status_code}")

    if response.status_code != 200:
        print(f"Response: {response.text}")
        print("⚠ Single-point submission failed (config file may not exist)\n")
        return None

    job = response.json()
    job_id = job['id']
    print(f"Job created: {job_id}")
    print(f"Initial status: {job['status']}\n")

    # Poll job status
    print("Polling job status...")
    for i in range(10):
        response = requests.get(f"{BASE_URL}/api/workflow/jobs/{job_id}")
        if response.status_code == 200:
            job = response.json()
            status = job['status']
            progress = job.get('progress', {})
            print(f"  [{i+1}] Status: {status}, Progress: {progress.get('percentage', 0):.1f}%")

            if status in ('completed', 'failed', 'stopped'):
                break
        time.sleep(1)

    # Final status
    response = requests.get(f"{BASE_URL}/api/workflow/jobs/{job_id}")
    if response.status_code == 200:
        job = response.json()
        print(f"\nFinal status: {job['status']}")
        if job.get('result'):
            print(f"Result: {json.dumps(job['result'], indent=2)}")
        if job.get('error'):
            print(f"Error: {job['error']}")

        if job['status'] == 'completed':
            print("✓ Single-point measurement completed\n")
        else:
            print(f"⚠ Job ended with status: {job['status']}\n")

    return job_id


def test_list_jobs():
    """Test listing all jobs."""
    print("=" * 60)
    print("Testing List Jobs")
    print("=" * 60)

    response = requests.get(f"{BASE_URL}/api/workflow/jobs")
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        jobs = response.json()
        print(f"Found {len(jobs)} jobs:")
        for job in jobs[-3:]:  # Show last 3
            print(f"  - {job['id']}: {job['type']} ({job['status']})")
        print("✓ List jobs passed\n")
    else:
        print(f"Response: {response.text}\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("FastAPI Backend Test Suite")
    print("=" * 60 + "\n")

    try:
        # Basic tests
        test_health()
        test_api_health()
        test_list_configs()
        test_list_jobs()

        # Workflow test (may fail if config doesn't exist)
        test_single_point_simulated()

        print("=" * 60)
        print("All tests completed!")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Cannot connect to server at", BASE_URL)
        print("Make sure the server is running:")
        print("  ./start_api.sh")
        print("\nor:")
        print("  PYTHONPATH=src uvicorn lab_auto.api.main:app --port 8008")
        return 1
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
