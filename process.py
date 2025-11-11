import sys

d = {}
s = {}
single = {}
year = {}

with open('output.csv', 'r', encoding='utf8') as f:
	for line in f.readlines():
		ID,LOCATION,TYPE,SIZE,TOWARDS,FLOOD,YEAR,BUILDING,TOTAL_PRICE,UNIT_PRICE,DATE_PRICE = line.split(',', 10)
		price = float(TOTAL_PRICE.encode('utf8')[:-3])
		size = float(SIZE.encode('utf8')[:-6])
		YEAR = YEAR.encode('utf8')[:-3].decode('utf8')
		try:
			d[LOCATION] = d.get(LOCATION, []) + [price]
			s[LOCATION] = s.get(LOCATION, []) + [size]
			single[LOCATION] = single.get(LOCATION, []) + [price/size]
			year[LOCATION] = YEAR
		except:
			continue
		
with open('result', 'w', encoding='utf8') as f:
	for k, v in d.items():
		f.write("%s\t%d~%d\t%d~%d\t%.1f~%.1f\t%s\t%d\n" % (k, int(min(d[k])), int(max(d[k])), int(min(s[k])), int(max(s[k])), min(single[k]), max(single[k]), year[k], len(v)))
