from licencia.nlp import get_nlp_engine_status
import json
print(json.dumps(get_nlp_engine_status(),ensure_ascii=False,indent=2))
