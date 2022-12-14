import numpy as np
import itertools
import matplotlib.pyplot as plt
from tiles3 import tiles, IHT
import pandas as pd
import neurokit2 as nk
import mne
from sklearn.preprocessing import normalize
import torch

NUM_STEPS = 3000
class HeartBeatTileCoder:
    def __init__(self, iht_size=256, num_tilings=16, num_tiles=4):
        """
        Initializes the HeartBeat Tile Coder
        Initializers:
        iht_size -- int, the size of the index hash table, typically a power of 2
        num_tilings -- int, the number of tilings
        num_tiles -- int, the number of tiles. Here both the width and height of the
                     tile coder are the same
        Class Variables:
        self.iht -- tc.IHT, the index hash table that the tile coder will use
        self.num_tilings -- int, the number of tilings the tile coder will use
        self.num_tiles -- int, the number of tiles the tile coder will use
        """
        self.iht = IHT(iht_size)
        self.num_tilings = num_tilings
        self.num_tiles = num_tiles
        
    
    def get_tiles(self, sensor0, sensor1, row1, row2):
        """
        Takes in a position from the heartbeat environment
        and returns a numpy array of active tiles.
        
        returns:
        tiles - np.array, active tiles
        """
    
        
        sensor0_scaled = 0
        sensor1_scaled = 0
        
        sensor0_min = feature_ranges[row1][0]
        sensor0_max = feature_ranges[row1][1]
        sensor1_min = feature_ranges[row2][0]
        sensor1_max = feature_ranges[row2][1]
        
        
        sensor0_scaled = self.num_tiles* ((sensor0 - sensor0_min)/(sensor0_max - sensor0_min))
        sensor1_scaled = self.num_tiles* ((sensor1 - sensor1_min)/(sensor1_max - sensor1_min))
        
      
        
        tiles_ = tiles(self.iht, self.num_tilings, [sensor0_scaled,sensor1_scaled])
       
        
        return np.array(tiles_)


def get_feature(i):
    c = 0
    active_tiles = []
    x = np.zeros(10 * iht_size)  # x is the feature_vector

    for j in range(4):
        for k in range(j+1, 5):
            t = hbtc.get_tiles(new_data[j][i], new_data[k][i], j, k)
            t = list(np.asarray(t) + (c * iht_size))
            c = c + 1
            active_tiles.append(t)

    for feature in active_tiles:
        x[feature] = 1

    return np.array(x)

def exponential_weighted_data(raw_data):
    weighted_data = []
    for i in range(len(raw_data)):
        alpha = 0.98
        beta = alpha
        s = 0  
        data = [] 
        for t in range(len(raw_data[i])):
            s_new = (1 - beta) * raw_data[i][t] + beta * s
            data.append(s_new)
            s = s_new
        weighted_data.append(data) 
    return np.array(weighted_data)

# load data
file = "data/r04.edf"
data = mne.io.read_raw_edf(file)
raw_data = data.get_data()


# after normalization 
raw_data = normalize(raw_data,axis=1,norm="max")
# you can get the metadata included in the file and a list of all channels:
info = data.info
channels = data.ch_names

# # # cleanup the data
# for i in range(len(raw_data)):
#     raw_data[i] = nk.ecg_clean(raw_data[i],method="neurokit")


#exponential weighted averages of the heart sensors
new_data = exponential_weighted_data(raw_data)

# feature range
feature_ranges = []
for i in range(len(new_data)):
    feature_ranges.append([min(new_data[i]), max(new_data[i])])


# tile coder parameter initilization
num_tilings = 16
num_tiles = 4
iht_size = num_tiles * num_tiles * num_tilings
hbtc = HeartBeatTileCoder(iht_size, num_tilings, num_tiles)


#implementing td_lambda
gamma = 0.95
alpha = 0.1/(num_tilings * 10)
lambda_ = 0.9
w = np.zeros(10 * iht_size)
z = np.zeros(10 * iht_size)

#training
for t in range(1, NUM_STEPS):
    reward = new_data[1][t]    #considering 2nd sensor
    x_last = get_feature(t - 1)  #get features for 10 pairs of heart sensor data
    x_current = get_feature(t)

    delta = reward + gamma * np.dot(w.T, x_current) - np.dot(w.T, x_last) # size x is (1 x m) and size w is (m x 1)
    z = (gamma * lambda_ * z) + x_last
    w = w + alpha * delta * z

# prediction and error calculation
nmse = []
#v = np.var(raw_data[1])

for t in range(NUM_STEPS):
     
    x_current = get_feature(t)
    pred = np.dot(w.T, x_current) #td_lambda prediction
 
    #calculating discounted sum of future sensor data
    actual_value = 0
    G = []
    gamma_count = 0
    for i in range(t, NUM_STEPS):
        discounted_sum = np.power(gamma, gamma_count) * new_data[1][i]
        actual_value += discounted_sum
        G.append(discounted_sum)
        gamma_count += 1

    mse = np.mean(np.power(pred - actual_value, 2)) / np.var(G)

    nmse.append(mse)


y = np.array(nmse)
plt.plot(y)
plt.show()
