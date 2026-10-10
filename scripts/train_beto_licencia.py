from __future__ import annotations

import json
import math
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report
from torch import nn
from torch.optim import AdamW
from torch.utils.data import DataLoader, TensorDataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification, get_linear_schedule_with_warmup

ROOT=Path(__file__).resolve().parents[1]
TRAIN_CSV=ROOT/"data"/"beto_training_v5.csv"
VAL_CSV=ROOT/"data"/"beto_validation_v5.csv"
OUT=ROOT/"models"/"beto_licencia"
BASE_MODEL="dccuchile/bert-base-spanish-wwm-cased"
MAX_LENGTH=96
SEED=42
EPOCHS=4

random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
if torch.cuda.is_available(): torch.cuda.manual_seed_all(SEED)

device=torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Dispositivo:",device)
if device.type=="cuda":
    print("GPU:",torch.cuda.get_device_name(0))
else:
    print("ADVERTENCIA: BETO se entrenará sin GPU. La integración funciona, pero se recomienda CUDA para fine-tuning.")

train_df=pd.read_csv(TRAIN_CSV).dropna(subset=["text","intent"])
val_df=pd.read_csv(VAL_CSV).dropna(subset=["text","intent"])
labels=sorted(set(train_df.intent.astype(str)))
label2id={label:i for i,label in enumerate(labels)}
id2label={i:label for label,i in label2id.items()}
print("Ejemplos entrenamiento:",len(train_df))
print("Ejemplos validación:",len(val_df))
print("Clases:",labels)

tokenizer=AutoTokenizer.from_pretrained(BASE_MODEL)
model=AutoModelForSequenceClassification.from_pretrained(
    BASE_MODEL,
    num_labels=len(labels),
    label2id=label2id,
    id2label=id2label,
)
model.to(device)

def encode(df):
    enc=tokenizer(
        df.text.astype(str).tolist(),
        truncation=True,
        padding="max_length",
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )
    y=torch.tensor([label2id[x] for x in df.intent.astype(str)],dtype=torch.long)
    return TensorDataset(enc["input_ids"],enc["attention_mask"],y)

train_ds=encode(train_df)
val_ds=encode(val_df)
batch_size=16 if device.type=="cuda" else 8
train_loader=DataLoader(train_ds,batch_size=batch_size,shuffle=True,pin_memory=(device.type=="cuda"))
val_loader=DataLoader(val_ds,batch_size=batch_size*2,shuffle=False,pin_memory=(device.type=="cuda"))

optimizer=AdamW(model.parameters(),lr=2e-5,weight_decay=0.01)
steps_per_epoch=math.ceil(len(train_loader)/2)
total_steps=steps_per_epoch*EPOCHS
scheduler=get_linear_schedule_with_warmup(optimizer,num_warmup_steps=max(1,int(total_steps*0.08)),num_training_steps=total_steps)
criterion=nn.CrossEntropyLoss(label_smoothing=0.04)
use_amp=device.type=="cuda"
scaler=torch.amp.GradScaler("cuda",enabled=use_amp)

best_f1=-1.0
patience=0
OUT.mkdir(parents=True,exist_ok=True)

@torch.no_grad()
def evaluate():
    model.eval(); preds=[]; gold=[]; losses=[]
    for input_ids,attention_mask,y in val_loader:
        input_ids=input_ids.to(device); attention_mask=attention_mask.to(device); y=y.to(device)
        logits=model(input_ids=input_ids,attention_mask=attention_mask).logits
        loss=criterion(logits,y); losses.append(float(loss.item()))
        preds.extend(torch.argmax(logits,dim=-1).cpu().tolist()); gold.extend(y.cpu().tolist())
    acc=accuracy_score(gold,preds)
    p,r,f1,_=precision_recall_fscore_support(gold,preds,average="weighted",zero_division=0)
    return {"loss":float(np.mean(losses)),"accuracy":acc,"precision":p,"recall":r,"f1":f1},gold,preds

for epoch in range(1,EPOCHS+1):
    model.train(); optimizer.zero_grad(set_to_none=True); running=[]
    for step,(input_ids,attention_mask,y) in enumerate(train_loader,1):
        input_ids=input_ids.to(device); attention_mask=attention_mask.to(device); y=y.to(device)
        with torch.amp.autocast(device_type="cuda",dtype=torch.float16,enabled=use_amp):
            logits=model(input_ids=input_ids,attention_mask=attention_mask).logits
            loss=criterion(logits,y)/2
        scaler.scale(loss).backward(); running.append(float(loss.item()*2))
        if step%2==0 or step==len(train_loader):
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
            scaler.step(optimizer); scaler.update(); optimizer.zero_grad(set_to_none=True); scheduler.step()
    metrics,gold,preds=evaluate()
    print(f"Epoch {epoch}: train_loss={np.mean(running):.4f} val_loss={metrics['loss']:.4f} accuracy={metrics['accuracy']:.4f} precision={metrics['precision']:.4f} recall={metrics['recall']:.4f} f1={metrics['f1']:.4f}")
    if metrics["f1"]>best_f1+1e-4:
        best_f1=metrics["f1"]; patience=0
        model.save_pretrained(OUT,safe_serialization=True)
        tokenizer.save_pretrained(OUT)
        (OUT/"training_metrics.json").write_text(json.dumps({**metrics,"epoch":epoch,"base_model":BASE_MODEL,"training_examples":len(train_df),"validation_examples":len(val_df)},indent=2),encoding="utf-8")
        print("Mejor modelo guardado en",OUT)
    else:
        patience+=1
        if patience>=2:
            print("Early stopping: F1 no mejoró en dos épocas consecutivas.")
            break

# Final report using the best saved model.
model=AutoModelForSequenceClassification.from_pretrained(OUT).to(device)
model.eval(); metrics,gold,preds=evaluate()
print("\nMétricas finales:",json.dumps(metrics,indent=2))
print(classification_report(gold,preds,target_names=labels,zero_division=0))
print("\nBETO listo. Reinicia Streamlit para que LicencIA lo use como motor principal.")
