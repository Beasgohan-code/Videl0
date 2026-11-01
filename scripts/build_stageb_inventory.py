"""Generate source-syntax indexes for the Stage B authorization audit.

These indexes are discovery aids, not authorization proofs; see
docs/STAGE_B_MUTATION_SURFACE_INVENTORY.md for limits.
"""
import ast,csv,re
from pathlib import Path
root=Path('videl')

# Telegram callback handler inventory: exact registration pattern and observable boundary/write cues.
rows=[]
for p in sorted(root.rglob('*.py')):
    text=p.read_text(errors='replace')
    try: tree=ast.parse(text)
    except SyntaxError: continue
    for n in ast.walk(tree):
        if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
        deco=[]
        for d in n.decorator_list:
            if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr=='on_callback_query': deco.append(ast.unparse(d))
        if not deco: continue
        body=ast.get_source_segment(text,n) or ''
        cues=[]
        for label,patterns in [
          ('owner/sudo',r'OWNER_ID|is_sudo_user|sudoadmin'),('fresh group-admin',r'is_user_authorized|is_admin\(|get_chat_member|authorize\(|require_admin|current admin'),
          ('connected mapping',r'connected_target|connected_chat'),('actor/message binding',r'from_user|actor_id|interaction_chat|message\.chat\.id|chat_kind'),
          ('revision/CAS',r'revision|engine\.commit|compare|commit'),('bot-rights check',r'bot.*(?:permission|right)|can_restrict|can_delete|has_right')]:
            if re.search(patterns,body,re.I): cues.append(label)
        writes=sorted(set(re.findall(r'\b(?:insert_one|insert_many|update_one|replace_one|delete_one|delete_many|find_one_and_update|find_one_and_delete)\b',body)))
        delegates=sorted(set(re.findall(r'\b(?:await\s+)?(?:[A-Za-z_]\w*\.)?([A-Za-z_]\w*)\(',body)) & {'commit','authorize','connected_target','is_user_authorized','answer_challenge','remove','approve','apply','save','update','delete','clear','set','mutate','toggle','run'})
        rows.append([str(p),n.lineno,n.name,' | '.join(deco),'; '.join(cues) or 'No direct cue; inspect helper/delegate',', '.join(writes) or 'None directly detected; helper may mutate',', '.join(delegates),'No path-level test mapping generated; search tests and inspect call path'])
with open('docs/STAGE_B_TELEGRAM_CALLBACK_INVENTORY.csv','w',newline='') as f:
    w=csv.writer(f,lineterminator="\n"); w.writerow(['source','line','handler','registration_pattern','source_cues_not_proof','direct_write_primitives','notable_delegates','test_mapping_status']); w.writerows(rows)

# Literal/template callback_data keyword uses, one row per AST keyword.
rows=[]
for p in sorted(root.rglob('*.py')):
    text=p.read_text(errors='replace')
    try: tree=ast.parse(text)
    except SyntaxError: continue
    parent={}
    for node in ast.walk(tree):
      for child in ast.iter_child_nodes(node): parent[child]=node
    for node in ast.walk(tree):
      if isinstance(node,ast.Call):
       for kw in node.keywords:
        if kw.arg=='callback_data':
         q=node
         while q in parent and not isinstance(q,(ast.FunctionDef,ast.AsyncFunctionDef)): q=parent[q]
         owner=(q.name if isinstance(q,(ast.FunctionDef,ast.AsyncFunctionDef)) else '<module>')
         rows.append([str(p),node.lineno,owner,ast.unparse(kw.value)])
with open('docs/STAGE_B_TELEGRAM_KEYBOARD_ACTIONS.csv','w',newline='') as f:
    w=csv.writer(f,lineterminator="\n"); w.writerow(['source','line','enclosing_function','callback_data_expression']); w.writerows(rows)

# Internal Flask route inventory: declarations and simple guard/mutation cues.
rows=[]
for p in [Path('videl/__main__.py'),*sorted(Path('videl/api').glob('*.py'))]:
 if not p.exists(): continue
 text=p.read_text(errors='replace')
 try: tree=ast.parse(text)
 except SyntaxError: continue
 for n in ast.walk(tree):
  if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
  routes=[]
  for d in n.decorator_list:
   if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr=='route': routes.append(ast.unparse(d))
  if not routes: continue
  body=ast.get_source_segment(text,n) or ''
  cues=[k for k,patt in [('internal shared-secret',r'_internal_authorized\('),('owner gate',r'owner|OWNER_ID|owner_required'),('current actor/admin',r'require_admin|is_admin|actor|telegram'),('CSRF/origin',r'origin|csrf|same.origin'),('signed assertion',r'assertion|signature|hmac')] if re.search(patt,body,re.I)]
  writes=sorted(set(re.findall(r'\b(?:insert_one|insert_many|update_one|replace_one|delete_one|delete_many|find_one_and_update|find_one_and_delete)\b',body)))
  rows.append([str(p),n.lineno,n.name,' | '.join(routes),'; '.join(cues) or 'No direct guard cue; inspect registration wrapper',', '.join(writes) or 'No direct DB write primitive detected; helper/backend may mutate'])
