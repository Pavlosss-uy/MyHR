import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader, Subset
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import StratifiedKFold

from models.emotion_model import InterviewEmotionModel
from training.dataset import InterviewEmotionDataset
from training.metrics import classification_metrics, make_writer

EMOTION_LABELS = [
    "confident", "hesitant", "nervous", "engaged",
    "neutral", "frustrated", "enthusiastic", "uncertain"
]


# ---------------------------------------------------------------------------
# Custom Focal Loss for class imbalance
# ---------------------------------------------------------------------------

class FocalLoss(nn.Module):
    def __init__(self, alpha=1, gamma=2, reduction="mean"):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, inputs, targets):
        ce_loss = F.cross_entropy(inputs, targets, reduction="none")
        pt = torch.exp(-ce_loss)
        focal_loss = self.alpha * (1 - pt) ** self.gamma * ce_loss
        return focal_loss.mean() if self.reduction == "mean" else focal_loss.sum()


# ---------------------------------------------------------------------------
# One training epoch
# ---------------------------------------------------------------------------

def train_epoch(model, dataloader, optimizer, criterion, device):
    model.train()
    total_loss, correct, total = 0.0, 0, 0

    for batch in dataloader:
        input_values  = batch["input_values"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels         = batch["labels"].to(device)

        optimizer.zero_grad()
        logits = model(input_values, attention_mask)
        loss   = criterion(logits, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        preds   = torch.argmax(logits, dim=-1)
        correct += (preds == labels).sum().item()
        total   += labels.size(0)

    return total_loss / len(dataloader), correct / total


# ---------------------------------------------------------------------------
# One validation epoch — returns loss, preds, true labels
# ---------------------------------------------------------------------------

def val_epoch(model, dataloader, criterion, device):
    model.eval()
    total_loss = 0.0
    all_preds, all_labels = [], []

    with torch.no_grad():
        for batch in dataloader:
            input_values   = batch["input_values"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels         = batch["labels"].to(device)

            logits = model(input_values, attention_mask)
            loss   = criterion(logits, labels)
            total_loss += loss.item()

            preds = torch.argmax(logits, dim=-1)
            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(labels.cpu().tolist())

    avg_loss = total_loss / len(dataloader)
    return avg_loss, all_preds, all_labels


# ---------------------------------------------------------------------------
# Save confusion matrix plot
# ---------------------------------------------------------------------------

def save_confusion_matrix(cm, label_names, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        np.array(cm), annot=True, fmt="d", cmap="Blues",
        xticklabels=label_names, yticklabels=label_names, ax=ax
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Emotion Model — Confusion Matrix")
    plt.tight_layout()
    plt.savefig(save_path, dpi=120)
    plt.close(fig)
    print(f"Confusion matrix saved → {save_path}")


# ---------------------------------------------------------------------------
# Train one fold (or full dataset if no k-fold)
# ---------------------------------------------------------------------------

def train_fold(model, train_loader, val_loader, device,
               epochs=10, fold_tag="full", checkpoint_path=None):
    writer    = make_writer(f"emotion_{fold_tag}")
    criterion = FocalLoss(gamma=2.0)
    optimizer = optim.AdamW(model.parameters(), lr=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", patience=3, factor=0.5, verbose=True
    )

    best_val_loss    = float("inf")
    patience_counter = 0
    best_cm          = None
    best_metrics     = None

    for epoch in range(epochs):
        train_loss, train_acc = train_epoch(
            model, train_loader, optimizer, criterion, device
        )
        val_loss, val_preds, val_labels = val_epoch(
            model, val_loader, criterion, device
        )

        metrics = classification_metrics(val_labels, val_preds, EMOTION_LABELS)

        # TensorBoard
        writer.add_scalar("Loss/train",           train_loss,              epoch)
        writer.add_scalar("Loss/val",             val_loss,                epoch)
        writer.add_scalar("Accuracy/train",       train_acc,               epoch)
        writer.add_scalar("Metric/weighted_f1",   metrics["weighted_f1"],  epoch)
        writer.add_scalar("Metric/macro_f1",      metrics["macro_f1"],     epoch)
        writer.add_scalar("Metric/accuracy_val",  metrics["accuracy"],     epoch)
        writer.add_scalar(
            "LR", optimizer.param_groups[0]["lr"], epoch
        )

        print(
            f"[{fold_tag}] Epoch {epoch+1}/{epochs} | "
            f"train_loss={train_loss:.4f}  val_loss={val_loss:.4f} | "
            f"weighted_F1={metrics['weighted_f1']:.4f}  acc={metrics['accuracy']:.4f}"
        )

        scheduler.step(val_loss)

        # Early stopping & checkpoint
        if val_loss < best_val_loss:
            best_val_loss    = val_loss
            patience_counter = 0
            best_cm          = metrics["confusion_matrix"]
            best_metrics     = metrics

            if checkpoint_path:
                os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
                torch.save(model.state_dict(), checkpoint_path)
                print(f"  --> Checkpoint saved ({fold_tag})")
        else:
            patience_counter += 1
            if patience_counter >= 5:
                print(f"  Early stopping at epoch {epoch+1} ({fold_tag})")
                break

    writer.close()
    return best_metrics, best_cm


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Starting Emotion Model training on {device}...\n")

    csv_path = "data/interview_emotions_train.csv"
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found. Run preprocessing.py first.")
        return

    full_dataset = InterviewEmotionDataset(csv_path)
    all_labels   = [full_dataset[i]["labels"].item() for i in range(len(full_dataset))]

    epochs           = 10
    checkpoint_path  = "models/checkpoints/emotion_finetuned_v1.pt"
    cm_save_path     = "training/results/emotion_confusion_matrix.png"

    # --- 5-fold cross-validation ---
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    fold_weighted_f1s = []

    for fold, (train_idx, val_idx) in enumerate(
        skf.split(np.zeros(len(all_labels)), all_labels)
    ):
        print(f"\n{'='*60}")
        print(f"  FOLD {fold+1}/5")
        print(f"{'='*60}")

        train_loader = DataLoader(
            Subset(full_dataset, train_idx), batch_size=8, shuffle=True
        )
        val_loader = DataLoader(
            Subset(full_dataset, val_idx), batch_size=8
        )

        model = InterviewEmotionModel().to(device)

        ckpt = checkpoint_path if fold == 0 else None
        fold_metrics, fold_cm = train_fold(
            model, train_loader, val_loader, device,
            epochs=epochs, fold_tag=f"fold{fold+1}", checkpoint_path=ckpt
        )

        if fold_metrics:
            fold_weighted_f1s.append(fold_metrics["weighted_f1"])
            print(f"\n  Fold {fold+1} best weighted F1: {fold_metrics['weighted_f1']:.4f}")
            print(fold_metrics["report_str"])

        # Save confusion matrix from fold 1 as the representative plot
        if fold == 0 and fold_cm:
            save_confusion_matrix(fold_cm, EMOTION_LABELS, cm_save_path)

    if fold_weighted_f1s:
        mean_f1 = np.mean(fold_weighted_f1s)
        std_f1  = np.std(fold_weighted_f1s)
        print(f"\n{'='*60}")
        print(f"5-Fold CV Results: mean weighted F1 = {mean_f1:.4f} ± {std_f1:.4f}")
        print(f"{'='*60}")

    print(f"\nCheckpoint: {checkpoint_path}")
    print(f"Confusion matrix: {cm_save_path}")


if __name__ == "__main__":
    main()
