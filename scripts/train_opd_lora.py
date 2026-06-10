"""
OPD LoRA training script using transformers + peft + DeepSpeed ZeRO-3 CPU offload.
Bypasses GPU memory limitations by offloading model/optimizer to CPU RAM.
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List

import torch
from torch.utils.data import Dataset
from transformers import (
    AutoProcessor,
    AutoModelForVision2Seq,
    TrainingArguments,
    Trainer,
    TrainerCallback,
)
from peft import LoraConfig, get_peft_model, TaskType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("opd_train")


class OPDDataset(Dataset):
    """Dataset for OPD multimodal training."""

    def __init__(self, jsonl_path: str, processor, max_length: int = 1024):
        self.processor = processor
        self.max_length = max_length
        self.samples = []

        with open(jsonl_path) as f:
            for line in f:
                d = json.loads(line.strip())
                self.samples.append(d)
        logger.info(f"Loaded {len(self.samples)} samples from {jsonl_path}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]
        messages = sample["messages"]
        image_paths = sample.get("images", [])

        # Build conversation text
        system_msg = messages[0]["content"] if messages[0]["role"] == "system" else ""
        user_msg = messages[1]["content"]
        assistant_msg = messages[2]["content"]

        # For text-only training (without actual image loading for speed)
        # We include the image token but process as text
        prompt = f"<|im_start|>system\n{system_msg}<|im_end|>\n<|im_start|>user\n{user_msg}<|im_end|>\n<|im_start|>assistant\n"
        full_text = prompt + assistant_msg + "<|im_end|>"

        # Tokenize
        encodings = self.processor.tokenizer(
            full_text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )

        input_ids = encodings["input_ids"].squeeze(0)
        attention_mask = encodings["attention_mask"].squeeze(0)

        # Create labels: mask the prompt portion
        prompt_ids = self.processor.tokenizer(
            prompt, truncation=True, max_length=self.max_length
        )["input_ids"]
        labels = input_ids.clone()
        labels[:len(prompt_ids)] = -100  # Don't compute loss on prompt

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }


class LogCallback(TrainerCallback):
    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs and state.global_step > 0:
            loss = logs.get("loss", "N/A")
            lr = logs.get("learning_rate", "N/A")
            logger.info(f"Step {state.global_step}: loss={loss}, lr={lr}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="/Knowin/foundation/weilinruan/hf_models/Qwen/Qwen2.5-VL-7B-Instruct")
    parser.add_argument("--dataset", default="data/opd_train_v2/opd_multimodal.jsonl")
    parser.add_argument("--output-dir", default="outputs/opd_lora/round1")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--lora-rank", type=int, default=32)
    parser.add_argument("--lora-alpha", type=int, default=64)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--deepspeed", default="configs/ds_zero3_offload.json")
    parser.add_argument("--local_rank", type=int, default=-1)
    args = parser.parse_args()

    logger.info(f"Loading processor from {args.model}...")
    processor = AutoProcessor.from_pretrained(args.model, trust_remote_code=True)

    logger.info(f"Loading model...")
    model = AutoModelForVision2Seq.from_pretrained(
        args.model,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )

    # Configure LoRA
    lora_config = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "v_proj", "o_proj", "k_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Dataset
    dataset = OPDDataset(args.dataset, processor, max_length=args.max_length)

    # Training args
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        warmup_ratio=0.05,
        bf16=True,
        logging_steps=10,
        save_strategy="epoch",
        save_total_limit=2,
        gradient_checkpointing=True,
        deepspeed=args.deepspeed,
        report_to="wandb",
        run_name="opd_r1_trimodal",
        remove_unused_columns=False,
        dataloader_num_workers=4,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        callbacks=[LogCallback()],
    )

    logger.info("Starting training...")
    trainer.train()

    # Save final adapter
    final_dir = Path(args.output_dir) / "final_adapter"
    model.save_pretrained(str(final_dir))
    processor.save_pretrained(str(final_dir))
    logger.info(f"Training complete! Adapter saved to {final_dir}")


if __name__ == "__main__":
    main()
