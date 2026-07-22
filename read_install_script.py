import re
f = open('skillhub_install.sh', 'r', encoding='utf-8')
content = f.read()
f.close()
# Remove non-ASCII
result = re.sub(r'[^\x00-\x7f]+', ' ', content)
f2 = open('install_clean.txt', 'w', encoding='utf-8')
f2.write(result)
f2.close()
print('Done, len:', len(result))
