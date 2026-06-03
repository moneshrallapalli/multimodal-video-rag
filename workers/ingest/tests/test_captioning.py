"""Frame captioner tests with a fake Bedrock client."""

from __future__ import annotations

from pathlib import Path

from ingest.captioning import FrameCaptioner


class FakeBedrockRuntime:
    def __init__(self, text: str = "A person standing at a whiteboard.") -> None:
        self.calls: list[dict] = []
        self.text = text

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "output": {
                "message": {
                    "content": [{"text": self.text}]
                }
            }
        }


def test_caption_returns_generated_text(tmp_path: Path):
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")
    client = FakeBedrockRuntime()
    captioner = FrameCaptioner(client=client, model_id="test-model")

    result = captioner.caption(image)

    assert result == "A person standing at a whiteboard."
    assert len(client.calls) == 1
    assert client.calls[0]["modelId"] == "test-model"


def test_caption_frames_handles_errors_gracefully(tmp_path: Path):
    good = tmp_path / "good.jpg"
    good.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")

    class FailOnSecond:
        def __init__(self):
            self.count = 0

        def converse(self, **kwargs):
            self.count += 1
            if self.count == 2:
                raise RuntimeError("throttled")
            return {
                "output": {
                    "message": {
                        "content": [{"text": "Good caption."}]
                    }
                }
            }

    captioner = FrameCaptioner(client=FailOnSecond(), model_id="test-model")
    results = captioner.caption_frames([good, bad])

    assert results[0] == "Good caption."
    assert "bad" in results[1]
