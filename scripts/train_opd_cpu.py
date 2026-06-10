"""
OPD LoRA training - pure CPU mode.
Uses transformers + peft without any GPU.
Designed for when GPU memory is unavailable.
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

os.environ["CUDA_VISIBLE_DEVICES"] = ""  # Force no GPU

import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model, TaskType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("opd_train_cpu")


class OPDTextDataset(Dataset):
    """Text-only OPD dataset (uses chart description instead of image for CPU training)."""

    def __init__(self, jsonl_path: str, tokenizer, max_length: int = 768):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.samples = []

        with open(jsonl_path) as f:
            for line in f:
                self.samples.append(json.loads(line.strip()))
        logger.info(f"Loaded {len(self.samples)} samples")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]
        msgs = sample["messages"]

        system = msgs[0]["content"]
        user = msgs[1]["content"].replace("<image>\n", "")  # Remove image token for text-only
        assistant = msgs[2]["content"]

        prompt = f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"
        full = prompt + assistant + "<|im_end|>"

        enc = self.tokenizer(full, truncation=True, max_length=self.max_length, padding="max_length", return_tensors="pt")
        input_ids = enc["input_ids"].squeeze(0)
        attention_mask = enc["attention_mask"].squeeze(0)

        # Mask prompt tokens in labels
        prompt_enc = self.tokenizer(prompt, truncation=True, max_length=self.max_length)
        prompt_len = len(prompt_enc["input_ids"])
        labels = input_ids.clone()
        labels[:prompt_len] = -100

        return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="/Knowin/foundation/weilinruan/hf_models/Qwen/Qwen2.5-VL-7B-Instruct")
    parser.add_argument("--dataset", default="data/opd_train_v2/opd_multimodal.jsonl")
    parser.add_argument("--output-dir", default="outputs/opd_lora/round1")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--lora-rank", type=int, default=32)
    parser.add_argument("--lora-alpha", type=int, default=64)
    parser.add_argument("--max-length", type=int, default=768)
    parser.add_argument("--max-samples", type=int, default=None)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Loading tokenizer from {args.model}...")
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    logger.info(f"Loading model in float32 on CPU...")
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        trust_remote_code=True,
        torch_dtype=torch.float32,
        device_map="cpu",
    )

    # LoRA config
    lora_config = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "v_proj", "o_proj", "k_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Dataset
    dataset = OPDTextDataset(args.dataset, tokenizer, max_length=args.max_length)
    if args.max_samples and args.max_samples < len(dataset):
        from torch.utils.data import Subset
        indices = list(range(args.max_samples))
        dataset = Subset(dataset, indices)
        logger.info(f"Using {args.max_samples} samples")

    # Training
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        warmup_ratio=0.05,
        logging_steps=10,
        save_strategy="epoch",
        save_total_limit=2,
        no_cuda=True,
        fp16=False,
        bf16=False,
        report_to="wandb",
        run_name="opd_r1_cpu",
        remove_unused_columns=False,
        dataloader_num_workers=8,
        gradient_checkpointing=True,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
    )

    logger.info(f"Starting CPU training: {len(dataset)} samples, {args.epochs} epochs")
    trainer.train()

    # Save
    model.save_pretrained(str(output_dir / "final_adapter"))
    tokenizer.save_pretrained(str(output_dir / "final_adapter"))
    logger.info(f"Done! Adapter saved to {output_dir / 'final_adapter'}")


if __name__ == "__main__":
    main()
