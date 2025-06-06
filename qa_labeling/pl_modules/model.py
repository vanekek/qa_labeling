from typing import Any

import numpy as np
import pytorch_lightning as pl
import torch
from scipy.stats import spearmanr


class QALabler(pl.LightningModule):
    """Module for training and evaluation models
    for the classification task
    """

    def __init__(self, model, lr, loss_weights, freeze):
        super().__init__()
        self.save_hyperparameters()
        self.model = model
        self.lr = lr
        self.loss_weights = loss_weights
        self.freeze = freeze
        self.criterion = torch.nn.BCEWithLogitsLoss()

    def forward(
        self,
        input_ids,
        attention_mask,
        token_type_ids,
    ):
        return self.model(input_ids, attention_mask, token_type_ids)

    def training_step(self, batch: Any, batch_idx: int, dataloader_idx=0):
        input_ids, input_masks, input_segments, labels, _ = batch

        if self.freeze is True:
            self.model.eval()
        logits = self(
            input_ids=input_ids,
            attention_mask=input_masks,
            token_type_ids=input_segments,
        )

        loss1 = self.criterion(logits[:, 0:9], labels[:, 0:9])
        loss2 = self.criterion(logits[:, 9:10], labels[:, 9:10])
        loss3 = self.criterion(logits[:, 10:21], labels[:, 10:21])
        loss4 = self.criterion(logits[:, 21:26], labels[:, 21:26])
        loss5 = self.criterion(logits[:, 26:30], labels[:, 26:30])
        loss = self.loss_weights["question"] * (
            loss1 + loss3 + loss5
        ) + self.loss_weights["answer"] * (loss2 + loss4)

        self.log("train_loss", loss, prog_bar=True, on_step=False, on_epoch=True)
        return loss

    def validation_step(self, batch: Any, batch_idx: int, dataloader_idx: int = 0):
        input_ids, input_masks, input_segments, labels, _ = batch

        logits = self(
            input_ids=input_ids,
            attention_mask=input_masks,
            token_type_ids=input_segments,
        )

        val_loss = self.criterion(logits, labels).item()

        original = labels.squeeze().numpy()
        preds = torch.sigmoid(torch.tensor(logits.squeeze())).numpy()

        rho_val = np.mean(
            [
                np.nan_to_num(spearmanr(original[:, i], preds[:, i]).statistic)
                for i in range(preds.shape[1])
            ]
        )

        self.log("val_loss", val_loss, prog_bar=True, on_epoch=True)
        self.log("val_rho", rho_val, prog_bar=True, on_epoch=True)
        return {"val_loss": val_loss, "val_rho": rho_val}

    def test_step(self, batch: Any, batch_idx: int, dataloader_idx: int = 0):
        pass

    def predict_step(self, batch: Any, batch_idx: int, dataloader_idx: int = 0) -> Any:
        input_ids, input_masks, input_segments, _ = batch

        logits = self(
            input_ids=input_ids,
            attention_mask=input_masks,
            token_type_ids=input_segments,
        )

        preds_numpy = logits.squeeze().numpy()
        preds = torch.sigmoid(torch.tensor(preds_numpy)).numpy()

        return preds

    def configure_optimizers(self) -> Any:
        no_decay = ["bias", "LayerNorm.bias", "LayerNorm.weight"]
        param_optimizer = self.named_parameters()
        optimizer_grouped_parameters = [
            {
                "params": [
                    p for n, p in param_optimizer if not any(nd in n for nd in no_decay)
                ],
                "weight_decay": 0.8,
            },
            {
                "params": [
                    p for n, p in param_optimizer if any(nd in n for nd in no_decay)
                ],
                "weight_decay": 0.0,
            },
        ]
        return torch.optim.AdamW(optimizer_grouped_parameters, lr=self.lr)
