"""Optional local BERT fine-tuning. No paid APIs; no automatic serving promotion."""

import argparse
import json
import math
import platform
import random
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score

from finguard_ai.benchmark_data import LABELS, digest, load_splits
from finguard_ai.context_benchmark import dev_cost, measure
from finguard_ai.encoder_data import load_registered, reference_hashes, register
from finguard_ai.privacy import mask

MODEL = "klue/bert-base"
REVISION = "77c8b3d707df785034b4e50f2da5d37be5f0f546"


def dependencies():
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as e:
        raise RuntimeError(
            "Install optional training environment: pip install -r requirements-encoder.txt"
        ) from e
    return torch, AutoModelForSequenceClassification, AutoTokenizer


def prediction(scores, threshold):
    scores = np.asarray(scores, dtype=float)
    if (
        scores.shape != (3,)
        or not np.isfinite(scores).all()
        or np.any(scores < 0)
        or not np.isclose(scores.sum(), 1)
        or not 1 / 3 <= threshold <= 1
    ):
        raise ValueError("Invalid probabilities or threshold")
    label = LABELS[int(scores.argmax())]
    return {
        "label": label,
        "decision": "ABSTAIN" if scores.max() < threshold else "FLAG" if label == "PHISHING" else "PASS",
        "probabilities": dict(zip(LABELS, map(float, scores))),
    }


def select_threshold(rows, probabilities):
    if len(rows) != len(probabilities) or not rows:
        raise ValueError("Nonempty aligned dev rows required")
    trials = [
        {"threshold": t, "devCost": dev_cost(rows, [prediction(p, t) for p in probabilities])}
        for t in (0.4, 0.5, 0.6, 0.7)
    ]
    selected = min(trials, key=lambda r: (r["devCost"], r["threshold"]))
    return selected["threshold"], trials


