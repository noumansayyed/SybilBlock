from pathlib import Path
import numpy as np, pandas as pd, joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score

BASE = Path(__file__).resolve().parent
FEATURES = ["account_age_days","posts_per_day","followers_count","following_count",
"account_activity_hours","duplicate_content_ratio","interaction_rate",
"shared_device_count","registration_burst_count"]

def generate(n=2500, seed=42):
    rng=np.random.default_rng(seed); labels=rng.binomial(1,.35,n); rows=[]
    for y in labels:
        if y:
            row=[rng.integers(1,180),rng.gamma(5,7),rng.integers(0,400),rng.integers(300,3000),
            rng.uniform(10,24),rng.beta(7,2),rng.beta(1.5,12),rng.integers(2,12),rng.integers(2,15)]
        else:
            row=[rng.integers(30,2500),rng.gamma(2,1.5),rng.integers(5,5000),rng.integers(5,1200),
            rng.uniform(1,15),rng.beta(2,7),rng.beta(3,8),rng.integers(1,3),rng.integers(0,3)]
        rows.append(row+[int(y)])
    df=pd.DataFrame(rows,columns=FEATURES+["label"])
    (BASE/"data").mkdir(exist_ok=True); df.to_csv(BASE/"data/accounts.csv",index=False)
    return df

if __name__=="__main__":
    df=generate(); X=df[FEATURES]; y=df.label
    Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.2,random_state=42,stratify=y)
    model=RandomForestClassifier(n_estimators=150,max_depth=10,class_weight="balanced",random_state=42)
    model.fit(Xtr,ytr); pred=model.predict(Xte); prob=model.predict_proba(Xte)[:,1]
    print(classification_report(yte,pred,target_names=["normal","sybil"]))
    print("Confusion matrix:\\n",confusion_matrix(yte,pred),"\\nROC-AUC:",round(roc_auc_score(yte,prob),4))
    (BASE/"models").mkdir(exist_ok=True)
    joblib.dump({"model":model,"features":FEATURES,"version":"rf-v1"},BASE/"models/sybil_model.joblib")
    print("Model and synthetic dataset generated.")
