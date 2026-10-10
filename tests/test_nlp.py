\
from licencia.nlp import _rule_hint

def test_explicit_intents():
  assert _rule_hint("asigna M365 E3 a juan@empresas.com.pe") == "assign"
  assert _rule_hint("retira Visio P2 a juan@empresas.com.pe") == "unassign"
  assert _rule_hint("reasigna Power BI de a@empresas.com.pe a b@empresas.com.pe") == "reassign"
  assert _rule_hint("cuántas licencias M365 E3 hay en stock") == "inventory"
  assert _rule_hint("qué licencias tiene juan@empresas.com.pe") == "user_licenses"
  assert _rule_hint("busca en internet el clima") == "out_of_scope"