class Encoder:
    def __init__(self, model, tokenizer, max_length=128):
        self.model, self.tokenizer, self.max_length = model, tokenizer, max_length
        self.threshold = 0.5

    def probabilities(self, texts):
        torch, _, _ = dependencies()
        self.model.eval()
        batch = self.tokenizer(
            [mask(t) for t in texts],
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        with torch.no_grad():
            return torch.softmax(self.model(**batch).logits, dim=-1).cpu().numpy()

    def predict(self, text):
        return prediction(self.probabilities([text])[0], self.threshold)

    def truncation_count(self, rows):
        return sum(
            len(self.tokenizer(mask(r["text"]), truncation=False)["input_ids"]) > self.max_length
            for r in rows
        )


def train(args):
    if not (
        1 <= args.epochs <= 5
        and 1 <= args.batch_size <= 16
        and 16 <= args.max_length <= 512
        and math.isfinite(args.learning_rate)
        and 0 < args.learning_rate <= 0.001
        and 1 <= args.threads <= 8
    ):
        raise ValueError("Invalid bounded training configuration")
    output = Path(args.output)
    if output.exists():
        raise ValueError("Use a new output directory; experiments must not overwrite previous runs")
    # Deliberately do not open test.jsonl here, even for validation or model selection.
    splits, manifest = load_splits(args.data, split_names=("train", "dev"))
    rows, dev = splits["train"], splits["dev"]
    synthetic = any(r["sourceType"] == "synthetic" for r in rows + dev)
    if synthetic and not args.allow_synthetic:
        raise ValueError("Synthetic experiments require --allow-synthetic")
    if len(rows) > 10000 or len(dev) > 2000:
        raise ValueError("Dataset exceeds bounded local experiment limits")
    torch, auto_model, auto_tokenizer = dependencies()
    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.use_deterministic_algorithms(True)
    tokenizer = auto_tokenizer.from_pretrained(
        MODEL,
        revision=REVISION,
        trust_remote_code=False,
        cache_dir=args.cache,
        local_files_only=not args.download,
    )
    model = auto_model.from_pretrained(
        MODEL,
        revision=REVISION,
        trust_remote_code=False,
        cache_dir=args.cache,
        local_files_only=not args.download,
        use_safetensors=True,
        num_labels=3,
        id2label=dict(enumerate(LABELS)),
        label2id={x: i for i, x in enumerate(LABELS)},
    )
    encoder = Encoder(model, tokenizer, args.max_length)
    output.mkdir(parents=True)
    config = {
        "model": MODEL,
        "revision": REVISION,
        "license": "cc-by-sa-4.0",
        "seed": args.seed,
        "epochs": args.epochs,
        "batchSize": args.batch_size,
        "maxLength": args.max_length,
        "learningRate": args.learning_rate,
        "threads": args.threads,
        "device": "cpu",
        "python": platform.python_version(),
        "torch": torch.__version__,
        "synthetic": synthetic,
        "benchmark": manifest,
        "referenceHashes": reference_hashes(rows + dev),
        "trainRows": len(rows),
        "devRows": len(dev),
        "testUsedForSelection": False,
        "paidCalls": 0,
        "parameterCount": sum(p.numel() for p in model.parameters()),
        "trainableParameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
        "truncatedTrain": encoder.truncation_count(rows),
        "truncatedDev": encoder.truncation_count(dev),
    }
    # Written before training; failed runs retain their settings, without claiming completion.
    (output / "run-config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01)
    encoded = tokenizer(
        [mask(r["text"]) for r in rows],
        padding=True,
        truncation=True,
        max_length=args.max_length,
        return_tensors="pt",
    )
    targets = torch.tensor([LABELS.index(r["label"]) for r in rows])
    history, best, selected = [], None, None
    started = time.perf_counter()
    for epoch in range(1, args.epochs + 1):
        model.train()
        order = torch.randperm(len(rows))
        total_loss = 0
        for offset in range(0, len(rows), args.batch_size):
            ids = order[offset : offset + args.batch_size]
            optimizer.zero_grad(set_to_none=True)
            result = model(**{k: v[ids] for k, v in encoded.items()}, labels=targets[ids])
            if not torch.isfinite(result.loss):
                raise ValueError("Non-finite training loss")
            result.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += float(result.loss.detach()) * len(ids)
        probabilities = np.concatenate(
            [
                encoder.probabilities([r["text"] for r in dev[i : i + args.batch_size]])
                for i in range(0, len(dev), args.batch_size)
            ]
        )
        threshold, trials = select_threshold(dev, probabilities)
        preds = [prediction(p, threshold) for p in probabilities]
        f1 = f1_score(
            [r["label"] for r in dev],
            [p["label"] for p in preds],
            labels=list(LABELS),
            average="macro",
            zero_division=0,
        )
        cost = dev_cost(dev, preds)
        row = {
            "epoch": epoch,
            "trainLoss": total_loss / len(rows),
            "devMacroF1": float(f1),
            "devCost": cost,
            "threshold": threshold,
            "thresholdTrials": trials,
        }
        history.append(row)
        key = (cost, -f1, epoch)
        if best is None or key < best:
            best, selected = key, row
            model.save_pretrained(output / "model", safe_serialization=True)
            tokenizer.save_pretrained(output / "model")
        print(json.dumps(row), flush=True)
    config.update(
        history=history,
        selected=selected,
        trainingSeconds=time.perf_counter() - started,
        completed=True,
        weightsSha256=digest(output / "model/model.safetensors"),
    )
    (output / "experiment.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    return config


def load_encoder(directory, allow_synthetic):
    torch, auto_model, auto_tokenizer = dependencies()
    root = Path(directory)
    config = json.loads((root / "experiment.json").read_text())
    if not config.get("completed") or (config["synthetic"] and not allow_synthetic):
        raise ValueError("Incomplete or unapproved synthetic model")
    if digest(root / "model/model.safetensors") != config["weightsSha256"]:
        raise ValueError("Model weights changed")
    torch.set_num_threads(config["threads"])
    model = auto_model.from_pretrained(
        root / "model", local_files_only=True, trust_remote_code=False, use_safetensors=True
    )
    if [model.config.id2label[i] for i in range(3)] != list(LABELS):
        raise ValueError("Unexpected model label mapping")
    encoder = Encoder(
        model,
        auto_tokenizer.from_pretrained(root / "model", local_files_only=True, trust_remote_code=False),
        config["maxLength"],
    )
    encoder.threshold = config["selected"]["threshold"]
    return encoder, config


def evaluate(args):
    output = Path(args.output)
    if output.exists():
        raise ValueError("Refusing to overwrite evaluation report")
    encoder, config = load_encoder(args.model, args.allow_synthetic)
    if args.registration:
        rows, registration = load_registered(args.data, args.registration, config["referenceHashes"])
        provenance = {"kind": "external-review-attested", "registration": registration}
    else:
        splits, manifest = load_splits(args.data)
        if manifest != config["benchmark"]:
            raise ValueError("Training benchmark differs; register external evaluation explicitly")
        rows = splits["test"]
        provenance = {"kind": "previously-exposed-synthetic-regression", "benchmark": manifest}
    if any(r["sourceType"] == "synthetic" for r in rows) and not args.allow_synthetic:
        raise ValueError("Synthetic evaluation requires --allow-synthetic")
    result = measure(rows, encoder.predict, three_class=True)
    result.update(
        provenance=provenance,
        model=config["model"],
        revision=config["revision"],
        weightsSha256=config["weightsSha256"],
        threshold=encoder.threshold,
        truncatedSamples=encoder.truncation_count(rows),
        paidCalls=0,
        selectedEpoch=config["selected"]["epoch"],
        trainingSeconds=config["trainingSeconds"],
    )
    if args.baseline_report:
        baseline = json.loads(args.baseline_report.read_text())
        if args.registration or baseline["benchmark"] != config["benchmark"]:
            raise ValueError("Baseline must use the identical versioned regression benchmark")
        for candidate in baseline["models"].values():
            if [(r["id"], r["expected"]) for r in candidate["cases"]] != [
                (r["id"], r["label"]) for r in rows
            ]:
                raise ValueError("Baseline case order/labels differ")
        result["baselineComparison"] = {
            name: {"metrics": candidate["metrics"], "latencyMs": candidate["latencyMs"]}
            for name, candidate in baseline["models"].items()
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["metrics"], indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("train")
    t.add_argument("--data", type=Path, required=True)
    t.add_argument("--output", type=Path, required=True)
    t.add_argument("--cache", type=Path, default=Path(".artifacts/hf-cache"))
    t.add_argument("--download", action="store_true", help="Allow public model downloads, no inference API")
    t.add_argument("--allow-synthetic", action="store_true")
    t.add_argument("--epochs", type=int, default=1)
    t.add_argument("--batch-size", type=int, default=4)
    t.add_argument("--max-length", type=int, default=128)
    t.add_argument("--learning-rate", type=float, default=2e-5)
    t.add_argument("--seed", type=int, default=42)
    t.add_argument("--threads", type=int, default=2)
    e = sub.add_parser("evaluate")
    e.add_argument("--model", type=Path, required=True)
    e.add_argument("--data", type=Path, required=True)
    e.add_argument("--registration", type=Path)
    e.add_argument("--baseline-report", type=Path)
    e.add_argument("--output", type=Path, required=True)
    e.add_argument("--allow-synthetic", action="store_true")
    r = sub.add_parser("register-evaluation")
    r.add_argument("--data", type=Path, required=True)
    r.add_argument("--review", type=Path, required=True)
    r.add_argument("--benchmark", type=Path, required=True)
    r.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "train":
        train(args)
    elif args.command == "evaluate":
        evaluate(args)
    else:
        splits, _ = load_splits(args.benchmark)
        reference = reference_hashes([row for rows in splits.values() for row in rows])
        register(args.data, args.review, reference, args.output)


if __name__ == "__main__":
    main()
