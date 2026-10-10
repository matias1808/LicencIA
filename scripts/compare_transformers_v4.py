from pathlib import Path
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

ROOT=Path(__file__).resolve().parents[1]
STRESS=ROOT/"data"/"nlp_stress_v4.csv"

MODELS={
    "BETO": ROOT/"models"/"beto_intent_v3",
    "DistilBERT-ES": ROOT/"models"/"distilbert_es_intent_v3",
}

df=pd.read_csv(STRESS)
device=torch.device("cuda" if torch.cuda.is_available() else "cpu")

def evaluate(name,path):
    if not path.exists():
        print(f"{name}: no entrenado ({path})")
        return None
    tok=AutoTokenizer.from_pretrained(path)
    model=AutoModelForSequenceClassification.from_pretrained(path).to(device)
    model.eval()
    preds=[]
    bs=32
    texts=df["text"].astype(str).tolist()
    with torch.no_grad():
        for i in range(0,len(texts),bs):
            batch=tok(texts[i:i+bs],padding=True,truncation=True,max_length=128,return_tensors="pt").to(device)
            logits=model(**batch).logits
            ids=logits.argmax(dim=1).cpu().tolist()
            preds.extend([model.config.id2label[int(x)] for x in ids])
    acc=accuracy_score(df["intent"],preds)
    p,r,f,_=precision_recall_fscore_support(df["intent"],preds,average="weighted",zero_division=0)
    print(f"{name}: Accuracy={acc:.4f} Precision={p:.4f} Recall={r:.4f} F1={f:.4f}")
    return {"model":name,"accuracy":acc,"precision":p,"recall":r,"f1":f}

rows=[]
for name,path in MODELS.items():
    x=evaluate(name,path)
    if x: rows.append(x)

if rows:
    out=pd.DataFrame(rows).sort_values("f1",ascending=False)
    out.to_csv(ROOT/"models"/"transformer_comparison_v4.csv",index=False)
    print("\nRanking por F1:")
    print(out.to_string(index=False))
else:
    print("Primero entrena BETO y/o DistilBERT.")
