from numpy import linalg as LA
import numpy as np

w, v = LA.eig(np.array([[1.5, -0.5, -0.5, -1.5], [-0.5, 1.5, -1.5, -0.5], [-0.5, -1.5, 1.5, -0.5], [-1.5, -0.5, -0.5, 1.5]]))

print("eigen values:", w)
print("eigen vectors:", v)