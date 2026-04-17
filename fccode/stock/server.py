# -*- coding: utf-8 -*-
"""
阿里云函数计算 FC 3.0 - Serverless 部署入口 (v2.0)
"""

import sys
import os
import json
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

app = create_app()

def handler(event, context):
    """
    阿里云 FC 3.0 事件函数入口
    """
    print(f"[DEBUG] Input type: {type(event)}")
    print(f"[DEBUG] Input: {json.dumps(event, ensure_ascii=False, default=str)[:1000]}")
    
    # 解析事件数据
    if isinstance(event, bytes):
        try:
            event = json.loads(event.decode('utf-8'))
        except json.JSONDecodeError as e:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': f'Bad Request: Invalid JSON'})
            }
    
    if not isinstance(event, dict):
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Expected dict, got {type(event)}'})
        }
    
    # 🔧 关键修复：FC 3.0 HTTP触发器路径解析
    # 尝试多种路径字段
    path = '/'
    
    # 方式1: 直接 path 字段
    if 'path' in event:
        path = event['path']
    # 方式2: rawPath 字段 (FC 3.0)
    elif 'rawPath' in event:
        path = event['rawPath']
    # 方式3: requestContext.http.path
    elif 'requestContext' in event and isinstance(event['requestContext'], dict):
        http_ctx = event['requestContext'].get('http', {})
        if isinstance(http_ctx, dict) and 'path' in http_ctx:
            path = http_ctx['path']
    
    print(f"[DEBUG] Resolved path: {path}")
    
    # 获取请求方法
    method = 'GET'
    if 'httpMethod' in event:
        method = event['httpMethod']
    elif 'requestContext' in event and isinstance(event['requestContext'], dict):
        http_ctx = event['requestContext'].get('http', {})
        if isinstance(http_ctx, dict) and 'method' in http_ctx:
            method = http_ctx['method']
    
    # 获取查询参数
    query_string = ''
    if 'queryString' in event:
        query_string = event['queryString']
    elif 'queryStringParameters' in event:
        qs = event.get('queryStringParameters', {})
        if qs:
            query_string = '&'.join(f"{k}={v}" for k, v in qs.items())
    
    # 获取请求头
    headers = event.get('headers', {})
    
    # 构建 WSGI environ
    wsgi_environ = {
        'REQUEST_METHOD': method,
        'SCRIPT_NAME': '',
        'PATH_INFO': path,
        'QUERY_STRING': query_string,
        'SERVER_NAME': 'localhost',
        'SERVER_PORT': '443',
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': 'https',
        'wsgi.input': BytesIO(),
        'wsgi.errors': sys.stderr,
        'wsgi.multithread': False,
        'wsgi.multiprocess': True,
        'wsgi.run_once': False,
    }
    
    # 添加 HTTP 头
    for key, value in headers.items():
        header_key = f'HTTP_{key.upper().replace("-", "_")}'
        wsgi_environ[header_key] = value
    
    # 添加请求体
    body = event.get('body', '')
    if body:
        if isinstance(body, str):
            body = body.encode('utf-8')
        wsgi_environ['wsgi.input'] = BytesIO(body)
        wsgi_en['CONTENT_LENGTH'] = str(len(body))
    
    print(f"[DEBUG] WSGI: PATH={path}, METHOD={method}")
    
    # 调用 Flask 应用
    response_started = []
    response_headers = []
    
    def start_response(status, headers):
        response_started.append(status)
        response_headers.extend(headers)
    
    try:
        response_body = b''.join(app(wsgi_environ, start_response))
        
        # 转换 headers 为字典格式
        headers_dict = {}
        for key, value in response_headers:
            if key in headers_dict:
                headers_dict[key] = f"{headers_dict[key]}, {value}"
            else:
                headers_dict[key] = value
        
        # 强制设置正确的Content-Type
        # 检查路径是否是API请求
        is_api = path.startswith('/api/') or path.startswith('/debug/') or path == '/health'
        
        if is_api:
            # API请求必须返回JSON
            headers_dict['Content-Type'] = 'application/json; charset=utf-8'
        elif 'Content-Type' not in headers_dict:
            # 非API请求，检查响应体
            try:
                body_preview = response_body[:100].decode('utf-8', errors='ignore')
                if body_preview.strip().startswith('{') or body_preview.strip().startswith('['):
                    headers_dict['Content-Type'] = 'application/json; charset=utf-8'
                elif '<!DOCTYPE' in body_preview or '<html' in body_preview.lower():
                    headers_dict['Content-Type'] = 'text/html; charset=utf-8'
                else:
                    headers_dict['Content-Type'] = 'text/html; charset=utf-8'
            except:
                headers_dict['Content-Type'] = 'text/html; charset=utf-8'
        
        # 将bytes转换为字符串
        try:
            body_str = response_body.decode('utf-8')
        except UnicodeDecodeError:
            import base64
            body_str = base64.b64encode(response_body).decode('ascii')
        
        return {
            'statusCode': int(response_started[0].split()[0]),
            'headers': headers_dict,
            'body': body_str
        }
    except Exception as e:
        print(f"[ERROR] Flask app error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Internal Server Error: {str(e)}'})
        }
