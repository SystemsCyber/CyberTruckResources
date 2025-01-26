filename = "SYSE549 Networks.bib"
with open(filename,'rb') as f:
    data = f.read()
data_string = data.decode('ascii','ignore')
lines = data_string.split('\n')

with open('vehicle_security_references.bib','w') as bib:
        for line in lines:
            if 'file' not in line.strip()[:10]:
                bib.write(line+'\n')
                print(line)