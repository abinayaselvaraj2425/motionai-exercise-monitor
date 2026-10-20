"""Hosted entry point. Local users should continue to use backend.launch."""
import os
from pathlib import Path
from backend.configuration import load_configuration

def main():
    load_configuration(Path(__file__).resolve().parent.parent)
    from backend.deployment import validate_deployment
    validate_deployment()
    import uvicorn
    uvicorn.run('backend.submission_api:app',host='0.0.0.0',port=int(os.getenv('PORT','8000')),workers=1,proxy_headers=True,forwarded_allow_ips=os.getenv('FORWARDED_ALLOW_IPS','127.0.0.1'),limit_concurrency=24,timeout_keep_alive=10)

if __name__=='__main__':main()
