import numpy as np
import matplotlib.pyplot as plt

# If this is a regular Python script, also include:
# from mpl_toolkits.mplot3d import Axes3D  # (not strictly needed in newer matplotlib)

def plot_3d(f, title):
    fig = plt.figure(figsize=(9, 6))
    ax = fig.add_subplot(111, projection='3d')

    x = np.linspace(-2.1, 2.1, 120)
    y = np.linspace(-2.1, 2.1, 120)
    X, Y = np.meshgrid(x, y)
    Z = f(X, Y)

    # Cleaner surface (no black grid lines)
    surf = ax.plot_surface(
        X, Y, Z,
        cmap="coolwarm",
        edgecolor="none",
        antialiased=True,
        alpha=0.9
    )

    # Optional contour projection to help depth perception
    ax.contour(X, Y, Z, zdir='z', offset=Z.min() - 0.2, cmap='coolwarm', levels=12)

    ax.set_xlabel("$x$", fontsize=12)
    ax.set_ylabel("$y$", fontsize=12)
    ax.set_zlabel("$z$", fontsize=12)
    ax.set_title(title, fontsize=13)

    # Nice viewing angle
    ax.view_init(elev=28, azim=-55)

    # Add colorbar
    fig.colorbar(surf, ax=ax, shrink=0.7, pad=0.08, label="$z$")

    return fig, ax


def plot_tangents(ax, x0, y0, f, df_dx, df_dy, draw_plane=True):
    z0 = f(x0, y0)

    # Point on the surface
    ax.scatter([x0], [y0], [z0], color="black", s=50, zorder=10)

    # Tangent in x-direction (holding y = y0)
    x_line = np.linspace(-2.1, 2.1, 200)
    slope_x = df_dx(x0, y0)
    z_x = z0 + slope_x * (x_line - x0)
    ax.plot(x_line, np.full_like(x_line, y0), z_x, "b--", linewidth=2, label="x-direction tangent")

    # Tangent in y-direction (holding x = x0)
    y_line = np.linspace(-2.1, 2.1, 200)
    slope_y = df_dy(x0, y0)
    z_y = z0 + slope_y * (y_line - y0)
    ax.plot(np.full_like(y_line, x0), y_line, z_y, "r-", linewidth=2, label="y-direction tangent")

    # Tangent plane: z ≈ z0 + fx(x-x0) + fy(y-y0)
    if draw_plane:
        xp = np.linspace(x0 - 0.8, x0 + 0.8, 25)
        yp = np.linspace(y0 - 0.8, y0 + 0.8, 25)
        XP, YP = np.meshgrid(xp, yp)
        ZP = z0 + slope_x * (XP - x0) + slope_y * (YP - y0)

        ax.plot_surface(XP, YP, ZP, alpha=0.35, edgecolor='none')

    ax.legend(loc="upper left")


def f(x, y):
    return np.sin(x * y)

def df_dx(x, y):
    return y * np.cos(x * y)

def df_dy(x, y):
    return x * np.cos(x * y)


fig, ax = plot_3d(f, r"$z = f(x, y) = \sin(xy)$")
plot_tangents(ax, 0.1, -1, f, df_dx, df_dy, draw_plane=True)

plt.tight_layout()
plt.show()