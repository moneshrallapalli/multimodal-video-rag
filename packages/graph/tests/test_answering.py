"""Bedrock answer generation tests."""

from __future__ import annotations

from graph.answering import BedrockAnswerGenerator


class FakeBedrockRuntime:
    def __init__(self) -> None:
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "output": {
                "message": {
                    "content": [{"text": "The evidence points to self-sabotage around 1:15."}]
                }
            }
        }


def test_bedrock_answer_generator_uses_converse_with_grounding_prompt():
    client = FakeBedrockRuntime()
    generator = BedrockAnswerGenerator(client=client, model_id="model-id")

    answer = generator.generate(query="Where?", context="[1] context")

    assert answer == "The evidence points to self-sabotage around 1:15."
    assert client.calls[0]["modelId"] == "model-id"
    prompt = client.calls[0]["messages"][0]["content"][0]["text"]
    assert "Use only the evidence" in prompt
    assert "QUESTION:\nWhere?" in prompt
    assert "CONTEXT:\n[1] context" in prompt
    assert client.calls[0]["inferenceConfig"]["temperature"] == 0.1


def test_bedrock_answer_generator_rewrites_query_with_converse():
    client = FakeBedrockRuntime()
    generator = BedrockAnswerGenerator(client=client, model_id="model-id")

    rewrite = generator.rewrite_query(query="why stuck?")

    assert rewrite == "The evidence points to self-sabotage around 1:15."
    assert client.calls[0]["modelId"] == "model-id"
    prompt = client.calls[0]["messages"][0]["content"][0]["text"]
    assert "Rewrite this video search query" in prompt
    assert "Return only the rewritten query." in prompt
    assert "QUERY:\nwhy stuck?" in prompt
    assert client.calls[0]["inferenceConfig"] == {"maxTokens": 80, "temperature": 0.0}
