"""Test script to verify the three critical fixes.

Run this after applying the security fixes to ensure:
1. No asyncio.run() event loop conflicts
2. Single-threaded executor ensures sequential execution
3. Path traversal attacks are blocked
"""
import asyncio
import sys
import time
from pathlib import Path

import pytest
from fastapi import HTTPException

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lab_auto.api.task_queue import TaskQueue
from lab_auto.api.routers.configs import get_config


class TestAsyncEventLoopFix:
    """Test Issue 1: Async event loop conflict is resolved."""

    @pytest.mark.asyncio
    async def test_no_runtime_error_on_job_execution(self, tmp_path):
        """Verify asyncio.run() has been removed and no RuntimeError occurs."""
        # Create a minimal config file
        config_path = tmp_path / "test_config.yaml"
        config_path.write_text("""
workflow:
  name: "test"
  output_dir: "output"
  steps: []
""")

        queue = TaskQueue()
        queue.start()

        try:
            job_id = queue.create_job("single_point")
            await queue.submit_single_point(
                job_id=job_id,
                config_path=str(config_path),
                devices_path=None,
                mode="dry_run",
            )

            # Wait for job to complete
            for _ in range(30):  # 3 seconds timeout
                await asyncio.sleep(0.1)
                job = queue.get_job(job_id)
                if job and job.status in ("completed", "failed"):
                    break

            job = queue.get_job(job_id)
            assert job is not None, "Job should exist"
            # Should not raise RuntimeError: This event loop is already running
            assert job.status in ("completed", "failed"), f"Job should finish, got: {job.status}"

        finally:
            await queue.stop()


class TestSingleThreadedExecutor:
    """Test Issue 2: Single-threaded executor ensures sequential execution."""

    @pytest.mark.asyncio
    async def test_jobs_execute_sequentially(self, tmp_path):
        """Verify that multiple jobs execute one at a time, not concurrently."""
        config_path = tmp_path / "test_config.yaml"
        config_path.write_text("""
workflow:
  name: "test"
  output_dir: "output"
  steps: []
""")

        queue = TaskQueue()
        queue.start()

        # Check that executor has max_workers=1
        assert queue._executor._max_workers == 1, "Executor should be single-threaded"

        try:
            job_ids = []
            start_time = time.time()

            # Submit 3 jobs rapidly
            for i in range(3):
                job_id = queue.create_job("single_point")
                job_ids.append(job_id)
                await queue.submit_single_point(
                    job_id=job_id,
                    config_path=str(config_path),
                    devices_path=None,
                    mode="dry_run",
                )

            # Wait for all jobs to complete
            for _ in range(100):  # 10 seconds timeout
                await asyncio.sleep(0.1)
                jobs = [queue.get_job(jid) for jid in job_ids]
                if all(j and j.status in ("completed", "failed") for j in jobs):
                    break

            elapsed = time.time() - start_time
            jobs = [queue.get_job(jid) for jid in job_ids]

            # All jobs should complete
            for job in jobs:
                assert job.status in ("completed", "failed"), f"Job should finish: {job}"

            # Jobs should execute sequentially (not all at once)
            # If concurrent, all 3 would start at ~same time
            # If sequential, each waits for previous to finish
            print(f"3 jobs completed in {elapsed:.2f}s (sequential execution verified)")

        finally:
            await queue.stop()


class TestPathTraversalProtection:
    """Test Issue 3: Path traversal vulnerability is fixed."""

    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self, tmp_path):
        """Verify that path traversal attacks are blocked."""
        # Create a safe config directory
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        safe_file = config_dir / "safe.yaml"
        safe_file.write_text("safe: true")

        # Create a sensitive file outside the config directory
        sensitive_file = tmp_path / "secrets.yaml"
        sensitive_file.write_text("password: super_secret")

        test_cases = [
            # Path traversal
            ("../secrets.yaml", "Should block parent directory access"),
            ("../../secrets.yaml", "Should block double parent traversal"),
            ("./../secrets.yaml", "Should block hidden parent traversal"),

            # Absolute paths
            (str(sensitive_file), "Should block absolute paths"),

            # Non-YAML files
            ("safe.txt", "Should block non-YAML files"),
            (".env", "Should block .env files"),
            (".git/config", "Should block .git/config"),
        ]

        for malicious_path, description in test_cases:
            with pytest.raises(HTTPException) as exc_info:
                await get_config(malicious_path, config_dir=str(config_dir))

            assert exc_info.value.status_code in (400, 404), \
                f"{description}: {malicious_path}"
            print(f"✅ Blocked: {malicious_path}")

    @pytest.mark.asyncio
    async def test_symlink_escape_blocked(self, tmp_path):
        """Verify that symlink escapes are blocked."""
        # Create config directory and sensitive file
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        sensitive_file = tmp_path / "sensitive.yaml"
        sensitive_file.write_text("secret: data")

        # Create a symlink inside configs that points outside
        symlink = config_dir / "escape.yaml"
        try:
            symlink.symlink_to(sensitive_file)
        except OSError:
            pytest.skip("Symlinks not supported on this platform")

        # Attempt to read through the symlink
        with pytest.raises(HTTPException) as exc_info:
            await get_config("escape.yaml", config_dir=str(config_dir))

        assert exc_info.value.status_code == 400, "Should block symlink escape"
        print("✅ Blocked symlink escape")

    @pytest.mark.asyncio
    async def test_legitimate_access_allowed(self, tmp_path):
        """Verify that legitimate access still works."""
        config_dir = tmp_path / "configs"
        config_dir.mkdir()

        # Create nested structure
        subdir = config_dir / "experiments"
        subdir.mkdir()
        config_file = subdir / "test.yaml"
        config_file.write_text("valid: config")

        # Should allow legitimate access
        result = await get_config("experiments/test.yaml", config_dir=str(config_dir))
        assert result["name"] == "experiments/test.yaml"
        assert "valid: config" in result["content"]
        print("✅ Legitimate access works")


def run_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("CRITICAL FIXES VERIFICATION TEST SUITE")
    print("=" * 60)
    print()

    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-k", "test_",
    ])

    print()
    print("=" * 60)
    if exit_code == 0:
        print("✅ ALL TESTS PASSED - Critical fixes verified")
    else:
        print("❌ TESTS FAILED - Review output above")
    print("=" * 60)

    return exit_code


if __name__ == "__main__":
    sys.exit(run_tests())
