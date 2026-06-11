"""Bedrock answer generation tests."""

from __future__ import annotations

from graph.answering import BedrockAnswerGenerator, _parse_answer


class FakeBedrockRuntime:
    def __init__(
        self,
        text: str = (
            '{"answer": "The evidence points to self-sabotage around 1:15.", "grounded": true}'
        ),
    ) -> None:
        self.text = text
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return {"output": {"message": {"content": [{"text": self.text}]}}}


def test_bedrock_answer_generator_uses_converse_with_grounding_prompt():
    client = FakeBedrockRuntime()
    generator = BedrockAnswerGenerator(client=client, model_id="model-id")

    generated = generator.generate(query="Where?", context="[1] context")

    assert generated.text == "The evidence points to self-sabotage around 1:15."
    assert generated.grounded is True
    assert client.calls[0]["modelId"] == "model-id"
    prompt = client.calls[0]["messages"][0]["content"][0]["text"]
    assert "Use only the evidence" in prompt
    assert '"grounded"' in prompt
    # Anti-over-refusal rules must reach every intent, not just visual: eval
    # showed hybrid/timestamp questions about visual content refuse too.
    assert "Partial evidence is still evidence" in prompt
    assert "cites context timestamps" in prompt
    assert "visual_caption" in prompt
    assert "QUESTION:\nWhere?" in prompt
    assert "CONTEXT:\n[1] context" in prompt
    assert client.calls[0]["inferenceConfig"]["temperature"] == 0.1


def test_bedrock_answer_generator_propagates_ungrounded_flag():
    client = FakeBedrockRuntime(
        text='{"answer": "The indexed videos do not cover that.", "grounded": false}'
    )
    generator = BedrockAnswerGenerator(client=client, model_id="model-id")

    generated = generator.generate(query="Off-domain?", context="[1] unrelated")

    assert generated.grounded is False
    assert "do not cover" in generated.text


def test_bedrock_hyde_generates_hypothetical_passage():
    client = FakeBedrockRuntime(text="The evidence points to self-sabotage around 1:15.")
    generator = BedrockAnswerGenerator(client=client, model_id="model-id")

    passage = generator.rewrite_query(query="why stuck?")

    assert passage == "The evidence points to self-sabotage around 1:15."
    assert client.calls[0]["modelId"] == "model-id"
    prompt = client.calls[0]["messages"][0]["content"][0]["text"]
    assert "write a short passage" in prompt
    assert "QUERY:\nwhy stuck?" in prompt
    assert client.calls[0]["inferenceConfig"] == {"maxTokens": 150, "temperature": 0.3}


def test_parse_answer_tolerates_code_fences():
    generated = _parse_answer('```json\n{"answer": "Around 2:10.", "grounded": true}\n```')
    assert generated == ("Around 2:10.", True)


def test_parse_answer_tolerates_prose_around_json():
    generated = _parse_answer(
        'Here is the result: {"answer": "Around 2:10.", "grounded": false} Hope that helps.'
    )
    assert generated == ("Around 2:10.", False)


def test_parse_answer_falls_back_to_grounded_plain_text():
    """If the model ignores the JSON instruction, the raw text is treated as a
    grounded answer (logged for observability) rather than dropped."""
    generated = _parse_answer("The speaker covers this around 1:15.")
    assert generated.text == "The speaker covers this around 1:15."
    assert generated.grounded is True


def test_parse_answer_falls_back_when_answer_field_empty():
    generated = _parse_answer('{"answer": "", "grounded": false}')
    assert generated.grounded is True  # malformed payload → conservative fallback
