import os
from supabase import create_client

def get_db():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key: return None
    return create_client(url,key)
