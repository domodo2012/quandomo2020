
# dd1 = {111: {'aa': 'a1', 'bb': 'b1'},
#        112: {'aa': 'a2', 'bb': 'b2'},
#        113: {'aa': 'a3', 'bb': 'b3'}}

dd1 = [111, 112, 113]
dd2 = iter(dd1)

while True:
    try:
        x = next(dd2)
    except StopIteration:
        print("no data!")
        break
    else:
        print(x)

