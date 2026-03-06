"""Tests for lib/fingerprint.py"""

import pytest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from lib.fingerprint import compute_fingerprint, save_fingerprint, load_fingerprint, check_collision


@pytest.fixture
def workflow_a():
    """API-format workflow with KSampler + CLIP."""
    return {
        "1": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 12345,
                "steps": 20,
                "cfg": 7.0,
                "model": ["2", 0],
                "positive": ["3", 0],
            },
        },
        "2": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "dreamshaperXL.safetensors"},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "a beautiful sunset", "clip": ["2", 1]},
        },
    }


@pytest.fixture
def workflow_b():
    """Different workflow (different checkpoint)."""
    return {
        "1": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 99999,
                "steps": 30,
                "model": ["2", 0],
                "positive": ["3", 0],
            },
        },
        "2": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "flux_dev.safetensors"},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "a mountain landscape", "clip": ["2", 1]},
        },
    }


class TestComputeFingerprint:
    def test_same_workflow_same_hash(self, workflow_a):
        fp1 = compute_fingerprint(workflow_a)
        fp2 = compute_fingerprint(workflow_a)
        assert fp1 == fp2

    def test_different_seed_same_hash(self, workflow_a):
        fp1 = compute_fingerprint(workflow_a)
        workflow_a["1"]["inputs"]["seed"] = 99999
        fp2 = compute_fingerprint(workflow_a)
        assert fp1 == fp2

    def test_different_prompt_same_hash(self, workflow_a):
        fp1 = compute_fingerprint(workflow_a)
        workflow_a["3"]["inputs"]["text"] = "completely different prompt"
        fp2 = compute_fingerprint(workflow_a)
        assert fp1 == fp2

    def test_different_checkpoint_different_hash(self, workflow_a, workflow_b):
        fp_a = compute_fingerprint(workflow_a)
        fp_b = compute_fingerprint(workflow_b)
        assert fp_a != fp_b

    def test_different_connections_different_hash(self, workflow_a):
        fp1 = compute_fingerprint(workflow_a)
        # Change a connection
        workflow_a["1"]["inputs"]["positive"] = ["3", 1]  # different slot
        fp2 = compute_fingerprint(workflow_a)
        assert fp1 != fp2


class TestCollisionDetection:
    def test_first_run_saves_and_allows(self, workflow_a, tmp_path):
        fp = compute_fingerprint(workflow_a)
        result = check_collision(fp, str(tmp_path), "my_project")
        assert result is None  # No collision
        assert load_fingerprint(str(tmp_path), "my_project") is not None

    def test_same_workflow_allows(self, workflow_a, tmp_path):
        fp = compute_fingerprint(workflow_a)
        check_collision(fp, str(tmp_path), "my_project")
        result = check_collision(fp, str(tmp_path), "my_project")
        assert result is None

    def test_different_workflow_blocks(self, workflow_a, workflow_b, tmp_path):
        fp_a = compute_fingerprint(workflow_a)
        fp_b = compute_fingerprint(workflow_b)
        check_collision(fp_a, str(tmp_path), "my_project")
        result = check_collision(fp_b, str(tmp_path), "my_project")
        assert result is not None
        assert "BLOCKED" in result
        assert "my_project" in result
        assert "Options:" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
