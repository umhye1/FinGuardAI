"""Tiny randomly initialized BERT exercises real gradients/serialization, not model quality."""

import json
import shutil
from argparse import Namespace
from pathlib import Path

import pytest

# The normal service test environment need not install research dependencies or download weights.
torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")

from finguard_ai import encoder_experiment as experiment  # noqa: E402

DATA = Path(__file__).parents[1] / "data/benchmarks/context-v1"


def test_real_gradients_checkpoint_reload_and_no_test_access(tmp_path, monkeypatch):
    torch.set_num_threads(1)
    torch.manual_seed(42)
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("[PAD]\n[UNK]\n[CLS]\n[SEP]\n[MASK]\n돈\n사기\n안내\n")
    tokenizer = transformers.BertTokenizerFast(vocab_file=str(vocab), do_lower_case=False)
    config = transformers.BertConfig(
        vocab_size=len(tokenizer),
        hidden_size=16,
        num_hidden_layers=1,
        num_attention_heads=2,
        intermediate_size=32,
        num_labels=3,
        id2label=dict(enumerate(experiment.LABELS)),
        label2id={x: i for i, x in enumerate(experiment.LABELS)},
    )
    model = transformers.BertForSequenceClassification(config)
    initial = model.bert.embeddings.word_embeddings.weight.detach().clone()
    actual_dependencies = experiment.dependencies

    class Models:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            assert kwargs["use_safetensors"] is True
            assert kwargs["trust_remote_code"] is False
            return model

    class Tokenizers:
        @staticmethod
        def from_pretrained(*args, **kwargs):
            return tokenizer

    monkeypatch.setattr(experiment, "dependencies", lambda: (torch, Models, Tokenizers))
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    (data / "test.jsonl").unlink()
    args = Namespace(
        data=data,
        output=tmp_path / "run",
        cache=tmp_path / "cache",
        allow_synthetic=True,
        epochs=1,
        batch_size=4,
        max_length=32,
        learning_rate=2e-5,
        threads=1,
        seed=42,
        download=False,
    )
    result = experiment.train(args)
    assert result["completed"] is True
    assert result["testUsedForSelection"] is False
    assert not torch.equal(initial, model.bert.embeddings.word_embeddings.weight.detach())
    monkeypatch.setattr(experiment, "dependencies", actual_dependencies)
    loaded, saved = experiment.load_encoder(args.output, True)
    assert saved["weightsSha256"] == result["weightsSha256"]
    assert loaded.predict("돈 사기 안내")["decision"] in {"PASS", "FLAG", "ABSTAIN"}
    with pytest.raises(ValueError, match="synthetic"):
        experiment.load_encoder(args.output, False)
    with pytest.raises(ValueError, match="new output"):
        experiment.train(args)
    assert json.loads((args.output / "experiment.json").read_text())["trainRows"] == 36