with open('docs/STAGE_B_INTERNAL_API_INVENTORY.csv','w',newline='') as f:
 w=csv.writer(f,lineterminator="\n"); w.writerow(['source','line','handler','route_declaration','source_guard_cues_not_proof','direct_write_primitives']); w.writerows(rows)
import ast,csv,re
from pathlib import Path
# Next API route inventory by file and exported HTTP method.
rows=[]
for p in sorted(Path('webapp/src/app/api').rglob('route.ts')):
 s=p.read_text(errors='replace')
 methods=sorted(set(re.findall(r'export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)\b|export\s+const\s+(GET|POST|PUT|PATCH|DELETE)\b',s)))
 methods=sorted({x for pair in methods for x in pair if x})
 guards=[]
 for label,pat in [('ownerRequired',r'ownerRequired\s*\('),('playerRequired',r'playerRequired\s*\('),('auth/session boundary',r'ownerTelegramLogin|playerTelegramLogin|clearOwnerSession|clearPlayerSession'),('cross-site guard',r'rejectCrossSite|sameOrigin|same-site')]:
  if re.search(pat,s):guards.append(label)
 backend=sorted(set(re.findall(r'(?:internalBackendFetch|botBackendFetch|backendFetch|fetch)\s*\([^\n]{0,180}',s)))
 writes=bool(set(methods)&{'POST','PUT','PATCH','DELETE'})
 rows.append([str(p),'/'+str(p.parent.relative_to('webapp/src/app/api')).replace('\\','/'),','.join(methods),'; '.join(guards) or 'No direct guard text; inspect imported wrapper', 'state-changing HTTP method' if writes else 'read/auth route or no exported state-change method', ' | '.join(x.strip() for x in backend) or 'See handler; no simple backend call matched'])
with open('docs/STAGE_B_WEB_API_INVENTORY.csv','w',newline='') as f:
 w=csv.writer(f,lineterminator="\n");w.writerow(['source','route_path','exported_methods','source_guard_cues_not_proof','method_class','backend_call_cues_not_proof']);w.writerows(rows)

# Python functions with direct Mongo-like write calls; AST walkers exclude nested functions.
writers=[]
write_names={'insert_one','insert_many','update_one','replace_one','delete_one','delete_many','find_one_and_update','find_one_and_delete'}
for p in sorted(Path('videl').rglob('*.py')):
 s=p.read_text(errors='replace')
 try:t=ast.parse(s)
 except SyntaxError:continue
 def direct_calls(n):
  out=[]
  def walk(x):
   for c in ast.iter_child_nodes(x):
    if isinstance(c,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda,ast.ClassDef)) and c is not n:continue
    if isinstance(c,ast.Call):out.append(c)
    walk(c)
  walk(n);return out
 for n in ast.walk(t):
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
   calls=[c for c in direct_calls(n) if isinstance(c.func,ast.Attribute) and c.func.attr in write_names]
   if not calls:continue
   body=ast.get_source_segment(s,n) or ''
   auth=[v for v,pat in [('owner',r'OWNER_ID|owner'),('admin/role',r'admin|authorize|permission|is_sudo'),('actor binding',r'actor|user_id'),('connection',r'connected_target|connection')] if re.search(pat,body,re.I)]
   scopes=[]
   for c in calls:
    scopes.append(f'{ast.unparse(c.func)}@{c.lineno}')
   writers.append([str(p),n.lineno,n.name,'; '.join(scopes),'; '.join(auth) or 'No auth cue in this writer; likely worker/helper—trace caller and stored scope'])
with open('docs/STAGE_B_PYTHON_WRITE_INVENTORY.csv','w',newline='') as f:
 w=csv.writer(f,lineterminator="\n");w.writerow(['source','line','function','direct_write_calls_and_lines','source_cues_not_proof']);w.writerows(writers)
print('web_route_files',len(rows),'python_writer_functions',len(writers))

print("generated source-syntax inventories under docs/")
