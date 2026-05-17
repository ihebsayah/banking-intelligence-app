import os, glob

for path in glob.glob("services/*/main.py"):
    # skip api_gateway which already has CORS
    if "api_gateway" in path: continue
    
    with open(path, "r") as f:
        content = f.read()
        
    if "CORSMiddleware" in content:
        print(f"Skipping {path} (already has CORS)")
        continue
        
    print(f"Patching {path}")
    
    # 1. Add import
    content = content.replace("from fastapi import", "from fastapi.middleware.cors import CORSMiddleware\nfrom fastapi import")
    
    # 2. Add middleware after app = FastAPI(...)
    app_lines = []
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith("app = FastAPI"):
            # find where this declaration ends
            end_idx = i
            while ")" not in lines[end_idx]:
                end_idx += 1
            
            # insert middleware after end_idx
            middleware = [
                "",
                "app.add_middleware(",
                "    CORSMiddleware,",
                "    allow_origins=['*'],",
                "    allow_credentials=True,",
                "    allow_methods=['*'],",
                "    allow_headers=['*'],",
                ")"
            ]
            lines = lines[:end_idx+1] + middleware + lines[end_idx+1:]
            break
            
    with open(path, "w") as f:
        f.write('\n'.join(lines))
        
print("Done!")
