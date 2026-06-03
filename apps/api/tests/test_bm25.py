"""Tests for the pure-Python BM25 sparse encoder."""

from __future__ import annotations

from shared.bm25 import BM25Encoder, _hash_index, _tokens


def test_fit_handles_empty_corpus_gracefully():
    encoder = BM25Encoder.fit([])
    assert encoder.n_docs == 0
    assert encoder.encode_document("any text")["indices"] == []
    assert encoder.encode_query("any text")["indices"] == []


def test_document_encoding_emits_per_term_weights():
    docs = [
        "she explains self sabotage and fear of failure in detail",
        "the speaker discusses comfort zone and motivation",
        "small steps overcome paralysis and self doubt",
    ]
    encoder = BM25Encoder.fit(docs)

    encoded = encoder.encode_document(docs[0])
    assert encoded["indices"] and encoded["values"]
    # Every weight is a finite positive float.
    assert all(value > 0 for value in encoded["values"])  # type: ignore[operator]
    # The encoded sparse vector should have one index per unique content token.
    unique_tokens = {token for token in _tokens(docs[0])}
    assert len(encoded["indices"]) == len(unique_tokens)


def test_query_encoding_uses_idf_so_rare_terms_dominate():
    """Rare query terms must outweigh common ones — that's the whole point of idf."""
    docs = [
        "the common common word appears often everywhere",
        "the common common word again",
        "the common common word and again again",
    ]
    docs.append("anchoring is a rare salary-negotiation tactic")
    encoder = BM25Encoder.fit(docs)

    query = encoder.encode_query("common anchoring")
    pairs = dict(zip(query["indices"], query["values"], strict=True))
    common_idx = _hash_index("common")
    rare_idx = _hash_index("anchoring")
    assert rare_idx in pairs
    # The rare term ("anchoring" appears in 1/4 docs) must outweigh the common one
    # ("common" appears in 3/4 docs).
    if common_idx in pairs:
        assert pairs[rare_idx] > pairs[common_idx]


def test_roundtrip_via_to_dict_preserves_encoding():
    docs = ["alpha beta gamma", "beta gamma delta", "gamma delta epsilon"]
    encoder = BM25Encoder.fit(docs)

    restored = BM25Encoder.from_dict(encoder.to_dict())

    a = encoder.encode_document("alpha beta")
    b = restored.encode_document("alpha beta")
    assert a["indices"] == b["indices"]
    assert a["values"] == b["values"]


def test_stopwords_and_short_tokens_are_ignored():
    encoder = BM25Encoder.fit(["the speaker explains a key idea about fear"])
    encoded = encoder.encode_document("the speaker a is on of")
    # "the", "a", "is", "on", "of" are stopwords; everything else is <=2 chars,
    # except "speaker" which should survive.
    assert _hash_index("speaker") in encoded["indices"]
    assert _hash_index("the") not in encoded["indices"]
    assert _hash_index("a") not in encoded["indices"]
