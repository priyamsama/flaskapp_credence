import re

b = '9'

for i in range(1,100):
    if b in str(i):
        print(i)
        i += 1
print("----------------------------")
for y in range (1,100):
    if re.search("9",str(y)):
        print(y)

print("----------------------------")


for y in range (1,100):
    if re.search("^9",str(y)):
        print(y)

print("---------------99-------------")


for y in range (1,100):
    if re.search("99",str(y)):
        print(y)
print("----------------------------")

amino = 'MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKTRREAEDLQVGQVELGGGPGAGSLQPLALEGSLQKRGIVEQCCTSICSLYQLENYCN'


#split each 3 as 3 letters and save it in a list 
# then search using re.search for each frame 
# 
codon =[]
# this print the first frame reading
for i in range(0,len(amino),3):
    cod = amino[i:i+3]
    print(cod)
    i=i+1
print("------------------------------------")



print("------------------------------------")

cod

codon=[]
for i in range (0,len(amino),3):
    codon = amino[i:i+3]
    print(codon)
    for x in codon:
        a= re.search("^M",codon)
        if a :
            print(a)