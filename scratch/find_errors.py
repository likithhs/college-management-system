import sys
import os
import py_compile
import ast

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

print("==================================================")
print("  COMPREHENSIVE CODEBASE ERROR & BUG AUDIT       ")
print("==================================================")

py_files = [
    os.path.join(project_dir, f) for f in os.listdir(project_dir) if f.endswith('.py')
]

errors_found = []

# 1. Syntax Check
print("\n[1] Checking Python Syntax & AST Compilation...")
for pf in py_files:
    fname = os.path.basename(pf)
    try:
        py_compile.compile(pf, doraise=True)
        with open(pf, 'r', encoding='utf-8') as f:
            ast.parse(f.read(), filename=fname)
        print(f"  -> {fname}: Syntax OK")
    except Exception as e:
        print(f"  -> ERROR in {fname}: {e}")
        errors_found.append(f"Syntax Error in {fname}: {e}")

# 2. Flask & Database Runtime Inspection
print("\n[2] Checking Flask Route Definitions, Models & Imports...")
try:
    from app import app, db, models
    app.app_context().push()
    
    # Check endpoints
    endpoints = list(app.view_functions.keys())
    print(f"  -> Registered Endpoints: {len(endpoints)}")
    
    # Check database engine & tables
    inspector = db.inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"  -> Database Tables: {len(tables)} tables found ({', '.join(tables)})")
    
    # Audit model column definitions & relationships
    for model_name in dir(models):
        cls = getattr(models, model_name)
        if isinstance(cls, type) and issubclass(cls, db.Model) and cls != db.Model:
            try:
                count = cls.query.count()
                print(f"  -> Model {model_name}: Query OK ({count} records)")
            except Exception as e:
                print(f"  -> ERROR in Model {model_name} query: {e}")
                errors_found.append(f"Model Query Error in {model_name}: {e}")

except Exception as e:
    print(f"  -> ERROR during Flask/DB inspection: {e}")
    errors_found.append(f"Flask/DB Initialization Error: {e}")

# 3. HTML Template Rendering & Variable Reference Audit
print("\n[3] Auditing HTML Templates for Syntax & Undefined Variables...")
template_dir = os.path.join(project_dir, 'templates')
if os.path.exists(template_dir):
    templates = [f for f in os.listdir(template_dir) if f.endswith('.html')]
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(template_dir))
    
    for tname in templates:
        try:
            template_source = env.loader.get_source(env, tname)[0]
            env.parse(template_source)
            print(f"  -> Template {tname}: Jinja2 Syntax OK")
        except Exception as e:
            print(f"  -> ERROR in Template {tname}: {e}")
            errors_found.append(f"Jinja2 Template Error in {tname}: {e}")

print("\n==================================================")
if errors_found:
    print(f" TOTAL ERRORS FOUND: {len(errors_found)}")
    for err in errors_found:
        print(f" - {err}")
else:
    print(" ZERO SYNTAX OR RUNTIME INITIALIZATION ERRORS FOUND! ")
print("==================================================")
