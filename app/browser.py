import webbrowser
from urllib.parse import urlparse

def validate_url(url:str):
    p=urlparse(url or '')
    if p.scheme not in {'http','https'} or not p.netloc: raise ValueError('Invalid job URL')
    return url

def open_for_review(url:str):
    validate_url(url); webbrowser.open(url,new=2); return {'message':'Opened in your normal browser.','url':url}
