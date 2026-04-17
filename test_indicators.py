import requests

try:
    r = requests.get('http://localhost:9100/api/indicators/600519?is_pro=true', timeout=15)
    data = r.json()
    if data.get('success'):
        print('指标已格式化到2位小数:')
        for i in data['indicators'][:8]:
            print(i['name'] + ': ' + str(i['value']))
    else:
        print('失败:', data.get('error'))
except Exception as e:
    print('错误:', e)