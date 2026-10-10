from pathlib import Path
import json
import sys
import pandas as pd
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from licencia.nlp import parse_message,get_nlp_engine_status

print("Motor NLP:",json.dumps(get_nlp_engine_status(),ensure_ascii=False,indent=2))
val=pd.read_csv(ROOT/"data"/"beto_validation_v5.csv")
preds=[]
for text in val.text.astype(str):
    preds.append(parse_message(text).intent)
acc=accuracy_score(val.intent,preds)
p,r,f1,_=precision_recall_fscore_support(val.intent,preds,average="weighted",zero_division=0)
print(f"Accuracy={acc:.4f} Precision={p:.4f} Recall={r:.4f} F1={f1:.4f}")
print(classification_report(val.intent,preds,zero_division=0))

samples=[
 "¿Qué usuarios tienen F3?",
 "Necesito darle Power BI a juan.perez0001@empresas.com.pe",
 "Quiero asignar una licencia",
 "¿Qué pasó en la guerra con Chile?",
 "Pasa Visio P2 de usuario1@empresas.com.pe a usuario2@empresas.com.pe",
]
print("\nPruebas manuales:")
for s in samples:
    r=parse_message(s)
    print(f"- {s} -> {r.intent} ({r.confidence:.3f}) | licencia={r.license_name} | emails={r.emails}")
