#@title
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

# To get smooth animations
import matplotlib.animation as animation
mpl.rc('animation', html='jshtml')

#@title
xs = np.linspace(-2.1, 2.1, 500)
ys = xs**2
plt.plot(xs, ys)

plt.plot([0, 0], [0, 3], "k--")
plt.arrow(-1.4, 2.5, 0.5, -1.3, head_width=0.1)
plt.arrow(0.85, 1.05, 0.5, 1.3, head_width=0.1)
#show([-2.1, 2.1, 0, 2.8], title="Slope of the curve $y = x^2$")
plt.axis([-2.1, 2.1, 0, 2.8])
plt.title("Slope of the curve $y = x^2$")
plt.show()
