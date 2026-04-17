import requests
base = 'http://localhost:9100'

print('=== 1. 推荐股票实时数据 ===')
r = requests.get(base + '/api/market/recommended?nocache=v5', timeout=30)
d = r.json()
for s in d.get('stocks', []):
    code = s.get('code', '')
    name = s.get('name', '')
    price = s.get('price', '--')
    change = s.get('change_pct', 0)
    print(f'  {code} {name}: {price} ({change}%)')

print()
print('=== 2. 自选股实时价格 ===')
r = requests.get(base + '/api/portfolio?nocache=v6', timeout=30)
d = r.json()
for s in d.get('stocks', []):
    code = s.get('stock_code', '')
    name = s.get('stock_name', '')
    price = s.get('current_price', '--')
    change = s.get('change_pct', '--')
    print(f'  {code} {name}: 现价={price} 涨跌={change}%')

print()
print('=== 3. 报告标题 ===')
r = requests.get(base + '/api/report/600839?is_pro=true', timeout=60)
d = r.json()
print(f'  stock_name: {d.get("stock_name")}')
print(f'  stock_code: {d.get("stock_code")}')
print(f'  score: {d.get("score")}')

print()
print('=== 4. 合规性抽查 ===')
r = requests.get(base + '/api/report/600519?is_pro=true', timeout=60)
text = str(r.json())
forbidden = ['建议买入','建议卖出','推荐买入','推荐卖出','抄底','逃顶','必涨','必跌','成功率','值得关注','逢低','逢高']
all_pass = True
for word in forbidden:
    if word in text:
        print(f'  XX 发现违禁词: {word}')
        all_pass = False
    else:
        print(f'  OK 无违禁词: {word}')

if all_pass:
    print('\n  合规性检查全部通过!')
else:
    print('\n  存在合规风险!')
