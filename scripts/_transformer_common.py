from pathlib import Path
import numpy as np
import pandas as pd
import torch
from datasets import Dataset
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from transformers import AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments, Trainer, EarlyStoppingCallback

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"/"nlp_training_v3.csv"

def prepare(base_model, out_dir):
    df=pd.read_csv(DATA)
    labels=sorted(df.intent.unique())
    label2id={x:i for i,x in enumerate(labels)}
    id2label={i:x for x,i in label2id.items()}
    df["label"]=df.intent.map(label2id)
    train_df, eval_df=train_test_split(df[["text","label"]], test_size=.12, random_state=42, stratify=df["label"])
    train_ds=Dataset.from_pandas(train_df.reset_index(drop=True))
    eval_ds=Dataset.from_pandas(eval_df.reset_index(drop=True))
    tok=AutoTokenizer.from_pretrained(base_model)
    def enc(b): return tok(b["text"], truncation=True, padding="max_length", max_length=128)
    train_ds=train_ds.map(enc, batched=True); eval_ds=eval_ds.map(enc, batched=True)
    model=AutoModelForSequenceClassification.from_pretrained(base_model,num_labels=len(labels),label2id=label2id,id2label=id2label)
    def metrics(p):
        pred=np.argmax(p.predictions,axis=1)
        acc=accuracy_score(p.label_ids,pred)
        pr,re,f1,_=precision_recall_fscore_support(p.label_ids,pred,average="weighted",zero_division=0)
        return {"accuracy":acc,"precision":pr,"recall":re,"f1":f1}
    gpu=torch.cuda.is_available()
    args=TrainingArguments(
        output_dir=str(out_dir), learning_rate=2e-5, per_device_train_batch_size=16 if gpu else 8,
        per_device_eval_batch_size=32 if gpu else 16, gradient_accumulation_steps=1 if gpu else 2,
        num_train_epochs=6, warmup_ratio=.08, weight_decay=.01, eval_strategy="epoch", save_strategy="epoch",
        load_best_model_at_end=True, metric_for_best_model="f1", greater_is_better=True, fp16=gpu,
        save_total_limit=2, report_to="none", logging_steps=100
    )
    trainer=Trainer(model=model,args=args,train_dataset=train_ds,eval_dataset=eval_ds,tokenizer=tok,
                    compute_metrics=metrics,callbacks=[EarlyStoppingCallback(early_stopping_patience=2)])
    trainer.train(); print(trainer.evaluate()); trainer.save_model(str(out_dir)); tok.save_pretrained(str(out_dir))

