import matplotlib.pyplot as plt

transitions = []
with open('DecodingCANFrame.txt','r') as file:
	for entry in file:
		transitions.append(int(entry))
		
transition_index = 0
micro_seconds = []
values = []
state = False
for i in range(transitions[0],transitions[-1]):
	micro_seconds.append(i)
	if 	i > transitions[transition_index]:
		state = ~state
		transition_index += 1
	if state:
		values.append(1)
	else:
		values.append(0)
plt.plot(transitions,values,'.-')
plt.xlabel('Microseconds')
plt.ylabel("CAN Signal Value")
plt.show()